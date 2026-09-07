# Architecture

## v3.0: ChatGPT Web as the only control plane

The v3.0 skill runs in ChatGPT Web. Work and Codex do the execution work, but they do not load the regulator.

```text
User goal
  ↓
ChatGPT Web + Regulator Skill
  ↓
class / gate / surface / model
  ↓
quota-sensitive decision?
  ├─ no  → continue Chat work
  └─ yes → get_quota_snapshot()
               ↓
          Regulator Quota Plugin/App
               ↓
          server-side quota backend
               ↓
          official codex app-server
               ↓
          account/rateLimits/read
               ↓
          normalized Work/Codex snapshot
               ↓
          v2.2 quota controller
               ↓
          Work or Codex handoff
               ↓
          evidence back to ChatGPT
```

## Product invariants

```text
SKILL_RUNTIME=CHATGPT_WEB_ONLY
ORCHESTRATION_MODE=CHATGPT_WEB
CONTROL_PLANE_OWNER=CHAT
WORK_CODEX_ROLE=EXECUTION_PLANE
CHATGPT_PRIMARY_ORCHESTRATOR=YES
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
USER_SETUP_AFTER_ZIP=NONE
PLUGIN_AUTH=JUST_IN_TIME
LOCAL_SOFTWARE_REQUIRED=NO
OS_DEPENDENCY=NO
```

There is no production standalone skill mode in Work or Codex.

## Bootstrap and authorization

The intended user path is short:

```text
GitHub Release ZIP
  ↓
attach to ChatGPT Web
  ↓
normal work begins
```

Plugin authorization is deferred until quota actually affects a decision. If already connected, the read is silent from the user's point of view. If not, ChatGPT surfaces the normal Connect/Auth experience.

The ZIP cannot grant itself account permissions. The Plugin/App owns the authenticated read boundary.

## No local bridge

The production architecture does not depend on the user's operating system.

```text
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN
LOCAL_COMPANION_REQUIRED=NO
CODEXBAR_USER_PREREQUISITE=NO
LOCALHOST_REQUIRED=NO
```

Earlier Companion/CodexBar/relay code on the feature branch is research history, not a release dependency.

## Plugin is a sensor, not a controller

The Plugin exposes one model-facing capability:

```text
get_quota_snapshot()
```

It supplies facts such as used percentage, reset time, plan class, credits state and additional windows when the source returns them. It does not decide:

- Work vs Codex;
- model/effort;
- future advance;
- pace risk;
- purchase/reset actions;
- project priority.

```text
QUOTA_PLUGIN=READ_ONLY
PLUGIN_DECISION_AUTHORITY=NONE
```

## Proven server-side acquisition

P0 on 2026-09-07 proved the remote Plus path with official OpenAI Codex:

```text
managed ChatGPT authorization
  ↓
account/login/completed
  ↓
account/updated
  ↓
account/rateLimits/read
  ↓
Plus codex rate-limit snapshot
```

The `account/updated` step is important. The P0 discovered that login completion can precede managed auth reload; waiting for the account update removes that race without an arbitrary delay.

P0 used ephemeral credentials and deleted the temporary auth state. This proves quota acquisition, not production credential persistence.

## Server-side backend

`plugin/quota_backend.py` is the current backend core. It contains:

- minimal JSON-RPC client for official `codex app-server`;
- managed auth readiness handling;
- read-only rate-limit retrieval;
- `codex` bucket selection;
- duration-based window normalization;
- secret-field exclusion self-test.

It deliberately does not expose a public production server yet. Identity, credential storage and ChatGPT Plugin transport are separate release gates.

## Window semantics

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS

300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

The P0 itself returned a weekly window without a 5h window. That is a valid source state. Missing data remains missing.

## Automatic refresh lifecycle

```text
BEFORE_AGENTIC_PASS
        ↓
fetch if quota-sensitive
        ↓
admit / alternative / defer
        ↓
meaningful Work/Codex pass
        ↓
AFTER_MEANINGFUL_AGENTIC_PASS
        ↓
updated meter?
  ├─ yes → aggregate burn candidate
  └─ no  → PENDING_BURN=YES
```

Also refresh on stale data, reset/epoch suspicion or when pending burn materially affects another large pass. Do not poll on every ordinary Chat turn.

## Manual fallback

```text
MANUAL_QUOTA_INPUT_REQUIRED=NO
MANUAL_QUOTA_INPUT_ACCEPTED=YES
```

If Plugin telemetry is unavailable, ChatGPT should continue useful planning/review/handoff first. Request a manual first-party snapshot only when the next quota-sensitive decision has no safe alternative.

## Control plane and execution plane

```text
ChatGPT regulator
  ↓
quota / routing / model / admission
  ↓
self-contained execution packet
  ↓
Work or Codex
  ↓
execution + evidence
  ↓
ChatGPT regulator
```

Quota trajectory, Plugin internals and risk scores stay out of ordinary executor prompts.

## v2.2 controller remains authoritative

At one quota epoch anchor:

```text
U0 = weekly used at anchor
H0 = hours to reset at anchor
```

Normal 24h look-ahead:

```text
BASE_LOOKAHEAD_HOURS = 24
BASE_ACTION_HEADROOM_PP = T(H-24h) - actual_spend - reservations - meter_buffer
```

Maximum bounded advance:

```text
MAX_ADVANCE_HOURS = 72
MAX_ADVANCE_HEADROOM_PP = T(H-72h) - actual_spend - reservations - meter_buffer
```

This is one cumulative trajectory. Recomputing after a pass cannot mint a new daily budget.

## Balanced admission

Hard constraints first:

```text
safety
permissions / authorization
QUALITY_FLOOR=NON_NEGOTIABLE
confirmed 5h breaker
```

Then:

```text
BALANCED_PRIORITY=QUOTA_50_PACE_50
```

Future advance is allowed only inside the bounded horizon and only when quota risk of launch is no greater than workflow risk of deferral.

## Credential architecture

The production backend must bind ChatGPT Plugin subject to the authorized OpenAI/Codex account outside model arguments.

Required release properties:

```text
SUBJECT_ACCOUNT_BINDING_AUDITED=YES
CREDENTIAL_ISOLATION_AUDITED=YES
ENCRYPTION_AT_REST_REQUIRED=YES
TOKEN_REFRESH_TESTED=YES
TOKEN_REVOCATION_TESTED=YES
LOGOUT_PATH_TESTED=YES
CROSS_SUBJECT_READ=FORBIDDEN
```

The model never receives raw credentials.

## Normative layers

- `SKILL.md`: executable ChatGPT Web contract.
- `references/01`–`11`: routing, risk, safety, controller and handoff rules retained from previous releases where compatible.
- `references/12_AUTONOMOUS_QUOTA_TELEMETRY.md`: Web-only automatic quota semantics.
- `references/13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md`: Plugin/backend boundary.
- `references/SOURCE_MAP.md`: provenance and time-sensitive facts.

## Executable references

- `scripts/weekly_quota_controller.py`: anchored trajectory, burn estimator and balanced admission.
- `scripts/quota_telemetry.py`: pure window/freshness normalization.
- `plugin/quota_backend.py`: official Codex server-side quota backend core.

CI runs deterministic self-tests for these components without requiring user credentials.

## Release boundary

The feature branch is not ready for `main` until a real ChatGPT Web flow completes:

```text
ZIP → ChatGPT Web → Connect/Auth → get_quota_snapshot() → controller → handoff
```

That path must pass security review, cross-user isolation tests and credential refresh/revoke tests before Pull Request.
