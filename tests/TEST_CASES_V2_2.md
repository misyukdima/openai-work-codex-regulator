# v2.2 regression additions

## Test 96 — self-contained Chat to Codex handoff
**Input:** regulator is loaded in Chat; Chat routes implementation to Codex; Codex has no regulator installation.  
**Expected:** `HANDOFF_SELF_CONTAINED=YES`, `EXECUTOR_SKILL_REQUIRED=NO`; Codex receives a complete execution contract with no prerequisite to locate or load the regulator.

## Test 97 — executor installation remains optional
**Input:** Codex happens to have the regulator installed after Chat already admitted the pass.  
**Expected:** Chat still sends a self-contained packet; Codex does not duplicate quota/model admission merely because the skill exists.

## Test 98 — direct Codex invocation
**Input:** user explicitly invokes an installed regulator inside Codex.  
**Expected:** Codex may be `CONTROL_PLANE_OWNER=CODEX` for that local pass; any later downstream handoff remains self-contained.

## Test 99 — control-plane fields omitted from executor packet
**Input:** Chat has current quota epoch, trajectory headroom and quota/pace risk values before Codex launch.  
**Expected:** ordinary executor packet omits `QUOTA_EPOCH_ID`, `BASE_ACTION_HEADROOM_PP`, `MAX_ADVANCE_HEADROOM_PP`, `PACE_RISK_IF_DEFER` and `QUOTA_RISK_IF_LAUNCH`.

## Test 100 — model admission remains upstream
**Input:** Chat selected a sufficient model/profile/effort before sending the pass to Codex, which lacks regulator skill.  
**Expected:** missing skill does not force Codex to reopen model admission; execute the bounded packet using the selected launch configuration.

## Test 101 — fresh trajectory base and max advance
**Input:** `U0=0`, `H0=168`, current `H=168`, current used `0`, meter buffer/reservations `0`.  
**Expected:** `BASE_ACTION_HEADROOM_PP≈12.857142857`; `MAX_ADVANCE_HEADROOM_PP≈38.571428571`.

## Test 102 — trajectory does not reissue budget after pass
**Input:** same fresh anchor; a pass immediately raises weekly used to 5pp.  
**Expected:** base headroom falls by exactly 5pp to ≈7.857142857; no fresh 24h budget is issued.

## Test 103 — continuous accrual without 24h boundary
**Input:** same anchor; 5pp already spent; one hour passes with no additional burn.  
**Expected:** base trajectory headroom increases slightly with elapsed time; useful work need not wait for a fixed 24h boundary.

## Test 104 — blocking project gate can use bounded advance
**Input:** fresh trajectory; quality-sufficient `B_SAFE=20pp`; `PACE_RISK_IF_DEFER=HIGH`.  
**Expected:** pass fits max advance; normalized quota risk is below 0.75; `QUOTA_DECISION=LAUNCH_WITH_ADVANCE`.

## Test 105 — same pass with low pace cost preserves quota
**Input:** same `B_SAFE=20pp`; `PACE_RISK_IF_DEFER=LOW`.  
**Expected:** quota risk exceeds pace risk; choose `PROGRESS_ALTERNATIVE_OR_DEFER`, not automatic advance.

## Test 106 — equal-risk tie has no quota bias
**Input:** required advance consumes exactly 50% of borrowable extra; `PACE_RISK_IF_DEFER=0.50`; pass closes the active gate.  
**Expected:** tie may `LAUNCH_WITH_ADVANCE`; equal priority does not silently prefer quota preservation.

## Test 107 — pass beyond max advance is denied
**Input:** quality-sufficient burn exceeds `MAX_ADVANCE_HEADROOM_PP`; pace risk is CRITICAL.  
**Expected:** no launch merely for urgency; choose productive alternative/defer or a separately authorized capacity path.

## Test 108 — quality floor overrides pace
**Input:** candidate could move the project immediately but is below minimum sufficient model/tests/evidence quality.  
**Expected:** `QUALITY_FLOOR=NON_NEGOTIABLE`; `DEFER_FOR_QUALITY` regardless of pace risk.

## Test 109 — 5h breaker overrides weekly advance
**Input:** weekly trajectory admits future advance, but the separate 5h window cannot safely fit the pass.  
**Expected:** do not launch; weekly advance cannot bypass the 5h circuit breaker.

## Test 110 — pending meter blocks only large future advance
**Input:** prior meaningful pass finished, aggregate meter is plausibly pending; another large advance is proposed, while useful Chat review remains possible.  
**Expected:** block the large advance; continue safe non-agentic Chat progress instead of stopping the whole workflow.

## Test 111 — meaningful Chat alternative prevents idle workflow
**Input:** agentic pass loses quota/pace comparison but architecture review and the next compact handoff can be completed in Chat.  
**Expected:** `MEANINGFUL_PROGRESS_WITHOUT_AGENTIC=YES`; do useful Chat work now rather than default to a 24h idle wait.

## Test 112 — scheduled commitment reduces both horizons
**Input:** fresh trajectory and 3pp expected scheduled shared burn during look-ahead.  
**Expected:** both base and max-advance headroom are reduced by 3pp; no double allocation.

## Test 113 — self-contained Chat to Work handoff
**Input:** Chat routes an admitted research/action gate to Work; Work has no regulator installation.  
**Expected:** Work receives self-contained goal/context/actions/output/stop packet; no regulator dependency.

## Test 114 — regulator repository edit is a file-read exception
**Input:** Codex is explicitly tasked with modifying this regulator repository and needs to inspect `SKILL.md`.  
**Expected:** reading `SKILL.md` as project target/evidence is allowed; it is not a prerequisite installation dependency.

## Test 115 — low-value polish should not borrow future quota
**Input:** base headroom is exhausted; optional polish needs future advance; `PACE_RISK_IF_DEFER=LOW`.  
**Expected:** preserve future quota and use alternative/defer; advance is reserved for cases where equal-weight pace risk justifies it.
