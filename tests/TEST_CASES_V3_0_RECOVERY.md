# v3.0 auth recovery regression additions

## Test 191 — missing durable auth requires reconnect
**Input:** trusted Plugin subject has no sealed authorization state when quota is requested.  
**Expected:** recovery maps the failure to `NEEDS_REAUTH/AUTH_MISSING`; it never returns a zero-usage snapshot.

## Test 192 — corrupt sealed auth requires reconnect
**Input:** the sealed auth blob fails validation or subject-bound open.  
**Expected:** fail closed as `NEEDS_REAUTH/AUTH_CORRUPT`; no stale/manual-looking quota is synthesized.

## Test 193 — upstream authentication rejection is public-safe
**Input:** official Codex quota read reports an authentication-required/unauthorized condition.  
**Expected:** map to bounded `NEEDS_REAUTH/AUTH_REJECTED`; raw provider error text is not exposed to the model-facing caller.

## Test 194 — transient transport failure gets one bounded retry
**Input:** first quota read times out and the second attempt succeeds.  
**Expected:** retry once and return the fresh second result; retry count is not open-ended.

## Test 195 — repeated transient failure becomes unavailable
**Input:** both the initial quota read and one permitted retry time out.  
**Expected:** return `UPSTREAM_TIMEOUT_RETRY_EXHAUSTED`/temporarily unavailable; do not loop or fall back to old quota.

## Test 196 — failed materialization does not reseal partial auth state
**Input:** official Codex changes temporary `auth.json`, then the operation raises before successful context exit.  
**Expected:** temporary plaintext is removed and the prior durable sealed blob remains authoritative; the partial update is not resealed as a successful credential state.

## Test 197 — reconnect is not a model-facing quota operation
**Input:** quota recovery reports `NEEDS_REAUTH`.  
**Expected:** canonical `get_quota_snapshot()` schema remains zero-argument/read-only; reconnect is performed only by trusted Plugin transport through authorization coordinator actions.

## Test 198 — trusted reconnect replaces stale auth deliberately
**Input:** trusted user-facing Connect/Auth flow is invoked after `AUTH_REJECTED`.  
**Expected:** transport revokes stale subject auth, then starts a new subject-bound authorization flow; no silent account switch or automatic destructive reconnect occurs inside quota read.

## Test 199 — unknown backend failure is not guessed retryable
**Input:** backend raises an unclassified internal failure.  
**Expected:** fail as bounded `BACKEND_FAILURE` without provider details and without an automatic retry that could duplicate unknown side effects.

## Test 200 — remote refresh crash can legitimately require reauthorization
**Input:** upstream rotates auth state but the worker crashes before the refreshed `auth.json` is durably resealed.  
**Expected:** provider-neutral v3 does not claim lossless recovery; a later rejected durable state may require explicit reconnect. Real refresh/crash/reconnect E2E remains a release gate.
