# v3.0 regression additions

## Test 116 — ChatGPT-first automatic quota refresh
**Input:** regulator runs in ChatGPT and a quota-sensitive Work/Codex pass is about to be admitted; a supported quota tool is connected.  
**Expected:** Chat refreshes telemetry automatically before admission; user is not asked to open Usage or resend percentages.

## Test 117 — manual quota is fallback only
**Input:** automatic telemetry returns a fresh weekly/5h snapshot.  
**Expected:** `AUTO_QUOTA_TELEMETRY=DEFAULT`; manual quota input is not required.

## Test 118 — automatic telemetry unavailable
**Input:** quota tool is unavailable while useful non-agentic Chat planning remains possible.  
**Expected:** continue productive Chat work; request a manual first-party snapshot only if a quota-sensitive decision later cannot be made safely.

## Test 119 — Chat may not assume localhost access
**Input:** regulator runs in browser/cloud ChatGPT while CodexBar is installed on the user's Mac.  
**Expected:** `CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN`; Chat does not pretend it can execute local CLI or read `127.0.0.1` directly.

## Test 120 — connected quota tool bridges local telemetry
**Input:** local sensor publishes a sanitized snapshot to a Chat-accessible connected app/tool.  
**Expected:** Chat uses `get_quota_snapshot()` as telemetry input while all admission/routing decisions remain in the regulator control plane.

## Test 121 — CodexBar primary/secondary position is not semantic
**Input:** CodexBar reports weekly window as `primary` and 5h window as `secondary`.  
**Expected:** classify by duration; weekly and 5h values are normalized correctly.

## Test 122 — five-hour window classification
**Input:** reported window duration is 300 minutes.  
**Expected:** classify as `FIVE_HOUR` regardless of field position.

## Test 123 — weekly window classification
**Input:** reported window duration is 10080 minutes.  
**Expected:** classify as `WEEKLY` regardless of field position.

## Test 124 — unknown 30-day window is not misclassified
**Input:** Codex telemetry contains a 43200-minute window with no weekly window.  
**Expected:** preserve it as `OTHER_WINDOW`; `WEEKLY_USED=unknown`, never reinterpret it as 5h or weekly.

## Test 125 — stale machine snapshot
**Input:** quota telemetry timestamp exceeds the configured freshness threshold.  
**Expected:** `QUOTA_TELEMETRY_STATE=STALE`; refresh before a large class 2–4 pass rather than treating stale values as current.

## Test 126 — post-pass unchanged meter remains pending
**Input:** meaningful Work/Codex pass completes and immediate fresh read shows the same aggregate meter while reporting may lag.  
**Expected:** do not infer zero burn; preserve `PENDING_BURN=YES`.

## Test 127 — later meter movement resolves pending burn
**Input:** a later snapshot in the same quota epoch advances after Test 126.  
**Expected:** aggregate delta may become an observed burn sample under existing compatibility/attribution rules; `PENDING_BURN` can clear.

## Test 128 — reset invalidates old trajectory
**Input:** automatic telemetry detects a confirmed reset or materially changed reset boundary.  
**Expected:** create a new quota epoch and re-anchor; never mix pre-reset anchor values with post-reset usage.

## Test 129 — telemetry cannot buy capacity
**Input:** local sensor or connected quota tool can read credits/reset eligibility.  
**Expected:** telemetry path remains read-only; it cannot buy credits, trigger a paid reset or mutate spending controls.

## Test 130 — telemetry provider is not an admission controller
**Input:** CodexBar or another provider exposes its own pacing/guard recommendation.  
**Expected:** ignore provider admission policy; only normalized meter/reset telemetry enters the regulator's v2.2 decision engine.

## Test 131 — no secrets in telemetry snapshot
**Input:** local provider has OAuth tokens, cookies and account credentials available internally.  
**Expected:** normalized snapshot contains no token/cookie/auth material and no raw auth file content.

## Test 132 — direct Codex standalone telemetry
**Input:** regulator is invoked directly inside local Codex with shell/tool access.  
**Expected:** `ORCHESTRATION_MODE=CODEX_STANDALONE`; local adapter may provide the same normalized snapshot without requiring ChatGPT or the remote bridge.

## Test 133 — Work standalone remains supported
**Input:** user invokes the regulator directly in Work and a supported connected quota tool is available.  
**Expected:** Work may own the local control plane for that pass and use automatic normalized telemetry; ChatGPT-first remains the preferred default, not a hard dependency.

## Test 134 — zero-friction onboarding requirement
**Input:** ordinary nontechnical user installs the final v3.0 product.  
**Expected:** normal setup does not require Terminal, Homebrew, manual CodexBar setup, JSON/YAML editing, token copy/paste, localhost/tunnel configuration or periodic quota messages.

## Test 135 — v2.2 controller remains mathematically authoritative
**Input:** automatic telemetry produces normalized weekly used/reset and 5h state.  
**Expected:** existing epoch-anchored trajectory, burn estimator, quality floor, 5h breaker and balanced quota/pace admission remain the decision engine; telemetry acquisition does not reimplement quota math.

## Test 136 — Companion discovers bundled sensor before user setup
**Input:** Companion bundle contains a compatible CodexBar helper and no system-wide CodexBar install exists.  
**Expected:** Companion can use the bundled helper; separate CodexBar installation is not a user prerequisite.

## Test 137 — explicit read-only CodexBar usage mode
**Input:** Companion invokes the CodexBar reference sensor.  
**Expected:** it requests Codex usage through explicit OAuth/read-only telemetry mode and does not invoke provider guard/admission or credit/reset actions.

## Test 138 — Companion strips credential-like data
**Input:** sensor internally has access to OAuth/account state.  
**Expected:** Companion→relay envelope contains only the normalized quota schema and no tokens, cookies, auth-file content or unnecessary account identity.

## Test 139 — production relay requires HTTPS
**Input:** Companion is configured with `http://127.0.0.1` or another plaintext relay URL for the Chat path.  
**Expected:** reject it as `INSECURE_RELAY`; ordinary Chat must not rely on localhost or plaintext transport.

## Test 140 — device and Chat reader credentials are separate
**Input:** relay provisions one installation.  
**Expected:** device-write token and Chat-reader token are distinct; a device token cannot read the Chat-facing snapshot.

## Test 141 — relay stores credential hashes only
**Input:** relay persists installation credentials.  
**Expected:** raw device/reader credentials are not stored in the relay database.

## Test 142 — relay rejects unexpected snapshot fields
**Input:** Companion tries to upload an extra `oauth_token`, `cookie`, password or other field outside the normalized contract.  
**Expected:** relay rejects the payload instead of storing or forwarding it.

## Test 143 — relay is telemetry cache, not controller
**Input:** a fresh snapshot is available remotely.  
**Expected:** relay returns telemetry/freshness only; it does not calculate `LAUNCH_BASE`, model tier, pace risk or future advance.

## Test 144 — Chat tool has zero model-provided identity arguments
**Input:** ChatGPT calls the canonical quota tool.  
**Expected:** `get_quota_snapshot()` takes no installation id, email, token or account selector from the model; authenticated app identity resolves the installation server-side.

## Test 145 — Chat tool is read-only
**Input:** tool contract is inspected.  
**Expected:** there is no credit purchase, paid reset, spending-control mutation, provider guard or generic write action in the quota tool surface.

## Test 146 — remote Chat path is primary
**Input:** browser/cloud ChatGPT is the regulator control plane.  
**Expected:** normal telemetry path is authenticated remote app/relay; local MCP/tunnel support may be optional but is not required for ordinary onboarding.

## Test 147 — local standalone path avoids unnecessary relay
**Input:** regulator runs directly in local Codex with a working local sensor.  
**Expected:** it may read the normalized local snapshot directly; remote relay is not a mandatory detour for standalone mode.

## Test 148 — relay recomputes freshness
**Input:** Companion uploaded a snapshot that later becomes old while no new upload arrives.  
**Expected:** Chat-facing relay read reports stale age based on captured/received time; old `FRESH` text from the original payload cannot keep it fresh indefinitely.

## Test 149 — source-only stack is not release-ready UX
**Input:** Companion/relay reference code passes CI but no novice-friendly packaged Companion and authenticated Chat app path exist yet.  
**Expected:** v3.0 remains development-only; passing core tests alone does not satisfy `ZERO_MAINTENANCE_USER_SETUP=REQUIRED`.

## Test 150 — user stays out of quota bookkeeping
**Input:** packaged Companion and Chat app are healthy during normal work.  
**Expected:** user states goals and approvals only; periodic quota copying/pasting is not part of the normal orchestration loop.

## Test 151 — pairing begins without copy/paste secret
**Input:** Companion starts pairing with the relay.  
**Expected:** relay returns an opaque pairing verifier directly to Companion and a browser `connect_url` containing only the non-secret pairing id; user is not shown a token to copy.

## Test 152 — pairing connect URL is HTTPS
**Input:** pairing is started with a plaintext connect base URL.  
**Expected:** reject with `INSECURE_CONNECT_URL`; production browser pairing requires HTTPS.

## Test 153 — pairing verifier is hash-only at rest
**Input:** relay stores a pending pairing.  
**Expected:** raw pairing verifier is not persisted; only a salted hash is stored.

## Test 154 — browser claim requires authenticated subject
**Input:** pairing claim arrives without an authenticated app/web subject identity.  
**Expected:** reject it; pairing id alone is not authorization to bind an installation.

## Test 155 — pairing claim binds server-side identity
**Input:** authenticated user opens the connect URL and approves the pending pairing.  
**Expected:** relay binds that server-side subject to the installation and marks pairing `CLAIMED`.

## Test 156 — Companion polls with verifier
**Input:** Companion checks pairing state before and after browser approval.  
**Expected:** correct verifier returns `PENDING` then `CLAIMED`; wrong verifier returns `PAIRING_UNAUTHORIZED`.

## Test 157 — expired pairing fails closed
**Input:** pending pairing exceeds its bounded TTL before approval.  
**Expected:** claim/status cannot silently reactivate the pairing; a new pairing flow is required.

## Test 158 — one subject cannot steal another claimed pairing
**Input:** a second authenticated subject attempts to claim an already claimed pairing.  
**Expected:** fail closed with `PAIRING_ALREADY_CLAIMED` or equivalent; existing binding is preserved.

## Test 159 — Chat tool resolves installation from auth context
**Input:** connected ChatGPT app calls `get_quota_snapshot()` for its authenticated subject.  
**Expected:** server resolves subject→installation internally; no installation id or pairing verifier is exposed to model arguments.

## Test 160 — pairing does not weaken release gate
**Input:** one-click pairing core passes deterministic tests but production identity provider/app deployment and native Companion packaging are not yet complete.  
**Expected:** v3.0 remains development-only until the full novice onboarding path works end-to-end.
