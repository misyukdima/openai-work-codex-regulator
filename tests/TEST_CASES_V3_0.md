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
