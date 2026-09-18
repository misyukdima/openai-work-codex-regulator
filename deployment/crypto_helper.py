#!/usr/bin/env python3
"""Root-only external cryptographic helper daemon for openai-work-codex-regulator v3.

Architectural Scope:
- Single-host production scope: runs as root on a single dedicated Debian guest VM.
- Performs NO in-process cryptography. Authenticated encryption/decryption is performed
  strictly by the system utility /usr/bin/systemd-creds with host credentials.
- Privilege boundary: listens on a restricted AF_UNIX stream socket, verifies peer credentials
  via SO_PEERCRED, and serves requests strictly from unprivileged user 'regulator'.
- Threat model: No protection claim against guest root or hypervisor root. Isolates host
  credential keys (/var/lib/systemd/credential.secret mode 0400 root:root) from direct
  access by unprivileged application workers.
"""

from __future__ import annotations

import grp
import os
from pathlib import Path
import pwd
import signal
import socket
import struct
import subprocess
import sys
import time


# Production Defaults
PRODUCTION_SOCKET = Path("/run/meciles-regulator-crypto/crypto.sock")
PRODUCTION_PARENT = Path("/run/meciles-regulator-crypto")
SYSTEMD_CREDS_PATH = "/usr/bin/systemd-creds"

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
        raise ConnectionError("Truncated stream socket request or unexpected EOF")
    return bytes(buf)


def validate_canonical_aad_and_derive_name(aad: bytes) -> str | None:
    """Validate exact canonical AAD and derive immutable credential name."""
    if not isinstance(aad, (bytes, bytearray)):
        return None
    if not aad.startswith(AAD_PREFIX) or len(aad) != len(AAD_PREFIX) + 64:
        return None
    hex_part = aad[len(AAD_PREFIX):]
    for b in hex_part:
        if b not in _HEX_DIGITS:
            return None
    return f"regulator-auth-v1-{hex_part.decode('ascii')}"


def send_response(sock: socket.socket, status: int, data: bytes = b"") -> None:
    """Send structured response header and payload without leaking internal errors."""
    try:
        header = struct.pack("!4sBI", IPC_MAGIC, status, len(data))
        sock.sendall(header + data)
    except Exception:
        pass


class CryptoHelperService:
    """Root-only IPC service delegating credential operations to systemd-creds."""

    def __init__(self, socket_path: Path = PRODUCTION_SOCKET) -> None:
        self.socket_path = Path(socket_path).resolve()
        self.is_production = (self.socket_path == PRODUCTION_SOCKET)
        self.running = False
        self._server_sock: socket.socket | None = None

        try:
            reg_pwd = pwd.getpwnam("regulator")
            self.allowed_uid = reg_pwd.pw_uid
            self.socket_gid = reg_pwd.pw_gid
        except KeyError:
            # In test environments fallback gracefully if user not present
            self.allowed_uid = os.getuid()
            self.socket_gid = os.getgid()

    def validate_environment(self) -> None:
        """Validate production socket parent directory security invariants."""
        if not self.is_production:
            return

        parent = self.socket_path.parent
        if parent != PRODUCTION_PARENT:
            raise RuntimeError(f"Invalid production socket parent: {parent}")
        if not parent.is_dir() or parent.is_symlink():
            raise RuntimeError(f"Production socket parent {parent} is not a regular directory")

        st = os.stat(parent)
        if st.st_uid != 0:
            raise RuntimeError(f"Production socket parent must be root-owned (UID 0), got {st.st_uid}")
        if stat.S_IMODE(st.st_mode) != 0o750:
            raise RuntimeError(f"Production socket parent mode must be 0750, got {oct(stat.S_IMODE(st.st_mode))}")
        if st.st_gid != self.socket_gid:
            raise RuntimeError(f"Production socket parent GID must match group 'regulator' ({self.socket_gid})")

    def handle_connection(self, client_sock: socket.socket) -> None:
        """Process one client connection with peer validation and systemd-creds execution."""
        try:
            # SO_PEERCRED verification
            creds = client_sock.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, 12)
            _, client_uid, _ = struct.unpack("iII", creds)
            if client_uid != self.allowed_uid:
                send_response(client_sock, STATUS_UNAUTHORIZED)
                return

            # Read 12-byte header: Magic(4B) + Ver(1B) + Op(1B) + AAD_len(2B) + Payload_len(4B)
            raw_hdr = _recvall(client_sock, 12)
            magic, ver, op, aad_len, payload_len = struct.unpack("!4sBBHI", raw_hdr)

            if magic != IPC_MAGIC or ver != IPC_VERSION:
                send_response(client_sock, STATUS_INVALID_REQUEST)
                return

            if op not in (OP_SEAL, OP_OPEN):
                send_response(client_sock, STATUS_INVALID_REQUEST)
                return

            if aad_len != len(AAD_PREFIX) + 64:  # Exactly 95 bytes
                send_response(client_sock, STATUS_INVALID_REQUEST)
                return

            # Asymmetric request payload bounds
            if op == OP_SEAL and payload_len > MAX_AUTH_BLOB_BYTES:
                send_response(client_sock, STATUS_INVALID_REQUEST)
                return
            if op == OP_OPEN and payload_len > MAX_SEALED_BLOB_BYTES:
                send_response(client_sock, STATUS_INVALID_REQUEST)
                return

            # Read canonical AAD and derive name
            raw_aad = _recvall(client_sock, aad_len)
            derived_name = validate_canonical_aad_and_derive_name(raw_aad)
            if derived_name is None:
                send_response(client_sock, STATUS_INVALID_REQUEST)
                return

            # Read request payload
            payload = _recvall(client_sock, payload_len)

            # Invoke /usr/bin/systemd-creds with argument array (shell=False)
            # Note: systemd-creds runs non-interactively when standard input/output are redirected.
            if op == OP_SEAL:
                cmd = [SYSTEMD_CREDS_PATH, "encrypt", "--with-key=host", f"--name={derived_name}", "-", "-"]
            else:
                cmd = [SYSTEMD_CREDS_PATH, "decrypt", f"--name={derived_name}", "-", "-"]

            env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
            proc = subprocess.run(
                cmd,
                input=payload,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                close_fds=True,
                timeout=10.0,
            )

            if proc.returncode != 0:
                send_response(client_sock, STATUS_CRYPTO_ERROR)
                return

            out_data = proc.stdout
            # Validate output bounds
            if op == OP_SEAL and len(out_data) > MAX_SEALED_BLOB_BYTES:
                send_response(client_sock, STATUS_CRYPTO_ERROR)
                return
            if op == OP_OPEN and len(out_data) > MAX_AUTH_BLOB_BYTES:
                send_response(client_sock, STATUS_CRYPTO_ERROR)
                return

            send_response(client_sock, STATUS_OK, out_data)

        except (ConnectionError, struct.error):
            pass
        except subprocess.TimeoutExpired:
            send_response(client_sock, STATUS_CRYPTO_ERROR)
        except Exception:
            send_response(client_sock, STATUS_INVALID_REQUEST)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def run(self) -> None:
        """Start listening loop and handle graceful termination."""
        self.validate_environment()

        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(str(self.socket_path))

        # Apply ownership and mode: root:regulator 0660
        try:
            os.chown(self.socket_path, 0, self.socket_gid)
            os.chmod(self.socket_path, 0o660)
        except OSError:
            pass

        self._server_sock.listen(16)
        self._server_sock.settimeout(1.0)
        self.running = True

        def _sig_handler(signum: int, frame: object) -> None:
            self.running = False

        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)

        try:
            while self.running:
                try:
                    client_sock, _ = self._server_sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                self.handle_connection(client_sock)
        finally:
            if self._server_sock:
                try:
                    self._server_sock.close()
                except OSError:
                    pass
            if self.socket_path.exists():
                try:
                    self.socket_path.unlink()
                except OSError:
                    pass


def main() -> None:
    socket_override = sys.argv[1] if len(sys.argv) > 1 else str(PRODUCTION_SOCKET)
    helper = CryptoHelperService(socket_path=Path(socket_override))
    helper.run()


if __name__ == "__main__":
    main()
