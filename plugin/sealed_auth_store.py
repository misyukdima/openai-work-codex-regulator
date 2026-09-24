#!/usr/bin/env python3
"""Sealed auth-blob lifecycle for the v3 quota Plugin backend.

Production design:
    opaque subject key
      -> encrypted/sealed auth.json blob at rest
      -> private temporary CODEX_HOME for one operation
      -> official Codex may refresh auth.json
      -> validate + reseal updated blob
      -> remove plaintext directory

Cryptography and durable storage are injected adapters. This repository does
not implement homemade production encryption. CI uses explicit test doubles
that are marked production_safe=False and must fail the production gate.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterator, Protocol, runtime_checkable

try:
    from plugin.subject_store import (
        SubjectAuthContext,
        SubjectStoreError,
        derive_subject_key,
        validate_pepper,
    )
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.subject_store import (
        SubjectAuthContext,
        SubjectStoreError,
        derive_subject_key,
        validate_pepper,
    )


AUTH_FILE_NAME = "auth.json"
MAX_AUTH_BLOB_BYTES = 1024 * 1024
AAD_PREFIX = b"openai-work-codex-regulator:v1:"


class ProductionVaultRequired(RuntimeError):
    """Raised when development-only storage/cipher is used in production mode."""


class SealedAuthNotFound(SubjectStoreError):
    pass


class InvalidAuthBlob(SubjectStoreError):
    pass


@runtime_checkable
class SealedBlobStore(Protocol):
    production_safe: bool

    def load(self, subject_key: str) -> bytes | None:
        ...

    def save(self, subject_key: str, sealed: bytes) -> None:
        ...

    def delete(self, subject_key: str) -> bool:
        ...


@runtime_checkable
class EnvelopeCipher(Protocol):
    production_safe: bool

    def seal(self, plaintext: bytes, *, aad: bytes) -> bytes:
        ...

    def open(self, sealed: bytes, *, aad: bytes) -> bytes:
        ...


class InMemoryBlobStore:
    """CI/test storage only. It is not durable and not production-safe."""

    production_safe = False

    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}

    def load(self, subject_key: str) -> bytes | None:
        value = self._items.get(subject_key)
        return bytes(value) if value is not None else None

    def save(self, subject_key: str, sealed: bytes) -> None:
        self._items[subject_key] = bytes(sealed)

    def delete(self, subject_key: str) -> bool:
        return self._items.pop(subject_key, None) is not None


class ReversibleTestCipher:
    """Reversible CI encoding, deliberately NOT encryption.

    The adapter exists only to exercise lifecycle/AAD logic without introducing
    a crypto dependency. `production_safe=False` is a hard release property.
    """

    production_safe = False
    _prefix = b"REGULATOR_TEST_ONLY\x00"

    def seal(self, plaintext: bytes, *, aad: bytes) -> bytes:
        payload = len(aad).to_bytes(4, "big") + aad + plaintext
        return self._prefix + base64.urlsafe_b64encode(payload)

    def open(self, sealed: bytes, *, aad: bytes) -> bytes:
        if not sealed.startswith(self._prefix):
            raise InvalidAuthBlob("test sealed blob prefix mismatch")
        try:
            payload = base64.urlsafe_b64decode(sealed[len(self._prefix):])
        except Exception as exc:
            raise InvalidAuthBlob("test sealed blob is malformed") from exc
        if len(payload) < 4:
            raise InvalidAuthBlob("test sealed blob is truncated")
        aad_len = int.from_bytes(payload[:4], "big")
        stored_aad = payload[4:4 + aad_len]
        if stored_aad != aad:
            raise InvalidAuthBlob("sealed auth blob subject binding mismatch")
        return payload[4 + aad_len:]


class SealedSubjectAuthStore:
    """Materializes one decrypted auth.json only for the duration of a call."""

    def __init__(
        self,
        *,
        pepper: bytes,
        blob_store: SealedBlobStore,
        cipher: EnvelopeCipher,
        temp_root: str | os.PathLike[str] | None = None,
    ) -> None:
        self._pepper = validate_pepper(pepper)
        self.blob_store = blob_store
        self.cipher = cipher
        self.temp_root = Path(temp_root).resolve() if temp_root else None
        self.production_safe = bool(
            getattr(blob_store, "production_safe", False)
            and getattr(cipher, "production_safe", False)
        )

    def _subject_key(self, subject: str) -> str:
        return derive_subject_key(subject, self._pepper)

    @staticmethod
    def _aad(subject_key: str) -> bytes:
        return AAD_PREFIX + subject_key.encode("ascii")

    @staticmethod
    def _validate_auth_json(data: bytes) -> bytes:
        if not data:
            raise InvalidAuthBlob("auth.json is empty")
        if len(data) > MAX_AUTH_BLOB_BYTES:
            raise InvalidAuthBlob("auth.json exceeds maximum allowed size")
        try:
            parsed = json.loads(data.decode("utf-8"))
        except Exception as exc:
            raise InvalidAuthBlob("auth.json is not valid UTF-8 JSON") from exc
        if not isinstance(parsed, dict):
            raise InvalidAuthBlob("auth.json root must be an object")
        return data

    @staticmethod
    def _write_private(path: Path, data: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(fd)
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _new_temp_home(self) -> Path:
        if self.temp_root is not None:
            self.temp_root.mkdir(parents=True, exist_ok=True)
            raw = tempfile.mkdtemp(prefix="regulator-codex-", dir=self.temp_root)
        else:
            raw = tempfile.mkdtemp(prefix="regulator-codex-")
        home = Path(raw)
        try:
            home.chmod(0o700)
        except OSError:
            pass
        return home

    def exists(self, subject: str) -> bool:
        return self.blob_store.load(self._subject_key(subject)) is not None

    def open(self, subject: str) -> SubjectAuthContext:
        raise SubjectStoreError(
            "sealed store cannot expose a durable plaintext context; use authorization_session()"
        )

    @contextmanager
    def authorization_session(self, subject: str) -> Iterator[SubjectAuthContext]:
        """Create a temporary empty CODEX_HOME for explicit authorization.

        On successful exit an official Codex-written auth.json is validated,
        sealed and persisted. Plaintext is removed in all cases.
        """
        subject_key = self._subject_key(subject)
        home = self._new_temp_home()
        context = SubjectAuthContext(subject_key=subject_key, codex_home=home)
        try:
            yield context
            auth_file = home / AUTH_FILE_NAME
            if not auth_file.is_file() or auth_file.is_symlink():
                raise InvalidAuthBlob("authorization completed without regular auth.json")
            plaintext = self._validate_auth_json(auth_file.read_bytes())
            sealed = self.cipher.seal(plaintext, aad=self._aad(subject_key))
            self.blob_store.save(subject_key, sealed)
        finally:
            shutil.rmtree(home, ignore_errors=True)

    @contextmanager
    def materialize(self, subject: str) -> Iterator[SubjectAuthContext]:
        """Decrypt one subject auth blob for one backend operation.

        On normal exit a valid updated auth.json is resealed, preserving official
        Codex refreshes. On exceptional exit no new plaintext state is persisted.
        The temporary directory is removed in all cases.
        """
        subject_key = self._subject_key(subject)
        sealed = self.blob_store.load(subject_key)
        if sealed is None:
            raise SealedAuthNotFound("subject has no sealed auth state")
        plaintext = self._validate_auth_json(
            self.cipher.open(sealed, aad=self._aad(subject_key))
        )

        home = self._new_temp_home()
        context = SubjectAuthContext(subject_key=subject_key, codex_home=home)
        auth_file = home / AUTH_FILE_NAME
        self._write_private(auth_file, plaintext)

        try:
            yield context
            if not auth_file.is_file() or auth_file.is_symlink():
                raise InvalidAuthBlob("backend operation removed or replaced auth.json")
            updated = self._validate_auth_json(auth_file.read_bytes())
            resealed = self.cipher.seal(updated, aad=self._aad(subject_key))
            self.blob_store.save(subject_key, resealed)
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def revoke(self, subject: str) -> bool:
        return self.blob_store.delete(self._subject_key(subject))


def require_production_safe(store: SealedSubjectAuthStore) -> None:
    if not store.production_safe:
        raise ProductionVaultRequired(
            "production requires production_safe blob storage and envelope cipher adapters"
        )


def self_test() -> None:
    pepper = b"s" * 32
    blobs = InMemoryBlobStore()
    cipher = ReversibleTestCipher()
    store = SealedSubjectAuthStore(pepper=pepper, blob_store=blobs, cipher=cipher)
    subject_a = "plugin-subject-a"
    subject_b = "plugin-subject-b"

    assert store.production_safe is False
    try:
        require_production_safe(store)
    except ProductionVaultRequired:
        pass
    else:
        raise AssertionError("test vault must fail production safety gate")

    # Explicit authorization creates plaintext only inside a temp home and seals
    # the official auth.json on successful exit.
    with store.authorization_session(subject_a) as ctx:
        auth_file = ctx.codex_home / AUTH_FILE_NAME
        SealedSubjectAuthStore._write_private(
            auth_file,
            json.dumps({"auth_mode": "chatgpt", "tokens": {"test": "only"}}).encode(),
        )
        auth_home = ctx.codex_home
        assert auth_file.exists()
    assert not auth_home.exists()
    assert store.exists(subject_a) is True
    assert store.exists(subject_b) is False

    key_a = derive_subject_key(subject_a, pepper)
    stored = blobs.load(key_a)
    assert stored is not None
    assert b'"auth_mode"' not in stored

    # Materialization is temporary and official refresh-like writes are resealed.
    with store.materialize(subject_a) as ctx:
        materialized_home = ctx.codex_home
        auth_file = materialized_home / AUTH_FILE_NAME
        parsed = json.loads(auth_file.read_text(encoding="utf-8"))
        assert parsed["auth_mode"] == "chatgpt"
        parsed["last_refresh"] = "2026-09-07T05:00:00Z"
        SealedSubjectAuthStore._write_private(
            auth_file,
            json.dumps(parsed).encode("utf-8"),
        )
    assert not materialized_home.exists()

    with store.materialize(subject_a) as ctx:
        parsed = json.loads((ctx.codex_home / AUTH_FILE_NAME).read_text(encoding="utf-8"))
        assert parsed["last_refresh"] == "2026-09-07T05:00:00Z"

    # Subject binding is included as AAD; another subject cannot open A's blob.
    blobs.save(derive_subject_key(subject_b, pepper), stored)
    try:
        with store.materialize(subject_b):
            pass
    except InvalidAuthBlob:
        pass
    else:
        raise AssertionError("sealed blob must be bound to its opaque subject key")

    assert store.revoke(subject_a) is True
    assert store.exists(subject_a) is False
    assert store.revoke(subject_a) is False

    print("sealed_auth_store_self_test=ok")


if __name__ == "__main__":
    self_test()
