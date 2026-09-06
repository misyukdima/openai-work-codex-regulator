# Architecture

## v3.0 ChatGPT-first control plane

`v3.0` сохраняет проверенную математику `v2.2`, но меняет способ доставки quota state в оркестратор.

```text
User goal
  ↓
ChatGPT regulator (preferred control plane)
  ↓
class / surface / gate / WHY_AGENTIC
  ↓
quota-sensitive decision?
  ├─ no  → continue Chat work
  └─ yes → automatic quota telemetry
               ↓
          normalized Work/Codex snapshot
               ↓
          quota epoch + absolute cumulative trajectory
               ↓
          model/effort + B_SAFE + hard quality/safety gates
               ↓
          quota risk of launch ↔ pace risk of defer
                  equal priority (50/50)
               ↓
          LAUNCH_BASE / LAUNCH_WITH_ADVANCE /
          PROGRESS_ALTERNATIVE / DEFER
               ↓
          self-contained executor packet
               ↓
          Work or Codex
               ↓
          evidence + post-pass telemetry refresh
```

## Product invariants

```text
CHATGPT_PRIMARY_ORCHESTRATOR=YES
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
ZERO_MAINTENANCE_USER_SETUP=REQUIRED
```

The regulator still supports direct invocation inside Work/Codex, but normal product architecture assumes Chat is the main orchestrator.

## Cloud/local boundary

A cloud/browser ChatGPT session cannot be designed around direct access to a local binary or localhost service.

```text
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN
```

Therefore the ChatGPT-primary data path is:

```text
local quota sensor
        ↓
sanitize / normalize
        ↓
Chat-accessible connected app/tool
        ↓
get_quota_snapshot()
        ↓
ChatGPT regulator
```

The local sensor and transport are implementation details behind one normalized contract. They may change without rewriting the quota controller.

## Telemetry is a sensor, not a controller

```text
QUOTA_SENSOR=<CODEXBAR|OPENAI_DIRECT|OTHER|UNKNOWN>
```

The provider supplies facts such as used percentage, reset boundaries and timestamps. It does not decide:

- whether a pass launches;
- whether future advance is justified;
- which model/effort is sufficient;
- how urgent the project is;
- whether paid credits/reset should be used.

Those decisions remain in the regulator control plane.

## Reference CodexBar adapter

The first adapter accepts CodexBar-compatible structured JSON through `scripts/quota_telemetry.py`.

It intentionally does not authenticate to OpenAI itself, read raw auth files, purchase anything or call Work/Codex.

Window semantics are duration-based:

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS

300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
```

This prevents `primary`/`secondary` field order from becoming a false invariant.

## Automatic refresh lifecycle

```text
BEFORE_AGENTIC_PASS
        ↓
refresh if quota-sensitive
        ↓
admit / alternative / defer
        ↓
meaningful Work/Codex pass
        ↓
AFTER_MEANINGFUL_AGENTIC_PASS
        ↓
updated meter?
  ├─ yes → observed aggregate burn candidate
  └─ no  → PENDING_BURN=YES
```

Additional refresh occurs when snapshot is stale or reset/epoch drift is suspected.

Polling on every Chat message is explicitly unnecessary.

## Manual fallback

Manual quota input remains backwards-compatible but is no longer the normal workflow.

```text
MANUAL_QUOTA_INPUT_REQUIRED=NO
MANUAL_QUOTA_INPUT_ACCEPTED=YES
```

If automatic telemetry is unavailable, the regulator should continue meaningful non-agentic Chat work. It requests a manual first-party snapshot only if an actual quota-sensitive gate cannot be resolved safely without one.

## Control plane / execution plane separation

```text
ORCHESTRATION_MODE=<CHATGPT_PRIMARY|WORK_STANDALONE|CODEX_STANDALONE>
CONTROL_PLANE_OWNER=<CHAT|WORK|CODEX>
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

A downstream executor receives a complete bounded contract and never needs regulator installation just to understand the task.

Quota trajectory and telemetry fields are control-plane state and are not copied into ordinary Work/Codex prompts.

## Absolute weekly trajectory

The `v2.2` controller is retained unchanged conceptually.

At one epoch anchor:

```text
U0 = weekly used at anchor
H0 = hours to reset at anchor
```

A deterministic cumulative target `T(H)` defines how much allowance could have been spent when `H` hours remain. Because all future decisions refer to the same anchor, recomputing after a pass cannot create another full daily budget.

Normal launch headroom looks 24h forward:

```text
BASE_LOOKAHEAD_HOURS = 24
BASE_ACTION_HEADROOM_PP = T(H-24h) - actual_spend - reservations - meter_buffer
```

Bounded future advance looks at most 72h forward:

```text
MAX_ADVANCE_HOURS = 72
MAX_ADVANCE_HEADROOM_PP = T(H-72h) - actual_spend - reservations - meter_buffer
```

The 24h quantity remains a pacing target, not a hard sleep timer.

## Balanced admission

Hard constraints first:

```text
safety
permissions / authorization
QUALITY_FLOOR=NON_NEGOTIABLE
5h circuit breaker
```

Then equal priority:

```text
BALANCED_PRIORITY=QUOTA_50_PACE_50
```

If a pass needs future advance:

```text
QUOTA_RISK_IF_LAUNCH = needed_advance / borrowable_extra
PACE_RISK_IF_DEFER = 0..1
```

Launch with advance when quota risk is no greater than pace risk and the pass remains inside the bounded advance horizon.

## Reset / epoch handling

Automatic telemetry makes reset detection easier, but the invariant remains strict:

```text
confirmed reset or material reset-boundary change
        ↓
invalidate old trajectory anchor
        ↓
new QUOTA_EPOCH_ID
```

Never combine pre-reset anchor values with post-reset telemetry.

## Progress-preserving fallback

If full agentic launch loses the balanced comparison, or automatic telemetry is temporarily unavailable, the regulator searches for useful work that does not consume the same shared pool before pure waiting: Chat planning/review/handoff, accepted-evidence reuse, quality-preserving split, independent work or an already-approved non-shared surface.

## Standalone modes

The same normalized quota contract is portable:

```text
CODEX_STANDALONE
  local telemetry adapter
      ↓
  normalized snapshot
      ↓
  controller
```

```text
WORK_STANDALONE
  available connected telemetry tool
      ↓
  normalized snapshot
      ↓
  controller
```

Standalone support does not demote ChatGPT from the preferred product architecture.

## Zero-maintenance onboarding boundary

Final v3.0 is not release-ready while ordinary setup requires Terminal, Homebrew, separate CodexBar setup, token copy/paste, manual JSON/YAML, localhost/tunnel configuration or periodic quota messages.

This criterion is architectural, not cosmetic.

## Model architecture

```text
MODEL_PROFILE=TIERED
  MODEL_TIER=LUNA|TERRA|SOL

MODEL_PROFILE=ASTRA
  MODEL_TIER=N/A
```

Quota pressure cannot force a model below minimum sufficient quality.

## Normative layers

- `SKILL.md` — executable synthesis.
- `references/01` — routing and control-plane ownership.
- `references/02` — shared allowance / credits / reset facts.
- `references/03` — class 0–4.
- `references/04` — project runway / burn accounting.
- `references/05` — Work/browser/actions/schedules.
- `references/06` — Codex executor discipline.
- `references/07` — failures/recovery.
- `references/08` — model routing.
- `references/09` — Astra execution.
- `references/10` — balanced weekly quota + pace controller.
- `references/11` — orchestration / self-contained handoff.
- `references/12` — autonomous quota telemetry.
- `references/SOURCE_MAP.md` — provenance.

## Executable references

- `scripts/weekly_quota_controller.py` — anchored trajectory, burn estimator and balanced admission.
- `scripts/quota_telemetry.py` — telemetry normalization and freshness/window classification.

Repository validation imports both and runs deterministic self-tests.
