#!/usr/bin/env python3
"""Local quota companion core for regulator v3.0.

The companion is a sensor/transport component, not an orchestrator. It reads a
supported local telemetry source, normalizes the result through
scripts/quota_telemetry.py and may publish only the sanitized snapshot to a
remote relay that ChatGPT can read.

No OpenAI bearer token, browser cookie or raw auth file is returned by this
module. The first reference sensor is CodexBar/CodexBarCLI. A production app may
bundle that helper or provide another compatible sensor behind the same
interface.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_PATH = ROOT / "scripts" / "quota_telemetry.py"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RELAY_TIMEOUT_SECONDS = 10


class CompanionError(RuntimeError):
    """Safe, bounded companion failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SensorStatus:
    state: str
    sensor: str
    detail: str
    snapshot: dict[str, Any] | None


def _load_telemetry_module():
    spec = importlib.util.spec_from_file_location("regulator_quota_telemetry", TELEMETRY_PATH)
    if spec is None or spec.loader is None:
        raise CompanionError("TELEMETRY_MODULE_UNAVAILABLE", "quota telemetry normalizer is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _candidate_codexbar_paths() -> list[Path]:
    candidates: list[Path] = []

    explicit = os.environ.get("REGULATOR_CODEXBAR_BIN") or os.environ.get("CODEXBAR_BIN")
    if explicit:
        candidates.append(Path(explicit).expanduser())

    # Production Companion may ship a helper inside its own bundle/resources.
    executable = Path(sys.executable).resolve()
    candidates.extend(
        [
            executable.parent / "Helpers" / "CodexBarCLI",
            ROOT / "companion" / "Helpers" / "CodexBarCLI",
            Path("/Applications/OpenAI Work + Codex Regulator.app/Contents/Helpers/CodexBarCLI"),
            Path("/Applications/CodexBar.app/Contents/Helpers/CodexBarCLI"),
        ]
    )

    for name in ("codexbar", "CodexBarCLI"):
        resolved = shutil.which(name)
        if resolved:
            candidates.append(Path(resolved))

    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def discover_codexbar() -> Path | None:
    for path in _candidate_codexbar_paths():
        try:
            if path.is_file() and os.access(path, os.X_OK):
                return path
        except OSError:
            continue
    return None


def _safe_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def collect_codexbar_snapshot(
    binary: Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    command = [
        str(binary),
        "usage",
        "--provider",
        "codex",
        "--source",
        "oauth",
        "--format",
        "json",
        "--json-only",
        "--no-color",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            env=_safe_subprocess_env(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CompanionError("SENSOR_TIMEOUT", "quota sensor did not respond in time") from exc
    except OSError as exc:
        raise CompanionError("SENSOR_EXEC_FAILED", "quota sensor could not be started") from exc

    if result.returncode != 0:
        # Do not return raw stderr: upstream tools may include paths/account data.
        raise CompanionError("SENSOR_READ_FAILED", "quota sensor could not read current usage")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CompanionError("SENSOR_INVALID_JSON", "quota sensor returned invalid JSON") from exc

    telemetry = _load_telemetry_module()
    try:
        snapshot = telemetry.normalize_codexbar(payload)
    except Exception as exc:
        raise CompanionError("SENSOR_UNSAFE_PAYLOAD", f"quota telemetry could not be normalized safely: {exc}") from exc

    return telemetry.snapshot_dict(snapshot)


def collect_snapshot() -> SensorStatus:
    binary = discover_codexbar()
    if binary is None:
        return SensorStatus(
            state="UNAVAILABLE",
            sensor="CODEXBAR",
            detail="No bundled or installed CodexBar-compatible sensor is available.",
            snapshot=None,
        )

    try:
        snapshot = collect_codexbar_snapshot(binary)
    except CompanionError as exc:
        return SensorStatus(state="ERROR", sensor="CODEXBAR", detail=exc.code, snapshot=None)

    return SensorStatus(state="READY", sensor="CODEXBAR", detail="OK", snapshot=snapshot)


def sanitized_envelope(status: SensorStatus) -> dict[str, Any]:
    """Return the only payload allowed to cross the Companion→relay boundary."""
    if status.state != "READY" or status.snapshot is None:
        raise CompanionError("SNAPSHOT_NOT_READY", "no normalized quota snapshot is ready to publish")

    allowed = {
        "schema_version",
        "allowance_domain",
        "source",
        "sensor",
        "snapshot_at",
        "freshness",
        "age_seconds",
        "weekly_meter_semantics",
        "weekly_used",
        "weekly_reset",
        "five_hour_used",
        "five_hour_reset",
        "other_windows",
    }
    snapshot = {key: value for key, value in status.snapshot.items() if key in allowed}
    return {"schema_version": 1, "snapshot": snapshot}


def push_snapshot(
    relay_base_url: str,
    installation_id: str,
    device_token: str,
    status: SensorStatus,
    *,
    timeout_seconds: int = DEFAULT_RELAY_TIMEOUT_SECONDS,
) -> None:
    if not relay_base_url.lower().startswith("https://"):
        raise CompanionError("INSECURE_RELAY", "production relay URL must use HTTPS")
    if not installation_id or not device_token:
        raise CompanionError("PAIRING_REQUIRED", "companion is not paired with a relay installation")

    body = json.dumps(sanitized_envelope(status), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    url = relay_base_url.rstrip("/") + f"/v1/installations/{installation_id}/snapshot"
    request = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {device_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "openai-work-codex-regulator-companion/3.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1, int(timeout_seconds))) as response:
            if response.status < 200 or response.status >= 300:
                raise CompanionError("RELAY_REJECTED", "relay rejected quota snapshot")
    except urllib.error.HTTPError as exc:
        raise CompanionError("RELAY_REJECTED", f"relay rejected quota snapshot ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise CompanionError("RELAY_UNREACHABLE", "quota relay is currently unreachable") from exc


def self_test() -> None:
    fixture = {
        "provider": "codex",
        "source": "oauth",
        "updatedAt": "2026-09-07T00:00:00Z",
        "usage": {
            "primary": {"usedPercent": 12, "windowMinutes": 300, "resetsAt": "2026-09-07T03:00:00Z"},
            "secondary": {"usedPercent": 34, "windowMinutes": 10080, "resetsAt": "2026-09-12T10:00:00Z"},
        },
    }

    with tempfile.TemporaryDirectory(prefix="regulator-companion-test-") as tmp:
        helper = Path(tmp) / "codexbar"
        helper.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            f"print(json.dumps({fixture!r}))\n",
            encoding="utf-8",
        )
        helper.chmod(0o755)

        snapshot = collect_codexbar_snapshot(helper)
        assert snapshot["weekly_used"] == 34
        assert snapshot["five_hour_used"] == 12
        assert snapshot["source"] == "CODEXBAR_OAUTH"
        envelope = sanitized_envelope(SensorStatus("READY", "CODEXBAR", "OK", snapshot))
        encoded = json.dumps(envelope)
        for forbidden in ("token", "cookie", "auth.json", "email"):
            assert forbidden not in encoded.lower()

    # A local HTTP URL must never be accepted as the production Chat bridge.
    try:
        push_snapshot("http://127.0.0.1:8080", "x", "y", SensorStatus("READY", "CODEXBAR", "OK", snapshot))
    except CompanionError as exc:
        assert exc.code == "INSECURE_RELAY"
    else:
        raise AssertionError("insecure relay URL was accepted")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Regulator v3.0 local quota companion core")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true", help="print current sanitized status as JSON")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("quota companion self-test OK")
        return

    status = collect_snapshot()
    if args.json:
        print(json.dumps(asdict(status), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{status.state}: {status.detail}")


if __name__ == "__main__":
    main()
