# Changelog

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
- Added normalized `MODEL_AVAILABILITY_SNAPSHOT`, `MODEL_TIER`, `EFFORT`, `WHY_THIS_MODEL`, `FALLBACK_MODEL` and `MODEL_COST_POSTURE` fields.
- Added routing defaults: Luna for high-volume routine discovery/extraction, Terra as the balanced default for most multi-source research and implementation, Sol for consequential legal/security/production/final synthesis.
- Added explicit `WHY_MAX` / `MAX_SCOPE_BOUND` and `WHY_ULTRA` / `ULTRA_MERGE_PLAN` gates before expensive reasoning escalation.
- Added escalation/de-escalation rules that distinguish model-capability failures from blockers such as CAPTCHA, unavailable data or bad scope.
- Added staged mixed-tier policy (`Luna → Terra → Sol only if justified`) without duplicate rereading of the same evidence.
- Re-verified current first-party model availability and rate-card sources on 2026-08-22; account/workspace UI remains authoritative for actual model/effort availability.
- Added regression tests 51–60 covering extraction, ordinary research, legal/security synthesis, max/ultra, fallbacks, blockers and generation-independent routing.
- Validator now requires the model-routing reference, its core invariants, the new first-party model/rate-card sources and at least 60 contiguous regression tests.
- Updated README and usage guide for v1.2 model-tier operation.

## 1.1 — 2026-08-22

Quota-saving routing, security and release-hardening release. Architecture of v1.0 preserved.

- Added bounded Chat policy (`CHAT_BOUNDED_WEB`) so simple lookups, attached-file summaries and simple artifacts from supplied content stay in CHAT instead of burning an agentic pass.
- Added `WHY_AGENTIC` / `VALUE_OUTPUT` gate before expensive agentic passes, and `USER_SURFACE_OVERRIDE=YES` for explicit user insistence after one quota-saving warning.
- Added untrusted-content / prompt-injection doctrine for Work/browser/connected apps.
- Added account/browser identity checks before external browser actions.
- Added download ≠ execution safety rule.
- Generalized burn attribution: `OTHER_SHARED_POOL_ACTIVITY` + `ATTRIBUTION=CLEAN|MIXED|UNKNOWN`.
- Split paid-credit authorization from feature eligibility.
- Added capability/permission snapshot and quota snapshot freshness policy.
- Hardened Scheduled Tasks and context budget discipline.
- Added regression tests 37–50 and release validation/packaging automation.

## 1.0 — 2026-08-21

Initial release.

- Added Chat / Work / Codex surface routing.
- Added shared agentic pool / credit architecture.
- Added first-party quota snapshot and paid-credit policy.
- Added project runway and observed-burn discipline.
- Added Work browser/action and Scheduled Task rules.
- Added Codex repository/server/Git discipline.
- Added class 0–4 risk model.
- Added Fast/Ultra/model escalation controls.
- Added failure, anti-bot, duplicate-pass and result-verification rules.
- Added official OpenAI source map and regression tests.
