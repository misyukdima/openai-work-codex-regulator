#!/usr/bin/env python3
"""Per-subject serialization for sealed Plugin authorization state.

Concurrent operations for one subject must not materialize the same auth blob
and later overwrite a newer official Codex refresh with stale state. Production
must inject an audited distributed/session-bound lease provider. CI uses an
in-process lock provider that is deliberately not production-safe.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
import threading
from typing import Any, Iterator, Protocol, runtime_checkable

try:
    from plugin.subject_store import SubjectAuthContext, derive_subject_key, validate_pepper
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.subject_store import SubjectAuthContext, derive_subject_key, validate_pepper


class SubjectLeaseError(RuntimeError):
    pass


class SubjectLeaseTimeout(SubjectLeaseError):
    pass


@runtime_checkable
class SubjectLeaseProvider(Protocol):
    """Provider must keep one subject operation exclusive for the context lifetime."""

    production_safe: bool

    def lease(
        self,
        subject_key: str,
        *,
        purpose: str,
        wait_timeout_seconds: float,
    ) -> AbstractContextManager[None]:
        ...


class InProcessSubjectLeaseProvider:
    """Single-process CI/P1 lock provider; never sufficient for multi-replica production."""

    production_safe = False

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def _lock_for(self, subject_key: str) -> threading.RLock:
        with self._guard:
            lock = self._locks.get(subject_key)
            if lock is None:
                lock = threading.RLock()
                self._locks[subject_key] = lock
            return lock

    @contextmanager
    def lease(
        self,
        subject_key: str,
        *,
        purpose: str,
        wait_timeout_seconds: float,
    ) -> Iterator[None]:
        if wait_timeout_seconds <= 0:
            raise ValueError("lease wait timeout must be positive")
        lock = self._lock_for(subject_key)
        acquired = lock.acquire(timeout=wait_timeout_seconds)
        if not acquired:
            raise SubjectLeaseTimeout(f"timed out acquiring subject lease for {purpose}")
        try:
            yield
        finally:
            lock.release()


class LeaseProtectedAuthStore:
    """Decorator that serializes authorization/read/revoke for each opaque subject key."""

    def __init__(
        self,
        *,
        delegate: Any,
        pepper: bytes,
        lease_provider: SubjectLeaseProvider,
        wait_timeout_seconds: float = 30.0,
    ) -> None:
        self.delegate = delegate
        self._pepper = validate_pepper(pepper)
        self.lease_provider = lease_provider
        self.wait_timeout_seconds = float(wait_timeout_seconds)
        if self.wait_timeout_seconds <= 0:
            raise ValueError("lease wait timeout must be positive")
        self.production_safe = bool(
            getattr(delegate, "production_safe", False)
            and getattr(lease_provider, "production_safe", False)
        )

    def _subject_key(self, subject: str) -> str:
        return derive_subject_key(subject, self._pepper)

    def exists(self, subject: str) -> bool:
        return bool(self.delegate.exists(subject))

    def open(self, subject: str) -> SubjectAuthContext:
        raise SubjectLeaseError("lease-protected sealed store does not expose durable plaintext open()")

    @contextmanager
    def authorization_session(self, subject: str) -> Iterator[SubjectAuthContext]:
        subject_key = self._subject_key(subject)
        with self.lease_provider.lease(
            subject_key,
            purpose="authorize",
            wait_timeout_seconds=self.wait_timeout_seconds,
        ):
            with self.delegate.authorization_session(subject) as context:
                yield context

    @contextmanager
    def materialize(self, subject: str) -> Iterator[SubjectAuthContext]:
        subject_key = self._subject_key(subject)
        with self.lease_provider.lease(
            subject_key,
            purpose="quota-read",
            wait_timeout_seconds=self.wait_timeout_seconds,
        ):
            with self.delegate.materialize(subject) as context:
                yield context

    def revoke(self, subject: str) -> bool:
        subject_key = self._subject_key(subject)
        with self.lease_provider.lease(
            subject_key,
            purpose="revoke",
            wait_timeout_seconds=self.wait_timeout_seconds,
        ):
            return bool(self.delegate.revoke(subject))


def self_test() -> None:
    import json
    import time

    from plugin.sealed_auth_store import (
        InMemoryBlobStore,
        ReversibleTestCipher,
        SealedSubjectAuthStore,
    )

    pepper = b"l" * 32
    subject = "concurrency-subject"
    delegate = SealedSubjectAuthStore(
        pepper=pepper,
        blob_store=InMemoryBlobStore(),
        cipher=ReversibleTestCipher(),
    )
    leases = InProcessSubjectLeaseProvider()
    store = LeaseProtectedAuthStore(
        delegate=delegate,
        pepper=pepper,
        lease_provider=leases,
        wait_timeout_seconds=2.0,
    )
    assert store.production_safe is False

    with store.authorization_session(subject) as context:
        (context.codex_home / "auth.json").write_text(
            '{"auth_mode":"chatgpt","generation":0}',
            encoding="utf-8",
        )

    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def mutate(first: bool) -> None:
        with store.materialize(subject) as context:
            auth_file = context.codex_home / "auth.json"
            data = json.loads(auth_file.read_text(encoding="utf-8"))
            if first:
                first_entered.set()
                assert release_first.wait(1.0)
            else:
                second_entered.set()
            data["generation"] += 1
            auth_file.write_text(json.dumps(data), encoding="utf-8")

    t1 = threading.Thread(target=mutate, args=(True,))
    t2 = threading.Thread(target=mutate, args=(False,))
    t1.start()
    assert first_entered.wait(1.0)
    t2.start()
    time.sleep(0.05)
    assert second_entered.is_set() is False
    release_first.set()
    t1.join(1.0)
    t2.join(1.0)
    assert not t1.is_alive() and not t2.is_alive()

    with store.materialize(subject) as context:
        data = json.loads((context.codex_home / "auth.json").read_text(encoding="utf-8"))
        assert data["generation"] == 2

    read_entered = threading.Event()
    release_read = threading.Event()
    revoke_done = threading.Event()

    def hold_read() -> None:
        with store.materialize(subject):
            read_entered.set()
            assert release_read.wait(1.0)

    def revoke() -> None:
        assert store.revoke(subject) is True
        revoke_done.set()

    reader = threading.Thread(target=hold_read)
    revoker = threading.Thread(target=revoke)
    reader.start()
    assert read_entered.wait(1.0)
    revoker.start()
    time.sleep(0.05)
    assert revoke_done.is_set() is False
    release_read.set()
    reader.join(1.0)
    revoker.join(1.0)
    assert revoke_done.is_set() is True
    assert store.exists(subject) is False

    print("auth_concurrency_self_test=ok")


if __name__ == "__main__":
    self_test()
