#!/usr/bin/env python3
"""P0 feasibility probe for server-side Codex quota telemetry.

Purpose:
- launch official `codex app-server --stdio` in an isolated CODEX_HOME;
- initialize JSON-RPC;
- start ChatGPT device-code login;
- emit only verification URL + one-time user code;
- after `account/login/completed`, wait for `account/updated` so managed auth is active;
- call `account/rateLimits/read`;
- emit a sanitized quota snapshot;
- never print or persist auth tokens.

This is an EXPERIMENTAL DEVELOPMENT HARNESS, not production Plugin code.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def send(proc: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def recv(proc: subprocess.Popen[str], timeout: float = 120.0) -> dict[str, Any]:
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(f"codex app-server exited with code {proc.returncode}")
            time.sleep(0.05)
            continue
        try:
            return json.loads(line.strip())
        except json.JSONDecodeError:
            continue
    raise TimeoutError("timed out waiting for codex app-server response")


def wait_for_id(proc: subprocess.Popen[str], request_id: int, timeout: float = 120.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = recv(proc, timeout=max(1.0, deadline - time.monotonic()))
        if msg.get("id") == request_id:
            return msg
    raise TimeoutError(f"timed out waiting for response id={request_id}")


def wait_login_completed(proc: subprocess.Popen[str], login_id: str, timeout: float = 300.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = recv(proc, timeout=max(1.0, deadline - time.monotonic()))
        if msg.get("method") != "account/login/completed":
            continue
        params = msg.get("params") or {}
        if params.get("loginId") not in (None, login_id):
            continue
        return params
    raise TimeoutError("device-code login timed out")


def wait_account_updated(proc: subprocess.Popen[str], timeout: float = 30.0) -> dict[str, Any]:
    """Wait until app-server has reloaded the newly persisted managed auth.

    Codex emits account/login/completed before auth_manager.reload() and emits
    account/updated after the reload. Reading rate limits on the first event can
    therefore race and return "authentication required" even after a successful
    user authorization.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = recv(proc, timeout=max(1.0, deadline - time.monotonic()))
        if msg.get("method") != "account/updated":
            continue
        params = msg.get("params") or {}
        if params.get("authMode") is not None:
            return params
    raise TimeoutError("timed out waiting for authenticated account/updated notification")


def atomic_write_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temp.replace(target)


def sanitize_rate_limits(result: dict[str, Any]) -> dict[str, Any]:
    def clean_snapshot(snapshot: Any) -> Any:
        if not isinstance(snapshot, dict):
            return snapshot
        out: dict[str, Any] = {}
        for key in ("limitId", "limitName", "planType", "rateLimitReachedType"):
            if key in snapshot:
                out[key] = snapshot[key]
        for key in ("primary", "secondary"):
            value = snapshot.get(key)
            if isinstance(value, dict):
                out[key] = {
                    k: value[k]
                    for k in ("usedPercent", "windowDurationMins", "resetsAt")
                    if k in value
                }
        credits = snapshot.get("credits")
        if isinstance(credits, dict):
            out["credits"] = {
                k: credits[k]
                for k in ("hasCredits", "unlimited", "balance")
                if k in credits
            }
        return out

    output: dict[str, Any] = {
        "ordinaryUsageAllowed": result.get("ordinaryUsageAllowed"),
        "capturedAt": int(time.time()),
    }
    if isinstance(result.get("rateLimits"), dict):
        output["rateLimits"] = clean_snapshot(result["rateLimits"])
    by_id = result.get("rateLimitsByLimitId")
    if isinstance(by_id, dict):
        output["rateLimitsByLimitId"] = {
            str(limit_id): clean_snapshot(snapshot)
            for limit_id, snapshot in by_id.items()
        }
    reset_credits = result.get("rateLimitResetCredits")
    if isinstance(reset_credits, dict):
        output["rateLimitResetCredits"] = {"availableCount": reset_credits.get("availableCount")}
    return output


def main() -> int:
    codex_bin = os.environ.get("CODEX_BIN", "codex")
    codex_home = Path(os.environ.get("CODEX_HOME", ".p0-codex-home")).resolve()
    auth_file = os.environ.get("P0_AUTH_FILE")
    quota_file = os.environ.get("P0_QUOTA_FILE")
    codex_home.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)

    proc = subprocess.Popen(
        [codex_bin, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        env=env,
    )

    try:
        send(proc, {
            "method": "initialize",
            "id": 1,
            "params": {"clientInfo": {
                "name": "openai_work_codex_regulator_p0",
                "title": "OpenAI Work + Codex Regulator P0 Probe",
                "version": "0.1.1",
            }},
        })
        init = wait_for_id(proc, 1, 30.0)
        if "error" in init:
            raise RuntimeError(f"initialize failed: {init['error']}")
        send(proc, {"method": "initialized", "params": {}})

        send(proc, {
            "method": "account/login/start",
            "id": 2,
            "params": {"type": "chatgptDeviceCode"},
        })
        login = wait_for_id(proc, 2, 60.0)
        if "error" in login:
            raise RuntimeError(f"login start failed: {login['error']}")
        result = login.get("result") or {}
        if result.get("type") != "chatgptDeviceCode":
            raise RuntimeError(f"unexpected login response: {result}")

        login_id = str(result["loginId"])
        verification_url = str(result["verificationUrl"])
        user_code = str(result["userCode"])
        auth_payload = {"verificationUrl": verification_url, "userCode": user_code}
        atomic_write_json(auth_file, auth_payload)
        print("P0_DEVICE_AUTH_READY", flush=True)

        completed = wait_login_completed(proc, login_id, 300.0)
        if not completed.get("success"):
            raise RuntimeError(f"login failed: {completed.get('error') or 'unknown error'}")

        wait_account_updated(proc, 30.0)

        send(proc, {"method": "account/rateLimits/read", "id": 3})
        rate = wait_for_id(proc, 3, 60.0)
        if "error" in rate:
            raise RuntimeError(f"rate limit read failed: {rate['error']}")

        sanitized = sanitize_rate_limits(rate.get("result") or {})
        atomic_write_json(quota_file, sanitized)
        print("P0_QUOTA_READY", flush=True)
        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
