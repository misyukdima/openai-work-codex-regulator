# Weekly Work/Codex quota controller v4

**Policy version:** v4.0
**Verified:** 2026-09-24
**Status:** normative

The controller keeps weekly percentage-point accounting but paces by active working minutes instead of raw wall-clock hours.

```text
QUALITY_FLOOR=NON_NEGOTIABLE
ALLOWANCE_DOMAIN=WORK_CODEX
ACTIVE_LIMITS=DERIVED_FROM_CURRENT_SNAPSHOT
TASK_DURATION_LIMIT=NONE
```

The canonical implementation is scripts/v4_quota_controller.py.

## Weekly anchor

Keep one quota epoch until confirmed reset or material allowance change.

```text
ANCHOR_WEEKLY_USED_PP=<U0>
ANCHOR_ACTIVE_MINUTES_TO_RESET=<A0>
CURRENT_WEEKLY_USED_PP=<U>
CURRENT_ACTIVE_MINUTES_TO_RESET=<A>
```

Do not reissue a fresh daily budget after each pass. Off-hours do not consume planned runway.

## Schedule

Default local schedule:

```text
09:00 start
22:00 normal soft end
23:00 hard extension end
MON-SUN
```

User configuration overrides these defaults. Normal base lookahead uses the soft-day duration; bounded future advance may use the hard-window duration.

## Reserve and headroom

Project policy:

```text
BASE_WEEKLY_RESERVE_PP=10
RESERVE_FRACTION_CAP=0.50
RESERVE_RELEASE_ACTIVE_MINUTES=360
BASE_LOOKAHEAD_WORKDAYS=1
MAX_ADVANCE_WORKDAYS=2
```

The reserve releases over the final six active hours. Headroom subtracts observed spend since anchor, meter granularity and already-admitted commitments.

## Burn estimator

Use at most five recent materially compatible weekly-pp observations.

One sample:

```text
B_SAFE = x + max(g, 0.50*x)
```

Two samples:

```text
m=max(x1,x2)
B_SAFE=m+max(g,0.25*m)
```

Three to five:

```text
M=median(samples)
MAD=median(abs(sample-M))
ROBUST_SIGMA=1.4826*MAD
P80=empirical 80th percentile
B_SAFE=max(P80,M+1.645*ROBUST_SIGMA)+g
```

This is conservative project policy, not a statistical guarantee. Never convert API prices/tokens into weekly pp.

## Admission

Safety, authorization and quality are stronger than quota pacing.

If quality is insufficient:

```text
DEFER_FOR_QUALITY
```

If burn is unknown:

```text
CALIBRATE_OR_PREPARE
```

If safe burn fits normal active-time headroom:

```text
LAUNCH_BASE
```

Otherwise compare the required bounded future advance with pace risk. A gate may use LAUNCH_WITH_ADVANCE only inside max active-time headroom and when the quota risk is no greater than the project cost of deferral.

This preserves useful flow without making the allowance unlimited.

## Active secondary limits

Weekly is the primary runway. Any secondary limit is enforced only if current telemetry reports it. If a valid weekly snapshot contains no secondary window, use weekly-only admission.

Different window percentages are never added.

## Pending burn

Immediate unchanged aggregate usage does not prove zero burn. PENDING_BURN=YES prevents stacking another large future advance until telemetry resolves or the next pass is safely bounded.

## Progress-preserving fallback

Before pure waiting: remove duplicate work/context, reuse accepted evidence, batch naturally dependent steps, continue ChatGPT planning/review/handoff, and defer only when no quality-preserving productive path remains.
