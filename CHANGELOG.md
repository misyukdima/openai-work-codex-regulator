# Changelog

## 2.1 — 2026-09-05

Adaptive weekly quota-control release focused on keeping shared Work/Codex capacity usable throughout the entire reset window without lowering the minimum sufficient quality of work.

- Added normative `references/10_WEEKLY_QUOTA_CONTROLLER.md` with a stateful feedback controller driven by first-party weekly meter/reset telemetry rather than guessed token/model coefficients.
- Added `QUOTA_EPOCH_ID` and reset/re-anchor semantics: normal, paid, banked/promotional or allowance-architecture reset events invalidate old daily/slice state without erasing completed project gates.
- Replaced static average-per-pass budgeting with fixed rolling 24h `CONTROL_SLICE_BUDGET_PP` envelopes that cannot be reissued after every pass.
- Added dynamic early risk reserve: 10 percentage points maximum, capped at 50% of current remaining allowance and linearly released through the final 72 hours.
- Added reproducible fresh-week reference math: first 24h envelope is `90 * 24 / 168 = 12.857142857 pp`; exact planned spending releases the reserve by reset instead of stranding it.
- Added stateful `SLICE_SPENT_PP`, `SLICE_HEADROOM_PP` and `EFFECTIVE_SLICE_HEADROOM_PP` accounting with meter-granularity buffer.
- Added `QUALITY_FLOOR=NON_NEGOTIABLE`: quota pressure may remove duplication/context/waste but must not force an insufficient model, remove required sources/tests or accept an incomplete gate. If quality does not fit, `QUOTA_DECISION=DEFER_FOR_QUALITY`.
- Added conservative `B_SAFE` pass-burn estimator using strong bootstrap margins for 1–2 samples and median/MAD/P80 planning for 3–5 recent compatible observations.
- Separated aggregate continuity accounting from exact pass attribution: `MIXED` intervals still reduce shared weekly headroom even when they cannot be assigned exactly to one pass.
- Added independent 5-hour circuit-breaker handling; weekly percentage points and 5h percentage points are never compared as the same denominator.
- Added `PENDING_BURN` / post-pass meter-state handling so large passes are not stacked on top of plausibly lagged aggregate telemetry.
- Added scheduled-work reservations so recurring Work/Codex burn is subtracted before interactive capacity is admitted.
- Added `CONTINUITY_FEASIBLE` to prevent false promises of useful daily work when the minimum quality-sufficient pass is mathematically larger than current headroom.
- Added paid weekly reset policy: `PAID_WEEKLY_RESET_ALLOWED=NO` by default; an authorized reset is a separate class-4 money action and starts a new quota epoch.
- Reworked `references/02_SHARED_QUOTA_AND_CREDITS.md` and `references/04_RUNWAY_AND_BURN.md` to separate project runway from quota runway and incorporate current reset/usage-reporting behavior.
- Added executable reference calculator `scripts/weekly_quota_controller.py` with deterministic self-tests for fresh-week math, reserve release, feedback, sparse/robust burn estimates and quality-floor admission.
- Updated `SKILL.md`, README, architecture and usage guide around adaptive weekly control.
- Re-verified first-party OpenAI Work/Codex shared-allowance, usage-dashboard, paid-reset, reporting and credit sources on 2026-09-05.
- Added regression tests 76–95 covering daily envelopes, meter semantics, stateful slices, reserve release, quota epochs, paid reset, mixed attribution, burn estimation, quality preservation, 5h separation, lagged telemetry and scheduled reservations.
- Validator upgraded for v2.1: requires the weekly-controller reference/script, at least 95 contiguous tests, v2.1 provenance and a successful imported controller self-test.

## 2.0 — 2026-09-05

Major Astra architecture release for ChatGPT Work + Codex.

- Added GPT-6 Astra as a separate exceptional `MODEL_PROFILE=ASTRA`, not as a fourth Luna/Terra/Sol tier.
- Added `ASTRA_JUSTIFIED`, `ASTRA_SCOPE_BOUND`, Astra fallback and explicit admission rules so the strongest model is not the default for ordinary work.
- Added `ALLOWANCE_DOMAIN=WORK_CODEX|CHAT_PRO|API|UNKNOWN` to prevent mixing Chat/GPT-6 Pro message allowances with Work/Codex shared agentic usage.
- Added Astra-specific quota discipline based on current OpenAI guidance that Astra can consume Work/Codex allowance faster than GPT-5.6 Sol.
- Added Codex Astra readiness gate (`CODEX_CLIENT_ASTRA_READY`) and first-party source tracking for the current minimum Codex client requirement.
- Added steering transaction semantics for mid-turn requirement changes: same-gate refinements may continue, while gate/class/action expansion requires re-admission.
- Added `SAFETY_STATE=PAUSED_FOR_REVIEW` recovery semantics. Astra safety pauses/stops are review events, not ordinary capability failures, and must not be bypassed by switching surface/model or blind retry.
- Added Astra cyber-sensitive authorization posture: stronger capability never expands target ownership, permissions, write scope or external-action approval.
- Added long-context discipline: large context is a capability, not permission to dump entire histories; compact handoffs and bounded evidence packages remain the default.
- Added normative `references/09_ASTRA_EXECUTION.md` with Astra admission, burn, steering, safety-pause and fallback rules.
- Reworked `references/08_MODEL_TIER_ROUTING.md` into a two-axis router: `MODEL_PROFILE` plus optional `MODEL_TIER`.
- Re-verified first-party OpenAI model, Work/Codex, rate-card and safety sources on 2026-09-05.
- Updated shared quota reference for current Astra rollout and plan-dependent included/credit usage semantics without hardcoding personal limits.
- Reworked executable `SKILL.md`, architecture and usage guide around allowance-domain separation and Astra admission.
- Added regression tests 61–75 for Astra admission, Work/Codex quota separation, Fast cost posture, Codex client readiness, steering, safety pauses, cyber authorization, long context and fallback.
- Validator upgraded to v2.0 invariants and now requires the Astra execution reference and at least 75 contiguous regression tests.
- Release remains immutable and ships the validated portable ZIP plus SHA-256 checksum.

## 1.2 — 2026-08-22

Model-tier routing release focused on quota efficiency and explicit model/effort selection for ChatGPT Work and Codex.

- Added normative `references/08_MODEL_TIER_ROUTING.md` with capability-tier routing based on durable `Luna / Terra / Sol` roles rather than permanent generation IDs.
- Added normalized model availability/tier/effort/fallback fields.
- Added Luna/Terra/Sol routing defaults and max/ultra escalation gates.
- Added staged mixed-tier policy and regression tests 51–60.

## 1.1 — 2026-08-22

Quota-saving routing, security and release-hardening release.

- Added bounded Chat, `WHY_AGENTIC` / `VALUE_OUTPUT`, surface override, prompt-injection/account/download safety, shared-pool attribution, paid-credit eligibility, capability snapshots, scheduled-task hardening and release automation.
- Added regression tests 37–50.

## 1.0 — 2026-08-21

Initial release.

- Added Chat / Work / Codex routing, shared agentic pool, quota snapshot, project runway, Work/browser/Codex discipline, class 0–4, failure recovery and official source map.
