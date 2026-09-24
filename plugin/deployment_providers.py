#!/usr/bin/env python3
"""Production deployment providers for openai-work-codex-regulator v3.

Architectural Scope:
- Single-host production scope: all components run on a single dedicated Debian guest VM.
- No multi-host distributed lease guarantee: FlockSubjectLeaseProvider uses local
  kernel fcntl.flock serialization across local processes/workers.
- systemd-creds external crypto boundary: SystemdCredsEnvelopeCryptoProvider performs
  NO in-process cryptography. Authenticated encryption/decryption is delegated
  strictly over an AF_UNIX stream socket to a root-only external helper invoking
  systemd-creds with host-bound credentials.
- Threat model: No protection claim against guest root or hypervisor root. Privilege
  separation protects host credential keys and storage against unprivileged application
  memory disclosure or unauthorized key export.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import grp
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import struct
import time
from typing import Iterator
import uuid

try:
    from plugin.auth_concurrency import SubjectLeaseTimeout
except ImportError:
    class SubjectLeaseTimeout(RuntimeError):
        """Raised when acquiring a subject lease times out."""


# Explicit Production Paths
PRODUCTION_VAULT_ROOT = Path("/var/lib/meciles-regulator/auth-vault")
PRODUCTION_LOCK_ROOT = Path("/run/meciles-regulator/locks")
PRODUCTION_CRYPTO_SOCKET = Path("/run/meciles-regulator-crypto/crypto.sock")
CRYPTO_SOCKET_PARENT = Path("/run/meciles-regulator-crypto")

# Asymmetric Size Limits
MAX_AUTH_BLOB_BYTES = 1024 * 1024       # 1 MiB (max plaintext auth.json)
MAX_SEALED_BLOB_BYTES = 2 * 1024 * 1024  # 2 MiB (max sealed ciphertext)

# IPC Framing Constants
IPC_MAGIC = b"REGC"
IPC_VERSION = 1

OP_SEAL = 1
OP_OPEN = 2

STATUS_OK = 0
STATUS_UNAUTHORIZED = 1
STATUS_INVALID_REQUEST = 2
STATUS_CRYPTO_ERROR = 3

AAD_PREFIX = b"openai-work-codex-regulator:v1:"
_HEX_DIGITS = set(b"0123456789abcdef")
_SUBJECT_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
_OBJECT_KEY_RE = re.compile(r"^regulator-auth/v1/([0-9a-f]{64})\.sealed$")

SO_PEERCRED = getattr(socket, "SO_PEERCRED", 17)


def _recvall(sock: socket.socket, n: int) -> bytes:
    """Read exact number of bytes from stream socket or raise ConnectionError."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(n - len(buf), 65536))
        if not chunk:
            break
        buf.extend(chunk)
    if len(buf) != n:
        raise ConnectionError("Truncated stream socket response or unexpected EOF")
    return bytes(buf)


def validate_canonical_aad(aad: bytes) -> str:
    """Validate exact canonical AAD syntax: b'openai-work-codex-regulator:v1:' + 64 hex bytes."""
    if not isinstance(aad, (bytes, bytearray)):
        raise ValueError("AAD must be bytes")
    if not aad.startswith(AAD_PREFIX) or len(aad) != len(AAD_PREFIX) + 64:
        raise ValueError("AAD must be exactly 95 bytes starting with canonical prefix")
    hex_part = aad[len(AAD_PREFIX):]
    for b in hex_part:
        if b not in _HEX_DIGITS:
            raise ValueError("AAD subject key must contain only lowercase hex characters")
    return hex_part.decode("ascii")


class HardenedAtomicFileBlobProvider:
    """Hardened local atomic file blob provider for sealed subject auth credentials.

    Conforms to plugin.production_vault.DurableBlobProvider protocol.
    Enforces atomic replace, 0600 file permissions, strict key confinement,
    and symlink/traversal rejection.
    """

    atomic_replace: bool = True

    def __init__(self, root_dir: str | Path = PRODUCTION_VAULT_ROOT) -> None:
        self.root_dir = Path(root_dir).resolve()

    @property
    def production_safe(self) -> bool:
        """Dynamically evaluate whether deployment root satisfies production invariants."""
        if self.root_dir != PRODUCTION_VAULT_ROOT:
            return False
        if not self.root_dir.is_absolute() or not self.root_dir.is_dir() or self.root_dir.is_symlink():
            return False
        try:
            st = os.stat(self.root_dir)
            if st.st_uid != os.getuid():
                return False
            if stat.S_IMODE(st.st_mode) != 0o700:
                return False
            return True
        except OSError:
            return False

    def _resolve_target(self, object_key: str) -> tuple[Path, str]:
        if not isinstance(object_key, str):
            raise ValueError("object_key must be a string")
        if object_key.startswith("/") or ".." in object_key:
            raise ValueError(f"Path traversal or absolute path rejected: {object_key}")
        match = _OBJECT_KEY_RE.fullmatch(object_key)
        if not match:
            raise ValueError(f"Object key violates canonical grammar: {object_key}")
        subject_key = match.group(1)
        auth_dir = self.root_dir / "regulator-auth" / "v1"
        target_path = auth_dir / f"{subject_key}.sealed"
        return target_path, subject_key

    def get_bytes(self, object_key: str) -> bytes | None:
        target_path, _ = self._resolve_target(object_key)
        if not target_path.exists():
            return None

        st = os.lstat(target_path)
        if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
            raise RuntimeError(f"Refusing to read non-regular file or symlink: {target_path}")

        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC

        fd = os.open(target_path, flags)
        try:
            with os.fdopen(fd, "rb", closefd=False) as handle:
                data = handle.read()
                if len(data) > MAX_SEALED_BLOB_BYTES:
                    raise RuntimeError("Sealed blob on disk exceeds MAX_SEALED_BLOB_BYTES")
                return data
        finally:
            os.close(fd)

    def put_bytes(self, object_key: str, value: bytes) -> None:
        if not isinstance(value, (bytes, bytearray)) or len(value) == 0:
            raise ValueError("Value must be non-empty bytes")
        if len(value) > MAX_SEALED_BLOB_BYTES:
            raise ValueError(f"Sealed payload exceeds maximum bound of {MAX_SEALED_BLOB_BYTES} bytes")

        target_path, _ = self._resolve_target(object_key)
        parent_dir = target_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        temp_name = f".tmp.{uuid.uuid4().hex}.sealed"
        temp_path = parent_dir / temp_name

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC

        fd = os.open(temp_path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as handle:
                written = 0
                while written < len(value):
                    n = handle.write(value[written:])
                    if n is None:
                        break
                    written += n
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        else:
            os.close(fd)
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
            os.replace(temp_path, target_path)

            dir_flags = os.O_RDONLY
            if hasattr(os, "O_DIRECTORY"):
                dir_flags |= os.O_DIRECTORY
            if hasattr(os, "O_CLOEXEC"):
                dir_flags |= os.O_CLOEXEC
            dir_fd = os.open(parent_dir, dir_flags)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def delete(self, object_key: str) -> bool:
        target_path, _ = self._resolve_target(object_key)
        if not target_path.exists():
            return False

        st = os.lstat(target_path)
        if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
            raise RuntimeError(f"Refusing to delete non-regular file or symlink: {target_path}")

        parent_dir = target_path.parent
        target_path.unlink()

        dir_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            dir_flags |= os.O_DIRECTORY
        if hasattr(os, "O_CLOEXEC"):
            dir_flags |= os.O_CLOEXEC
        dir_fd = os.open(parent_dir, dir_flags)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return True


class FlockSubjectLeaseProvider:
    """Cross-process subject serialization provider based on local fcntl.flock locks.

    Conforms to plugin.auth_concurrency.SubjectLeaseProvider protocol.
    Guarantees mutual exclusion per subject across concurrent workers on this host.
    """

    def __init__(self, lock_dir: str | Path = PRODUCTION_LOCK_ROOT) -> None:
        self.lock_dir = Path(lock_dir).resolve()

    @property
    def production_safe(self) -> bool:
        """Verify lock directory satisfies production security requirements."""
        if self.lock_dir != PRODUCTION_LOCK_ROOT:
            return False
        if not self.lock_dir.is_absolute() or not self.lock_dir.is_dir() or self.lock_dir.is_symlink():
            return False
        try:
            st = os.stat(self.lock_dir)
            if st.st_uid != os.getuid():
                return False
            if stat.S_IMODE(st.st_mode) != 0o700:
                return False
            return True
        except OSError:
            return False

    @contextmanager
    def lease(
        self,
        subject_key: str,
        *,
        purpose: str,
        wait_timeout_seconds: float,
    ) -> Iterator[None]:
        if not isinstance(subject_key, str) or not _SUBJECT_KEY_RE.fullmatch(subject_key):
            raise ValueError(f"Invalid subject_key for lease: {subject_key}")
        if wait_timeout_seconds <= 0:
            raise ValueError("wait_timeout_seconds must be positive")

        self.lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.lock_dir / f"{subject_key}.lock"

        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC

        fd = os.open(lock_path, flags, 0o600)
        deadline = time.monotonic() + wait_timeout_seconds
        acquired = False
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (BlockingIOError, OSError) as exc:
                    if time.monotonic() >= deadline:
                        raise SubjectLeaseTimeout(
                            f"timed out acquiring subject lease for {purpose} on {subject_key}"
                        ) from exc
                    time.sleep(0.02)
            yield
        finally:
            try:
                if acquired:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


class SystemdCredsEnvelopeCryptoProvider:
    """Envelope crypto provider adapter communicating with root-only external helper.

    Conforms to plugin.production_vault.EnvelopeCryptoProvider protocol.
    Contains NO cryptographic primitive or cipher code. All encryption/decryption
    occurs externally via systemd-creds in the helper daemon.
    """

    key_reference: str = "systemd-creds:host"
    algorithm_id: str = "SYSTEMD-CREDS-AES256-GCM"

    def __init__(self, socket_path: str | Path = PRODUCTION_CRYPTO_SOCKET) -> None:
        self.socket_path = Path(socket_path).resolve()

    @property
    def production_safe(self) -> bool:
        """Verify socket path and parent directory ownership and permissions."""
        if self.socket_path != PRODUCTION_CRYPTO_SOCKET:
            return False
        parent = self.socket_path.parent
        if parent != CRYPTO_SOCKET_PARENT:
            return False
        if not parent.is_absolute() or not parent.is_dir() or parent.is_symlink():
            return False
        try:
            st_parent = os.stat(parent)
            if st_parent.st_uid != 0:
                return False
            if stat.S_IMODE(st_parent.st_mode) != 0o750:
                return False
            reg_gid = grp.getgrnam("regulator").gr_gid
            if st_parent.st_gid != reg_gid:
                return False

            if not self.socket_path.exists():
                return False
            st_sock = os.stat(self.socket_path)
            if not stat.S_ISSOCK(st_sock.st_mode) or self.socket_path.is_symlink():
                return False
            if st_sock.st_uid != 0 or st_sock.st_gid != reg_gid:
                return False
            if stat.S_IMODE(st_sock.st_mode) != 0o660:
                return False
            return True
        except (OSError, KeyError):
            return False

    def _call(self, op: int, aad: bytes, payload: bytes) -> bytes:
        validate_canonical_aad(aad)

        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("Payload must be bytes")

        if op == OP_SEAL and len(payload) > MAX_AUTH_BLOB_BYTES:
            raise ValueError(f"Plaintext exceeds maximum SEAL limit of {MAX_AUTH_BLOB_BYTES} bytes")
        if op == OP_OPEN and len(payload) > MAX_SEALED_BLOB_BYTES:
            raise ValueError(f"Sealed payload exceeds maximum OPEN limit of {MAX_SEALED_BLOB_BYTES} bytes")

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(15.0)
        try:
            s.connect(str(self.socket_path))

            # Verify server peer credentials (must be root UID 0)
            try:
                creds = s.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, 12)
                _, server_uid, _ = struct.unpack("iII", creds)
            except (OSError, struct.error) as exc:
                raise PermissionError("Failed to verify server peer credentials via SO_PEERCRED") from exc

            if server_uid != 0:
                raise PermissionError("Crypto helper server peer is not UID 0 (root)")

            # Framing: Magic(4B) + Ver(1B) + Op(1B) + AAD_len(2B) + Payload_len(4B)
            req_hdr = struct.pack("!4sBBHI", IPC_MAGIC, IPC_VERSION, op, len(aad), len(payload))
            s.sendall(req_hdr + aad + payload)

            # Response header: Magic(4B) + Status(1B) + Data_len(4B) = 9 bytes
            resp_hdr = _recvall(s, 9)
            resp_magic, status, data_len = struct.unpack("!4sBI", resp_hdr)

            if resp_magic != IPC_MAGIC:
                raise RuntimeError("Invalid magic header in crypto helper response")

            # Asymmetric bounds check before allocating response buffer
            if op == OP_SEAL and data_len > MAX_SEALED_BLOB_BYTES:
                raise RuntimeError("Crypto helper response exceeds MAX_SEALED_BLOB_BYTES")
            if op == OP_OPEN and data_len > MAX_AUTH_BLOB_BYTES:
                raise RuntimeError("Crypto helper response exceeds MAX_AUTH_BLOB_BYTES")

            if status != STATUS_OK:
                if status == STATUS_UNAUTHORIZED:
                    raise PermissionError("Crypto helper rejected caller: unauthorized peer")
                elif status == STATUS_INVALID_REQUEST:
                    raise ValueError("Crypto helper rejected malformed or invalid request")
                elif status == STATUS_CRYPTO_ERROR:
                    raise RuntimeError("External systemd-creds operation failed")
                else:
                    raise RuntimeError(f"Crypto helper returned error status: {status}")

            return _recvall(s, data_len)
        finally:
            s.close()

    def seal(self, plaintext: bytes, *, key_reference: str, aad: bytes) -> bytes:
        if key_reference != self.key_reference:
            raise ValueError(f"Key reference mismatch: expected {self.key_reference}, got {key_reference}")
        return self._call(OP_SEAL, aad, plaintext)

    def open(self, sealed: bytes, *, key_reference: str, aad: bytes) -> bytes:
        if key_reference != self.key_reference:
            raise ValueError(f"Key reference mismatch: expected {self.key_reference}, got {key_reference}")
        return self._call(OP_OPEN, aad, sealed)
