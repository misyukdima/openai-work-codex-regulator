# Official source map

**Skill release:** 1.2  
**Verified:** 2026-08-22

Time-sensitive provisions are marked **[time-sensitive]**: they must be re-verified against first-party OpenAI sources or the actual account UI before being relied upon, and must never be promoted into permanent hardcoded logic.

## Product-role routing

Rule: Chat = quick conversation; Work = longer multi-step research/deliverables; Codex = software/technical work.

Source:
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

Used in:
- `SKILL.md` sections 4, 13, 15
- `references/01_SURFACE_ROUTING.md`

## Shared Work/Codex agentic pool

Rule: Codex and ChatGPT Work draw from the same agentic usage/credit pool when available on the plan. **[time-sensitive]** As of the verification date, official material also documents tasks started through Voice in Work/Codex as drawing from the same shared agentic pool, and Workspace Agent / ChatGPT for Excel / PowerPoint as token-metered agentic features that can share credits.

Sources:
- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/20001106-codex-rate-card
- https://help.openai.com/en/articles/12642688

Used in:
- `SKILL.md` sections 1, 6, 8.4, 12, 20
- `references/02_SHARED_QUOTA_AND_CREDITS.md`
- `references/04_RUNWAY_AND_BURN.md`

Operational consequence:
- the set of OpenAI shared-pool consumers is NOT hardcoded; only features confirmed by current official sources / account UI count for `OTHER_SHARED_POOL_ACTIVITY`. External tools (Kimi, Skyvern, etc.) are not OpenAI shared-pool consumers.

## Usage dashboard / limits / reset

Rule: first-party Settings/Usage is the source for actual account state; Codex help refers to 5-hour and weekly reset behavior.

Source:
- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan

Used in:
- `SKILL.md` sections 6, 8, 9

## Flexible credits / Auto top-up / credit eligibility

Rule: supported Plus/Pro accounts can purchase credits after included usage; Auto top-up may be available; shared credits can be consumed by supported features. **[time-sensitive]** As of the verification date the official credits article contains feature-specific wording that can change; exact per-feature eligibility must therefore be confirmed in first-party account UI and must not be assumed.

Source:
- https://help.openai.com/en/articles/12642688

Used in:
- `SKILL.md` section 6.3
- `references/02_SHARED_QUOTA_AND_CREDITS.md`

Operational consequence:
- `CREDIT_ELIGIBILITY_WORK` / `CREDIT_ELIGIBILITY_CODEX` exist because user authorization does not prove feature eligibility; `UNKNOWN` eligibility → PREPARE + first-party UI check.

## Workspace capability / permission controls

Rule: workspace owners/admins can separately control Work Cloud, Work Local and Codex Local; browser use and network access have separate controls where supported. A surface can be unavailable even when quota remains. **[time-sensitive]**

Source:
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

Used in:
- `SKILL.md` section 6.4
- `references/02_SHARED_QUOTA_AND_CREDITS.md` section 8

## Model tiers / Work and Codex availability

Rule: OpenAI defines `Sol`, `Terra`, and `Luna` as capability tiers: Sol is flagship, Terra is balanced/lower-cost for everyday work, and Luna is the fastest/lowest-cost tier. OpenAI states that the generation number and the Sol/Terra/Luna tier names are separate concepts, so tier names can be used as durable routing roles while exact generation IDs remain time-sensitive. **[time-sensitive]**

Sources:
- https://help.openai.com/en/articles/20001354-gpt-5-6-in-chatgpt
- https://openai.com/index/gpt-5-6/

As of 2026-08-22 the official availability page says ChatGPT Work exposes Sol, Terra and Luna to Plus/Pro/Business/Enterprise, subject to rollout/workspace controls. Current account UI wins if availability differs.

Used in:
- `SKILL.md` section 10 (generic minimal-sufficient-model rule)
- `references/08_MODEL_TIER_ROUTING.md`
- `tests/TEST_CASES.md` tests 51–60

Operational consequence:
- route by capability tier and task profile, not by a permanent generation ID;
- if a recommended tier is unavailable in current UI, use an explicit sufficient fallback or PREPARE when risk/cost changes materially.

## Model/token cost and relative tier economics

Rule: current first-party rate cards show materially different token/credit cost across Sol, Terra and Luna; actual cost depends on model, input/cached/output tokens and features. **[time-sensitive]**

Sources:
- https://help.openai.com/en/articles/20001415
- https://help.openai.com/en/articles/20001106-codex-rate-card

Used in:
- `references/08_MODEL_TIER_ROUTING.md`
- `SKILL.md` sections 6, 8, 10

Operational consequence:
- use the cheapest tier that is sufficient for the gate;
- rate cards justify relative cost posture but never substitute for the user's first-party usage snapshot;
- do not copy current numeric rates into permanent operational thresholds.

## Token-based Codex rate card / Fast / reasoning

Rule: current Codex credit pricing is token-based for most plans; actual spend depends on model/tokens/tools; Fast can cost more; maximum reasoning can do more work/agents. **[time-sensitive]**

Source:
- https://help.openai.com/en/articles/20001106-codex-rate-card

Used in:
- `SKILL.md` sections 6, 10
- `references/08_MODEL_TIER_ROUTING.md`

## Work Scheduled Tasks / approvals

Rule: Work can run scheduled/triggered tasks and users can review progress/approve important actions where supported.

Sources:
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/10128477-chatgpt-enterprise-edu-release-notes

Used in:
- `SKILL.md` sections 13, 14
- `references/05_WORK_BROWSER_AND_ACTIONS.md`

## Built-in browser / browser safety

Rule: the ChatGPT desktop built-in browser uses its own browser state; official guidance says to treat website content as untrusted, enter credentials only in the browser (never in the chat), review the active account before allowing ChatGPT to continue, and stop the task if ChatGPT opens the wrong account or page. **[time-sensitive]**

Source:
- https://help.openai.com/en/articles/20001277-using-the-built-in-browser-in-the-chatgpt-desktop-app

Used in:
- `SKILL.md` sections 13.2, 13.3, 13.4
- `references/05_WORK_BROWSER_AND_ACTIONS.md` sections 8–10
- `references/07_FAILURES_AND_RECOVERY.md` section 8

## Model names are stale-sensitive

Generation-specific model names, exact effort availability, Fast/Ultra availability and rate-card values are time-sensitive. Current account UI and first-party documentation override old prompts or old releases.

Sources:
- https://help.openai.com/en/articles/20001354-gpt-5-6-in-chatgpt
- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001106-codex-rate-card

Operational consequence:
- keep Sol/Terra/Luna as capability-tier roles while resolving the actual generation/model from current UI;
- do not preserve a retired generation ID because it appeared in an old prompt.

## Internal operating policies, not OpenAI product facts

The following are deliberate regulator policies:

- class 0–4 taxonomy;
- one gate = one primary surface;
- bounded Chat (`CHAT_BOUNDED_WEB`) profile and the `WHY_AGENTIC` gate;
- `USER_SURFACE_OVERRIDE` after one quota-saving warning;
- 10 percentage-point 5h/weekly reserve;
- pass/runway ledger;
- two-attempt rule;
- paid credits disabled by default;
- credit authorization vs credit eligibility separation;
- snapshot freshness policy per class;
- untrusted-content / prompt-injection doctrine;
- download ≠ execution permission;
- account identity check before browser actions;
- scheduled-task runaway stop after 2–3 identical failures;
- exact-file Git staging;
- no `git add .`;
- manual-run-before-schedule requirement;
- default model-tier routing: Luna for high-volume routine extraction, Terra as balanced default, Sol for consequential synthesis;
- `WHY_MAX` / `WHY_ULTRA` gates before expensive reasoning escalation.

They must not be described as official OpenAI limits.
