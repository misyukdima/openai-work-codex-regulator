#!/usr/bin/env python3
"""Just-in-time authorization coordinator for the v3 ChatGPT quota Plugin.

The model-facing quota tool remains read-only and zero-argument. This module is
used only by the trusted Plugin transport when a user must connect or reconnect
an OpenAI account.

Device-code authorization is stateful: one official `codex app-server` process
must stay alive from challenge creation until the user completes, cancels, or
times out. The current coordinator therefore represents one pinned worker. A
multi-replica deployment must add an audited routing/lease layer instead of
pretending a live authorization process is stateless.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hmac
from pathlib import Path
import secrets
import threading
import time
from typing import Any, Callable, Protocol

try:
    from plugin.quota_backend import (
        CodexAppServer,
        CodexProtocolTimeout,
        DeviceAuthorization,
    )
    from plugin.quota_service import PluginRequestContext
    from plugin.subject_store import derive_subject_key, normalize_subject, validate_pepper
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.quota_backend import (
        CodexAppServer,
        CodexProtocolTimeout,
        DeviceAuthorization,
    )
    from plugin.quota_service import PluginRequestContext
    from plugin.subject_store import derive_subject_key, normalize_subject, validate_pepper


class AuthorizationState(str, Enum):
    STARTING = "STARTING"
    WAITING_USER = "WAITING_USER"
    AUTHORIZED = "AUTHORIZED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


TERMINAL_STATES = {
    AuthorizationState.AUTHORIZED,
    AuthorizationState.CANCELLED,
    AuthorizationState.EXPIRED,
    AuthorizationState.FAILED,
}


class AuthorizationCoordinatorError(RuntimeError):
    pass


class AlreadyAuthorized(AuthorizationCoordinatorError):
    pass


class AuthorizationNotFound(AuthorizationCoordinatorError):
    """Unknown and cross-subject ids deliberately share the same error."""


class AuthorizationStartupFailed(AuthorizationCoordinatorError):
    pass


class AuthorizationBusy(AuthorizationCoordinatorError):
    pass


class AuthorizableAuthStore(Protocol):
    production_safe: bool

    def exists(self, subject: str) -> bool:
        ...

    def authorization_session(self, subject: str) -> AbstractContextManager[Any]:
        ...

    def revoke(self, subject: str) -> bool:
        ...


class DeviceAuthClient(Protocol):
    def __enter__(self) -> "DeviceAuthClient":
        ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        ...

    def start_device_login(self) -> DeviceAuthorization:
        ...

    def wait_until_authenticated(self, login_id: str, *, timeout: float) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


ClientFactory = Callable[[str], AbstractContextManager[DeviceAuthClient]]


def default_client_factory(codex_home: str) -> AbstractContextManager[DeviceAuthClient]:
    return CodexAppServer(codex_home=codex_home)


@dataclass(frozen=True)
class AuthorizationView:
    authorization_id: str
    state: str
    verification_url: str | None
    user_code: str | None
    expires_at: str
    error_code: str | None = None


@dataclass
class _AuthorizationRecord:
    authorization_id: str
    subject_key: str
    subject: str = field(repr=False)
    expires_at: datetime
    state: AuthorizationState = AuthorizationState.STARTING
    challenge: DeviceAuthorization | None = None
    error_code: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    ready_event: threading.Event = field(default_factory=threading.Event, repr=False)
    done_event: threading.Event = field(default_factory=threading.Event, repr=False)
    client: DeviceAuthClient | None = field(default=None, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)


class AuthorizationCoordinator:
    """Pinned-worker state machine for trusted Plugin Connect/Auth flows."""

    def __init__(
        self,
        *,
        auth_store: AuthorizableAuthStore,
        subject_binding_secret: bytes,
        client_factory: ClientFactory = default_client_factory,
        authorization_timeout_seconds: float = 600.0,
        startup_timeout_seconds: float = 30.0,
        terminal_retention_seconds: float = 900.0,
    ) -> None:
        self.auth_store = auth_store
        self._binding_secret = validate_pepper(subject_binding_secret)
        self.client_factory = client_factory
        self.authorization_timeout_seconds = float(authorization_timeout_seconds)
        self.startup_timeout_seconds = float(startup_timeout_seconds)
        self.terminal_retention_seconds = float(terminal_retention_seconds)
        if self.authorization_timeout_seconds <= 0 or self.startup_timeout_seconds <= 0:
            raise ValueError("authorization timeouts must be positive")
        self._lock = threading.RLock()
        self._records: dict[str, _AuthorizationRecord] = {}
        self._active_by_subject: dict[str, str] = {}
        self._terminal_at: dict[str, float] = {}

    def _subject(self, context: PluginRequestContext) -> tuple[str, str]:
        subject = normalize_subject(context.authenticated_subject)
        return subject, derive_subject_key(subject, self._binding_secret)

    @staticmethod
    def _view(record: _AuthorizationRecord) -> AuthorizationView:
        challenge = record.challenge
        return AuthorizationView(
            authorization_id=record.authorization_id,
            state=record.state.value,
            verification_url=challenge.verification_url if challenge else None,
            user_code=challenge.user_code if challenge else None,
            expires_at=record.expires_at.isoformat(),
            error_code=record.error_code,
        )

    def _lookup(self, context: PluginRequestContext, authorization_id: str) -> _AuthorizationRecord:
        _, subject_key = self._subject(context)
        with self._lock:
            record = self._records.get(authorization_id)
            if record is None or not hmac.compare_digest(record.subject_key, subject_key):
                raise AuthorizationNotFound("authorization session not found")
            return record

    def begin(self, context: PluginRequestContext) -> AuthorizationView:
        subject, subject_key = self._subject(context)
        if self.auth_store.exists(subject):
            raise AlreadyAuthorized("subject already has authorized quota state")

        new_thread: threading.Thread | None = None
        with self._lock:
            existing_id = self._active_by_subject.get(subject_key)
            if existing_id:
                record = self._records.get(existing_id)
                if record is not None and record.state not in TERMINAL_STATES:
                    pass
                else:
                    self._active_by_subject.pop(subject_key, None)
                    record = None
            else:
                record = None

            if record is None:
                authorization_id = secrets.token_urlsafe(24)
                record = _AuthorizationRecord(
                    authorization_id=authorization_id,
                    subject_key=subject_key,
                    subject=subject,
                    expires_at=datetime.now(timezone.utc)
                    + timedelta(seconds=self.authorization_timeout_seconds),
                )
                new_thread = threading.Thread(
                    target=self._run,
                    args=(record,),
                    name=f"regulator-auth-{authorization_id[:8]}",
                    daemon=True,
                )
                record.thread = new_thread
                self._records[authorization_id] = record
                self._active_by_subject[subject_key] = authorization_id

        if new_thread is not None:
            new_thread.start()

        if not record.ready_event.wait(self.startup_timeout_seconds):
            self._cancel_record(record)
            raise AuthorizationStartupFailed("authorization challenge did not start in time")

        with self._lock:
            view = self._view(record)
        if record.state == AuthorizationState.FAILED:
            raise AuthorizationStartupFailed(view.error_code or "authorization startup failed")
        return view

    def status(self, context: PluginRequestContext, authorization_id: str) -> AuthorizationView:
        record = self._lookup(context, authorization_id)
        with self._lock:
            return self._view(record)

    def wait(
        self,
        context: PluginRequestContext,
        authorization_id: str,
        *,
        timeout: float | None = None,
    ) -> AuthorizationView:
        record = self._lookup(context, authorization_id)
        record.done_event.wait(timeout)
        with self._lock:
            return self._view(record)

    def cancel(self, context: PluginRequestContext, authorization_id: str) -> AuthorizationView:
        record = self._lookup(context, authorization_id)
        self._cancel_record(record)
        return self.wait(context, authorization_id, timeout=5.0)

    def _cancel_record(self, record: _AuthorizationRecord) -> None:
        record.cancel_event.set()
        client = record.client
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def revoke(self, context: PluginRequestContext, *, wait_timeout: float = 5.0) -> bool:
        subject, subject_key = self._subject(context)
        record: _AuthorizationRecord | None = None
        with self._lock:
            active_id = self._active_by_subject.get(subject_key)
            if active_id:
                record = self._records.get(active_id)
        if record is not None and record.state not in TERMINAL_STATES:
            self._cancel_record(record)
            if not record.done_event.wait(wait_timeout):
                raise AuthorizationBusy("authorization worker did not stop before revoke")
        return self.auth_store.revoke(subject)

    def reap(self) -> int:
        cutoff = time.monotonic() - self.terminal_retention_seconds
        removed = 0
        with self._lock:
            for authorization_id, terminal_at in list(self._terminal_at.items()):
                if terminal_at > cutoff:
                    continue
                record = self._records.pop(authorization_id, None)
                self._terminal_at.pop(authorization_id, None)
                if record is not None:
                    current = self._active_by_subject.get(record.subject_key)
                    if current == authorization_id:
                        self._active_by_subject.pop(record.subject_key, None)
                    removed += 1
        return removed

    def close(self) -> None:
        with self._lock:
            records = list(self._records.values())
        for record in records:
            if record.state not in TERMINAL_STATES:
                self._cancel_record(record)
        deadline = time.monotonic() + 5.0
        for record in records:
            remaining = max(0.0, deadline - time.monotonic())
            record.done_event.wait(remaining)

    def _finish(
        self,
        record: _AuthorizationRecord,
        state: AuthorizationState,
        *,
        error_code: str | None = None,
    ) -> None:
        with self._lock:
            record.state = state
            record.error_code = error_code
            record.client = None
            current = self._active_by_subject.get(record.subject_key)
            if current == record.authorization_id:
                self._active_by_subject.pop(record.subject_key, None)
            self._terminal_at[record.authorization_id] = time.monotonic()
            # Raw identity is needed only while the live worker owns the flow.
            record.subject = ""
            record.ready_event.set()
            record.done_event.set()

    def _run(self, record: _AuthorizationRecord) -> None:
        try:
            with self.auth_store.authorization_session(record.subject) as auth_context:
                with self.client_factory(str(auth_context.codex_home)) as client:
                    with self._lock:
                        record.client = client
                    if record.cancel_event.is_set():
                        raise RuntimeError("authorization_cancelled")

                    challenge = client.start_device_login()
                    if not challenge.verification_url.lower().startswith("https://"):
                        raise RuntimeError("insecure_verification_url")

                    with self._lock:
                        record.challenge = challenge
                        record.state = AuthorizationState.WAITING_USER
                        record.ready_event.set()

                    remaining = (record.expires_at - datetime.now(timezone.utc)).total_seconds()
                    if remaining <= 0:
                        raise CodexProtocolTimeout("authorization expired before user challenge")
                    client.wait_until_authenticated(challenge.login_id, timeout=remaining)
                    if record.cancel_event.is_set():
                        raise RuntimeError("authorization_cancelled")

            self._finish(record, AuthorizationState.AUTHORIZED)
        except CodexProtocolTimeout:
            if record.cancel_event.is_set():
                self._finish(record, AuthorizationState.CANCELLED)
            else:
                self._finish(record, AuthorizationState.EXPIRED)
        except Exception as exc:
            if record.cancel_event.is_set() or str(exc) == "authorization_cancelled":
                self._finish(record, AuthorizationState.CANCELLED)
            else:
                # Public status exposes only a bounded class name, never raw provider
                # messages that could contain account or authentication detail.
                self._finish(record, AuthorizationState.FAILED, error_code=type(exc).__name__)


class _FakeAuthClient:
    def __init__(self, codex_home: str) -> None:
        self.codex_home = Path(codex_home)
        self.complete_event = threading.Event()
        self.closed_event = threading.Event()

    def __enter__(self) -> "_FakeAuthClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def start_device_login(self) -> DeviceAuthorization:
        return DeviceAuthorization(
            login_id="fake-login-id",
            verification_url="https://example.invalid/device",
            user_code="ABCD-EFGH",
        )

    def wait_until_authenticated(self, login_id: str, *, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.closed_event.is_set():
                raise RuntimeError("fake client closed")
            if self.complete_event.wait(0.01):
                (self.codex_home / "auth.json").write_text(
                    '{"auth_mode":"chatgpt","tokens":{"fixture":"only"}}',
                    encoding="utf-8",
                )
                return {"authMode": "chatgpt"}
        raise CodexProtocolTimeout("fake authorization timed out")

    def close(self) -> None:
        self.closed_event.set()


def self_test() -> None:
    from plugin.sealed_auth_store import InMemoryBlobStore, ReversibleTestCipher, SealedSubjectAuthStore

    pepper = b"a" * 32
    store = SealedSubjectAuthStore(
        pepper=pepper,
        blob_store=InMemoryBlobStore(),
        cipher=ReversibleTestCipher(),
    )
    clients: list[_FakeAuthClient] = []

    def factory(codex_home: str) -> _FakeAuthClient:
        client = _FakeAuthClient(codex_home)
        clients.append(client)
        return client

    coordinator = AuthorizationCoordinator(
        auth_store=store,
        subject_binding_secret=pepper,
        client_factory=factory,
        authorization_timeout_seconds=1.0,
        startup_timeout_seconds=1.0,
        terminal_retention_seconds=0.0,
    )
    a = PluginRequestContext("subject-a@example.test")
    b = PluginRequestContext("subject-b@example.test")

    first = coordinator.begin(a)
    assert first.state == AuthorizationState.WAITING_USER.value
    assert first.verification_url == "https://example.invalid/device"
    assert "subject-a" not in first.authorization_id
    duplicate = coordinator.begin(a)
    assert duplicate.authorization_id == first.authorization_id

    try:
        coordinator.status(b, first.authorization_id)
    except AuthorizationNotFound:
        pass
    else:
        raise AssertionError("cross-subject authorization id lookup must fail")

    clients[0].complete_event.set()
    finished = coordinator.wait(a, first.authorization_id, timeout=1.0)
    assert finished.state == AuthorizationState.AUTHORIZED.value
    assert store.exists(a.authenticated_subject) is True

    try:
        coordinator.begin(a)
    except AlreadyAuthorized:
        pass
    else:
        raise AssertionError("already authorized subject must not start another login")

    assert coordinator.revoke(a) is True
    assert store.exists(a.authenticated_subject) is False

    second = coordinator.begin(b)
    cancelled = coordinator.cancel(b, second.authorization_id)
    assert cancelled.state == AuthorizationState.CANCELLED.value
    assert store.exists(b.authenticated_subject) is False

    coordinator.reap()
    coordinator.close()
    print("authorization_coordinator_self_test=ok")


if __name__ == "__main__":
    self_test()
