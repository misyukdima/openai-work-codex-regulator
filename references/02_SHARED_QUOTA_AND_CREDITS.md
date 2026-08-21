# Shared agentic usage, credits and first-party snapshot

**Version:** 1.1  
**Verified:** 2026-08-22  
**Status:** normative

## 1. Core architecture

OpenAI currently states that, when available on the user's plan, Codex, ChatGPT Work and other supported agentic features draw from the same agentic usage / credit pool. Tasks started through Voice in Work or Codex are documented as drawing from the same shared pool as well.

Therefore:

- Work is not a free fallback after Codex exhaustion;
- Codex is not a free fallback after Work exhaustion;
- parallel Work + Codex can compound shared usage;
- scheduled Work executions also need runway planning;
- credit balance must be treated as shared where the account says so.

## 2. Sources of truth

For personal remaining usage:

1. ChatGPT/Codex `Settings → Usage / Usage Dashboard`;
2. account limit banner / reset shown by first-party UI;
3. first-party credit balance and Auto top-up state;
4. `/status` inside Codex as supplemental session telemetry;
5. thread-level credits where displayed.

Do not use a static rate card to infer personal remaining quota.

## 3. Snapshot

```text
SNAPSHOT_AT=
PLAN=
FIVE_HOUR_USED=
FIVE_HOUR_RESET=
WEEKLY_USED=
WEEKLY_RESET=
CREDIT_BALANCE=
AUTO_TOP_UP=
PAID_CREDITS_ALLOWED=
OTHER_SHARED_POOL_ACTIVITY=YES|NO|UNKNOWN
CREDIT_ELIGIBILITY_WORK=CONFIRMED|UNAVAILABLE|UNKNOWN
CREDIT_ELIGIBILITY_CODEX=CONFIRMED|UNAVAILABLE|UNKNOWN
SOURCE=
```

Unknown means unknown.

`OTHER_SHARED_POOL_ACTIVITY` records whether another confirmed OpenAI shared-pool consumer ran between before/after snapshots (see `references/04_RUNWAY_AND_BURN.md` section 8). External tools such as Kimi or Skyvern are not OpenAI shared-pool activity.

## 4. Included usage and paid credits

Default internal policy:

```text
PAID_CREDITS_ALLOWED=NO
```

For Plus/Pro, OpenAI currently offers flexible credits for supported features after included usage is exhausted, depending on account availability. Auto top-up can also be available.

The regulator must never:

- enable Auto top-up;
- buy credits;
- assume paid credits are approved;
- use paid spend to rescue a poor strategy.

To allow paid credits:

```text
PAID_CREDITS_ALLOWED=YES
MAX_PAID_CREDITS=<explicit cap>
```

No cap → PREPARE before first paid draw.

## 4.1. Credit eligibility is separate from authorization

User authorization (`PAID_CREDITS_ALLOWED=YES`) does not mean the concrete feature/account technically supports paid continuation. The set of credit-eligible features is time-sensitive and confirmed only by the first-party account UI / current official documentation.

```text
CREDIT_ELIGIBILITY_WORK=CONFIRMED|UNAVAILABLE|UNKNOWN
CREDIT_ELIGIBILITY_CODEX=CONFIRMED|UNAVAILABLE|UNKNOWN
```

If included usage is exhausted, paid spend is authorized, but eligibility is `UNKNOWN` → PREPARE and check the first-party account UI. Never invent credit availability.

## 5. Rate card facts are not budget facts

OpenAI's Codex rate card is token-based for most current plans. Actual usage depends on input, cached input and output tokens, model, tools, reasoning, fast mode and agents.

The rate card is useful for understanding relative cost, not for reconstructing a user's remaining included usage.

Current official material also notes that Fast mode consumes credits at a higher rate for supported models. Maximum/Ultra-style reasoning can produce more work/agents and therefore more usage.

## 6. 5h / weekly windows

Current official Codex help material refers to 5-hour and weekly usage windows/reset behavior. Work follows the same usage structure as Codex, but the exact UI shown to an account can vary.

Operational rule:

- if the account shows 5h/weekly → record them;
- if it does not → do not fabricate them;
- use the actual first-party Usage Dashboard.

## 7. Snapshot freshness policy

A snapshot is not a ritual before every action:

- class 0: snapshot usually not needed;
- class 1: snapshot optional;
- bounded low-burn class 2: allowed with `QUOTA=UNKNOWN` if there is no paid spill risk, the user has not reported being near a limit, and the pass is genuinely small and bounded;
- class 3–4: fresh quota snapshot required, except urgent incident/read-only containment with an explicit caveat.

A stale snapshot may be reused only if it is inside the same relevant reset window and no significant shared-pool activity happened after it.

## 8. Capability / permission snapshot

Quota does not guarantee the surface is enabled: workspace/account permissions can turn off Work Cloud, Work Local, Codex Local, browser use or network access. Current official documentation describes these as separate workspace controls.

```text
WORK_CLOUD=ON|OFF|UNKNOWN
WORK_LOCAL=ON|OFF|UNKNOWN
CODEX_LOCAL=ON|OFF|UNKNOWN
BROWSER_ACCESS=ON|OFF|UNKNOWN
NETWORK_ACCESS=ON|OFF|UNKNOWN
CONNECTED_APP_REQUIRED=<name|NO>
CONNECTED_APP_PERMISSION=OK|MISSING|UNKNOWN
```

If quota exists but the required surface is disabled by workspace/account permissions, do not burn a pass on pointless runtime discovery: PREPARE, request access from the workspace admin, or change the plan. This is an optional gate — check capabilities only when the pass actually depends on them.

## 9. Official sources

- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/20001106-codex-rate-card
- https://help.openai.com/en/articles/12642688
