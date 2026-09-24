# v3.0 regression additions

## Test 116 — ChatGPT Web is the only skill runtime
**Input:** v3.0 ZIP is attached in ChatGPT Web and a task later routes to Work or Codex.  
**Expected:** `SKILL_RUNTIME=CHATGPT_WEB_ONLY`; ChatGPT owns the regulator and downstream executors receive self-contained packets without loading the skill.

## Test 117 — no standalone Work/Codex skill mode
**Input:** a handoff is prepared for Work or Codex.  
**Expected:** no instruction asks the executor to invoke/load/read/follow the regulator; `EXECUTOR_SKILL_REQUIRED=NO`.

## Test 118 — ZIP bootstrap ends user setup
**Input:** ordinary user attaches the release ZIP in ChatGPT Web.  
**Expected:** normal skill bootstrap requires no Terminal, desktop app, local daemon, Homebrew, CodexBar, localhost, tunnel or OS-specific configuration.

## Test 119 — Plugin auth is just in time
**Input:** Plugin is not connected but current work is ordinary Chat planning with no quota-sensitive decision.  
**Expected:** do not interrupt the user with authorization; `PLUGIN_AUTH=JUST_IN_TIME`.

## Test 120 — quota-sensitive decision triggers Plugin path
**Input:** next Work/Codex pass needs current allowance and Plugin is not connected.  
**Expected:** ChatGPT surfaces supported Connect/Auth rather than asking for recurring manual quota bookkeeping.

## Test 121 — connected Plugin reads automatically
**Input:** quota-sensitive decision occurs and Regulator Quota Plugin is already connected.  
**Expected:** ChatGPT calls `get_quota_snapshot()` automatically before admission.

## Test 122 — quota tool has zero model identity arguments
**Input:** inspect canonical `get_quota_snapshot` contract.  
**Expected:** input schema has no email, account id, installation id, workspace id, token or arbitrary properties.

## Test 123 — Plugin is read-only
**Input:** inspect model-callable Plugin surface.  
**Expected:** no credit purchase, paid reset, spending mutation, generic Codex RPC, shell or account-mutation tool is exposed.

## Test 124 — Plugin has no admission authority
**Input:** fresh quota snapshot is returned.  
**Expected:** Plugin returns facts only; ChatGPT regulator alone computes routing/model/admission/pace decisions.

## Test 125 — Chat may not assume localhost
**Input:** user happens to have Codex/CodexBar installed locally.  
**Expected:** ChatGPT Web never assumes shell/local-file/`127.0.0.1` access and does not make local software a prerequisite.

## Test 126 — no OS-specific production dependency
**Input:** same skill is used from Windows, macOS or Linux browser.  
**Expected:** product contract is unchanged because quota acquisition is server-side; `OS_DEPENDENCY=NO`.

## Test 127 — official Codex server-side source
**Input:** authenticated backend needs exact Work/Codex quota.  
**Expected:** supported backend path uses official `codex app-server` account rate-limit read and normalizes its result.

## Test 128 — login completion alone is not auth readiness
**Input:** `account/login/completed(success=true)` arrives before managed auth reload.  
**Expected:** backend does not immediately read rate limits; it waits for authenticated `account/updated`.

## Test 129 — account updated unlocks rate-limit read
**Input:** successful login completion is followed by `account/updated` with non-null auth mode.  
**Expected:** backend may call `account/rateLimits/read`.

## Test 130 — unauthenticated rate-limit read fails closed
**Input:** app-server has no active account auth.  
**Expected:** backend returns authorization-required/unavailable state, never a zero-usage snapshot.

## Test 131 — prefer codex bucket
**Input:** `rateLimitsByLimitId` contains both `base_model_inference` and `codex`.  
**Expected:** Work/Codex quota normalization selects `codex`, not another product bucket.

## Test 132 — weekly window classification
**Input:** a rate window reports `windowDurationMins=10080`.  
**Expected:** classify as `WEEKLY` regardless of `primary`/`secondary` position.

## Test 133 — five-hour window classification
**Input:** a rate window reports `windowDurationMins=300`.  
**Expected:** classify as `FIVE_HOUR` regardless of field position.

## Test 134 — unknown window remains other
**Input:** a rate window reports 43200 minutes.  
**Expected:** preserve as `OTHER_WINDOW`; never reinterpret it as weekly or 5h.

## Test 135 — missing five-hour window remains unavailable
**Input:** exact source contains a weekly window but no 300-minute window.  
**Expected:** `FIVE_HOUR_USED/FIVE_HOUR_RESET=unknown|null`; never synthesize 0%.

## Test 136 — missing weekly window remains unavailable
**Input:** source contains no 10080-minute window.  
**Expected:** weekly fields remain unknown/null; controller does not infer a fresh week.

## Test 137 — field position is not semantics
**Input:** weekly is `primary` and 5h is `secondary`, then positions reverse in another payload.  
**Expected:** both normalize identically by duration; `RATE_WINDOW_POSITION_IS_NOT_SEMANTICS`.

## Test 138 — no secrets in model snapshot
**Input:** backend auth state internally contains OAuth/access/refresh material.  
**Expected:** normalized output contains no token, cookie, Authorization header, raw auth file, password or credential-store id.

## Test 139 — raw provider response is not model output
**Input:** upstream response includes extra account/provider fields outside allow-list.  
**Expected:** tool emits normalized schema only; unknown raw fields do not leak through.

## Test 140 — subject identity resolved server-side
**Input:** connected ChatGPT Plugin invokes quota tool.  
**Expected:** authenticated Plugin context resolves subject/account server-side; model cannot choose another identity via arguments.

## Test 141 — cross-subject read is forbidden
**Input:** subject A attempts to address subject B's quota state.  
**Expected:** fail closed; no cross-user snapshot is returned.

## Test 142 — silent account switch is forbidden
**Input:** backend observes a different account/workspace than the bound authorization.  
**Expected:** report binding conflict and require explicit reauthorization; do not silently switch.

## Test 143 — credential isolation is release gate
**Input:** quota acquisition works but per-subject credential isolation has not been audited.  
**Expected:** branch remains development-only; technical P0 success is insufficient for release.

## Test 144 — token refresh is release gate
**Input:** access credential expires.  
**Expected:** production design must have tested refresh/re-auth behavior; no repeated manual quota copy/paste fallback as normal UX.

## Test 145 — revoke/logout invalidates backend session
**Input:** user disconnects/revokes authorization.  
**Expected:** subsequent quota read requires authorization and cannot continue using stale credentials.

## Test 146 — stale snapshot is recomputed as stale
**Input:** a previously fresh snapshot ages beyond policy threshold.  
**Expected:** report `STALE`; old `FRESH` label cannot survive indefinitely.

## Test 147 — automatic refresh before agentic pass
**Input:** meaningful Work/Codex pass is about to launch and current snapshot is stale/absent.  
**Expected:** attempt fresh `get_quota_snapshot()` before quota-sensitive admission.

## Test 148 — automatic refresh after meaningful pass
**Input:** meaningful Work/Codex execution completes.  
**Expected:** refresh meter when available to observe aggregate movement and reset state.

## Test 149 — unchanged post-pass meter remains pending
**Input:** immediate fresh read matches pre-pass aggregate meter while reporting may lag.  
**Expected:** do not infer zero burn; `PENDING_BURN=YES`.

## Test 150 — later meter movement resolves pending burn
**Input:** later fresh snapshot in same epoch advances after Test 149.  
**Expected:** compatible aggregate delta may become observed burn sample and pending state may clear.

## Test 151 — reset creates new quota epoch
**Input:** confirmed reset or material reset-boundary change appears in fresh telemetry.  
**Expected:** invalidate old anchor and create new `QUOTA_EPOCH_ID` before further controller math.

## Test 152 — automatic telemetry unavailable does not halt Chat
**Input:** Plugin/source is unavailable while useful non-agentic Chat work remains.  
**Expected:** continue planning/review/handoff; do not stop project merely because quota telemetry is temporarily unavailable.

## Test 153 — manual snapshot is last fallback
**Input:** automatic telemetry remains unavailable and next quota-sensitive pass cannot be admitted safely.  
**Expected:** only then request a first-party manual snapshot; `MANUAL_QUOTA_INPUT=FALLBACK_ONLY`.

## Test 154 — v2.2 controller remains authoritative
**Input:** Plugin returns normalized fresh meter state.  
**Expected:** epoch trajectory, burn estimator, quality floor, 5h breaker and balanced quota/pace controller remain the admission engine.

## Test 155 — quality floor cannot be bypassed by fresh quota
**Input:** quota has headroom but selected plan/model would miss required tests/sources/security.  
**Expected:** `QUALITY_FLOOR=NON_NEGOTIABLE`; do not launch insufficient execution.

## Test 156 — Plugin cannot spend money
**Input:** snapshot reports credits or paid reset eligibility.  
**Expected:** telemetry path remains read-only; any purchase/reset is a separate explicitly authorized class-4 action outside quota Plugin surface.

## Test 157 — executor packet contains no Plugin plumbing
**Input:** ChatGPT sends a normal Work/Codex handoff.  
**Expected:** no quota tool, credential, source, trajectory headroom or internal risk fields are copied into the executor packet.

## Test 158 — P0 proof is not production auth design
**Input:** ephemeral server-side Plus quota P0 passes.  
**Expected:** record acquisition as proven while keeping persistent credential lifecycle and ChatGPT Web Plugin E2E as open release gates.

## Test 159 — deterministic backend self-test is credential-free
**Input:** CI runs `python3 plugin/quota_backend.py --self-test`.  
**Expected:** tests normalization and secret exclusion without network or user credentials.

## Test 160 — release requires real ChatGPT Web E2E
**Input:** unit/regression tests are green but no production Connect/Auth → quota read → controller flow has passed.  
**Expected:** v3.0 remains development-only; PR/merge waits for E2E, cross-subject isolation, credential refresh/revoke and security review.
