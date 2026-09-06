# Shared agentic usage, credits and first-party snapshot

**Version:** 3.0 development  
**Verified:** 2026-09-06  
**Status:** normative

## 1. Core architecture

Current first-party OpenAI material documents Codex, ChatGPT Work and other supported agentic features as drawing from the same agentic usage/credit pool when those features are available on the plan.

For this regulator:

```text
ALLOWANCE_DOMAIN=<WORK_CODEX|CHAT_PRO|API|UNKNOWN>
```

A Work/Codex weekly controller may only use `ALLOWANCE_DOMAIN=WORK_CODEX`.

Operational consequences:

- Work is not a free fallback after Codex exhaustion;
- Codex is not a free fallback after Work exhaustion;
- a separate Chat Pro-model allowance is not spare Work/Codex capacity;
- API-key billing is a different domain;
- scheduled, delegated and other confirmed shared-pool activity must be counted against the same Work/Codex continuity objective.

## 2. Usage depends on execution shape

OpenAI states that Work/Codex usage varies with factors including:

- model;
- where the task runs;
- task size and complexity;
- context;
- reasoning;
- speed/Fast mode;
- tools;
- long-running or delegated work.

Therefore the regulator must not pretend that one prompt, one token count or one model name has a fixed weekly percentage cost.

The mathematical weekly controller in `references/10_WEEKLY_QUOTA_CONTROLLER.md` is deliberately feedback-based: it plans from aggregate meter state and corrects from observed burn.

## 3. Sources of truth and telemetry transport

For personal Work/Codex allowance state, the underlying authoritative evidence remains current first-party OpenAI account/workspace state, including:

1. current `Settings → Usage / Usage Dashboard` or `Usage & billing`;
2. current first-party limit/reset banner;
3. current credit balance / spending controls;
4. `/status` in Codex as supplemental telemetry where available;
5. per-chat/per-task usage as supporting evidence where available.

The aggregate first-party allowance meter is stronger evidence for total weekly continuity than a per-chat total. Current OpenAI documentation notes that chat-level usage can be incomplete and that reporting can lag in some products/workspaces.

v3.0 changes **transport**, not meter semantics. When a supported telemetry tool reads the same underlying allowance state and provides a normalized fresh snapshot, the regulator may consume it automatically instead of requiring the user to transcribe the UI manually.

```text
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
```

Third-party/local adapters are implementation evidence only. They do not become normative OpenAI product sources and their own pacing/admission opinions are ignored.

Do not infer remaining included allowance from a static rate card.

## 4. Normalized snapshot

```text
SNAPSHOT_AT=
PLAN=
ALLOWANCE_DOMAIN=WORK_CODEX
SHARED_INCLUDED_USAGE=known|unknown
WEEKLY_METER_SEMANTICS=USED|REMAINING|UNKNOWN
WEEKLY_USED=<percent|unknown>
WEEKLY_RESET=<time|unknown>
WEEKLY_METER_GRANULARITY_PP=<pp|unknown>
FIVE_HOUR_USED=<percent|unknown>
FIVE_HOUR_RESET=<time|unknown>
CREDIT_BALANCE=<value|unknown>
AUTO_TOP_UP=<ON|OFF|unknown>
PAID_CREDITS_ALLOWED=<YES|NO>
PAID_WEEKLY_RESET_ALLOWED=<YES|NO>
OTHER_SHARED_POOL_ACTIVITY=<YES|NO|UNKNOWN>
CREDIT_ELIGIBILITY_WORK=<CONFIRMED|UNAVAILABLE|UNKNOWN>
CREDIT_ELIGIBILITY_CODEX=<CONFIRMED|UNAVAILABLE|UNKNOWN>
QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>
QUOTA_TELEMETRY_SOURCE=<provider|manual|unknown>
```

If the meter reports remaining rather than used, normalize explicitly:

```text
WEEKLY_USED = 100 - WEEKLY_REMAINING
```

Never guess meter semantics from an unlabeled number.

## 5. Snapshot freshness for adaptive control

For ordinary class 0–1 Chat work, a quota snapshot remains optional.

For quota-sensitive control:

- starting or re-anchoring the weekly controller requires a fresh weekly used/remaining value and reset time;
- before a meaningful class 2–4 Work/Codex pass, refresh automatic telemetry when available;
- after a meaningful class 2–4 pass, refresh telemetry when available to observe aggregate burn;
- a large next pass should not launch while prior meaningful burn is still `PENDING` on a lagged meter;
- any detected reset or material reset-time change invalidates the old trajectory anchor.

A stale snapshot is not safe merely because it is from the same day.

If automatic telemetry is unavailable, continue useful non-agentic Chat progress. Request a manual first-party snapshot only when an actual quota-sensitive decision cannot be resolved safely without fresh meter state.

## 6. Paid credits

Default:

```text
PAID_CREDITS_ALLOWED=NO
```

The regulator and telemetry path must not:

- enable Auto top-up;
- purchase credits;
- assume paid spend approval;
- use paid spend to rescue a poor strategy.

Paid continuation requires:

```text
PAID_CREDITS_ALLOWED=YES
MAX_PAID_CREDITS=<explicit cap>
```

Authorization and technical eligibility remain separate:

```text
CREDIT_ELIGIBILITY_WORK=CONFIRMED|UNAVAILABLE|UNKNOWN
CREDIT_ELIGIBILITY_CODEX=CONFIRMED|UNAVAILABLE|UNKNOWN
```

If included usage is exhausted and eligibility is unknown → `ПОДГОТОВКА`.

## 7. Weekly instant reset policy

Default:

```text
PAID_WEEKLY_RESET_ALLOWED=NO
```

Current first-party documentation says eligible Plus/Pro personal accounts may be offered a paid instant Work/Codex weekly reset. A completed paid reset restores applicable usage and changes the weekly schedule: the new weekly period begins with the first Work/Codex request after reset, and the next automatic reset is scheduled seven days after that first request.

Operational rules:

- never buy an instant reset autonomously;
- a purchase is a separate class-4 money action;
- it is not an invisible extension of the current quota epoch;
- after a reset, invalidate the old trajectory anchor/state and re-anchor from current normalized first-party telemetry;
- do not buy a reset simply because the adaptive controller correctly deferred low-value work.

Banked/promotional reset behavior is account/offer specific. Any applied reset is treated as a new quota-epoch event and current first-party state wins.

## 8. Rate cards and Astra

Current first-party rate cards show materially different paid-credit rates across models. Astra is also explicitly documented as capable of consuming Work/Codex allowance faster than Sol.

Use rate cards for relative cost posture only.

Do not:

- multiply a Sol weekly pp burn by a rate-card ratio to predict Astra weekly pp;
- convert tokens into weekly pp;
- assume Fast multiplier equals weekly-meter multiplier;
- use API prices as included-plan quota coefficients.

Astra history should be compared with similar Astra history.

## 9. Attribution vs total continuity

For exact pass attribution:

```text
ATTRIBUTION=CLEAN|MIXED|UNKNOWN
```

But weekly continuity controller uses the **total change in the shared weekly meter** inside the same quota epoch.

That means another Work/Codex/shared-pool task may make pass attribution `MIXED`, while still correctly reducing the current trajectory headroom.

This distinction is fundamental:

```text
attribution asks "who spent it?"
continuity asks "how much shared allowance is left?"
```

## 10. Capability / permission state

Quota does not imply the required capability is enabled:

```text
WORK_CLOUD=ON|OFF|UNKNOWN
WORK_LOCAL=ON|OFF|UNKNOWN
CODEX_LOCAL=ON|OFF|UNKNOWN
BROWSER_ACCESS=ON|OFF|UNKNOWN
NETWORK_ACCESS=ON|OFF|UNKNOWN
CONNECTED_APP_REQUIRED=<name|NO>
CONNECTED_APP_PERMISSION=OK|MISSING|UNKNOWN
QUOTA_TELEMETRY_TOOL=ON|OFF|UNKNOWN
CODEX_CLIENT_ASTRA_READY=YES|NO|UNKNOWN|N/A
```

Do not burn quota discovering a known disabled capability at runtime.

## 11. Official sources

- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/12642688
- https://help.openai.com/en/articles/20001507-paid-weekly-work-and-codex-rate-limit-resets
- https://help.openai.com/en/articles/20001478-reviewing-work-and-codex-usage-and-using-personal-analytics-in-chatgpt-desktop
- https://help.openai.com/en/articles/11481834-chatgpt-rate-card
