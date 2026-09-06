# Balanced weekly Work/Codex quota + workflow pace controller

**Policy version:** v2.2  
**Verified:** 2026-09-06  
**Status:** normative

This reference replaces v2.1's fixed 24h slice as a hard admission boundary. v2.2 keeps a 24h normal look-ahead but anchors all calculations to one cumulative weekly trajectory and gives quota continuity and workflow pace equal priority after hard safety/quality gates.

## 1. Required state

```text
ALLOWANCE_DOMAIN=WORK_CODEX
WEEKLY_METER_SEMANTICS=<USED|REMAINING>
TRAJECTORY_ANCHOR_WEEKLY_USED_PP=<U0>
TRAJECTORY_ANCHOR_HOURS_TO_RESET=<H0>
WEEKLY_USED_NOW=<U>
HOURS_TO_WEEKLY_RESET=<H>
WEEKLY_METER_GRANULARITY_PP=<g|unknown>
QUOTA_EPOCH_ID=<id>
```

If UI reports remaining, normalize:

```text
WEEKLY_USED = 100 - WEEKLY_REMAINING
```

Never infer an unlabeled meter's semantics. Never convert tokens/API prices/rate-card credits into weekly pp.

## 2. Epoch anchor

One epoch/controller anchor remains authoritative until confirmed reset or material allowance architecture change.

```text
QUOTA_EPOCH_EVENT=<NONE|RESET|PLAN_CHANGE|ALLOWANCE_CHANGE|UNKNOWN>
```

On a new epoch:

1. take a fresh first-party weekly meter/reset snapshot;
2. set new `U0` and `H0`;
3. invalidate old trajectory state;
4. revalidate burn-history compatibility;
5. preserve completed project gates/evidence.

Paid/banked reset remains a separate explicitly authorized action and creates a new epoch after it is actually applied.

## 3. Internal constants

```text
BASE_WEEKLY_RESERVE_PP = 10
RESERVE_FRACTION_CAP = 0.50
RESERVE_RELEASE_HOURS = 72
BASE_LOOKAHEAD_HOURS = 24
MAX_ADVANCE_HOURS = 72
```

These are regulator policies, not OpenAI limits.

## 4. Absolute cumulative trajectory

At anchor:

```text
R0 = max(0, 100 - U0)
Z0 = min(BASE_WEEKLY_RESERVE_PP, RESERVE_FRACTION_CAP * R0)
     * clamp(H0 / RESERVE_RELEASE_HOURS, 0, 1)
S0 = max(0, R0 - Z0)
```

For any current time with `0 <= H <= H0`:

```text
S_REMAINING(H) = S0 * H / H0

RELEASE_DENOMINATOR = min(RESERVE_RELEASE_HOURS, H0)
Z_REMAINING(H) = Z0 * clamp(H / RELEASE_DENOMINATOR, 0, 1)

T(H) = R0 - S_REMAINING(H) - Z_REMAINING(H)
```

`T(H)` is the absolute cumulative amount that the anchor trajectory would permit to have been spent by the moment `H` hours remain.

Critical property: because `T(H)` is anchored to `U0/H0`, recomputing after a pass does not reissue a new daily budget.

## 5. Normal 24h look-ahead

```text
ACTUAL = max(0, WEEKLY_USED_NOW - U0)
H_BASE = max(0, H - min(BASE_LOOKAHEAD_HOURS, H))
TARGET_BASE = T(H_BASE)

BASE_ACTION_HEADROOM_PP =
  max(0, TARGET_BASE - ACTUAL - reservations - g)
```

Fresh normalized 7-day example with `U0=0`, `H0=168`:

```text
BASE_ACTION_HEADROOM_PP = 12.857142857 pp
```

This preserves v2.1's useful first-day pacing reference without making 24 hours a mandatory waiting boundary.

## 6. Bounded future advance

When a quality-sufficient pass exceeds base headroom, calculate a bounded advance window rather than automatically waiting.

```text
H_ADVANCE = max(0, H - min(MAX_ADVANCE_HOURS, H))
TARGET_ADVANCE = T(H_ADVANCE)

MAX_ADVANCE_HEADROOM_PP =
  max(0, TARGET_ADVANCE - ACTUAL - reservations - g)

BORROWABLE_EXTRA_PP =
  max(0, MAX_ADVANCE_HEADROOM_PP - BASE_ACTION_HEADROOM_PP)
```

At a fresh 168h anchor with zero meter buffer/reservations:

```text
BASE_ACTION_HEADROOM_PP ≈ 12.8571
MAX_ADVANCE_HEADROOM_PP ≈ 38.5714
BORROWABLE_EXTRA_PP ≈ 25.7143
```

This does not authorize spending the rest of the week early. A pass above `MAX_ADVANCE_HEADROOM_PP` cannot be launched merely to preserve pace.

## 7. Burn estimator

Use at most five recent materially compatible observations.

```text
BURN_HISTORY_COMPATIBLE=<YES|NO|UNKNOWN>
BURN_SAMPLE_i=<weekly pp>
```

One sample:

```text
B_SAFE = x + max(g, 0.50*x)
```

Two samples:

```text
m = max(x1,x2)
B_SAFE = m + max(g, 0.25*m)
```

Three to five:

```text
M = median(samples)
MAD = median(abs(sample-M))
ROBUST_SIGMA = 1.4826*MAD
P80 = empirical 80th percentile
B_SAFE = max(P80, M + 1.645*ROBUST_SIGMA) + g
```

This is a conservative planning heuristic, not a statistical guarantee.

## 8. Equal-priority balanced admission

Hard prerequisites remain lexicographically stronger:

```text
safety
permissions/authorization
QUALITY_FLOOR=NON_NEGOTIABLE
5h circuit breaker
```

Only after they pass do quota continuity and workflow pace receive equal priority:

```text
BALANCED_PRIORITY=QUOTA_50_PACE_50
```

Normalize pace cost of deferral:

```text
PACE_RISK_IF_DEFER:
NONE     = 0.00
LOW      = 0.25
MEDIUM   = 0.50
HIGH     = 0.75
CRITICAL = 1.00
```

Interpretation:

- NONE/LOW — useful independent work remains or waiting has little process cost;
- MEDIUM — meaningful throughput/rework penalty;
- HIGH — blocks critical path or creates material idle time;
- CRITICAL — incident/deadline/revenue/production/reputation window is at risk.

Admission:

```text
if B_SAFE <= BASE_ACTION_HEADROOM_PP:
    QUOTA_DECISION=LAUNCH_BASE

else:
    NEEDED_ADVANCE_PP = B_SAFE - BASE_ACTION_HEADROOM_PP
```

If no bounded extra exists or `B_SAFE > MAX_ADVANCE_HEADROOM_PP`:

```text
QUOTA_DECISION=PROGRESS_ALTERNATIVE_OR_DEFER
```

Otherwise:

```text
QUOTA_RISK_IF_LAUNCH =
  clamp(NEEDED_ADVANCE_PP / BORROWABLE_EXTRA_PP, 0, 1)

LOSS_LAUNCH = QUOTA_RISK_IF_LAUNCH
LOSS_DEFER = PACE_RISK_IF_DEFER
```

Equal-priority decision:

```text
if LOSS_LAUNCH <= LOSS_DEFER:
    QUOTA_DECISION=LAUNCH_WITH_ADVANCE
else:
    QUOTA_DECISION=PROGRESS_ALTERNATIVE_OR_DEFER
```

A tie may launch if it closes the active gate. That is not a quota or pace bias: both normalized harms are equal.

## 9. Why this fixes the v2.1 stall failure

v2.1 used:

```text
B_SAFE <= EFFECTIVE_SLICE_HEADROOM_PP
```

as a hard launch gate. A quality pass just above the current 24h envelope could therefore force a full wait even when future weekly capacity and workflow criticality justified continuing.

v2.2 turns the 24h amount into the **normal target** and adds a bounded, risk-priced future advance. Waiting becomes one candidate action, not the default quota-preservation response.

## 10. Progress-preserving fallback

When full agentic launch loses the balanced comparison, do not automatically stop all work.

Check, in order:

1. duplicate work/context removal;
2. accepted evidence reuse;
3. natural same-gate batching;
4. quality-preserving split;
5. non-agentic Chat planning/review/handoff;
6. already-approved external/non-shared execution surface;
7. pure defer only if no meaningful productive path remains.

```text
MEANINGFUL_PROGRESS_WITHOUT_AGENTIC=<YES|NO|UNKNOWN>
```

## 11. Pending telemetry

```text
POST_PASS_METER_STATE=<UPDATED|PENDING|UNKNOWN>
PENDING_BURN=<YES|NO>
```

If aggregate telemetry plausibly has not reflected a prior meaningful pass:

- do not stack another large **future advance**;
- do not treat the unknown burn as zero;
- continue safe non-agentic progress when useful.

## 12. 5-hour circuit breaker

Weekly and 5h percentage points are separate denominators. A weekly `LAUNCH_WITH_ADVANCE` does not bypass an exhausted or unsafe 5h window.

Existing near-reset rule may still defer heavy non-incident work when the 5h reset is imminent.

## 13. Scheduled/parallel commitments

Subtract expected shared-pool commitments before calculating both base and max-advance headroom.

```text
SCHEDULED_WEEKLY_COMMITMENT_PP=<estimate|unknown>
EXPECTED_SHARED_BURN_DURING_LOOKAHEAD_PP=<estimate|unknown>
```

Never double-allocate the same future allowance.

## 14. Quality floor

Quota/pace balancing cannot weaken:

- minimum sufficient model;
- required authoritative sources;
- tests/verification;
- security baseline;
- rollback requirements;
- exact action/permission boundaries.

If a candidate is below quality floor:

```text
QUOTA_DECISION=DEFER_FOR_QUALITY
```

regardless of pace risk.

## 15. Reference implementation

```text
scripts/weekly_quota_controller.py
```

The validator imports it and executes deterministic self-tests for:

- fresh-week base look-ahead;
- absolute trajectory no-reissue behavior;
- continuous accrual without 24h boundary;
- scheduled reservations;
- robust burn estimator;
- high-pace advance vs low-pace defer;
- equal-risk tie;
- max-advance rejection;
- hard quality floor.

## 16. Official sources

- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/20001507-paid-weekly-work-and-codex-rate-limit-resets
- https://help.openai.com/en/articles/20001478-reviewing-work-and-codex-usage-and-using-personal-analytics-in-chatgpt-desktop
- https://help.openai.com/en/articles/12642688
