# Weekly Work/Codex quota controller v4

**Policy version:** v4.0
**Verified:** 2026-09-24
**Status:** normative

The controller keeps the proven weekly percentage-point discipline from v2/v3, but paces by active working minutes instead of raw wall-clock hours.

```text
QUALITY_FLOOR=NON_NEGOTIABLE
ALLOWANCE_DOMAIN=WORK_CODEX
ACTIVE_LIMITS=DERIVED_FROM_CURRENT_SNAPSHOT
TASK_DURATION_LIMIT=NONE
```

The canonical schedule/runway math is in references/14_WORK_SCHEDULE_RUNWAY.md and scripts/v4_quota_controller.py.

## Weekly anchor

Keep one quota epoch until confirmed reset or material allowance change.

```text
ANCHOR_WEEKLY_USED_PP=<U0>
ANCHOR_ACTIVE_MINUTES_TO_RESET=<A0>
CURRENT_WEEKLY_USED_PP=<U>
CURRENT_ACTIVE_MINUTES_TO_RESET=<A>
```

Never recreate a full fresh budget after every pass.

## Active limits

Weekly is the primary runway. Any secondary limit is enforced only if current telemetry reports it. Missing secondary data is not synthesized and is not treated as zero or exhausted.

```text
SECONDARY_WINDOW_PRESENT=<YES|NO|UNKNOWN>
```

If YES, enforce it independently. If NO and the weekly window is valid, use weekly-only admission.

## Burn

Use observed compatible weekly meter deltas only. Do not convert public API prices, token counts or credit rate cards into weekly percentage points.

Compatibility dimensions are surface, canonical model id, reasoning effort, execution preset, task class and context band.

One or two observations require conservative bootstrap margins. Three to five may use robust median/MAD/P80 planning. Missing compatible history remains UNKNOWN.

## Headroom

Normal lookahead is one configured active workday; bounded advance is two. Subtract meter granularity and scheduled commitments. A future advance may protect critical-path pace but may not consume the rest of the week early.

## Quality

Quota pressure can only choose among independently sufficient execution candidates. If every candidate that fits quota is below the quality floor, defer the agentic pass and continue useful ChatGPT work.

## Pending burn

An unchanged aggregate meter immediately after meaningful execution does not prove zero burn. PENDING_BURN=YES blocks another large future advance until telemetry catches up or the next gate is safely small.

## Reference implementation

scripts/v4_quota_controller.py
