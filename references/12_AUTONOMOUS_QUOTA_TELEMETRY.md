# Autonomous quota telemetry for ChatGPT

**Target version:** v4.0
**Status:** normative

```text
CONTROL_PLANE_OWNER=CHAT
CHATGPT_PRIMARY_ORCHESTRATOR=YES
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
USER_SETUP_AFTER_ZIP=NONE
```

Canonical tool:

```text
get_quota_snapshot()
```

The model supplies no identity or secret arguments. The connected backend resolves the authenticated subject server-side.

Minimum normalized state includes weekly usage/reset and telemetry freshness. Secondary windows are optional account-state facts.

```text
ALLOWANCE_DOMAIN=WORK_CODEX
WEEKLY_USED=<percent|unknown>
WEEKLY_RESET=<timestamp|unknown>
SECONDARY_WINDOW_PRESENT=<YES|NO|UNKNOWN>
QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>
```

If the upstream response contains a 300-minute window, preserve it as an independent secondary limit. If that window is absent but weekly telemetry is valid, do not synthesize a five-hour limit and do not block weekly-only admission.

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
UNKNOWN_IS_NOT_ZERO=YES
```

Refresh before a quota-sensitive agentic pass, after meaningful execution when burn attribution matters, when telemetry is stale, and when reset/epoch change is suspected. Do not poll on every ordinary ChatGPT message.

Immediate unchanged meter movement may be reporting lag:

```text
PENDING_BURN=YES
```

The Plugin/backend supplies facts only. It may not buy credits, trigger resets, change permissions, select models/surfaces or expose auth material.

Production credential lifecycle, subject binding and crypto-helper hardening remain inherited from the v3 development baseline.
