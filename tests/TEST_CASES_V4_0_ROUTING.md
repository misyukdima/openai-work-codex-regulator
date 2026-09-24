# v4.0 routing and runway regression additions

## Test 270 — ChatGPT is the primary orchestrator
**Expected:** ChatGPT owns task understanding, quota admission, surface selection and model/reasoning routing; Work/Codex are execution planes.

## Test 271 — default active working window
**Expected:** default local window is 09:00–23:00 with 22:00 as normal soft end; user may override it.

## Test 272 — no per-task duration limit
**Expected:** long Work/Codex execution is allowed when quality requires it; schedule paces quota rather than imposing a task timeout.

## Test 273 — off-hours do not consume runway
**Expected:** weekly pacing uses active minutes remaining before reset, not raw wall-clock hours.

## Test 274 — weekly-only current snapshot
**Expected:** a valid weekly window with no secondary window remains usable; no synthetic five-hour gate is created.

## Test 275 — secondary window when actually reported
**Expected:** a reported additional quota window is enforced independently from weekly usage.

## Test 276 — percentages from different windows are not combined
**Expected:** weekly and secondary-window percentages remain separate denominators.

## Test 277 — quality floor precedes economy
**Expected:** no model/reasoning downgrade below minimum sufficient quality.

## Test 278 — mechanical routing
**Expected:** Luna Low starts extraction/dedupe/fixed-schema work when available.

## Test 279 — routine routing
**Expected:** Luna Medium starts clear-brief bounded coordinated work when available.

## Test 280 — professional routing
**Expected:** Sol Medium starts normal coding/research/writing/debugging requiring judgment.

## Test 281 — complex reasoning-depth routing
**Expected:** Sol High is used when Sol capability is sufficient but deeper deliberation is needed.

## Test 282 — complex capability routing
**Expected:** Astra Low/Medium may replace Sol High/xhigh when breadth/capability, not reasoning depth, is the bottleneck.

## Test 283 — critical routing
**Expected:** high-error-cost security/production work starts from Astra High unless evidence justifies another sufficient configuration.

## Test 284 — permission blocker is not a model blocker
**Expected:** missing permission/authorization/network access stops or prepares the gate; no model escalation workaround.

## Test 285 — quota pressure picks among sufficient candidates
**Expected:** choose the lightest observed-burn candidate only after below-quality candidates are rejected.

## Test 286 — unknown burn is not zero burn
**Expected:** heavy work with no compatible history is prepared/calibrated conservatively.

## Test 287 — pending burn blocks heavy stacking
**Expected:** reporting lag prevents another large future advance until resolved or safely bounded.

## Test 288 — model availability is current-account state
**Expected:** documented existence does not imply selectable access; current picker/workspace state wins.

## Test 289 — reset creates a new active-time epoch
**Expected:** confirmed weekly reset invalidates the old anchor and recomputes active minutes.
