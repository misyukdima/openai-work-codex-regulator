#!/usr/bin/env python3
"""Subject isolation primitives for the v3 quota Plugin backend."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterator, Protocol, runtime_checkable


MIN_PEPPER_BYTES = 32


class SubjectStoreError(RuntimeError):
    pass


class InvalidSubjectError(SubjectStoreError):
    pass


class InvalidPepperError(SubjectStoreError):
    pass


@dataclass(frozen=True)
class SubjectAuthContext:
    """Opaque server-side auth context. Never return this object to the model."""

    subject_key: str
    codex_home: Path


@runtime_checkable
class SubjectAuthStore(Protocol):
    """Auth-session provider consumed by the read-only quota service."""

    production_safe: bool

    def open(self, subject: str) -> SubjectAuthContext:
        """Create/open a context for an explicit authorization flow."""
        ...

    def materialize(self, subject: str) -> Iterator[SubjectAuthContext]:
        """Yield a private Codex home for one quota operation."""
        ...

    def exists(self, subject: str) -> bool:
        ...

    def revoke(self, subject: str) -> bool:
        ...


def normalize_subject(subject: str) -> str:
    if not isinstance(subject, str):
        raise InvalidSubjectError("authenticated subject must be a string")
    normalized = subject.strip()
    if not normalized:
        raise InvalidSubjectError("authenticated subject must not be empty")
    if len(normalized.encode("utf-8")) > 4096:
        raise InvalidSubjectError("authenticated subject is unreasonably large")
    return normalized


def validate_pepper(pepper: bytes) -> bytes:
    if not isinstance(pepper, bytes) or len(pepper) < MIN_PEPPER_BYTES:
        raise InvalidPepperError(
            f"subject-key pepper must contain at least {MIN_PEPPER_BYTES} bytes"
        )
    return pepper


def derive_subject_key(subject: str, pepper: bytes) -> str:
    """Derive a fixed path-safe key without persisting raw subject PII."""
    normalized = normalize_subject(subject)
    key = validate_pepper(pepper)
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


class EphemeralSubjectAuthStore:
    """Development-only persistent-directory store for CI/P0/P1.

    It makes no production encryption-at-rest claim. Production startup must not
    accept this implementation as a credential vault.
    """

    production_safe = False

    def __init__(
        self,
        *,
        pepper: bytes,
        root: str | os.PathLike[str] | None = None,
    ) -> None:
        self._pepper = validate_pepper(pepper)
        self._owns_root = root is None
        if root is None:
            self.root = Path(tempfile.mkdtemp(prefix="regulator-quota-auth-"))
        else:
            self.root = Path(root).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        self._chmod_private(self.root)

    @staticmethod
    def _chmod_private(path: Path) -> None:
        try:
            path.chmod(0o700)
        except OSError:
            pass

    def _path_for(self, subject: str) -> tuple[str, Path]:
        subject_key = derive_subject_key(subject, self._pepper)
        return subject_key, self.root / subject_key

    def open(self, subject: str) -> SubjectAuthContext:
        subject_key, path = self._path_for(subject)
        path.mkdir(mode=0o700, parents=False, exist_ok=True)
        self._chmod_private(path)
        return SubjectAuthContext(subject_key=subject_key, codex_home=path)

    @contextmanager
    def materialize(self, subject: str) -> Iterator[SubjectAuthContext]:
        if not self.exists(subject):
            raise SubjectStoreError("subject auth context does not exist")
        yield self.open(subject)

    def exists(self, subject: str) -> bool:
        _, path = self._path_for(subject)
        return path.is_dir()

    def revoke(self, subject: str) -> bool:
        _, path = self._path_for(subject)
        if not path.exists():
            return False
        if path.is_symlink():
            raise SubjectStoreError("refusing to revoke symlinked auth context")
        shutil.rmtree(path)
        return True

    def close(self) -> None:
        if self._owns_root and self.root.exists():
            shutil.rmtree(self.root)

    def __enter__(self) -> "EphemeralSubjectAuthStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def self_test() -> None:
    pepper = bytes(range(32))
    raw_a = "chatgpt|user@example.com|../subject-a"
    raw_b = "chatgpt|other@example.com|../../subject-b"

    key_a = derive_subject_key(raw_a, pepper)
    key_b = derive_subject_key(raw_b, pepper)
    assert key_a != key_b
    assert len(key_a) == 64
    assert all(ch in "0123456789abcdef" for ch in key_a)
    assert "@" not in key_a and "/" not in key_a and ".." not in key_a

    with EphemeralSubjectAuthStore(pepper=pepper) as store:
        root = store.root
        a = store.open(raw_a)
        b = store.open(raw_b)
        assert a.codex_home.parent == root
        assert b.codex_home.parent == root
        assert a.codex_home != b.codex_home
        assert raw_a not in str(a.codex_home)
        assert raw_b not in str(b.codex_home)

        (a.codex_home / "auth.json").write_text("development-only-a", encoding="utf-8")
        (b.codex_home / "auth.json").write_text("development-only-b", encoding="utf-8")
        with store.materialize(raw_a) as materialized:
            assert materialized.codex_home == a.codex_home

        assert store.revoke(raw_a) is True
        assert store.exists(raw_a) is False
        assert store.exists(raw_b) is True
        assert (b.codex_home / "auth.json").read_text(encoding="utf-8") == "development-only-b"
        assert store.revoke(raw_a) is False

    assert not root.exists()

    for bad_pepper in (b"", b"short"):
        try:
            derive_subject_key("x", bad_pepper)
        except InvalidPepperError:
            pass
        else:
            raise AssertionError("weak pepper must fail")

    try:
        derive_subject_key("   ", pepper)
    except InvalidSubjectError:
        pass
    else:
        raise AssertionError("empty subject must fail")

    print("subject_auth_store_self_test=ok")


if __name__ == "__main__":
    self_test()
