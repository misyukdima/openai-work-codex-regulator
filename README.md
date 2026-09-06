# OpenAI Work + Codex Regulator

**Version:** v2.2

`openai-work-codex-regulator` — operational skill for ChatGPT orchestration across Chat, Work and Codex with shared Work/Codex quota awareness, quality/safety controls and evidence-based execution.

## v2.2: balanced quota + workflow pace

v2.1 successfully prevented front-loading but treated the current 24h quota slice too much like a hard launch boundary. In real testing that could preserve weekly allowance at the cost of a 24h workflow stall.

v2.2 changes the objective:

```text
hard safety + quality
        ↓
quota continuity  =  workflow pace
        50%               50%
```

A 24h amount is now the **normal look-ahead target**, not a mandatory wait timer.

The controller uses one epoch-anchored cumulative trajectory:

```text
weekly meter/reset
→ quota epoch anchor
→ absolute target trajectory T(H)
→ 24h base action headroom
→ bounded 72h future advance
→ B_SAFE
→ quota-risk vs pace-risk comparison
→ launch / launch-with-advance / productive alternative / defer
```

## Why the trajectory is safer than reissuing daily budgets

All decisions stay tied to the same `U0/H0` anchor until reset/allowance change. After a pass, actual shared burn is subtracted from the same cumulative curve; recomputing does not create another full daily allowance.

Fresh normalized 7-day reference:

```text
BASE_ACTION_HEADROOM_PP ≈ 12.8571
MAX_ADVANCE_HEADROOM_PP ≈ 38.5714
```

The second number is only the bounded future-advance ceiling, not normal day-one spending.

## Equal-priority admission

```text
BALANCED_PRIORITY=QUOTA_50_PACE_50
```

Pace risk:

```text
NONE=0.00
LOW=0.25
MEDIUM=0.50
HIGH=0.75
CRITICAL=1.00
```

For a pass above base headroom:

```text
QUOTA_RISK_IF_LAUNCH = needed_advance / borrowable_extra
```

If the quality-sufficient pass remains inside max advance and quota risk is no greater than pace risk of waiting:

```text
QUOTA_DECISION=LAUNCH_WITH_ADVANCE
```

This prevents automatic 24h idle periods when the active gate blocks the project's critical path.

## Control plane / execution plane

v2.2 also fixes cross-surface orchestration:

```text
CONTROL_PLANE_OWNER=<surface with regulator>
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

If Chat has the regulator and routes work to Codex, Chat resolves quota/model/admission and sends a complete technical packet. Codex does **not** need this skill installed and must not be told to load it as a prerequisite.

Quota trajectory/risk math stays in Chat. Executor prompt carries only goal, accepted fact pack, scope, tests/evidence, rollback and stop conditions.

Detailed handoff contract: `references/11_ORCHESTRATION_AND_HANDOFF.md`.

## Progress-preserving fallback

When a full agentic pass should not launch, v2.2 does not jump straight to waiting. It checks for meaningful Chat planning/review/handoff, accepted-evidence reuse, quality-preserving split/batching or an already-approved non-shared execution path.

```text
MEANINGFUL_PROGRESS_WITHOUT_AGENTIC=<YES|NO|UNKNOWN>
```

Pure defer is the last option when no quality-preserving useful progress remains.

## Quality / safety remain hard constraints

```text
QUALITY_FLOOR=NON_NEGOTIABLE
```

Equal quota/pace priority does not weaken permissions, target authorization, 5h limits, mandatory sources/tests, security baseline, rollback or minimum sufficient model capability.

## Shared allowance

```text
ALLOWANCE_DOMAIN=WORK_CODEX
```

Work, Codex and other supported agentic features may share allowance. Chat-model allowances/API billing are separate and are not treated as spare Work/Codex capacity.

## Model architecture

```text
MODEL_PROFILE=TIERED
  LUNA  = routine/high-volume
  TERRA = balanced default
  SOL   = consequential synthesis

MODEL_PROFILE=ASTRA
  exceptional bounded end-to-end work
```

Quota pressure may select cheaper options only when they remain independently sufficient.

## Repository structure

```text
SKILL.md
references/
  01_SURFACE_ROUTING.md
  02_SHARED_QUOTA_AND_CREDITS.md
  03_TASK_CLASSIFICATION.md
  04_RUNWAY_AND_BURN.md
  05_WORK_BROWSER_AND_ACTIONS.md
  06_CODEX_TECHNICAL_WORK.md
  07_FAILURES_AND_RECOVERY.md
  08_MODEL_TIER_ROUTING.md
  09_ASTRA_EXECUTION.md
  10_WEEKLY_QUOTA_CONTROLLER.md
  11_ORCHESTRATION_AND_HANDOFF.md
  SOURCE_MAP.md
docs/
scripts/
  validate_repo.py
  package_release.py
  weekly_quota_controller.py
tests/
  TEST_CASES.md
  TEST_CASES_V2_2.md
```

## Validation

```bash
python3 scripts/validate_repo.py
python3 scripts/weekly_quota_controller.py \
  --anchor-weekly-used 0 \
  --anchor-hours-to-reset 168 \
  --hours-to-reset-now 168 \
  --current-weekly-used 0 \
  --self-test
python3 scripts/package_release.py
```

Product/model/usage facts are time-sensitive. Current first-party OpenAI docs and actual account/workspace UI remain authoritative.
