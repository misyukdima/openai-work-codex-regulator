# Autonomous quota telemetry for ChatGPT-first orchestration

**Target version:** v3.0  
**Status:** normative development contract

v3.0 removes routine quota bookkeeping from the user. The regulator should acquire current Work/Codex allowance automatically whenever the active surface can access a supported telemetry tool. Manual quota input remains accepted, but only as a fallback when automatic telemetry is unavailable or cannot be trusted.

## 1. Product intent

```text
CHATGPT_PRIMARY_ORCHESTRATOR=YES
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
ZERO_MAINTENANCE_USER_SETUP=REQUIRED
```

The normal user workflow is:

```text
user goal
  ↓
ChatGPT regulator
  ↓
automatic quota refresh when needed
  ↓
v2.2 trajectory + burn controller
  ↓
Work / Codex admission and self-contained handoff
```

The user should not be asked to open Usage, copy percentages, calculate reset time or periodically resend quota state during ordinary operation.

## 2. ChatGPT remains the preferred control plane

The regulator continues to support direct invocation in Work or Codex, but the primary architecture is ChatGPT-first:

```text
ORCHESTRATION_MODE=<CHATGPT_PRIMARY|WORK_STANDALONE|CODEX_STANDALONE>
CONTROL_PLANE_OWNER=<CHAT|WORK|CODEX>
```

When `ORCHESTRATION_MODE=CHATGPT_PRIMARY`:

- Chat resolves routing, model/effort, quota admission, pace risk and project runway;
- Work and Codex remain execution surfaces;
- quota telemetry is input to Chat's decision, never a second controller;
- downstream executors still receive self-contained packets and do not need this skill.

## 3. Cloud/local boundary

A browser/cloud ChatGPT session must never assume it can execute a local binary, read a local file or reach `127.0.0.1` on the user's computer.

```text
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN
```

Therefore automatic telemetry for ChatGPT requires a Chat-accessible tool or connected app that exposes a sanitized current snapshot.

Conceptually:

```text
local sensor
   ↓
sanitized snapshot
   ↓
remote/readable quota tool
   ↓
ChatGPT regulator
```

The transport may evolve independently from the regulator. The skill depends on the normalized tool contract, not on one specific local implementation.

## 4. Normalized quota tool

Preferred tool contract:

```text
get_quota_snapshot()
```

Minimum successful result:

```text
ALLOWANCE_DOMAIN=WORK_CODEX
SNAPSHOT_AT=<timestamp>
QUOTA_TELEMETRY_SOURCE=<provider>
QUOTA_TELEMETRY_FRESHNESS=<FRESH|STALE|UNKNOWN>
WEEKLY_METER_SEMANTICS=USED
WEEKLY_USED=<percent>
WEEKLY_RESET=<time|unknown>
FIVE_HOUR_USED=<percent|unknown>
FIVE_HOUR_RESET=<time|unknown>
```

Optional fields may include meter granularity, plan class, credits and provider confidence when they are available without exposing secrets or unnecessary personal data.

The tool must not return OAuth tokens, cookies, bearer headers, private prompts, chat content or raw authentication files.

## 5. Local sensors and providers

The first reference provider is CodexBar-compatible telemetry because CodexBar can expose Codex usage in structured JSON and can use a read-only OAuth usage path.

This is an implementation detail, not a permanent dependency:

```text
QUOTA_SENSOR=<CODEXBAR|OPENAI_DIRECT|OTHER|UNKNOWN>
```

The regulator must not require the user to understand or manually operate CodexBar. A future companion/plugin may bundle or replace the provider completely.

For CodexBar-like payloads, window position is not semantic truth:

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
```

Classify by reported window duration:

```text
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
```

Never assume `primary=5h` and `secondary=weekly`.

## 6. Automatic refresh policy

Do not poll quota on every Chat message. Refresh when quota can materially affect a decision:

```text
AUTO_QUOTA_REFRESH=BEFORE_AGENTIC_PASS
AUTO_QUOTA_REFRESH=AFTER_MEANINGFUL_AGENTIC_PASS
AUTO_QUOTA_REFRESH=WHEN_PENDING_BURN_MATTERS
AUTO_QUOTA_REFRESH=WHEN_SNAPSHOT_STALE
AUTO_QUOTA_REFRESH=ON_RESET_OR_EPOCH_SUSPECTED
```

Ordinary bounded Chat planning, explanation and review do not require a quota fetch unless the next decision depends on quota state.

## 7. Freshness and failure

Normalized state:

```text
QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>
```

- `FRESH` — suitable for quota-sensitive admission;
- `STALE` — may be shown for context but should be refreshed before a large class 2–4 pass;
- `UNAVAILABLE` — automatic source cannot currently be read;
- `CONFLICT` — telemetry contradicts a known reset/account epoch boundary;
- `UNKNOWN` — semantics cannot be normalized safely.

If automatic telemetry fails, do not stop non-agentic Chat work. Use the progress-preserving fallback ladder. Ask the user for a manual first-party snapshot only when a quota-sensitive decision cannot be made safely without it.

```text
MANUAL_QUOTA_INPUT_REQUIRED=NO
MANUAL_QUOTA_INPUT_ACCEPTED=YES
```

## 8. Pending burn

An unchanged meter immediately after a meaningful Work/Codex pass does not prove zero burn.

```text
if post_pass_snapshot == pre_pass_snapshot and reporting_may_lag:
    PENDING_BURN=YES
```

When a later fresh snapshot advances inside the same quota epoch, the aggregate delta can become an observed burn sample. Existing v2.2 compatibility/attribution rules still apply.

## 9. Reset and epoch handling

A confirmed reset, materially changed reset timestamp or allowance architecture change invalidates the old trajectory anchor.

```text
QUOTA_EPOCH_EVENT=<NONE|RESET|PLAN_CHANGE|ALLOWANCE_CHANGE|UNKNOWN>
```

Do not combine pre-reset anchor values with post-reset telemetry. Re-anchor the v2.2 controller from the new normalized snapshot.

## 10. Standalone Work/Codex

When the regulator is invoked directly in a local environment that has shell/tool access, the same normalized contract may be fulfilled directly by a local adapter.

```text
CODEX_STANDALONE:
local telemetry adapter → normalized snapshot → controller

WORK_STANDALONE:
available connected telemetry tool → normalized snapshot → controller
```

Standalone support does not change the preferred ChatGPT-first architecture.

## 11. Zero-friction installation requirement

The final v3.0 user experience is not considered complete if routine setup requires the user to:

- open Terminal;
- install Homebrew;
- install or configure CodexBar separately;
- edit JSON/YAML;
- copy OAuth/API tokens;
- configure localhost ports;
- configure a tunnel manually;
- understand MCP internals;
- periodically resend quota values to ChatGPT.

The intended product surface is one Regulator installation/setup flow with automatic health checks and repair guidance.

## 12. Security boundary

Telemetry infrastructure is a read-only sensor path.

It must not:

- buy credits or trigger paid resets;
- mutate account settings;
- expose auth material to ChatGPT;
- expand Work/Codex permissions;
- become an admission controller;
- silently select a different account/workspace;
- execute downloaded code as part of a quota read.

The regulator remains the only component that applies quota/pace policy.

## 13. Backward compatibility

If automatic telemetry is unavailable, v3.0 falls back to the existing normalized manual snapshot contract. The v2.2 trajectory, burn estimator, quality floor, 5h breaker, bounded future advance and self-contained handoff semantics remain valid.

This makes automatic telemetry a major usability/architecture upgrade without replacing the proven controller mathematics.
