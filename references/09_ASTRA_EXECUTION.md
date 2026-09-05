# Astra execution contract

**Policy version:** v2.0  
**Verified:** 2026-09-05  
**Status:** normative

This reference defines Astra-specific admission, quota, steering and safety behavior for ChatGPT Work and Codex.

## 1. First-party facts verified for v2.0

As of 2026-09-05, OpenAI documents GPT-6 Astra as its most capable model for the hardest end-to-end work, with major improvements in coding, research, computer use and complex multi-step work.

Current first-party material states:

- Astra is rolling out to Plus, Pro, Business and Enterprise for Work/Codex, subject to account/workspace rollout and permissions;
- Astra uses the plan's Work/Codex allowance when available;
- Pro $100, Pro $200 and Business Premium can use their full existing Work/Codex allowance for Astra;
- Plus and Business Standard receive limited Astra usage with optional credits afterward where eligible;
- credits do not unlock early rollout access;
- Astra can consume Work/Codex allowance faster than GPT-5.6 Sol;
- consumption depends on task, input/output size, reasoning and Fast mode;
- current Codex guidance requires Codex CLI 0.153.0 or newer for Astra and recommends the latest ChatGPT Desktop app;
- the API model supports `low`, `medium`, `high`, `xhigh`, and `max` reasoning effort;
- the API model page lists a 1,050,000-token context window and 128,000 max output tokens;
- current first-party rate-card material lists Astra Fast in Work/Codex at 2.5× Standard rate;
- OpenAI added safety monitoring that may pause or stop a conversation when a potential instruction-interpretation problem is detected;
- OpenAI classifies Astra as reaching the Critical cybersecurity capability threshold under its Preparedness Framework.

All rollout, plan, client-version, context and rate facts above are **time-sensitive**. The account/workspace UI and latest official docs override this dated snapshot.

## 2. Astra is an exceptional profile

Astra is not a routine default and not a fourth `LUNA/TERRA/SOL` tier.

Required selection state:

```text
MODEL_PROFILE=ASTRA
MODEL_TIER=N/A
ASTRA_JUSTIFIED=YES
ASTRA_SCOPE_BOUND=<one exact gate>
ASTRA_EXPECTED_ADVANTAGE=<why this profile materially helps>
ASTRA_FALLBACK=<bounded fallback|none>
```

If `ASTRA_JUSTIFIED != YES`, use the minimum sufficient tiered profile or return PREPARE.

## 3. Admission criteria

Astra may be selected when the gate is bounded and one or more of these are true:

- multiple dependent stages must be coordinated end-to-end;
- heterogeneous tools/computer use/research/code must be combined inside one gate;
- stage handoffs would materially increase error/rework risk;
- consequential synthesis requires resolving conflicting evidence across domains;
- a valid tiered attempt demonstrated a capability ceiling and the new run has a new hypothesis;
- expected total burn/rework is lower with one Astra pass than with several repeated tiered passes.

The following do not justify Astra:

- novelty;
- “strongest model available”;
- task importance alone;
- impatience;
- missing access/permissions/data;
- CAPTCHA/network block;
- repeated identical prompt;
- an attempt to skip human approval, baseline or rollback.

## 4. Allowance-domain discipline

Before Astra Work/Codex execution:

```text
ALLOWANCE_DOMAIN=WORK_CODEX
ASTRA_ALLOWANCE_STATE=<INCLUDED|LIMITED_INCLUDED|PAID_ELIGIBLE|UNKNOWN>
```

Do not substitute Chat/GPT-6 Pro message allowance for Work/Codex usage.

Do not substitute API billing for ChatGPT-plan usage.

If plan-specific Astra availability or included usage is unclear, use `UNKNOWN` and current first-party UI.

## 5. Client-readiness gate

For Codex Astra usage:

```text
CODEX_CLIENT_ASTRA_READY=<YES|NO|UNKNOWN>
```

Current dated requirement: Codex CLI 0.153.0 or newer. Do not hardcode that number into permanent executable policy; re-check first-party docs at execution time if compatibility matters.

If Astra is necessary and readiness is `NO|UNKNOWN` → PREPARE or choose an explicitly sufficient fallback.

## 6. End-to-end execution boundary

Astra may complete several internal steps within one pass if they all belong to one gate.

Allowed:

```text
one gate
→ collect evidence
→ reason
→ use tools
→ produce/verify deliverable
→ STOP AFTER REPORT
```

Not allowed:

```text
gate A closes
→ silently start gate B
→ perform new external action
```

`ONE_GATE = ONE_PRIMARY_SURFACE` remains mandatory.

## 7. Mid-turn steering

Astra is designed to adapt when users add requirements or change direction. The regulator must make that adaptability transactional rather than silently scope-expanding.

Record:

```text
STEERING_EVENT=<YES|NO>
STEERING_SCOPE_EFFECT=<SAME_GATE|EXPANDS_GATE|CHANGES_ACTION|CHANGES_CLASS|UNKNOWN>
STEERING_DELTA=<short description>
```

Policy:

- `SAME_GATE`: continue only if permissions, class, quota and action scope remain valid; restate the delta briefly;
- `EXPANDS_GATE`: stop current pass after safe state capture and re-admit;
- `CHANGES_ACTION`: new approval is required if external/write action changes;
- `CHANGES_CLASS`: reclassify and re-run admission;
- `UNKNOWN`: stop and review.

A steering event cannot silently change recipient, target, repository, production environment, paid-spend cap, data-access scope or forbidden actions.

## 8. Safety-pause semantics

Normalize:

```text
SAFETY_STATE=<NORMAL|PAUSED_FOR_REVIEW|BLOCKED|UNKNOWN>
```

When OpenAI/model execution pauses or stops for review because instructions may have been misinterpreted:

1. treat it as a safety state, not a normal capability failure;
2. preserve last confirmed evidence and pending action;
3. inspect ambiguity, target, scope, permissions and approval;
4. do not bypass via Work↔Codex switch;
5. do not bypass via different model/profile;
6. do not replay the same prompt unchanged;
7. continue only after bounded re-admission.

`PAUSED_FOR_REVIEW` does not count as one of two ordinary same-strategy failures until the safety review determines that the issue was not safety-related.

## 9. Cyber-sensitive execution

Because OpenAI classifies Astra at Critical cybersecurity capability, cyber-sensitive class 4 work receives an explicit authorization gate:

```text
CYBER_SCOPE_AUTHORIZATION=<CONFIRMED|NOT_REQUIRED|UNKNOWN>
CYBER_TARGET_SCOPE=<owned/authorized target or N/A>
```

Rules:

- read-only defensive analysis of clearly owned/authorized systems may proceed within normal class 4 gates;
- mutation/exploitation-like actions require confirmed target authorization plus exact scope;
- `UNKNOWN` authorization → PREPARE/STOP;
- model capability never widens authorization;
- no opportunistic scanning of unrelated targets;
- no scope expansion after discovering an interesting adjacent system.

## 10. Long-context discipline

Astra's very large context is a capability, not a reason to abandon context hygiene.

Default:

- compact handoff;
- accepted evidence package;
- no whole-chat dump between gates;
- no repeated reading of unchanged large documents;
- preserve only decision-critical verbatim material.

If large context is genuinely required:

```text
LONG_CONTEXT_JUSTIFIED=YES
LONG_CONTEXT_SCOPE=<why summary would lose decision-critical information>
```

Rate/cost treatment for long context is product-dependent and time-sensitive. Use current first-party Work/Codex/account rules; do not copy API multipliers into ChatGPT-plan burn calculations.

## 11. Fast and maximum reasoning

Astra Fast requires explicit latency value and current cost awareness:

```text
FAST_REQUIRED=YES
WHY_FAST=<material latency reason>
FAST_COST_ACK=<current UI/rate card checked|unknown>
```

For maximum current reasoning:

```text
WHY_MAX=<why lower effort is insufficient>
MAX_SCOPE_BOUND=<exact bound>
```

Do not combine Astra + Fast + maximum reasoning “just in case.” Each escalation must independently close a real need.

## 12. Burn and runway

Astra can burn allowance faster than Sol, so a heavy Astra pass should have stronger pre-pass budget evidence than an equivalent routine tiered pass.

Record where useful:

```text
ASTRA_BURN_EVIDENCE=<task credits|clean usage delta|unknown>
ASTRA_COMPARABLE_HISTORY=<n passes|none>
```

Rules:

- compare like-for-like Astra passes;
- unknown burn on a class 3–4 Astra pass is a reason to narrow scope or obtain a fresh usage snapshot;
- do not estimate Astra burn by multiplying an old Sol/Terra pass by a guessed coefficient;
- Fast-mode rate facts are relative cost evidence, not personal usage predictions.

## 13. Failure and fallback

Astra fallback is explicit:

```text
ASTRA_FALLBACK=<TIERED/SOL|TIERED/TERRA|OTHER|none>
FALLBACK_REASON=<availability/client/quota/fit>
```

Fallback rules:

- rollout unavailable → use sufficient fallback, not purchased credits for early access;
- client incompatible → update client if allowed or use sufficient fallback;
- quota too constrained → narrow/defer/fallback rather than silently paid-spend;
- blocker unrelated to capability → change strategy, not model;
- two identical failures → stop strategy before another escalation.

## 14. Result acceptance

An Astra completion claim needs the same or stronger evidence as any other profile:

- exact gate closed;
- sources/diff/test evidence present;
- scope respected;
- external actions enumerated;
- steering events recorded;
- safety state normal or reviewed;
- residual risks listed;
- post-pass usage captured where available.

Astra is not accepted merely because the narrative sounds comprehensive.

## 15. Official sources

- https://openai.com/products/release-notes/
- https://openai.com/index/gpt-6-astra/
- https://openai.com/index/safety-overview-gpt-6-astra/
- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/guides/latest-model
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/20001354-gpt-56-and-gpt-6-pro-in-chatgpt
- https://help.openai.com/en/articles/11481834-chatgpt-rate-card
- https://help.openai.com/en/articles/12003714-chatgpt-business-models-and-limits
- https://help.openai.com/en/articles/20001415-chatgpt-rate-card-enterprise-token-based-pricing
