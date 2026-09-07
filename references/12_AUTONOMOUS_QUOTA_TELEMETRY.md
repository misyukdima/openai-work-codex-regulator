# Autonomous quota telemetry for ChatGPT Web

**Target version:** v3.0  
**Status:** normative development contract

v3.0 removes routine Work/Codex quota bookkeeping from the user while keeping the regulator inside ChatGPT Web.

## 1. Runtime contract

```text
SKILL_RUNTIME=CHATGPT_WEB_ONLY
CONTROL_PLANE_OWNER=CHAT
WORK_CODEX_ROLE=EXECUTION_PLANE
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
USER_SETUP_AFTER_ZIP=NONE
```

The skill does not run directly inside Work or Codex. Those surfaces receive self-contained execution packets from ChatGPT.

## 2. Normal user flow

```text
GitHub Release ZIP
  ↓
attach in ChatGPT Web
  ↓
ChatGPT loads regulator instructions
  ↓
ordinary Chat work
  ↓
quota-sensitive decision
  ↓
Plugin connected?
  ├─ yes → get_quota_snapshot()
  └─ no  → ChatGPT Connect/Auth
                  ↓
             one-time authorization
                  ↓
             get_quota_snapshot()
```

Do not front-load authorization if the current task does not need quota state.

```text
PLUGIN_AUTH=JUST_IN_TIME
LOCAL_SOFTWARE_REQUIRED=NO
OS_DEPENDENCY=NO
ZERO_MAINTENANCE_USER_SETUP=REQUIRED
```

## 3. Cloud boundary

Browser/cloud ChatGPT cannot assume access to a user's local binary, filesystem or localhost.

```text
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN
```

The production telemetry path is remote and Chat-accessible:

```text
ChatGPT Web
  → Regulator Quota Plugin/App
  → authenticated server-side backend
  → official OpenAI Codex app-server
  → account/rateLimits/read
  → normalized snapshot
```

A local Companion, CodexBar, MCP tunnel or OS service may exist in research history, but none is a production dependency for v3.0.

## 4. Canonical tool

```text
get_quota_snapshot()
```

The model supplies no identity or secret arguments. The connected app resolves the authenticated subject server-side.

Minimum result:

```text
ALLOWANCE_DOMAIN=WORK_CODEX
SNAPSHOT_AT=<timestamp>
QUOTA_TELEMETRY_SOURCE=OPENAI_CODEX_APP_SERVER
QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>
WEEKLY_METER_SEMANTICS=USED
WEEKLY_USED=<percent|unknown>
WEEKLY_RESET=<timestamp|unknown>
FIVE_HOUR_USED=<percent|unknown>
FIVE_HOUR_RESET=<timestamp|unknown>
```

Optional fields may include plan class, credits, additional windows and source health. The tool must not return OAuth tokens, cookies, bearer headers, raw auth files, private prompts or chat content.

## 5. Window semantics

Window position is not semantic truth:

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
```

Classify by reported duration:

```text
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

`primary` and `secondary` may change position. A missing 5h window is not 0% usage. A missing weekly window is not a fresh week.

## 6. Proven P0

On 2026-09-07 the feature branch completed a real server-side P0 against a ChatGPT Plus account.

The ephemeral runner:

1. used a pinned official OpenAI Codex CLI;
2. launched `codex app-server` in isolated temporary auth storage;
3. completed managed ChatGPT authorization;
4. waited for `account/login/completed` and then authenticated `account/updated`;
5. called `account/rateLimits/read`;
6. received a Plus `codex` rate-limit snapshot;
7. emitted only a sanitized proof;
8. deleted temporary auth state.

```text
P0_SERVER_SIDE_PLUS_QUOTA=PROVEN
```

This proves acquisition feasibility. It does **not** approve a production credential-storage design.

## 7. Auth readiness boundary

The P0 exposed an important race in official app-server sequencing. `account/login/completed` can arrive before the new managed auth is reloaded into the account processor. A quota read at that instant may return authentication required.

Production logic therefore waits for:

```text
account/login/completed(success=true)
        ↓
account/updated(authMode != null)
        ↓
account/rateLimits/read
```

Do not replace this readiness condition with an arbitrary sleep.

## 8. Automatic refresh policy

Refresh only when quota can change a decision:

```text
AUTO_QUOTA_REFRESH=BEFORE_AGENTIC_PASS
AUTO_QUOTA_REFRESH=AFTER_MEANINGFUL_AGENTIC_PASS
AUTO_QUOTA_REFRESH=WHEN_PENDING_BURN_MATTERS
AUTO_QUOTA_REFRESH=WHEN_SNAPSHOT_STALE
AUTO_QUOTA_REFRESH=ON_RESET_OR_EPOCH_SUSPECTED
```

Ordinary Chat planning/review does not need a quota fetch on every turn.

## 9. Freshness and failure

```text
QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>
```

- `FRESH`: suitable for quota-sensitive admission.
- `STALE`: refresh before a large class 2–4 pass.
- `UNAVAILABLE`: source cannot currently provide the needed fact/window.
- `CONFLICT`: snapshot contradicts known account/reset epoch state.
- `UNKNOWN`: semantics cannot be normalized safely.

Failure of automatic telemetry does not stop safe Chat work. Manual first-party snapshot is the last fallback when the next quota-sensitive decision cannot be made safely otherwise.

```text
MANUAL_QUOTA_INPUT_REQUIRED=NO
MANUAL_QUOTA_INPUT_ACCEPTED=YES
```

## 10. Pending burn

Immediate unchanged meter after a meaningful pass does not prove zero burn when aggregate reporting may lag.

```text
POST_PASS_METER_STATE=PENDING
PENDING_BURN=YES
```

A later fresh snapshot in the same epoch may resolve the aggregate delta under existing v2.2 compatibility/attribution rules.

## 11. Reset and epoch

Confirmed reset, materially changed reset boundary or allowance architecture change invalidates the previous anchor.

```text
QUOTA_EPOCH_EVENT=<NONE|RESET|PLAN_CHANGE|ALLOWANCE_CHANGE|UNKNOWN>
```

Never mix pre-reset trajectory values with post-reset telemetry.

## 12. Read-only boundary

Quota infrastructure may read current allowance facts. It must not:

- buy credits;
- trigger paid weekly reset;
- mutate spending controls;
- change Work/Codex permissions;
- choose surface/model/admission;
- expose auth material to the model;
- silently bind one ChatGPT subject to another account;
- reinterpret missing fields as known values.

```text
QUOTA_PLUGIN=READ_ONLY
PLUGIN_DECISION_AUTHORITY=NONE
FALSE_PRECISION=FORBIDDEN
```

## 13. Production credential lifecycle

P0 used ephemeral auth storage and deleted it. Production requires a separate audited lifecycle for each authenticated Plugin subject:

```text
SUBJECT_ACCOUNT_BINDING_AUDITED=YES
CREDENTIAL_ISOLATION_AUDITED=YES
TOKEN_REFRESH_TESTED=YES
TOKEN_REVOCATION_TESTED=YES
LOGOUT_PATH_TESTED=YES
```

Raw credentials must never enter tool arguments, model-visible output, logs or analytics payloads.

## 14. Backward compatibility

If Plugin telemetry is unavailable, the v2.2 normalized manual snapshot remains a fallback. The trajectory, burn estimator, quality floor, 5h breaker, bounded future advance and self-contained handoff semantics remain unchanged.

Automatic telemetry changes acquisition and UX, not the proven controller mathematics.
