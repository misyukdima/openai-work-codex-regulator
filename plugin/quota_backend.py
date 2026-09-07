#!/usr/bin/env python3
"""Read-only server-side quota backend primitives for Regulator v3.0.

This module is intentionally narrow:
- it speaks JSON-RPC to official `codex app-server`;
- it performs managed ChatGPT authentication when explicitly requested;
- it reads account rate limits;
- it normalizes only quota facts needed by the ChatGPT Web regulator;
- it never exposes auth tokens to the model-facing tool contract;
- it never decides routing, model tier, admission, purchases, or resets.

Persistent credential storage is deliberately out of scope here. Production code
must inject an audited per-subject credential lifecycle instead of treating a
temporary CODEX_HOME as durable storage.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FIVE_HOUR_MINUTES = 300
WEEKLY_MINUTES = 10080
ALLOWANCE_DOMAIN = "WORK_CODEX"
SOURCE = "OPENAI_CODEX_APP_SERVER"


class CodexProtocolError(RuntimeError):
    """Raised when codex app-server returns a JSON-RPC error."""


class CodexProtocolTimeout(TimeoutError):
    """Raised when the expected app-server message is not observed in time."""


@dataclass(frozen=True)
class DeviceAuthorization:
    login_id: str
    verification_url: str
    user_code: str


class CodexAppServer:
    """Minimal managed-auth client for `codex app-server --stdio`."""

    def __init__(
        self,
        codex_bin: str = "codex",
        *,
        codex_home: str | os.PathLike[str] | None = None,
        client_name: str = "openai_work_codex_regulator_plugin",
        client_title: str = "OpenAI Work + Codex Regulator",
        client_version: str = "0.1.0",
    ) -> None:
        self.codex_bin = codex_bin
        self.codex_home = Path(codex_home).resolve() if codex_home else None
        self.client_info = {
            "name": client_name,
            "title": client_title,
            "version": client_version,
        }
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1

    def __enter__(self) -> "CodexAppServer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    @property
    def process(self) -> subprocess.Popen[str]:
        if self._proc is None:
            raise RuntimeError("codex app-server is not running")
        return self._proc

    def start(self) -> None:
        if self._proc is not None:
            return

        env = os.environ.copy()
        if self.codex_home is not None:
            self.codex_home.mkdir(parents=True, exist_ok=True)
            env["CODEX_HOME"] = str(self.codex_home)

        self._proc = subprocess.Popen(
            [self.codex_bin, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        response = self.request(
            "initialize",
            {"clientInfo": self.client_info},
            timeout=30.0,
        )
        if response is None:
            raise CodexProtocolError("initialize returned no result")
        self.notify("initialized", {})

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return

        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
            proc.wait(timeout=5)

    def _send(self, payload: dict[str, Any]) -> None:
        proc = self.process
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        proc.stdin.flush()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def _read_message(self, timeout: float) -> dict[str, Any]:
        proc = self.process
        assert proc.stdout is not None

        selector = selectors.DefaultSelector()
        try:
            selector.register(proc.stdout, selectors.EVENT_READ)
            events = selector.select(timeout)
        finally:
            selector.close()

        if not events:
            if proc.poll() is not None:
                stderr = ""
                if proc.stderr is not None:
                    stderr = proc.stderr.read().strip()
                raise RuntimeError(
                    f"codex app-server exited with code {proc.returncode}"
                    + (f": {stderr}" if stderr else "")
                )
            raise CodexProtocolTimeout("timed out waiting for codex app-server")

        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("codex app-server closed stdout")

        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise CodexProtocolError(f"invalid JSON from codex app-server: {line!r}") from exc

    def _wait_for(
        self,
        predicate: Any,
        *,
        timeout: float,
        description: str,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            message = self._read_message(remaining)
            if predicate(message):
                return message
        raise CodexProtocolTimeout(f"timed out waiting for {description}")

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 60.0,
    ) -> dict[str, Any] | None:
        request_id = self._next_id
        self._next_id += 1

        payload: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            payload["params"] = params
        self._send(payload)

        message = self._wait_for(
            lambda msg: msg.get("id") == request_id,
            timeout=timeout,
            description=f"response to {method}",
        )
        if "error" in message:
            error = message["error"]
            raise CodexProtocolError(
                f"{method} failed: code={error.get('code')} message={error.get('message')}"
            )
        result = message.get("result")
        return result if isinstance(result, dict) else None

    def start_device_login(self) -> DeviceAuthorization:
        result = self.request(
            "account/login/start",
            {"type": "chatgptDeviceCode"},
            timeout=60.0,
        ) or {}
        if result.get("type") != "chatgptDeviceCode":
            raise CodexProtocolError(f"unexpected login response: {result!r}")
        return DeviceAuthorization(
            login_id=str(result["loginId"]),
            verification_url=str(result["verificationUrl"]),
            user_code=str(result["userCode"]),
        )

    def wait_until_authenticated(
        self,
        login_id: str,
        *,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        """Wait for both login completion and post-reload account state.

        Official Codex emits `account/login/completed` before the managed auth
        reload is guaranteed visible. `account/updated` is the safe readiness
        boundary for a subsequent `account/rateLimits/read`.
        """
        deadline = time.monotonic() + timeout
        completed = False

        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            message = self._read_message(remaining)
            method = message.get("method")
            params = message.get("params") or {}

            if method == "account/login/completed":
                returned_id = params.get("loginId")
                if returned_id not in (None, login_id):
                    continue
                if not params.get("success"):
                    raise CodexProtocolError(
                        f"ChatGPT login failed: {params.get('error') or 'unknown error'}"
                    )
                completed = True
                continue

            if method == "account/updated" and completed:
                if params.get("authMode") is not None:
                    return params

        raise CodexProtocolTimeout("timed out waiting for authenticated account/updated")

    def read_rate_limits(self) -> dict[str, Any]:
        return self.request("account/rateLimits/read", timeout=60.0) or {}


def _window_kind(duration_minutes: Any) -> str:
    try:
        duration = int(duration_minutes)
    except (TypeError, ValueError):
        return "OTHER_WINDOW"
    if duration == FIVE_HOUR_MINUTES:
        return "FIVE_HOUR"
    if duration == WEEKLY_MINUTES:
        return "WEEKLY"
    return "OTHER_WINDOW"


def _iter_windows(snapshot: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for field in ("primary", "secondary"):
        value = snapshot.get(field)
        if isinstance(value, dict):
            yield field, value


def _choose_codex_snapshot(result: dict[str, Any]) -> dict[str, Any] | None:
    by_id = result.get("rateLimitsByLimitId")
    if isinstance(by_id, dict):
        codex = by_id.get("codex")
        if isinstance(codex, dict):
            return codex
        for candidate in by_id.values():
            if isinstance(candidate, dict) and candidate.get("limitId") == "codex":
                return candidate

    default = result.get("rateLimits")
    return default if isinstance(default, dict) else None


def normalize_rate_limits(
    result: dict[str, Any],
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert Codex rate-limit response into the regulator's model-facing facts."""
    captured_at = captured_at or datetime.now(timezone.utc)
    snapshot = _choose_codex_snapshot(result)

    normalized: dict[str, Any] = {
        "schema_version": 1,
        "allowance_domain": ALLOWANCE_DOMAIN,
        "source": SOURCE,
        "snapshot_at": captured_at.isoformat(),
        "freshness": "FRESH",
        "weekly_meter_semantics": "USED",
        "weekly_used": None,
        "weekly_reset": None,
        "five_hour_used": None,
        "five_hour_reset": None,
        "other_windows": [],
        "plan_type": None,
        "ordinary_usage_allowed": result.get("ordinaryUsageAllowed"),
        "credits": {
            "has_credits": None,
            "unlimited": None,
            "balance": None,
        },
    }

    if snapshot is None:
        normalized["freshness"] = "UNKNOWN"
        return normalized

    normalized["plan_type"] = snapshot.get("planType")

    for field, window in _iter_windows(snapshot):
        kind = _window_kind(window.get("windowDurationMins"))
        clean = {
            "position": field,
            "used_percent": window.get("usedPercent"),
            "window_duration_mins": window.get("windowDurationMins"),
            "resets_at": window.get("resetsAt"),
        }
        if kind == "WEEKLY":
            normalized["weekly_used"] = clean["used_percent"]
            normalized["weekly_reset"] = clean["resets_at"]
        elif kind == "FIVE_HOUR":
            normalized["five_hour_used"] = clean["used_percent"]
            normalized["five_hour_reset"] = clean["resets_at"]
        else:
            normalized["other_windows"].append(clean)

    credits = snapshot.get("credits")
    if isinstance(credits, dict):
        normalized["credits"] = {
            "has_credits": credits.get("hasCredits"),
            "unlimited": credits.get("unlimited"),
            "balance": credits.get("balance"),
        }

    return normalized


def _assert_no_secret_fields(payload: Any) -> None:
    forbidden = {
        "access_token",
        "refresh_token",
        "oauth_token",
        "cookie",
        "cookies",
        "authorization",
        "bearer",
        "password",
        "auth_file",
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in forbidden:
                    raise AssertionError(f"secret-like field escaped normalization: {key}")
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)


def self_test() -> None:
    sample = {
        "ordinaryUsageAllowed": True,
        "rateLimitsByLimitId": {
            "base_model_inference": {
                "limitId": "base_model_inference",
                "planType": "plus",
                "primary": {
                    "usedPercent": 0,
                    "windowDurationMins": 10080,
                    "resetsAt": 2000000000,
                },
            },
            "codex": {
                "limitId": "codex",
                "planType": "plus",
                "primary": {
                    "usedPercent": 35,
                    "windowDurationMins": 10080,
                    "resetsAt": 2000000001,
                },
                "credits": {
                    "hasCredits": False,
                    "unlimited": False,
                    "balance": 0,
                },
            },
        },
    }

    normalized = normalize_rate_limits(
        sample,
        captured_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    assert normalized["allowance_domain"] == "WORK_CODEX"
    assert normalized["source"] == "OPENAI_CODEX_APP_SERVER"
    assert normalized["plan_type"] == "plus"
    assert normalized["weekly_used"] == 35
    assert normalized["weekly_reset"] == 2000000001
    assert normalized["five_hour_used"] is None
    assert normalized["five_hour_reset"] is None
    assert normalized["credits"]["has_credits"] is False
    _assert_no_secret_fields(normalized)

    reversed_positions = {
        "rateLimits": {
            "planType": "plus",
            "primary": {
                "usedPercent": 61,
                "windowDurationMins": 10080,
                "resetsAt": 10,
            },
            "secondary": {
                "usedPercent": 22,
                "windowDurationMins": 300,
                "resetsAt": 11,
            },
        }
    }
    normalized = normalize_rate_limits(reversed_positions)
    assert normalized["weekly_used"] == 61
    assert normalized["five_hour_used"] == 22

    unknown = {
        "rateLimits": {
            "primary": {
                "usedPercent": 9,
                "windowDurationMins": 43200,
                "resetsAt": 12,
            }
        }
    }
    normalized = normalize_rate_limits(unknown)
    assert normalized["weekly_used"] is None
    assert normalized["five_hour_used"] is None
    assert normalized["other_windows"][0]["window_duration_mins"] == 43200

    print("quota_plugin_backend_self_test=ok")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    parser.error("no standalone production server is exposed by this module")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
