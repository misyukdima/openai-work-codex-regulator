#!/usr/bin/env python3
"""Normalize quota telemetry for regulator v3.0.

This module is deliberately transport-agnostic. It does not authenticate to
OpenAI, read browser cookies, or decide whether Work/Codex should launch. It
only converts a supported telemetry payload into the normalized snapshot used
by the existing weekly quota controller.

The first reference adapter accepts CodexBar-style JSON. Window semantics are
classified by duration, never by primary/secondary position.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

FIVE_HOUR_MINUTES = 300
WEEKLY_MINUTES = 10080
DEFAULT_FRESHNESS_SECONDS = 15 * 60


class TelemetryError(ValueError):
    """Raised when a telemetry payload cannot be normalized safely."""


@dataclass(frozen=True)
class QuotaWindow:
    kind: str
    used_percent: float
    window_minutes: int
    reset_at: str | None


@dataclass(frozen=True)
class QuotaSnapshot:
    schema_version: int
    allowance_domain: str
    source: str
    sensor: str
    snapshot_at: str | None
    freshness: str
    age_seconds: float | None
    weekly_meter_semantics: str
    weekly_used: float | None
    weekly_reset: str | None
    five_hour_used: float | None
    five_hour_reset: str | None
    other_windows: tuple[QuotaWindow, ...]


def _clamp_percent(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TelemetryError(f"invalid used percent: {value!r}") from exc
    if not math.isfinite(number) or number < 0 or number > 100:
        raise TelemetryError(f"used percent outside 0..100: {number}")
    return number


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        # Accept seconds or milliseconds since epoch.
        if number > 10_000_000_000:
            number /= 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise TelemetryError(f"invalid epoch timestamp: {value!r}") from exc
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise TelemetryError(f"invalid ISO timestamp: {value!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise TelemetryError(f"unsupported timestamp type: {type(value).__name__}")


def _iso(value: Any) -> str | None:
    parsed = _parse_timestamp(value)
    return None if parsed is None else parsed.isoformat().replace("+00:00", "Z")


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _window_minutes(window: dict[str, Any]) -> int:
    direct = _first(window, "windowMinutes", "window_minutes")
    if direct is not None:
        try:
            minutes = int(round(float(direct)))
        except (TypeError, ValueError) as exc:
            raise TelemetryError(f"invalid window minutes: {direct!r}") from exc
        if minutes <= 0:
            raise TelemetryError(f"window minutes must be positive: {minutes}")
        return minutes

    seconds = _first(window, "limit_window_seconds", "windowSeconds", "window_seconds")
    if seconds is not None:
        try:
            value = float(seconds)
        except (TypeError, ValueError) as exc:
            raise TelemetryError(f"invalid window seconds: {seconds!r}") from exc
        if value <= 0:
            raise TelemetryError(f"window seconds must be positive: {value}")
        return int(round(value / 60.0))

    raise TelemetryError("window duration is missing")


def _classify_window(minutes: int) -> str:
    if minutes == FIVE_HOUR_MINUTES:
        return "FIVE_HOUR"
    if minutes == WEEKLY_MINUTES:
        return "WEEKLY"
    return "OTHER_WINDOW"


def _normalize_window(window: dict[str, Any]) -> QuotaWindow:
    minutes = _window_minutes(window)
    used = _clamp_percent(_first(window, "usedPercent", "used_percent"))
    reset = _iso(_first(window, "resetsAt", "reset_at", "resetAt"))
    return QuotaWindow(_classify_window(minutes), used, minutes, reset)


def _codex_result(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, list):
        raise TelemetryError("CodexBar payload must be an object or array")

    matches = [item for item in payload if isinstance(item, dict) and str(item.get("provider", "")).lower() == "codex"]
    if len(matches) == 1:
        return matches[0]
    if not matches and len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0]
    if not matches:
        raise TelemetryError("Codex provider is missing from telemetry array")
    raise TelemetryError("multiple Codex accounts/results require explicit selection before normalization")


def _iter_codex_windows(result: dict[str, Any]) -> Iterable[dict[str, Any]]:
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else result

    for key in ("primary", "secondary", "primaryWindow", "secondaryWindow"):
        value = usage.get(key) if isinstance(usage, dict) else None
        if isinstance(value, dict):
            yield value

    rate_limit = usage.get("rate_limit") if isinstance(usage, dict) else None
    if not isinstance(rate_limit, dict):
        rate_limit = result.get("rate_limit") if isinstance(result.get("rate_limit"), dict) else None
    if isinstance(rate_limit, dict):
        for key in ("primary_window", "secondary_window"):
            value = rate_limit.get(key)
            if isinstance(value, dict):
                yield value


def normalize_codexbar(
    payload: Any,
    *,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_FRESHNESS_SECONDS,
) -> QuotaSnapshot:
    result = _codex_result(payload)
    provider = str(result.get("provider", "codex")).lower()
    if provider not in ("", "codex"):
        raise TelemetryError(f"expected Codex provider, got {provider!r}")

    usage = result.get("usage") if isinstance(result.get("usage"), dict) else result
    updated_raw = _first(usage, "updatedAt", "updated_at") if isinstance(usage, dict) else None
    if updated_raw is None:
        updated_raw = _first(result, "updatedAt", "updated_at")
    updated = _parse_timestamp(updated_raw)

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if updated is None:
        freshness = "UNKNOWN"
        age_seconds = None
    else:
        age_seconds = max(0.0, (current - updated).total_seconds())
        freshness = "FRESH" if age_seconds <= max_age_seconds else "STALE"

    normalized = [_normalize_window(item) for item in _iter_codex_windows(result)]
    if not normalized:
        raise TelemetryError("no quota windows found")

    weekly = [w for w in normalized if w.kind == "WEEKLY"]
    five_hour = [w for w in normalized if w.kind == "FIVE_HOUR"]
    if len(weekly) > 1:
        raise TelemetryError("multiple weekly windows are ambiguous")
    if len(five_hour) > 1:
        raise TelemetryError("multiple five-hour windows are ambiguous")

    other = tuple(w for w in normalized if w.kind == "OTHER_WINDOW")
    source_name = str(result.get("source", "unknown")).strip().upper() or "UNKNOWN"

    return QuotaSnapshot(
        schema_version=1,
        allowance_domain="WORK_CODEX",
        source=f"CODEXBAR_{source_name}",
        sensor="CODEXBAR",
        snapshot_at=None if updated is None else updated.isoformat().replace("+00:00", "Z"),
        freshness=freshness,
        age_seconds=age_seconds,
        weekly_meter_semantics="USED",
        weekly_used=weekly[0].used_percent if weekly else None,
        weekly_reset=weekly[0].reset_at if weekly else None,
        five_hour_used=five_hour[0].used_percent if five_hour else None,
        five_hour_reset=five_hour[0].reset_at if five_hour else None,
        other_windows=other,
    )


def snapshot_dict(snapshot: QuotaSnapshot) -> dict[str, Any]:
    data = asdict(snapshot)
    data["other_windows"] = [asdict(item) for item in snapshot.other_windows]
    return data


def self_test() -> None:
    now = datetime(2026, 9, 6, 20, 0, tzinfo=timezone.utc)

    standard = {
        "provider": "codex",
        "source": "oauth",
        "updatedAt": "2026-09-06T19:58:00Z",
        "usage": {
            "primary": {"usedPercent": 21, "windowMinutes": 300, "resetsAt": "2026-09-06T23:00:00Z"},
            "secondary": {"usedPercent": 37, "windowMinutes": 10080, "resetsAt": "2026-09-10T08:00:00Z"},
        },
    }
    s = normalize_codexbar(standard, now=now)
    assert s.freshness == "FRESH"
    assert s.five_hour_used == 21
    assert s.weekly_used == 37
    assert s.source == "CODEXBAR_OAUTH"

    # Position must not define semantics: weekly can appear first.
    swapped = {
        "provider": "codex",
        "source": "oauth",
        "updatedAt": "2026-09-06T19:59:00Z",
        "usage": {
            "primary": {"usedPercent": 44, "windowMinutes": 10080},
            "secondary": {"usedPercent": 9, "windowMinutes": 300},
        },
    }
    s2 = normalize_codexbar(swapped, now=now)
    assert s2.weekly_used == 44
    assert s2.five_hour_used == 9

    direct_oauth = {
        "provider": "codex",
        "source": "oauth",
        "updated_at": "2026-09-06T19:59:30Z",
        "rate_limit": {
            "primary_window": {"used_percent": 11, "limit_window_seconds": 18000, "reset_at": 1788720000},
            "secondary_window": {"used_percent": 51, "limit_window_seconds": 604800, "reset_at": 1789120000},
        },
    }
    s3 = normalize_codexbar(direct_oauth, now=now)
    assert s3.five_hour_used == 11
    assert s3.weekly_used == 51

    monthly_only = {
        "provider": "codex",
        "source": "oauth",
        "updatedAt": "2026-09-06T19:59:00Z",
        "usage": {"primary": {"usedPercent": 12, "windowMinutes": 43200}},
    }
    s4 = normalize_codexbar(monthly_only, now=now)
    assert s4.weekly_used is None
    assert s4.five_hour_used is None
    assert len(s4.other_windows) == 1
    assert s4.other_windows[0].window_minutes == 43200

    stale = dict(standard)
    stale["updatedAt"] = "2026-09-06T18:00:00Z"
    s5 = normalize_codexbar(stale, now=now)
    assert s5.freshness == "STALE"

    array_payload = [{"provider": "claude"}, standard]
    s6 = normalize_codexbar(array_payload, now=now)
    assert s6.weekly_used == 37


def _load_payload(path: str) -> Any:
    if path == "-":
        import sys

        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Work/Codex quota telemetry for regulator v3.0")
    parser.add_argument("--input", default="-", help="JSON file or - for stdin")
    parser.add_argument("--provider", default="codexbar", choices=["codexbar"])
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_FRESHNESS_SECONDS)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("quota telemetry self-test OK")
        return

    payload = _load_payload(args.input)
    snapshot = normalize_codexbar(payload, max_age_seconds=max(0, args.max_age_seconds))
    print(json.dumps(snapshot_dict(snapshot), ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
