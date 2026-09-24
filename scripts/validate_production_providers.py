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


def test_crypto_helper_regressions() -> None:
    from deployment.crypto_helper import (
        CryptoHelperService,
        PRODUCTION_SOCKET,
        CLIENT_IO_TIMEOUT_SECONDS,
    )
    import pwd
    import inspect

    # Test 261: stat module import and validate_environment()
    import deployment.crypto_helper as helper_mod
    assert hasattr(helper_mod, "stat"), "stat module must be imported in crypto_helper"

    temp_dir = Path(tempfile.mkdtemp(prefix="regulator-test-helper-"))
    try:
        # Non-production instance validate_environment() is no-op
        ephemeral_sock = temp_dir / "test.sock"
        svc_nonprod = CryptoHelperService(socket_path=ephemeral_sock)
        svc_nonprod.validate_environment()

        # Test 262: client IO timeout bounds
        assert CLIENT_IO_TIMEOUT_SECONDS == 15.0, "CLIENT_IO_TIMEOUT_SECONDS must be 15.0"
        timeout_sock_path = temp_dir / "timeout.sock"
        timeout_svc = CryptoHelperService(
            socket_path=timeout_sock_path,
            client_timeout=0.2,
            allowed_uid_override=os.getuid(),
        )
        assert timeout_svc.client_timeout == 0.2

        # Test 263: CLI argument rejection
        cli_res = subprocess.run(
            [sys.executable, str(ROOT / "deployment" / "crypto_helper.py"), "--forbidden-cli-arg"],
            capture_output=True,
            text=True,
        )
        assert cli_res.returncode == 2, f"CLI with arguments must exit with code 2, got {cli_res.returncode}"
        assert "forbidden in production" in cli_res.stderr

        # Test 264: systemd-creds deterministic v257 command invocation & exactly-once execution
        handle_src = inspect.getsource(CryptoHelperService.handle_connection)
        assert "--no-ask-password" not in handle_src, "--no-ask-password must NOT be in crypto_helper"
        assert "cmd_compat" not in handle_src, "compatibility retry logic must NOT be in crypto_helper"
        assert "retry" not in handle_src.lower(), "retry logic must NOT be in crypto_helper"

        test_aad = AAD_PREFIX + (b"0" * 64)
        expected_name = f"regulator-auth-v1-{'0'*64}"
        test_svc = CryptoHelperService(socket_path=temp_dir / "exec_test.sock", allowed_uid_override=os.getuid())

        # Subprocess call 1: SEAL exact argv and exactly-once
        captured_calls: list[list[str]] = []
        def mock_seal_exec(cmd, **kwargs):
            captured_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout=b"SEALED_PAYLOAD", stderr=b"")

        orig_run = subprocess.run
        subprocess.run = mock_seal_exec
        try:
            c_sock, s_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            seal_req = struct.pack("!4sBBHI", IPC_MAGIC, IPC_VERSION, OP_SEAL, len(test_aad), 5) + test_aad + b"plain"
            c_sock.sendall(seal_req)
            test_svc.handle_connection(s_sock)
            c_sock.close()
            s_sock.close()
        finally:
            subprocess.run = orig_run

        assert len(captured_calls) == 1, f"SEAL must invoke systemd-creds exactly once, got {len(captured_calls)}"
        from deployment.crypto_helper import SYSTEMD_CREDS_PATH
        expected_seal_cmd = [
            SYSTEMD_CREDS_PATH,
            "encrypt",
            "--with-key=host",
            f"--name={expected_name}",
            "-",
            "-",
        ]
        assert captured_calls[0] == expected_seal_cmd, f"SEAL argv mismatch: {captured_calls[0]} != {expected_seal_cmd}"

        # Subprocess call 2: OPEN exact argv and exactly-once
        captured_calls.clear()
        def mock_open_exec(cmd, **kwargs):
            captured_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout=b"PLAIN_PAYLOAD", stderr=b"")

        subprocess.run = mock_open_exec
        try:
            c_sock, s_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            open_req = struct.pack("!4sBBHI", IPC_MAGIC, IPC_VERSION, OP_OPEN, len(test_aad), 6) + test_aad + b"sealed"
            c_sock.sendall(open_req)
            test_svc.handle_connection(s_sock)
            c_sock.close()
            s_sock.close()
        finally:
            subprocess.run = orig_run

        assert len(captured_calls) == 1, f"OPEN must invoke systemd-creds exactly once, got {len(captured_calls)}"
        expected_open_cmd = [
            SYSTEMD_CREDS_PATH,
            "decrypt",
            f"--name={expected_name}",
            "-",
            "-",
        ]
        assert captured_calls[0] == expected_open_cmd, f"OPEN argv mismatch: {captured_calls[0]} != {expected_open_cmd}"

        # Subprocess call 3: Failure must not retry
        captured_calls.clear()
        def mock_fail_exec(cmd, **kwargs):
            captured_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"crypto error")

        subprocess.run = mock_fail_exec
        try:
            c_sock, s_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            seal_req = struct.pack("!4sBBHI", IPC_MAGIC, IPC_VERSION, OP_SEAL, len(test_aad), 5) + test_aad + b"plain"
            c_sock.sendall(seal_req)
            test_svc.handle_connection(s_sock)
            fail_resp = c_sock.recv(1024)
            c_sock.close()
            s_sock.close()
        finally:
            subprocess.run = orig_run

        assert len(captured_calls) == 1, f"Failed execution must NOT retry: {len(captured_calls)}"
        _, fail_st, _ = struct.unpack("!4sBI", fail_resp[:9])
        assert fail_st == STATUS_CRYPTO_ERROR

        # Subprocess call 4: Timeout must not retry
        captured_calls.clear()
        def mock_timeout_exec(cmd, **kwargs):
            captured_calls.append(list(cmd))
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=10.0)

        subprocess.run = mock_timeout_exec
        try:
            c_sock, s_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            seal_req = struct.pack("!4sBBHI", IPC_MAGIC, IPC_VERSION, OP_SEAL, len(test_aad), 5) + test_aad + b"plain"
            c_sock.sendall(seal_req)
            test_svc.handle_connection(s_sock)
            timeout_resp = c_sock.recv(1024)
            c_sock.close()
            s_sock.close()
        finally:
            subprocess.run = orig_run

        assert len(captured_calls) == 1, f"Timed out execution must NOT retry: {len(captured_calls)}"
        _, timeout_st, _ = struct.unpack("!4sBI", timeout_resp[:9])
        assert timeout_st == STATUS_CRYPTO_ERROR

        # Test 265: production regulator identity resolution fail-closed
        orig_getpwnam = pwd.getpwnam
        try:
            def mock_missing_regulator(name: str):
                if name == "regulator":
                    raise KeyError("mock missing user")
                return orig_getpwnam(name)

            pwd.getpwnam = mock_missing_regulator
            try:
                CryptoHelperService(socket_path=PRODUCTION_SOCKET)
                raise AssertionError("Production helper must fail closed when user 'regulator' is missing")
            except RuntimeError as exc:
                assert "User 'regulator' not found" in str(exc)
        finally:
            pwd.getpwnam = orig_getpwnam

        # Test 266: production socket permission enforcement fail-closed
        orig_chown = os.chown
        try:
            def mock_failing_chown(path, uid, gid):
                raise OSError(1, "Operation not permitted")

            os.chown = mock_failing_chown
            fake_prod_sock = temp_dir / "fake_prod.sock"
            svc_perm = CryptoHelperService(socket_path=fake_prod_sock, allowed_uid_override=os.getuid())
            svc_perm.is_production = True
            svc_perm.validate_environment = lambda: None
            try:
                svc_perm.run()
                raise AssertionError("chown failure in production must raise RuntimeError")
            except RuntimeError as exc:
                assert "Failed to set production socket permissions" in str(exc)
        finally:
            os.chown = orig_chown

        # Test 267: safe startup pre-existing socket cleanup with lstat validation
        fake_prod_existing = temp_dir / "existing_file.sock"
        fake_prod_existing.write_text("regular file masquerading as socket")
        svc_startup = CryptoHelperService(socket_path=fake_prod_existing, allowed_uid_override=os.getuid())
        svc_startup.is_production = True
        svc_startup.validate_environment = lambda: None
        try:
            svc_startup.run()
            raise AssertionError("Pre-existing non-socket in production must raise RuntimeError")
        except RuntimeError as exc:
            assert "not a socket" in str(exc)
        assert fake_prod_existing.is_file(), "Unsafe startup must NOT unlink non-socket file"

        # Test 268: safe shutdown socket cleanup with device and inode verification
        fake_prod_shutdown = temp_dir / "shutdown.sock"
        svc_shutdown = CryptoHelperService(socket_path=fake_prod_shutdown, allowed_uid_override=os.getuid())
        th = threading.Thread(target=svc_shutdown.run, daemon=True)
        th.start()
        for _ in range(50):
            if fake_prod_shutdown.exists():
                break
            time.sleep(0.02)
        assert fake_prod_shutdown.exists(), "Shutdown test socket was not created"

        orig_inode = svc_shutdown._socket_inode
        assert orig_inode is not None
        fake_prod_shutdown.unlink()
        fake_prod_shutdown.write_text("tampered replacement")
        tampered_st = os.lstat(fake_prod_shutdown)
        assert (tampered_st.st_dev, tampered_st.st_ino) != orig_inode

        svc_shutdown.running = False
        th.join(timeout=2.0)
        assert fake_prod_shutdown.exists(), "Replaced socket must NOT be unlinked on shutdown"

        # Test 269: constructor allowed_uid_override isolation from production mode
        try:
            CryptoHelperService(socket_path=PRODUCTION_SOCKET, allowed_uid_override=1000)
            raise AssertionError("allowed_uid_override must be rejected in production mode")
        except ValueError as exc:
            assert "allowed_uid_override is strictly forbidden in production mode" in str(exc)

        custom_uid = 4321
        svc_custom = CryptoHelperService(socket_path=temp_dir / "custom.sock", allowed_uid_override=custom_uid)
        assert svc_custom.allowed_uid == custom_uid

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def self_test() -> None:
    test_blob_provider()
    test_lease_provider()
    test_ipc_framing_and_bounds()
    test_production_safety_invariants()
    test_crypto_helper_regressions()
    print("production_providers_self_test=ok")


if __name__ == "__main__":
    self_test()
