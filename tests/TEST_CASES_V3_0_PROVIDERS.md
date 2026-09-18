# v3.0 Production Providers / External Crypto Regressions

## Test 241 — provider object-key confinement
`HardenedAtomicFileBlobProvider` accepts only canonical object keys matching `regulator-auth/v1/<64-lowercase-hex>.sealed`. Arbitrary relative paths, uppercase hex, directory prefixes, and unapproved extensions are rejected with `ValueError`.

## Test 242 — hardened atomic durability and fsync path
Blob replacement creates an unpredictable temporary file in the destination directory with mode `0600`, calls `fsync()` on the temporary file descriptor, performs an atomic `os.replace()`, and calls `fsync()` on the parent directory file descriptor. Partial writes are never observable.

## Test 243 — symlink and traversal rejection in durable vault
`HardenedAtomicFileBlobProvider` rejects reading, writing, or deleting files that are symbolic links or contain path traversal (`..` or absolute path prefixes). Filesystem resolution verifies `stat.S_ISREG` before performing operations.

## Test 244 — durable vault sealed blob size boundary
The durable blob provider enforces a strict maximum sealed ciphertext limit of `MAX_SEALED_BLOB_BYTES` (2 MiB). Payloads exceeding 2,097,152 bytes are rejected before write allocation.

## Test 245 — cross-process subject lease mutual exclusion
`FlockSubjectLeaseProvider` serializes concurrent operations for the same subject across separate worker processes using `fcntl.flock(LOCK_EX | LOCK_NB)`. A concurrent worker attempting to acquire the same subject lease blocks or raises `SubjectLeaseTimeout` after `wait_timeout_seconds`.

## Test 246 — automatic kernel lease release on process crash
When a process holding a subject lease is abruptly terminated (e.g., via `SIGKILL`), the Linux kernel automatically closes open file descriptors and releases associated `flock` locks. Successor processes immediately reacquire the lease without stale PID residue.

## Test 247 — independent subject lease concurrency
`FlockSubjectLeaseProvider` locks are scoped strictly per 64-hex subject key (`<subject_key>.lock`). Acquiring a lease for subject A does not block or serialize concurrent operations for independent subject B.

## Test 248 — subject lease monotonic timeout bounds
Lease acquisition polling respects monotonic deadlines derived from `wait_timeout_seconds`. The provider never blocks indefinitely and closes the open file descriptor on timeout or exception exit.

## Test 249 — canonical AAD syntax and derived credential name
The cryptographic boundary accepts only canonical AAD matching `b"openai-work-codex-regulator:v1:" + 64 lowercase hex bytes`. The helper internally and deterministically derives credential name `regulator-auth-v1-<64hex>`. Callers cannot supply or override the credential name.

## Test 250 — IPC magic framing and version negotiation
The AF_UNIX stream protocol enforces a 12-byte request header beginning with magic `b"REGC"`, protocol version `1`, operation code (SEAL=1, OPEN=2), exact 95-byte AAD length, and 4-byte payload length. Requests with invalid magic, version, or opcode are rejected fail-closed.

## Test 251 — crypto helper SO_PEERCRED application UID restriction
`CryptoHelperService` inspects peer credentials on every incoming socket connection using `SO_PEERCRED`. Connections from UID 0 (root) or any user other than the unprivileged `regulator` UID are rejected immediately with `STATUS_UNAUTHORIZED` and closed.

## Test 252 — crypto socket client SO_PEERCRED root verification
`SystemdCredsEnvelopeCryptoProvider` checks `SO_PEERCRED` on the client side immediately after connecting to the daemon socket. If the server peer is not UID 0 (root), the client refuses to transmit plaintext and raises `PermissionError`.

## Test 253 — asymmetric IPC request and response size bounds
The IPC framing enforces asymmetric bounds: SEAL requests accept plaintext up to `MAX_AUTH_BLOB_BYTES` (1 MiB) and expect responses up to `MAX_SEALED_BLOB_BYTES` (2 MiB). OPEN requests accept sealed ciphertext up to 2 MiB and expect responses up to 1 MiB. Lengths are validated before buffer allocation.

## Test 254 — IPC malformed request and truncated frame fail-closed
Malformed requests, truncated frames, or client disconnects cause the helper to close the socket and return generic error codes without process crash, resource leak, or unhandled exceptions.

## Test 255 — rejection of mismatched AAD and tampered ciphertext
Decryption requests with an AAD subject key different from the encryption AAD fail name authentication in `systemd-creds`. Tampered ciphertexts with single-bit corruption fail authenticated decryption without leaking details.

## Test 256 — ephemeral authorization plaintext cleanup
`SealedSubjectAuthStore` authorization sessions and materializations write plaintext `auth.json` only into ephemeral private directories (`0700`, mode `0600` files). On session exit or exception, the temporary directory is unlinked.

## Test 257 — absence of durable auth.json at rest
Durable storage contains only `.sealed` ciphertext blobs under `regulator-auth/v1/`. Plaintext tokens or `auth.json` files never exist in the durable vault root at rest.

## Test 258 — systemd-creds subprocess environment and argument immobility
The helper invokes `/usr/bin/systemd-creds` using direct argument arrays (`shell=False`, `close_fds=True`) with a minimal deterministic environment (`PATH=/usr/bin:/bin`, `LC_ALL=C`). Callers cannot supply CLI arguments or paths.

## Test 259 — production socket parent directory isolation and mode 0750
The production crypto socket lives in dedicated parent `/run/meciles-regulator-crypto/` owned by `root:regulator` mode `0750`. This prevents unprivileged users from substituting or unlinking the socket.

## Test 260 — production path invariants and fail-closed unprovisioned gates
`HardenedAtomicFileBlobProvider`, `FlockSubjectLeaseProvider`, and `SystemdCredsEnvelopeCryptoProvider` verify their respective production filesystem paths, ownership, and mode before declaring `production_safe=True`. Unprovisioned or temporary test directories evaluate strictly to `production_safe=False`.
