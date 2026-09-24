# v3.0 Plugin isolation regression additions

## Test 161 — raw subject never becomes a filesystem path
**Input:** authenticated Plugin subject contains email-like text, slashes and `..`.  
**Expected:** backend derives a fixed opaque HMAC subject key; raw subject text is absent from the auth-context path.

## Test 162 — subject-key pepper has a minimum strength
**Input:** subject store is initialized with a short server pepper.  
**Expected:** initialization fails closed; weak pepper is not accepted for deterministic subject-key derivation.

## Test 163 — subject directories are isolated
**Input:** subject A and subject B both have backend auth contexts.  
**Expected:** they resolve to distinct opaque directories and cannot address each other's state through caller-controlled paths.

## Test 164 — revoke is scoped to one subject
**Input:** both A and B have auth state; A is revoked.  
**Expected:** only A's auth context is removed; B remains intact and readable by B's trusted context.

## Test 165 — unbound subject requires authorization
**Input:** authenticated Plugin subject has no backend auth context.  
**Expected:** quota service returns `AuthorizationRequired`; it never creates a successful zero-usage result.

## Test 166 — model arguments cannot override subject
**Input:** model calls `get_quota_snapshot` with `subject`, `email`, `account_id` or token-like argument.  
**Expected:** call is rejected because canonical tool accepts `{}` only; trusted transport identity remains authoritative.

## Test 167 — subject key is never model-visible
**Input:** successful quota read uses an opaque internal subject key and Codex auth directory.  
**Expected:** neither subject key nor backend path appears in normalized tool output.

## Test 168 — cross-subject auth reuse fails
**Input:** subject A is authorized while subject B is not.  
**Expected:** B cannot reuse A's backend session and receives authorization-required state.

## Test 169 — development auth store is explicitly not production-safe
**Input:** release configuration attempts to treat `EphemeralSubjectAuthStore` as a production credential vault.  
**Expected:** architecture/release gate rejects the assumption; ephemeral store makes no encryption-at-rest or persistence guarantee.

## Test 170 — credential-vault adapter stays outside model surface
**Input:** production later injects a KMS/secret-backed `SubjectAuthStore`.  
**Expected:** vault identifiers, encryption keys and credential paths remain server-side implementation details; `get_quota_snapshot()` schema does not change.

## Test 171 — duplicate Connect reuses one pending authorization
**Input:** the same authenticated Plugin subject calls authorization begin twice before completing the first device-code flow.  
**Expected:** coordinator returns the same pending authorization id/challenge; it does not launch a second `codex app-server` session.

## Test 172 — authorization ids are subject-bound server-side
**Input:** subject B presents subject A's opaque authorization id to status/cancel.  
**Expected:** fail closed with the same not-found result used for unknown ids; no existence oracle or challenge details leak across subjects.

## Test 173 — model-facing quota tool remains separate from Connect/Auth
**Input:** authorization coordinator exists in the Plugin backend.  
**Expected:** `get_quota_snapshot()` input schema stays `{}` and exposes no begin/status/cancel/revoke parameters or generic auth RPC.

## Test 174 — authorization success seals only after authenticated readiness
**Input:** user completes device-code login and official Codex reaches authenticated account state.  
**Expected:** successful authorization exits the temporary session, validates `auth.json`, seals it, deletes plaintext temp state, then marks the session `AUTHORIZED`.

## Test 175 — cancelled authorization cannot persist credentials
**Input:** a pending authorization is cancelled before completion.  
**Expected:** live client is stopped, worker finishes as `CANCELLED`, exceptional authorization-session exit stores no auth blob, and no later worker action can resurrect credentials.

## Test 176 — revoke waits for active authorization worker
**Input:** revoke arrives while the same subject still has a live authorization worker.  
**Expected:** coordinator cancels and waits for worker termination before deleting durable auth; if the worker cannot stop within the bound, revoke fails as busy rather than racing with a late reseal.

## Test 177 — public authorization status contains no raw subject or vault identity
**Input:** transport polls begin/status for a pending or terminal authorization.  
**Expected:** response contains opaque authorization id, bounded state, verification URL/user code when applicable, expiry and bounded error code only; no subject key, raw identity, vault object name or credential path.

## Test 178 — production durable blob keys accept only opaque subject keys
**Input:** vault adapter receives a caller-controlled string containing `/`, `..`, email text or other non-hex data.  
**Expected:** reject it; production object names are derived only from validated 64-character lowercase hex subject keys.

## Test 179 — unsafe storage or crypto provider cannot pass production gate
**Input:** durable-store or envelope-crypto provider reports `production_safe=False`.  
**Expected:** `build_production_auth_store()` fails closed; repository test doubles cannot be promoted to production by configuration alone.

## Test 180 — repository implements no production cryptographic primitive
**Input:** review production vault adapter.  
**Expected:** encryption/decryption is delegated to an injected audited external KMS/envelope provider with declared key reference and algorithm id; repository code only enforces binding, object-key validation and lifecycle contracts.
