#!/usr/bin/env python3
"""Reference implementation for the v2.2 balanced Work/Codex quota + workflow pace controller.

The controller operates only on normalized first-party Work/Codex weekly
percentage points. It never converts API/token/rate-card units into weekly pp.

v2.2 replaces the v2.1 hard fixed-24h admission cap with an epoch-anchored
cumulative trajectory. A 24h look-ahead remains the normal spend target, while
a bounded future advance can be admitted when equal-weight workflow pace risk
is greater than quota advance risk.
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
BASE_LOOKAHEAD_HOURS = 24.0
MAX_ADVANCE_HOURS = 72.0
DEFAULT_METER_GRANULARITY_PP = 1.0

PACE_LEVELS = {
    "NONE": 0.0,
    "LOW": 0.25,
    "MEDIUM": 0.50,
    "HIGH": 0.75,
    "CRITICAL": 1.0,
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def anchor_reserve_pp(weekly_remaining_pp: float, anchor_hours_to_reset: float) -> float:
    remaining = clamp(float(weekly_remaining_pp), 0.0, 100.0)
    hours = max(0.0, float(anchor_hours_to_reset))
    cap = min(BASE_WEEKLY_RESERVE_PP, RESERVE_FRACTION_CAP * remaining)
    return cap * clamp(hours / RESERVE_RELEASE_HOURS, 0.0, 1.0)


@dataclass(frozen=True)
class TrajectoryAnchor:
    anchor_weekly_used_pp: float
    anchor_weekly_remaining_pp: float
    anchor_hours_to_reset: float
    anchor_reserve_pp: float


def make_anchor(anchor_weekly_used_pp: float, anchor_hours_to_reset: float) -> TrajectoryAnchor:
    used = clamp(float(anchor_weekly_used_pp), 0.0, 100.0)
    hours = max(0.0, float(anchor_hours_to_reset))
    remaining = max(0.0, 100.0 - used)
    reserve = anchor_reserve_pp(remaining, hours)
    return TrajectoryAnchor(used, remaining, hours, reserve)


def target_cumulative_spend_pp(
    anchor_weekly_used_pp: float,
    anchor_hours_to_reset: float,
    hours_to_reset_now: float,
) -> float:
    """Cumulative pp the anchored trajectory permits spending by the current point."""
    a = make_anchor(anchor_weekly_used_pp, anchor_hours_to_reset)
    if a.anchor_hours_to_reset <= 0.0:
        return a.anchor_weekly_remaining_pp

    h = clamp(float(hours_to_reset_now), 0.0, a.anchor_hours_to_reset)
    schedulable0 = max(0.0, a.anchor_weekly_remaining_pp - a.anchor_reserve_pp)
    scheduled_remaining = schedulable0 * (h / a.anchor_hours_to_reset)

    release_denominator = min(RESERVE_RELEASE_HOURS, a.anchor_hours_to_reset)
    reserve_remaining = (
        0.0
        if release_denominator <= 0.0
        else a.anchor_reserve_pp * clamp(h / release_denominator, 0.0, 1.0)
    )

    target = a.anchor_weekly_remaining_pp - scheduled_remaining - reserve_remaining
    return clamp(target, 0.0, a.anchor_weekly_remaining_pp)


@dataclass(frozen=True)
class TrajectoryStatus:
    anchor_weekly_used_pp: float
    current_weekly_used_pp: float
    anchor_hours_to_reset: float
    hours_to_reset_now: float
    actual_spend_since_anchor_pp: float
    target_spend_now_pp: float
    target_spend_base_horizon_pp: float
    target_spend_max_advance_horizon_pp: float
    meter_granularity_pp: float
    scheduled_commitment_pp: float
    base_action_headroom_pp: float
    max_advance_headroom_pp: float
    borrowable_extra_pp: float


def trajectory_status(
    anchor_weekly_used_pp: float,
    anchor_hours_to_reset: float,
    hours_to_reset_now: float,
    current_weekly_used_pp: float,
    meter_granularity_pp: float | None = None,
    scheduled_commitment_pp: float = 0.0,
) -> TrajectoryStatus:
    """Return continuous trajectory headroom without resetting the anchor."""
    a = make_anchor(anchor_weekly_used_pp, anchor_hours_to_reset)
    current = clamp(float(current_weekly_used_pp), 0.0, 100.0)
    h_now = clamp(float(hours_to_reset_now), 0.0, a.anchor_hours_to_reset)
    g = DEFAULT_METER_GRANULARITY_PP if meter_granularity_pp is None else max(0.0, float(meter_granularity_pp))
    scheduled = max(0.0, float(scheduled_commitment_pp))

    actual = max(0.0, current - a.anchor_weekly_used_pp)
    base_future_h = max(0.0, h_now - min(BASE_LOOKAHEAD_HOURS, h_now))
    advance_future_h = max(0.0, h_now - min(MAX_ADVANCE_HOURS, h_now))

    target_now = target_cumulative_spend_pp(a.anchor_weekly_used_pp, a.anchor_hours_to_reset, h_now)
    target_base = target_cumulative_spend_pp(a.anchor_weekly_used_pp, a.anchor_hours_to_reset, base_future_h)
    target_advance = target_cumulative_spend_pp(a.anchor_weekly_used_pp, a.anchor_hours_to_reset, advance_future_h)

    base = max(0.0, target_base - actual - scheduled - g)
    advance = max(0.0, target_advance - actual - scheduled - g)
    extra = max(0.0, advance - base)

    return TrajectoryStatus(
        a.anchor_weekly_used_pp,
        current,
        a.anchor_hours_to_reset,
        h_now,
        actual,
        target_now,
        target_base,
        target_advance,
        g,
        scheduled,
        base,
        advance,
        extra,
    )


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
    samples = tuple(max(0.0, float(x)) for x in samples_pp)[-5:]
    g = DEFAULT_METER_GRANULARITY_PP if meter_granularity_pp is None else max(0.0, float(meter_granularity_pp))
    n = len(samples)
    if n == 0:
        return BurnEstimate(None, "UNKNOWN", "no-compatible-history", 0, samples)
    if n == 1:
        x = samples[0]
        return BurnEstimate(x + max(g, 0.50 * x), "LOW", "single-sample-50pct-bootstrap", 1, samples)
    if n == 2:
        m = max(samples)
        return BurnEstimate(m + max(g, 0.25 * m), "LOW", "two-sample-max-25pct-bootstrap", 2, samples)

    med = statistics.median(samples)
    mad = statistics.median(abs(x - med) for x in samples)
    robust_sigma = 1.4826 * mad
    p80 = _quantile_linear(samples, 0.80)
    safe = max(p80, med + 1.645 * robust_sigma) + g
    confidence = "HIGH" if n >= 5 else "MEDIUM"
    return BurnEstimate(safe, confidence, "median-mad-p80-one-sided-margin", n, samples)


def pace_risk(level_or_value: str | float) -> float:
    if isinstance(level_or_value, str):
        key = level_or_value.strip().upper()
        if key in PACE_LEVELS:
            return PACE_LEVELS[key]
        return clamp(float(level_or_value), 0.0, 1.0)
    return clamp(float(level_or_value), 0.0, 1.0)


@dataclass(frozen=True)
class BalancedAdmission:
    decision: str
    quality_floor: str
    balanced_priority: str
    base_headroom_pp: float
    max_advance_headroom_pp: float
    safe_burn_pp: float | None
    needed_advance_pp: float
    quota_risk_if_launch: float
    pace_risk_if_defer: float
    reason: str


def balanced_admission(
    status: TrajectoryStatus,
    burn_estimate: BurnEstimate,
    pace_risk_if_defer: str | float,
    quality_sufficient: bool = True,
) -> BalancedAdmission:
    """Equal-priority admission between quota continuity and workflow pace."""
    p_risk = pace_risk(pace_risk_if_defer)
    base = max(0.0, status.base_action_headroom_pp)
    advance = max(base, status.max_advance_headroom_pp)

    if not quality_sufficient:
        return BalancedAdmission(
            "DEFER_FOR_QUALITY", "NON_NEGOTIABLE", "QUOTA_50_PACE_50",
            base, advance, burn_estimate.safe_burn_pp, 0.0, 0.0, p_risk,
            "candidate pass is below the minimum sufficient quality floor",
        )

    safe = burn_estimate.safe_burn_pp
    if safe is None:
        return BalancedAdmission(
            "CALIBRATE_OR_PREPARE", "NON_NEGOTIABLE", "QUOTA_50_PACE_50",
            base, advance, None, 0.0, 0.0, p_risk,
            "no compatible observed burn history",
        )

    if safe <= base:
        return BalancedAdmission(
            "LAUNCH_BASE", "NON_NEGOTIABLE", "QUOTA_50_PACE_50",
            base, advance, safe, 0.0, 0.0, p_risk,
            "quality-sufficient burn fits the normal 24h trajectory look-ahead",
        )

    needed = max(0.0, safe - base)
    extra = max(0.0, advance - base)
    if extra <= 0.0 or safe > advance + 1e-12:
        return BalancedAdmission(
            "PROGRESS_ALTERNATIVE_OR_DEFER", "NON_NEGOTIABLE", "QUOTA_50_PACE_50",
            base, advance, safe, needed, 1.0, p_risk,
            "pass exceeds the bounded future-advance horizon",
        )

    q_risk = clamp(needed / extra, 0.0, 1.0)
    if q_risk <= p_risk + 1e-12:
        return BalancedAdmission(
            "LAUNCH_WITH_ADVANCE", "NON_NEGOTIABLE", "QUOTA_50_PACE_50",
            base, advance, safe, needed, q_risk, p_risk,
            "quota advance risk is no greater than the equal-weight pace risk of deferral",
        )

    return BalancedAdmission(
        "PROGRESS_ALTERNATIVE_OR_DEFER", "NON_NEGOTIABLE", "QUOTA_50_PACE_50",
        base, advance, safe, needed, q_risk, p_risk,
        "equal-weight quota risk of launch exceeds pace risk of deferral",
    )


def self_test() -> None:
    s0 = trajectory_status(0.0, 168.0, 168.0, 0.0, 0.0)
    assert math.isclose(s0.base_action_headroom_pp, 90.0 * 24.0 / 168.0, abs_tol=1e-9)
    assert math.isclose(s0.base_action_headroom_pp, 12.857142857142858, abs_tol=1e-9)
    assert math.isclose(s0.max_advance_headroom_pp, 38.57142857142858, abs_tol=1e-9)

    s1 = trajectory_status(0.0, 168.0, 168.0, 5.0, 0.0)
    assert math.isclose(s1.base_action_headroom_pp, s0.base_action_headroom_pp - 5.0, abs_tol=1e-9)

    s2 = trajectory_status(0.0, 168.0, 167.0, 5.0, 0.0)
    assert s2.base_action_headroom_pp > s1.base_action_headroom_pp

    ss = trajectory_status(0.0, 168.0, 168.0, 0.0, 0.0, scheduled_commitment_pp=3.0)
    assert math.isclose(ss.base_action_headroom_pp, s0.base_action_headroom_pp - 3.0, abs_tol=1e-9)
    assert math.isclose(ss.max_advance_headroom_pp, s0.max_advance_headroom_pp - 3.0, abs_tol=1e-9)

    e1 = robust_safe_burn_pp([4.0], 1.0)
    assert math.isclose(e1.safe_burn_pp or 0.0, 6.0, abs_tol=1e-9)
    e2 = robust_safe_burn_pp([3.0, 4.0], 1.0)
    assert math.isclose(e2.safe_burn_pp or 0.0, 5.0, abs_tol=1e-9)
    e5 = robust_safe_burn_pp([3.0, 4.0, 4.0, 5.0, 6.0], 1.0)
    assert e5.safe_burn_pp is not None and e5.safe_burn_pp >= 6.0
    assert e5.confidence == "HIGH"

    e20 = BurnEstimate(20.0, "MEDIUM", "self-test", 3, (18.0, 19.0, 20.0))
    high = balanced_admission(s0, e20, "HIGH", True)
    assert high.decision == "LAUNCH_WITH_ADVANCE"
    assert high.quota_risk_if_launch < high.pace_risk_if_defer

    low = balanced_admission(s0, e20, "LOW", True)
    assert low.decision == "PROGRESS_ALTERNATIVE_OR_DEFER"
    assert low.quota_risk_if_launch > low.pace_risk_if_defer

    tie_safe = s0.base_action_headroom_pp + 0.5 * s0.borrowable_extra_pp
    tie = balanced_admission(
        s0, BurnEstimate(tie_safe, "MEDIUM", "self-test", 3, (tie_safe,) * 3), 0.50, True
    )
    assert tie.decision == "LAUNCH_WITH_ADVANCE"
    assert math.isclose(tie.quota_risk_if_launch, 0.5, abs_tol=1e-9)

    too_big = BurnEstimate(s0.max_advance_headroom_pp + 1.0, "MEDIUM", "self-test", 3, (40.0,) * 3)
    denied = balanced_admission(s0, too_big, "CRITICAL", True)
    assert denied.decision == "PROGRESS_ALTERNATIVE_OR_DEFER"

    weak = balanced_admission(s0, e20, "CRITICAL", False)
    assert weak.decision == "DEFER_FOR_QUALITY"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v2.2 balanced weekly Work/Codex quota + workflow pace controller")
    p.add_argument("--anchor-weekly-used", type=float, required=True)
    p.add_argument("--anchor-hours-to-reset", type=float, required=True)
    p.add_argument("--hours-to-reset-now", type=float, required=True)
    p.add_argument("--current-weekly-used", type=float, required=True)
    p.add_argument("--meter-granularity", type=float, default=None)
    p.add_argument("--scheduled-commitment", type=float, default=0.0)
    p.add_argument("--samples", type=str, default="")
    p.add_argument("--pace-risk", type=str, default="MEDIUM", help="NONE|LOW|MEDIUM|HIGH|CRITICAL or 0..1")
    p.add_argument("--self-test", action="store_true")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.self_test:
        self_test()

    status = trajectory_status(
        args.anchor_weekly_used,
        args.anchor_hours_to_reset,
        args.hours_to_reset_now,
        args.current_weekly_used,
        args.meter_granularity,
        args.scheduled_commitment,
    )
    payload: dict[str, object] = {"trajectory": asdict(status)}

    samples = [float(x.strip()) for x in args.samples.split(",") if x.strip()]
    if samples:
        estimate = robust_safe_burn_pp(samples, args.meter_granularity)
        payload["burn_estimate"] = asdict(estimate)
        payload["admission"] = asdict(balanced_admission(status, estimate, args.pace_risk, True))

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
