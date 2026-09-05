# Shared agentic usage, credits and first-party snapshot

**Version:** 2.0  
**Verified:** 2026-09-05  
**Status:** normative

## 1. Core architecture

OpenAI currently documents ChatGPT Work and Codex as sharing the same agentic usage structure when available on the user's plan. Astra participates in that Work/Codex allowance when it is available.

A separate Chat model allowance, including GPT-6 Pro where offered, must not be treated as spare Work/Codex capacity.

Normalize the billing/usage domain first:

```text
ALLOWANCE_DOMAIN=<WORK_CODEX|CHAT_PRO|API|UNKNOWN>
```

Operational consequences:

- Work is not a free fallback after Codex exhaustion;
- Codex is not a free fallback after Work exhaustion;
- Chat/GPT-6 Pro message limits do not estimate Work/Codex remaining usage;
- API key billing is a different domain from ChatGPT-plan Work/Codex usage;
- parallel and scheduled runs can compound the shared Work/Codex pool.

## 2. Astra-specific current facts

As verified 2026-09-05, first-party OpenAI material states:

- GPT-6 Astra is rolling out to Plus, Pro, Business and Enterprise for Work/Codex, subject to actual account/workspace availability;
- Pro $100, Pro $200 and Business Premium can use their full existing Work/Codex allowance for Astra;
- Plus and Business Standard include limited Astra usage, with optional credits afterward where eligible;
- buying credits does not provide early rollout access;
- Astra can use Work/Codex allowance faster than GPT-5.6 Sol;
- usage depends on task size, input/output size, reasoning settings and Fast mode.

These plan/rollout facts are **time-sensitive**. Account/workspace UI wins.

## 3. Sources of truth

For personal remaining Work/Codex usage:

1. ChatGPT/Codex `Settings → Usage / Usage Dashboard`;
2. first-party usage banner/reset shown by the account;
3. first-party credit balance and spending controls;
4. `/status` inside Codex as supplemental session telemetry where available;
5. task/thread credit usage where displayed.

Do not infer personal remaining usage from a static rate card or API token price.

## 4. Snapshot

```text
SNAPSHOT_AT=
PLAN=
ALLOWANCE_DOMAIN=WORK_CODEX
SHARED_INCLUDED_USAGE=known|unknown
FIVE_HOUR_USED=
FIVE_HOUR_RESET=
WEEKLY_USED=
WEEKLY_RESET=
CREDIT_BALANCE=
AUTO_TOP_UP=
PAID_CREDITS_ALLOWED=YES|NO
OTHER_SHARED_POOL_ACTIVITY=YES|NO|UNKNOWN
CREDIT_ELIGIBILITY_WORK=CONFIRMED|UNAVAILABLE|UNKNOWN
CREDIT_ELIGIBILITY_CODEX=CONFIRMED|UNAVAILABLE|UNKNOWN
SOURCE=
```

Unknown means unknown.

## 5. Paid credits

Default regulator policy:

```text
PAID_CREDITS_ALLOWED=NO
```

The regulator must never enable Auto top-up, purchase credits, assume paid spend approval or use paid spend to rescue bad scope.

Paid continuation requires:

```text
PAID_CREDITS_ALLOWED=YES
MAX_PAID_CREDITS=<explicit cap>
```

No cap → PREPARE before the first paid draw.

Authorization and technical eligibility are separate:

```text
CREDIT_ELIGIBILITY_WORK=CONFIRMED|UNAVAILABLE|UNKNOWN
CREDIT_ELIGIBILITY_CODEX=CONFIRMED|UNAVAILABLE|UNKNOWN
```

If included usage is exhausted, spend is authorized, but eligibility is `UNKNOWN` → PREPARE and verify first-party account state.

## 6. Rate-card facts are not budget facts

Current first-party rate cards show materially different consumption across models and modes. Astra is explicitly documented as potentially using allowance faster than GPT-5.6 Sol. Current Work/Codex rate-card material also shows a Fast-mode multiplier for Astra.

Use those facts for relative cost posture only. Do not turn them into a universal personal quota coefficient.

## 7. Astra burn accounting

For an Astra pass record:

```text
MODEL_PROFILE=ASTRA
PASS_CREDITS=<if shown>
ASTRA_BURN_EVIDENCE=<task credits|clean delta|unknown>
```

Rules:

- compare Astra history primarily to similar Astra passes;
- do not reuse Terra/Sol burn coefficients as Astra estimates;
- do not infer weekly percentage from token count;
- if other shared-pool activity occurred, attribution is mixed.

```text
ATTRIBUTION=CLEAN|MIXED|UNKNOWN
OTHER_SHARED_POOL_ACTIVITY=YES|NO|UNKNOWN
```

External tools such as Kimi or Skyvern are not OpenAI shared-pool activity.

## 8. Snapshot freshness

- class 0: usually not needed;
- class 1: optional;
- bounded low-burn class 2: may proceed with `QUOTA=UNKNOWN` if no paid spill risk and no near-limit warning;
- class 3–4: fresh snapshot required except urgent read-only containment with explicit caveat;
- stale snapshot may be reused only in the same relevant reset window with no significant shared-pool activity afterward.

Astra class 2 can still require a fresh snapshot if expected burn is materially uncertain or current plan only includes limited Astra usage.

## 9. Capability / permission state

Quota does not imply capability:

```text
WORK_CLOUD=ON|OFF|UNKNOWN
WORK_LOCAL=ON|OFF|UNKNOWN
CODEX_LOCAL=ON|OFF|UNKNOWN
BROWSER_ACCESS=ON|OFF|UNKNOWN
NETWORK_ACCESS=ON|OFF|UNKNOWN
CONNECTED_APP_REQUIRED=<name|NO>
CONNECTED_APP_PERMISSION=OK|MISSING|UNKNOWN
CODEX_CLIENT_ASTRA_READY=YES|NO|UNKNOWN|N/A
```

As verified 2026-09-05, current OpenAI guidance requires a compatible Codex client for Astra and recommends the latest ChatGPT Desktop app. Exact minimum versions are time-sensitive and recorded in `references/09_ASTRA_EXECUTION.md` / `SOURCE_MAP.md`, not in permanent executable logic.

## 10. Official sources

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/11481834-chatgpt-rate-card
- https://help.openai.com/en/articles/12003714-chatgpt-business-models-and-limits
- https://help.openai.com/en/articles/20001415-chatgpt-rate-card-enterprise-token-based-pricing
- https://help.openai.com/en/articles/12642688
