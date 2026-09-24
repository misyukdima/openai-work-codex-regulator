#!/usr/bin/env python3
"""Provider-neutral production vault adapters for sealed Plugin auth state.

The repository intentionally does not implement cryptography or distributed
locking. Production injects audited external storage, crypto and per-subject
lease providers. These adapters bind them to the narrow regulator contracts and
fail closed when required safety properties are absent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, runtime_checkable

try:
    from plugin.auth_concurrency import LeaseProtectedAuthStore, SubjectLeaseProvider
    from plugin.sealed_auth_store import (
        EnvelopeCipher,
        SealedBlobStore,
        SealedSubjectAuthStore,
        require_production_safe,
    )
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.auth_concurrency import LeaseProtectedAuthStore, SubjectLeaseProvider
    from plugin.sealed_auth_store import (
        EnvelopeCipher,
        SealedBlobStore,
        SealedSubjectAuthStore,
        require_production_safe,
    )


_SUBJECT_KEY_RE = re.compile(r"^[0-9a-f]{64}$")


class InvalidVaultConfiguration(RuntimeError):
    pass


@runtime_checkable
class DurableBlobProvider(Protocol):
    """External durable object/secret store reviewed by the deployer.

    `atomic_replace=True` means readers never observe a partially written object
    when one sealed blob replaces another. The deployment is responsible for
    proving that property for the selected backend.
    """

    production_safe: bool
    atomic_replace: bool

    def get_bytes(self, object_key: str) -> bytes | None:
        ...

    def put_bytes(self, object_key: str, value: bytes) -> None:
        ...

    def delete(self, object_key: str) -> bool:
        ...


@runtime_checkable
class EnvelopeCryptoProvider(Protocol):
    """External KMS/envelope-crypto provider reviewed by the deployer."""

    production_safe: bool
    key_reference: str
    algorithm_id: str

    def seal(self, plaintext: bytes, *, key_reference: str, aad: bytes) -> bytes:
        ...

    def open(self, sealed: bytes, *, key_reference: str, aad: bytes) -> bytes:
        ...


class DurableSealedBlobStore:
    """Maps opaque subject keys to an external durable blob provider."""

    def __init__(self, provider: DurableBlobProvider, *, prefix: str = "regulator-auth/v1") -> None:
        self.provider = provider
        cleaned = prefix.strip().strip("/")
        if not cleaned or ".." in cleaned:
            raise InvalidVaultConfiguration("vault object prefix is invalid")
        self.prefix = cleaned
        self.production_safe = bool(
            getattr(provider, "production_safe", False)
            and getattr(provider, "atomic_replace", False)
        )

    def _object_key(self, subject_key: str) -> str:
        if not _SUBJECT_KEY_RE.fullmatch(subject_key):
            raise InvalidVaultConfiguration("subject key must be 64 lowercase hex characters")
        return f"{self.prefix}/{subject_key}.sealed"

    def load(self, subject_key: str) -> bytes | None:
        value = self.provider.get_bytes(self._object_key(subject_key))
        if value is None:
            return None
        if not isinstance(value, (bytes, bytearray)):
            raise InvalidVaultConfiguration("durable provider returned non-bytes payload")
        return bytes(value)

    def save(self, subject_key: str, sealed: bytes) -> None:
        if not isinstance(sealed, (bytes, bytearray)) or not sealed:
            raise InvalidVaultConfiguration("sealed payload must be non-empty bytes")
        self.provider.put_bytes(self._object_key(subject_key), bytes(sealed))

    def delete(self, subject_key: str) -> bool:
        return bool(self.provider.delete(self._object_key(subject_key)))


class ExternalEnvelopeCipher:
    """Pass-through adapter to an audited external crypto provider.

    No encryption primitive lives in this repository. A deployment may mark the
    adapter production-safe only when the injected provider itself is marked
    production-safe and declares a concrete key reference and algorithm id.
    """

    def __init__(self, provider: EnvelopeCryptoProvider) -> None:
        self.provider = provider
        self.key_reference = str(getattr(provider, "key_reference", "")).strip()
        self.algorithm_id = str(getattr(provider, "algorithm_id", "")).strip()
        self.production_safe = bool(
            getattr(provider, "production_safe", False)
            and self.key_reference
            and self.algorithm_id
        )
        if not self.key_reference or not self.algorithm_id:
            raise InvalidVaultConfiguration("crypto provider must declare key_reference and algorithm_id")

    def seal(self, plaintext: bytes, *, aad: bytes) -> bytes:
        sealed = self.provider.seal(
            plaintext,
            key_reference=self.key_reference,
            aad=aad,
        )
        if not isinstance(sealed, (bytes, bytearray)) or not sealed:
            raise InvalidVaultConfiguration("crypto provider returned invalid sealed payload")
        return bytes(sealed)

    def open(self, sealed: bytes, *, aad: bytes) -> bytes:
        plaintext = self.provider.open(
            sealed,
            key_reference=self.key_reference,
            aad=aad,
        )
        if not isinstance(plaintext, (bytes, bytearray)):
            raise InvalidVaultConfiguration("crypto provider returned invalid plaintext payload")
        return bytes(plaintext)


def build_production_auth_store(
    *,
    pepper: bytes,
    blob_provider: DurableBlobProvider,
    crypto_provider: EnvelopeCryptoProvider,
    lease_provider: SubjectLeaseProvider,
    prefix: str = "regulator-auth/v1",
    lease_wait_timeout_seconds: float = 30.0,
) -> LeaseProtectedAuthStore:
    """Build the complete production credential boundary.

    Production safety requires all three independently reviewed properties:
    durable atomic blob replacement, external envelope cryptography and a
    cross-worker subject lease. One missing property keeps the store unsafe.
    """
    blob_store: SealedBlobStore = DurableSealedBlobStore(blob_provider, prefix=prefix)
    cipher: EnvelopeCipher = ExternalEnvelopeCipher(crypto_provider)
    sealed_store = SealedSubjectAuthStore(
        pepper=pepper,
        blob_store=blob_store,
        cipher=cipher,
    )
    require_production_safe(sealed_store)

    protected = LeaseProtectedAuthStore(
        delegate=sealed_store,
        pepper=pepper,
        lease_provider=lease_provider,
        wait_timeout_seconds=lease_wait_timeout_seconds,
    )
    if not protected.production_safe:
        raise InvalidVaultConfiguration(
            "production requires a production-safe cross-worker subject lease provider"
        )
    return protected


class _UnsafeBlobProvider:
    production_safe = False
    atomic_replace = False

    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    def get_bytes(self, object_key: str) -> bytes | None:
        return self.items.get(object_key)

    def put_bytes(self, object_key: str, value: bytes) -> None:
        self.items[object_key] = bytes(value)

    def delete(self, object_key: str) -> bool:
        return self.items.pop(object_key, None) is not None


class _UnsafeCryptoProvider:
    production_safe = False
    key_reference = "test-only"
    algorithm_id = "not-encryption"

    def seal(self, plaintext: bytes, *, key_reference: str, aad: bytes) -> bytes:
        return aad + b"\x00" + plaintext

    def open(self, sealed: bytes, *, key_reference: str, aad: bytes) -> bytes:
        prefix = aad + b"\x00"
        if not sealed.startswith(prefix):
            raise InvalidVaultConfiguration("test AAD mismatch")
        return sealed[len(prefix):]


def self_test() -> None:
    from plugin.auth_concurrency import InProcessSubjectLeaseProvider

    blobs = _UnsafeBlobProvider()
    crypto = _UnsafeCryptoProvider()
    blob_adapter = DurableSealedBlobStore(blobs, prefix="regulator-auth/v1")
    cipher_adapter = ExternalEnvelopeCipher(crypto)

    key = "a" * 64
    blob_adapter.save(key, b"sealed-test")
    assert blob_adapter.load(key) == b"sealed-test"
    assert list(blobs.items) == [f"regulator-auth/v1/{key}.sealed"]
    assert blob_adapter.production_safe is False
    assert cipher_adapter.production_safe is False

    try:
        blob_adapter.save("../raw-subject", b"x")
    except InvalidVaultConfiguration:
        pass
    else:
        raise AssertionError("caller-controlled object keys must fail")

    try:
        build_production_auth_store(
            pepper=b"v" * 32,
            blob_provider=blobs,
            crypto_provider=crypto,
            lease_provider=InProcessSubjectLeaseProvider(),
        )
    except Exception as exc:
        assert "production" in str(exc).lower()
    else:
        raise AssertionError("unsafe provider set must fail production gate")

    print("production_vault_adapter_self_test=ok")


if __name__ == "__main__":
    self_test()
