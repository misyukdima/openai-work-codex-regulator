# Architecture

## v2.1 decision pipeline

```text
User goal
  ↓
Need agentic Work/Codex?
  ├─ no → CHAT
  └─ yes
       ↓
Class 1–4 + primary surface
       ↓
WHY_AGENTIC / VALUE_OUTPUT
       ↓
Allowance domain = WORK_CODEX
       ↓
Quota epoch
  current weekly meter + actual reset
       ↓
Adaptive fixed 24h control slice
  reserve / release / spent / headroom
       ↓
Project runway
       ↓
Capability / permissions
       ↓
Model profile / tier / effort
       ↓
Quality floor
  QUALITY_FLOOR=NON_NEGOTIABLE
       ↓
Conservative pass burn B_SAFE
       ↓
Weekly admission + separate 5h circuit breaker
       ↓
Astra admission if applicable
       ↓
Scope / approvals / tests / rollback
       ↓
Run
       ↓
Post-pass aggregate meter
       ↓
Update slice + burn history + project runway
```

## Two runway systems

v2.1 keeps two distinct state machines.

### Project runway

Answers:

```text
How many meaningful gates/passes remain before project readiness?
```

A failed attempt does not automatically reduce this count.

### Quota runway

Answers:

```text
How much shared Work/Codex allowance can be safely used before the weekly reset?
```

Any actual shared-pool burn reduces quota runway even when the project gate failed.

This separation prevents failed attempts from disappearing from quota accounting.

## Quota epoch

```text
QUOTA_EPOCH_ID
```

A quota epoch ends on a confirmed weekly reset or material allowance architecture change.

Normal reset, paid instant reset, applied banked/promotional reset or plan/allowance change invalidates:

```text
CONTROL_SLICE_ID
CONTROL_SLICE_START_WEEKLY_USED_PP
CONTROL_SLICE_BUDGET_PP
SLICE_SPENT_PP
EFFECTIVE_SLICE_HEADROOM_PP
```

Project evidence and completed gates survive the reset.

## Adaptive 24h controller

At an anchor:

```text
U = weekly used percentage points
R = 100 - U
H = hours to reset
```

Internal constants:

```text
BASE_WEEKLY_RESERVE_PP = 10
RESERVE_FRACTION_CAP = 0.50
RESERVE_RELEASE_HOURS = 72
CONTROL_SLICE_HOURS = 24
```

Held reserve:

```text
reserve_cap = min(10, 0.50 * R)
Z(H) = reserve_cap * clamp(H / 72, 0, 1)
```

Slice:

```text
h = min(24, H)
S = max(0, R - Z(H))

budget =
  S * h/H
  + max(0, Z(H) - Z(H-h))
```

For a fresh seven-day window:

```text
budget = 90 * 24 / 168 = 12.857142857 pp
```

The reserve is held early for robustness and released through the final 72h.

## Why slices are fixed

The slice budget is anchored once per control slice.

Within it:

```text
spent = current_weekly_used - slice_start_weekly_used
headroom = slice_budget - spent
```

The regulator must not recompute a fresh full 24h budget after each pass. Otherwise every pass can incorrectly consume a new fraction of the same future allowance.

## Feedback

The next slice is recalculated from actual first-party state:

- under-spend → next slice expands;
- over-spend → next slice contracts;
- on-plan → approximate trajectory remains stable;
- reset → new quota epoch.

The controller therefore does not need a hardcoded model-to-weekly-% coefficient.

## Aggregate meter vs attribution

Two questions are deliberately separated:

```text
Attribution: who spent the allowance?
Continuity: how much total shared allowance remains?
```

A `MIXED` interval cannot be exact burn attribution for one pass, but its total weekly meter increase still reduces shared slice headroom.

This lets Work, Codex and other confirmed shared-pool activity coexist without losing total-quota control.

## Conservative pass estimator

`references/10_WEEKLY_QUOTA_CONTROLLER.md` defines `B_SAFE` from up to five compatible observations.

Sparse data receives large bootstrap margins. With 3–5 samples the controller uses median/MAD and empirical P80.

The estimator is intentionally robust to a small outlier set. It is a planning heuristic, not a statistical guarantee.

## Quality-first admission

```text
QUALITY_FLOOR=NON_NEGOTIABLE
```

Quota can reduce waste, repeated context, duplicate research or optional work.

It cannot reduce:

- minimum sufficient model capability;
- required authoritative evidence;
- tests/verification;
- security baseline;
- rollback requirements.

If the quality-sufficient pass does not fit:

```text
QUOTA_DECISION=DEFER_FOR_QUALITY
```

## 5h constraint

Weekly and 5h percentages have different denominators.

The weekly controller is therefore intersected with a separate 5h circuit breaker where the account exposes one. A pass must fit both.

## Pending telemetry

Usage reporting can lag. After meaningful class 2–4 work:

```text
POST_PASS_METER_STATE=UPDATED|PENDING|UNKNOWN
PENDING_BURN=YES|NO
```

A large next pass is not stacked on a plausibly stale aggregate meter.

## Scheduled reservations

Recurring/triggered work reserves capacity before interactive admission:

```text
AVAILABLE_FOR_INTERACTIVE_WORK_PP =
  EFFECTIVE_SLICE_HEADROOM_PP
  - expected scheduled burn before slice end
```

No double allocation.

## Model architecture

v2.1 preserves v2.0's two-axis model router:

```text
MODEL_PROFILE=TIERED
  MODEL_TIER=LUNA|TERRA|SOL

MODEL_PROFILE=ASTRA
  MODEL_TIER=N/A
```

The quota controller runs before model admission but does not force an insufficient model. If Astra/Sol is minimum sufficient and does not fit, the pass defers or is quality-preservingly re-scoped.

## Normative layers

- `SKILL.md` — executable synthesis.
- `references/01` — surface routing.
- `references/02` — shared allowance / credits / reset facts.
- `references/03` — class 0–4.
- `references/04` — project runway / burn accounting.
- `references/05` — Work/browser/actions/schedules.
- `references/06` — Codex technical discipline.
- `references/07` — failure recovery.
- `references/08` — tier/model routing.
- `references/09` — Astra execution.
- `references/10` — adaptive weekly quota controller.
- `references/SOURCE_MAP.md` — first-party provenance.

## Executable reference

```text
scripts/weekly_quota_controller.py
```

The repository validator imports it and runs deterministic self-tests so the release fails closed if the mathematical reference implementation regresses.
