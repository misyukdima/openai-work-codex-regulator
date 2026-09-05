#!/usr/bin/env python3
"""Reference implementation for the v2.1 adaptive weekly Work/Codex quota controller.

The controller operates only on normalized first-party weekly percentage points.
It intentionally does not convert token counts or rate-card prices into weekly usage.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

BASE_WEEKLY_RESERVE_PP = 10.0
RESERVE_FRACTION_CAP = 0.50
RESERVE_RELEASE_HOURS = 72.0
CONTROL_SLICE_HOURS = 24.0
DEFAULT_METER_GRANULARITY_PP = 1.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def reserve_schedule_pp(weekly_remaining_pp: float, hours_to_reset: float) -> float:
    """Return the reserve still held at the current point in the weekly epoch."""
    remaining = clamp(float(weekly_remaining_pp), 0.0, 100.0)
    hours = max(0.0, float(hours_to_reset))
    reserve_cap = min(BASE_WEEKLY_RESERVE_PP, RESERVE_FRACTION_CAP * remaining)
    release_factor = clamp(hours / RESERVE_RELEASE_HOURS, 0.0, 1.0)
    return reserve_cap * release_factor


@dataclass(frozen=True)
class SlicePlan:
    weekly_used_pp: float
    weekly_remaining_pp: float
    hours_to_reset: float
    slice_hours: float
    held_reserve_start_pp: float
    held_reserve_end_pp: float
    control_slice_budget_pp: float


def plan_control_slice(weekly_used_pp: float, hours_to_reset: float) -> SlicePlan:
    """Plan one fixed rolling control slice from the current anchor."""
    used = clamp(float(weekly_used_pp), 0.0, 100.0)
    hours = max(0.0, float(hours_to_reset))
    remaining = max(0.0, 100.0 - used)
    if hours <= 0.0 or remaining <= 0.0:
        return SlicePlan(used, remaining, hours, 0.0, 0.0, 0.0, 0.0)

    h = min(CONTROL_SLICE_HOURS, hours)
    z0 = reserve_schedule_pp(remaining, hours)
    z1 = reserve_schedule_pp(remaining, max(0.0, hours - h))
    schedulable = max(0.0, remaining - z0)
    proportional = schedulable * (h / hours)
    released_reserve = max(0.0, z0 - z1)
    budget = min(remaining, max(0.0, proportional + released_reserve))
    return SlicePlan(used, remaining, hours, h, z0, z1, budget)


@dataclass(frozen=True)
class SliceStatus:
    slice_start_used_pp: float
    current_used_pp: float
    slice_budget_pp: float
    slice_spent_pp: float
    slice_headroom_pp: float
    meter_granularity_pp: float
    effective_slice_headroom_pp: float
    overrun_pp: float


def control_slice_status(
    slice_start_used_pp: float,
    current_used_pp: float,
    slice_budget_pp: float,
    meter_granularity_pp: float | None = None,
) -> SliceStatus:
    """Measure remaining headroom inside an already-anchored control slice."""
    start = clamp(float(slice_start_used_pp), 0.0, 100.0)
    current = clamp(float(current_used_pp), 0.0, 100.0)
    budget = max(0.0, float(slice_budget_pp))
    g = DEFAULT_METER_GRANULARITY_PP if meter_granularity_pp is None else max(0.0, float(meter_granularity_pp))
    spent = max(0.0, current - start)
    headroom = max(0.0, budget - spent)
    effective = max(0.0, headroom - g)
    overrun = max(0.0, spent - budget)
    return SliceStatus(start, current, budget, spent, headroom, g, effective, overrun)


def _quantile_linear(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    q = clamp(float(q), 0.0, 1.0)
    position = (len(ordered) - 1) * q
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        return ordered[lo]
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


@dataclass(frozen=True)
class BurnEstimate:
    safe_burn_pp: float | None
    confidence: str
    method: str
    sample_count: int
    samples_pp: tuple[float, ...]


def robust_safe_burn_pp(
    samples_pp: Iterable[float],
    meter_granularity_pp: float | None = None,
) -> BurnEstimate:
    """Conservative planning estimate from up to five recent compatible samples.

    This is a regulator heuristic, not a statistical guarantee.
    """
    samples = tuple(max(0.0, float(x)) for x in samples_pp)[-5:]
    g = DEFAULT_METER_GRANULARITY_PP if meter_granularity_pp is None else max(0.0, float(meter_granularity_pp))
    n = len(samples)
    if n == 0:
        return BurnEstimate(None, "UNKNOWN", "no-compatible-history", 0, samples)
    if n == 1:
        x = samples[0]
        safe = x + max(g, 0.50 * x)
        return BurnEstimate(safe, "LOW", "single-sample-50pct-bootstrap", 1, samples)
    if n == 2:
        m = max(samples)
        safe = m + max(g, 0.25 * m)
        return BurnEstimate(safe, "LOW", "two-sample-max-25pct-bootstrap", 2, samples)

    med = statistics.median(samples)
    mad = statistics.median(abs(x - med) for x in samples)
    robust_sigma = 1.4826 * mad
    p80 = _quantile_linear(samples, 0.80)
    safe = max(p80, med + 1.645 * robust_sigma) + g
    confidence = "HIGH" if n >= 5 else "MEDIUM"
    return BurnEstimate(safe, confidence, "median-mad-p80-one-sided-margin", n, samples)


@dataclass(frozen=True)
class AdmissionDecision:
    decision: str
    quality_floor: str
    continuity_feasible: str
    effective_headroom_pp: float
    estimated_safe_burn_pp: float | None
    reason: str


def admission_decision(
    effective_slice_headroom_pp: float,
    burn_estimate: BurnEstimate,
    quality_sufficient: bool = True,
) -> AdmissionDecision:
    headroom = max(0.0, float(effective_slice_headroom_pp))
    if not quality_sufficient:
        return AdmissionDecision(
            "DEFER_FOR_QUALITY",
            "NON_NEGOTIABLE",
            "NO",
            headroom,
            burn_estimate.safe_burn_pp,
            "candidate pass is below the minimum sufficient quality floor",
        )
    if burn_estimate.safe_burn_pp is None:
        return AdmissionDecision(
            "CALIBRATE_OR_PREPARE",
            "NON_NEGOTIABLE",
            "UNKNOWN",
            headroom,
            None,
            "no compatible observed burn history",
        )
    safe = burn_estimate.safe_burn_pp
    if safe <= headroom:
        return AdmissionDecision(
            "LAUNCH",
            "NON_NEGOTIABLE",
            "YES",
            headroom,
            safe,
            "quality-sufficient conservative burn fits the current fixed control slice",
        )
    return AdmissionDecision(
        "DEFER_FOR_QUALITY",
        "NON_NEGOTIABLE",
        "NO",
        headroom,
        safe,
        "quality-sufficient conservative burn does not fit the current fixed control slice",
    )


def self_test() -> None:
    # Fresh seven-day window: hold 10pp early reserve and schedule 90pp across 168h.
    first = plan_control_slice(0.0, 168.0)
    assert math.isclose(first.control_slice_budget_pp, 90.0 * 24.0 / 168.0, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(first.control_slice_budget_pp, 12.857142857142858, rel_tol=0, abs_tol=1e-9)

    # Spending exactly each planned slice must release the reserve and reach 100 by reset.
    used = 0.0
    hours = 168.0
    slices = 0
    while hours > 1e-9:
        p = plan_control_slice(used, hours)
        used = min(100.0, used + p.control_slice_budget_pp)
        hours = max(0.0, hours - p.slice_hours)
        slices += 1
        assert slices <= 7
    assert slices == 7
    assert math.isclose(used, 100.0, rel_tol=0, abs_tol=1e-7)

    # Feedback: under-spend expands the next envelope, over-spend compresses it.
    exact_first = first.control_slice_budget_pp
    exact_next = plan_control_slice(exact_first, 144.0).control_slice_budget_pp
    under_next = plan_control_slice(exact_first - 4.0, 144.0).control_slice_budget_pp
    over_next = plan_control_slice(exact_first + 4.0, 144.0).control_slice_budget_pp
    assert under_next > exact_next > over_next

    # Reserve never consumes more than half a low remaining allowance.
    assert reserve_schedule_pp(12.0, 120.0) <= 6.0 + 1e-12

    # Stateful slice ledger: 5pp spent from a 12.857pp slice leaves 7.857pp before granularity.
    status = control_slice_status(0.0, 5.0, first.control_slice_budget_pp, 0.0)
    assert math.isclose(status.slice_headroom_pp, first.control_slice_budget_pp - 5.0, abs_tol=1e-9)

    # Conservative sparse and robust estimates.
    e1 = robust_safe_burn_pp([4.0], 1.0)
    assert math.isclose(e1.safe_burn_pp or 0.0, 6.0, abs_tol=1e-9)
    e2 = robust_safe_burn_pp([3.0, 4.0], 1.0)
    assert math.isclose(e2.safe_burn_pp or 0.0, 5.0, abs_tol=1e-9)
    e5 = robust_safe_burn_pp([3.0, 4.0, 4.0, 5.0, 6.0], 1.0)
    assert e5.safe_burn_pp is not None and e5.safe_burn_pp >= 6.0
    assert e5.confidence == "HIGH"

    # Quality floor is stronger than quota pressure.
    launch = admission_decision(8.0, robust_safe_burn_pp([3.0, 4.0], 1.0), True)
    assert launch.decision == "LAUNCH"
    defer = admission_decision(4.0, robust_safe_burn_pp([5.0, 5.0], 1.0), True)
    assert defer.decision == "DEFER_FOR_QUALITY"
    weak = admission_decision(20.0, robust_safe_burn_pp([2.0, 2.0], 1.0), False)
    assert weak.decision == "DEFER_FOR_QUALITY"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v2.1 adaptive weekly Work/Codex quota controller")
    p.add_argument("--weekly-used", type=float, required=True, help="normalized first-party weekly used percentage")
    p.add_argument("--hours-to-reset", type=float, required=True, help="hours until the current weekly reset")
    p.add_argument("--slice-start-used", type=float, help="weekly used percentage at the current fixed slice anchor")
    p.add_argument("--current-used", type=float, help="current weekly used percentage")
    p.add_argument("--meter-granularity", type=float, default=None, help="known meter granularity in percentage points")
    p.add_argument("--samples", type=str, default="", help="comma-separated compatible pass burn samples in weekly pp")
    p.add_argument("--self-test", action="store_true", help="run deterministic controller checks before printing result")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.self_test:
        self_test()

    plan = plan_control_slice(args.weekly_used, args.hours_to_reset)
    payload: dict[str, object] = {"plan": asdict(plan)}

    if args.slice_start_used is not None or args.current_used is not None:
        if args.slice_start_used is None or args.current_used is None:
            raise SystemExit("--slice-start-used and --current-used must be supplied together")
        payload["slice_status"] = asdict(
            control_slice_status(
                args.slice_start_used,
                args.current_used,
                plan.control_slice_budget_pp,
                args.meter_granularity,
            )
        )

    samples = [float(x.strip()) for x in args.samples.split(",") if x.strip()]
    if samples:
        estimate = robust_safe_burn_pp(samples, args.meter_granularity)
        payload["burn_estimate"] = asdict(estimate)
        effective = (
            payload.get("slice_status", {}).get("effective_slice_headroom_pp", plan.control_slice_budget_pp)
            if isinstance(payload.get("slice_status"), dict)
            else plan.control_slice_budget_pp
        )
        payload["admission"] = asdict(admission_decision(float(effective), estimate, True))

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
