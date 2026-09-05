# Model profile and tier routing

**Policy version:** v2.0  
**Verified:** 2026-09-05

This reference defines model selection for ChatGPT Work and Codex. v2.0 replaces the old single-axis tier router with two axes:

```text
MODEL_PROFILE=<TIERED|ASTRA|OTHER|UNKNOWN>
MODEL_TIER=<LUNA|TERRA|SOL|N/A|OTHER|UNKNOWN>
```

Exact generation IDs and current effort names remain time-sensitive and must be resolved from the current account/workspace UI and fresh first-party documentation.

## 1. Why Astra is not a fourth tier

OpenAI currently describes GPT-6 Astra as its most capable model for the hardest end-to-end work, while GPT-5.6 continues to expose Luna/Terra/Sol capability tiers in Work/Codex.

Therefore the regulator treats Astra as a separate execution profile rather than forcing it into the durable tier axis.

Operationally:

- `TIERED` = normal quota-efficient routing through Luna/Terra/Sol;
- `ASTRA` = exceptional end-to-end capability profile with stronger admission and burn discipline;
- `OTHER` = current UI offers something outside both known profiles;
- `UNKNOWN` = current availability cannot be established.

## 2. Normalized model snapshot

For cost-sensitive class 2–4 Work/Codex passes:

```text
MODEL_AVAILABILITY_SNAPSHOT=<UI/source/time|unknown>
MODEL_PROFILE=<TIERED|ASTRA|OTHER|UNKNOWN>
MODEL_TIER=<LUNA|TERRA|SOL|N/A|OTHER|UNKNOWN>
EFFORT=<current available value>
WHY_THIS_MODEL=<one bounded reason>
FALLBACK_MODEL=<profile/tier/effort|none|unknown>
MODEL_COST_POSTURE=<ECONOMY|BALANCED|QUALITY_FIRST|EXCEPTIONAL>
```

Do not invent availability. Current account/workspace UI wins over stale prompts or old release notes.

## 3. TIERED defaults

### LUNA — economy / high-volume routine work

Use when value comes mainly from speed/volume and each unit is low-risk and strongly verifiable:

- URL/SERP discovery;
- extraction from many similar pages;
- deduplication/filtering;
- fixed-schema classification;
- routine monitoring with a meaningful-change filter;
- mechanical structuring of accepted evidence.

Do not use Luna for consequential legal/security/production synthesis merely to save quota.

### TERRA — balanced default

Use for most class 2–3 substantive work:

- ordinary multi-source research;
- buyer-demand discovery and qualification;
- competitive comparisons;
- browser research with several related branches;
- normal Codex implementation/debugging;
- funnel/operations analysis;
- reversible synthesis that will be verified.

If a task is not clearly Luna and does not justify Sol or Astra, begin with Terra.

### SOL — quality-first consequential synthesis

Use when synthesis complexity or cost of error is materially higher:

- legal + commercial synthesis;
- complex architecture/security reasoning;
- production incident read-only analysis;
- conflicting authoritative sources;
- final consequential synthesis from a heterogeneous fact pack;
- class 4 read-only decisions where wrong reasoning could materially affect money/data/production/reputation.

Sol is not the default merely because the task is important.

## 4. ASTRA profile

Astra is not a default escalation after Sol. It is selected only when the gate itself materially benefits from end-to-end capability.

Required fields:

```text
MODEL_PROFILE=ASTRA
MODEL_TIER=N/A
ASTRA_JUSTIFIED=YES
ASTRA_SCOPE_BOUND=<exact gate>
ASTRA_EXPECTED_ADVANTAGE=<bounded reason>
ASTRA_FALLBACK=<fallback|none>
```

Strong reasons include:

1. multi-stage end-to-end work where stage handoffs themselves create meaningful risk/rework;
2. heterogeneous tool/computer/research/code work inside one bounded gate;
3. complex cross-domain synthesis with contradictions that a tiered path cannot reliably resolve;
4. a demonstrated capability ceiling on a sufficient tiered attempt plus a new hypothesis;
5. a bounded gate where one Astra run is expected to cost less overall than several failed/redundant tiered passes.

Weak/non-reasons:

- novelty;
- importance alone;
- impatience;
- “use the strongest model” without task-specific reasoning;
- CAPTCHA/network/permission/data blocker;
- repeating an identical failing prompt;
- avoiding a required approval or baseline.

## 5. Effort routing

Effort is independent from profile/tier.

Use the lowest current effort that is sufficient. Current Astra API guidance supports `low`, `medium`, `high`, `xhigh`, and `max`, but Work/Codex UI availability may differ and can change.

For the strongest current effort:

```text
WHY_MAX=<why lower effort is insufficient>
MAX_SCOPE_BOUND=<what bounds the work>
```

Do not preserve retired effort names as permanent policy.

## 6. Fast mode

Fast is a latency/cost decision, not a capability requirement.

For Astra + Fast:

```text
FAST_REQUIRED=YES
WHY_FAST=<material latency reason>
FAST_COST_ACK=<current UI/rate card checked|unknown>
```

As verified 2026-09-05, current first-party Work/Codex rate-card material lists Astra Fast at 2.5× Standard rate. This number is time-sensitive and must not become a permanent quota threshold.

Impatience alone is not enough to enable Fast.

## 7. Escalation

Escalate only if:

1. current strategy is valid;
2. failure is capability/quality related rather than blocker/scope/data/permission related;
3. a new hypothesis exists;
4. quota/runway supports the higher-cost path;
5. `WHY_THIS_MODEL` is recorded;
6. Astra additionally passes `ASTRA_JUSTIFIED`.

Two identical failures do not justify stronger model/effort.

## 8. De-escalation

De-escalate when the task changes from reasoning to high-volume extraction/classification with strong verification, or when Astra completed the hard synthesis and remaining work is mechanical.

Do not keep Astra active for downstream routine steps merely because it started the workflow.

## 9. Mixed-profile pipelines

A staged pipeline may be efficient:

```text
Luna: discover/extract/filter
→ Terra: qualify/compare/implement
→ Sol: consequential synthesis if needed
→ Astra: only when a bounded end-to-end or capability ceiling case is justified
```

Astra should not reread every source by default. Pass compact accepted evidence forward.

A different valid pattern is:

```text
Astra: one bounded end-to-end gate
→ Terra/Luna: mechanical follow-up after the hard gate is closed
```

## 10. Fallback

If a recommended option is unavailable:

1. do not invent availability;
2. choose the nearest sufficient available profile/tier;
3. record `FALLBACK_MODEL`;
4. if risk/cost changes materially, return `ПОДГОТОВКА` for quota/user confirmation;
5. if Astra is requested but unavailable, do not treat purchased credits as a way to obtain rollout access.

## 11. Forbidden behavior

Forbidden:

- defaulting to Astra because it is newest/strongest;
- treating Astra as a fourth Luna/Terra/Sol tier;
- selecting Sol/Astra solely because a task is “important”;
- selecting Luna solely because it is cheap when error cost is high;
- using model escalation to fight CAPTCHA/network/permission blockers;
- using max/Fast without bounded justification;
- hardcoding a generation ID as permanent routing policy;
- using API/token rate cards as exact personal Work/Codex burn;
- assuming docs availability is stronger than actual account/workspace UI.

## 12. Official sources

- https://help.openai.com/en/articles/20001354-gpt-56-and-gpt-6-pro-in-chatgpt
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://openai.com/index/gpt-6-astra/
- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/guides/latest-model
- https://help.openai.com/en/articles/11481834-chatgpt-rate-card
