# Official source map

**Skill release:** 1.1  
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

Rule: supported Plus/Pro accounts can purchase credits after included usage; Auto top-up may be available; shared credits can be consumed by supported features. **[time-sensitive]** As of the verification date the official credits article states both that credits "can only be used with Codex (for Plus/Pro users only) and ChatGPT for Excel" and that auto top-up shared credits "can be used across supported features such as Codex, ChatGPT Work, and ChatGPT for Excel". The exact per-feature eligibility therefore must be confirmed in the first-party account UI and must not be assumed.

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

## Token-based Codex rate card / Fast / reasoning

Rule: current Codex credit pricing is token-based for most plans; actual spend depends on model/tokens/tools; Fast can cost more; maximum reasoning can do more work/agents. **[time-sensitive]**

Source:
- https://help.openai.com/en/articles/20001106-codex-rate-card

Used in:
- `SKILL.md` sections 6, 10

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

As of 2026-08-21, official Codex help announces GPT-5.4 and GPT-5.4 mini removal from ChatGPT-account Codex on 2026-08-31, with replacement guidance. This is intentionally NOT hardcoded into routing/model policy because model availability is time-sensitive.

Source:
- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan

Operational consequence:
- use current UI/official docs instead of persistent model hardcodes.

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
- manual-run-before-schedule requirement.

They must not be described as official OpenAI limits.
