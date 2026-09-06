# Architecture

## v2.2 control plane

```text
User goal
  ↓
Regulator on current surface (normally Chat)
  ↓
class / surface / gate / WHY_AGENTIC
  ↓
shared Work/Codex allowance snapshot
  ↓
quota epoch + absolute cumulative trajectory
  ↓
model/effort + B_SAFE + hard quality/safety gates
  ↓
quota risk of launch  ↔  pace risk of defer
          equal priority (50/50)
  ↓
LAUNCH_BASE / LAUNCH_WITH_ADVANCE /
PROGRESS_ALTERNATIVE / DEFER
  ↓
self-contained executor packet
  ↓
Work or Codex executes without regulator dependency
  ↓
evidence + aggregate usage
  ↓
control plane updates project/quota state
```

## Control plane / execution plane separation

v2.2 makes orchestration ownership explicit:

```text
CONTROL_PLANE_OWNER=<CHAT|WORK|CODEX>
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

The surface with the regulator resolves quota/model/admission. A downstream executor receives a complete bounded contract and never needs the regulator merely to understand the task.

Quota trajectory fields are control-plane state and are not copied into ordinary Work/Codex prompts.

## Absolute weekly trajectory

v2.1 used fixed 24h slices. v2.2 uses one epoch anchor:

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

The 24h quantity is therefore a pacing target, not a hard sleep timer.

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

This directly fixes the v2.1 failure mode where a pass just above the 24h envelope could force an idle day even while the project critical path was blocked.

## Progress-preserving fallback

If full agentic launch loses the balanced comparison, the regulator searches for useful work that does not consume the same shared pool before pure waiting: Chat planning/review/handoff, accepted-evidence reuse, quality-preserving split, independent work or an already-approved non-shared surface.

## Two runways

Project runway and quota runway remain separate. Failed attempts can preserve project gate count while still consuming aggregate allowance.

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
- `references/SOURCE_MAP.md` — provenance.

## Executable reference

`scripts/weekly_quota_controller.py` implements the anchored trajectory, burn estimator and balanced admission. Repository validation imports it and runs deterministic self-tests.
