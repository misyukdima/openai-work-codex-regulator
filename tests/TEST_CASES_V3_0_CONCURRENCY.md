# v3.0 concurrency and crash-safety regression additions

## Test 181 — same-subject quota operations serialize
**Input:** two quota reads for the same authenticated subject overlap.  
**Expected:** only one operation materializes that subject's sealed `auth.json` at a time; the second waits for the subject lease.

## Test 182 — concurrent refresh cannot lose the newer auth state
**Input:** two same-subject operations both need official Codex token refresh.  
**Expected:** operations are serialized so the second reads the first operation's resealed result; stale auth state cannot overwrite a newer refresh.

## Test 183 — revoke waits for an active materialized read
**Input:** revoke starts while a same-subject quota operation still owns the lease.  
**Expected:** revoke waits for the operation to finish, then deletes the sealed blob; it never deletes mid-operation and allows a late reseal to resurrect credentials.

## Test 184 — different subjects do not share one global lock
**Input:** subject A has a long quota operation while subject B reads quota.  
**Expected:** B can acquire its own subject lease independently; serialization scope is one opaque subject key, not the whole Plugin backend.

## Test 185 — in-process locking is not a production lease
**Input:** deployment uses `InProcessSubjectLeaseProvider`.  
**Expected:** `production_safe=False`; it is valid for CI/single-worker P1 only and cannot satisfy multi-replica release requirements.

## Test 186 — production requires cross-worker subject serialization
**Input:** storage and crypto providers are audited but no production-safe cross-worker lease provider is configured.  
**Expected:** production auth-store construction fails closed.

## Test 187 — durable sealed-blob replacement must be atomic
**Input:** external durable storage cannot guarantee atomic object replacement.  
**Expected:** `DurableSealedBlobStore.production_safe=False`; partial/corrupt replacement cannot be accepted as a production credential backend.

## Test 188 — lease timeout fails closed
**Input:** same-subject operation cannot acquire its lease within the bounded wait.  
**Expected:** raise a lease-timeout/busy error; never fall back to an unprotected read or write.

## Test 189 — authorization and quota read use the same subject lock domain
**Input:** a quota read races with an authorization/re-authorization flow for the same subject.  
**Expected:** both operations serialize on the same derived opaque subject key so quota cannot read a half-replaced authorization state.

## Test 190 — multi-replica authorization remains an explicit deployment gate
**Input:** core unit tests pass but production runs multiple backend replicas without audited pinned-session routing/lease semantics for the live device-code process.  
**Expected:** v3.0 remains development-only; a live authorization process may not be treated as stateless merely because sealed storage is shared.
