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
