#!/usr/bin/env python3
"""Zero-secret regression test harness for production deployment providers.

Validates:
- HardenedAtomicFileBlobProvider confinement, atomicity, permissions and bounds.
- FlockSubjectLeaseProvider mutual exclusion, crash release and concurrency.
- Crypto IPC framing, asymmetric bounds, canonical AAD validation and error handling.
- Production safety fail-closed invariants without needing production setup.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugin.deployment_providers import (
    HardenedAtomicFileBlobProvider,
    FlockSubjectLeaseProvider,
    SystemdCredsEnvelopeCryptoProvider,
    validate_canonical_aad,
    PRODUCTION_VAULT_ROOT,
    PRODUCTION_LOCK_ROOT,
    PRODUCTION_CRYPTO_SOCKET,
    MAX_AUTH_BLOB_BYTES,
    MAX_SEALED_BLOB_BYTES,
    IPC_MAGIC,
    IPC_VERSION,
    OP_SEAL,
    OP_OPEN,
    STATUS_OK,
    STATUS_UNAUTHORIZED,
    STATUS_INVALID_REQUEST,
    STATUS_CRYPTO_ERROR,
    AAD_PREFIX,
    SubjectLeaseTimeout,
)


def test_blob_provider() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="regulator-test-vault-"))
    try:
        provider = HardenedAtomicFileBlobProvider(temp_dir)
        # In temporary directory, provider must NEVER claim production_safe=True
        assert provider.production_safe is False, "Temp vault must be production_safe=False"
        assert provider.atomic_replace is True

        key = "a" * 64
        obj_key = f"regulator-auth/v1/{key}.sealed"
        data1 = b"SEALED_PAYLOAD_TEST_1"

        # put and get
        provider.put_bytes(obj_key, data1)
        assert provider.get_bytes(obj_key) == data1, "Blob put/get roundtrip mismatch"

        # atomic replace
        data2 = b"SEALED_PAYLOAD_TEST_2_UPDATED"
        provider.put_bytes(obj_key, data2)
        assert provider.get_bytes(obj_key) == data2, "Atomic replace failed"

        # check 0600 mode
        target = temp_dir / "regulator-auth" / "v1" / f"{key}.sealed"
        st = os.stat(target)
        assert stat.S_IMODE(st.st_mode) == 0o600, f"Expected 0600 mode, got {oct(stat.S_IMODE(st.st_mode))}"

        # symlink rejection
        sym_key = "b" * 64
        sym_obj = f"regulator-auth/v1/{sym_key}.sealed"
        sym_path = temp_dir / "regulator-auth" / "v1" / f"{sym_key}.sealed"
        try:
            sym_path.symlink_to(target)
            try:
                provider.get_bytes(sym_obj)
            except RuntimeError:
                pass
            else:
                raise AssertionError("Symlink get_bytes must fail")

            try:
                provider.delete(sym_obj)
            except RuntimeError:
                pass
            else:
                raise AssertionError("Symlink delete must fail")
        finally:
            if sym_path.is_symlink():
                sym_path.unlink()

        # traversal and absolute path rejection
        for bad_key in [
            "../outside.sealed",
            "/tmp/abs.sealed",
            "regulator-auth/v1/../../etc/passwd",
            f"wrong-prefix/v1/{key}.sealed",
            f"regulator-auth/v1/{'A'*64}.sealed",
            f"regulator-auth/v1/{'a'*63}.sealed",
            f"regulator-auth/v1/{'a'*65}.sealed",
        ]:
            try:
                provider.get_bytes(bad_key)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Malformed/traversal key must be rejected: {bad_key}")

            try:
                provider.put_bytes(bad_key, b"x")
            except ValueError:
                pass
            else:
                raise AssertionError(f"Malformed/traversal key must be rejected for put: {bad_key}")

        # oversize sealed payload rejection
        try:
            provider.put_bytes(obj_key, b"x" * (MAX_SEALED_BLOB_BYTES + 1))
        except ValueError:
            pass
        else:
            raise AssertionError("Oversized sealed payload must be rejected")

        # delete
        assert provider.delete(obj_key) is True, "Delete existing failed"
        assert provider.get_bytes(obj_key) is None, "Deleted blob still readable"
        assert provider.delete(obj_key) is False, "Repeated delete returned True"

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_lease_provider() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="regulator-test-locks-"))
    try:
        provider = FlockSubjectLeaseProvider(temp_dir)
        # In temporary directory, provider must NEVER claim production_safe=True
        assert provider.production_safe is False, "Temp lock dir must be production_safe=False"

        subj1 = "1" * 64
        subj2 = "2" * 64

        # Rejection of invalid subject keys
        for bad_subj in ["", "A"*64, "1"*63, "1"*65, "../traversal", "user@domain"]:
            try:
                with provider.lease(bad_subj, purpose="test", wait_timeout_seconds=0.1):
                    pass
            except ValueError:
                pass
            else:
                raise AssertionError(f"Bad subject key must be rejected for lease: {bad_subj}")

        # Cross-process exclusion test
        ready_file = temp_dir / "worker.ready"
        worker_code = f"""
import sys, time
from pathlib import Path
sys.path.insert(0, "{ROOT}")
from plugin.deployment_providers import FlockSubjectLeaseProvider

p = FlockSubjectLeaseProvider("{temp_dir}")
with p.lease("{subj1}", purpose="hold", wait_timeout_seconds=5.0):
    Path("{ready_file}").touch()
    time.sleep(2.0)
"""
        proc = subprocess.Popen([sys.executable, "-c", worker_code])
        for _ in range(30):
            if ready_file.exists():
                break
            time.sleep(0.1)
        assert ready_file.exists(), "Worker failed to acquire lease"

        # Parent attempts to acquire same subject with short timeout
        t0 = time.monotonic()
        try:
            with provider.lease(subj1, purpose="conflict", wait_timeout_seconds=0.2):
                raise AssertionError("Must not acquire held subject lease")
        except SubjectLeaseTimeout:
            pass
        assert time.monotonic() - t0 >= 0.15, "Timeout expired too quickly"

        # Independent subject concurrency while worker holds subj1
        with provider.lease(subj2, purpose="independent", wait_timeout_seconds=0.5):
            pass

        # Post-crash reacquire: kill worker with SIGKILL
        proc.kill()
        proc.wait()

        # Parent must now be able to acquire subj1 immediately
        with provider.lease(subj1, purpose="post-crash", wait_timeout_seconds=1.0):
            pass

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_ipc_framing_and_bounds() -> None:
    # Test canonical AAD validator directly
    valid_aad = AAD_PREFIX + (b"f" * 64)
    assert validate_canonical_aad(valid_aad) == ("f" * 64)

    for bad_aad in [
        b"",
        AAD_PREFIX + (b"F" * 64),
        AAD_PREFIX + (b"f" * 63),
        AAD_PREFIX + (b"f" * 65),
        AAD_PREFIX + (b"01234/67" * 8),
        AAD_PREFIX + (b"01234\x0067" * 8),
        AAD_PREFIX + (b"01234\n67" * 8),
        b"raw_subject_without_prefix",
    ]:
        try:
            validate_canonical_aad(bad_aad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Bad AAD must be rejected: {bad_aad!r}")

    # Set up local ephemeral mock UNIX socket helper to test client protocol enforcement
    sock_dir = Path(tempfile.mkdtemp(prefix="regulator-test-ipc-"))
    sock_path = sock_dir / "mock_helper.sock"

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(4)
    server.settimeout(2.0)

    server_running = True

    def _mock_server():
        while server_running:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                # Read 12-byte header
                hdr = conn.recv(12)
                if len(hdr) < 12:
                    conn.close()
                    continue
                magic, ver, op, aad_len, payload_len = struct.unpack("!4sBBHI", hdr)
                aad = conn.recv(aad_len)
                payload = conn.recv(payload_len)

                # Echo back test response with valid framing
                resp_payload = b"MOCK_RESULT:" + payload[:32]
                resp_hdr = struct.pack("!4sBI", IPC_MAGIC, STATUS_OK, len(resp_payload))
                conn.sendall(resp_hdr + resp_payload)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    th = threading.Thread(target=_mock_server, daemon=True)
    th.start()

    try:
        crypto_prov = SystemdCredsEnvelopeCryptoProvider(sock_path)
        assert crypto_prov.production_safe is False, "Temp crypto socket must be production_safe=False"

        # Client bounds check BEFORE sending:
        # SEAL > 1 MiB rejected
        try:
            crypto_prov.seal(b"x" * (MAX_AUTH_BLOB_BYTES + 1), key_reference="systemd-creds:host", aad=valid_aad)
        except ValueError:
            pass
        else:
            raise AssertionError("SEAL > 1 MiB must be rejected before socket send")

        # OPEN > 2 MiB rejected
        try:
            crypto_prov.open(b"x" * (MAX_SEALED_BLOB_BYTES + 1), key_reference="systemd-creds:host", aad=valid_aad)
        except ValueError:
            pass
        else:
            raise AssertionError("OPEN > 2 MiB must be rejected before socket send")

        # Key reference mismatch rejected
        try:
            crypto_prov.seal(b"x", key_reference="wrong:key", aad=valid_aad)
        except ValueError:
            pass
        else:
            raise AssertionError("Mismatched key reference must be rejected")

        # Valid mock calls:
        # Server peer SO_PEERCRED check:
        # Since mock server runs in same test process as current user (not root),
        # crypto_prov._call will raise PermissionError because server peer != UID 0!
        try:
            crypto_prov.seal(b"hello", key_reference="systemd-creds:host", aad=valid_aad)
        except PermissionError as exc:
            assert "server peer is not UID 0" in str(exc)
        else:
            if os.getuid() != 0:
                raise AssertionError("Non-root server peer must be rejected by client")

    finally:
        server_running = False
        try:
            server.close()
        except OSError:
            pass
        th.join(timeout=1.0)
        shutil.rmtree(sock_dir, ignore_errors=True)


def test_production_safety_invariants() -> None:
    # Instantiating production paths when directories do not exist must fail closed
    blob_prod = HardenedAtomicFileBlobProvider(PRODUCTION_VAULT_ROOT)
    assert blob_prod.production_safe is False, "Unprovisioned production vault root must be production_safe=False"

    lease_prod = FlockSubjectLeaseProvider(PRODUCTION_LOCK_ROOT)
    assert lease_prod.production_safe is False, "Unprovisioned production lock root must be production_safe=False"

    crypto_prod = SystemdCredsEnvelopeCryptoProvider(PRODUCTION_CRYPTO_SOCKET)
    assert crypto_prod.production_safe is False, "Unprovisioned production crypto socket must be production_safe=False"


def self_test() -> None:
    test_blob_provider()
    test_lease_provider()
    test_ipc_framing_and_bounds()
    test_production_safety_invariants()
    print("production_providers_self_test=ok")


if __name__ == "__main__":
    self_test()
