#!/usr/bin/env python3
"""Read-only remote quota relay core for regulator v3.0.

The relay stores only sanitized quota snapshots. Device and reader credentials
are separate and stored as keyed hashes. ChatGPT-facing adapters must resolve
the authenticated installation server-side; the model must never provide raw
relay credentials or an installation id as normal tool arguments.

This module is deliberately stdlib-only so repository validation can exercise
the security boundary without requiring a deployed service.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_SNAPSHOT_BYTES = 32 * 1024
DEFAULT_RELAY_FRESHNESS_SECONDS = 15 * 60


class RelayError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class InstallationCredentials:
    installation_id: str
    device_token: str
    reader_token: str


def _token_hash(token: str, salt: str) -> str:
    return hashlib.sha256((salt + "\0" + token).encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
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
    forbidden_fragments = ("token", "cookie", "password", "secret", "authorization", "email", "auth_file", "auth.json")

    if not isinstance(snapshot, dict):
        raise RelayError("INVALID_SNAPSHOT", "snapshot must be an object")
    unexpected = set(snapshot) - allowed
    if unexpected:
        raise RelayError("UNSAFE_SNAPSHOT_FIELDS", "snapshot contains fields outside the telemetry contract")
    for key in snapshot:
        lowered = key.lower()
        if any(fragment in lowered for fragment in forbidden_fragments):
            raise RelayError("UNSAFE_SNAPSHOT_FIELDS", "snapshot contains credential-like fields")

    if snapshot.get("allowance_domain") != "WORK_CODEX":
        raise RelayError("INVALID_ALLOWANCE_DOMAIN", "relay accepts only normalized WORK_CODEX telemetry")
    if snapshot.get("weekly_meter_semantics") not in ("USED", "UNKNOWN"):
        raise RelayError("INVALID_METER_SEMANTICS", "unsupported weekly meter semantics")

    encoded = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise RelayError("SNAPSHOT_TOO_LARGE", "snapshot exceeds relay size limit")

    return json.loads(encoded.decode("utf-8"))


class RelayStore:
    def __init__(self, database: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(database))
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS installations (
                installation_id TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                device_hash TEXT NOT NULL,
                reader_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                installation_id TEXT PRIMARY KEY REFERENCES installations(installation_id) ON DELETE CASCADE,
                received_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def provision_installation(self, installation_id: str | None = None) -> InstallationCredentials:
        ident = installation_id or secrets.token_urlsafe(18)
        device_token = secrets.token_urlsafe(32)
        reader_token = secrets.token_urlsafe(32)
        salt = secrets.token_urlsafe(18)
        try:
            self.db.execute(
                "INSERT INTO installations VALUES (?, ?, ?, ?, ?)",
                (ident, salt, _token_hash(device_token, salt), _token_hash(reader_token, salt), _now_iso()),
            )
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            raise RelayError("INSTALLATION_EXISTS", "installation id already exists") from exc
        return InstallationCredentials(ident, device_token, reader_token)

    def _authorize(self, installation_id: str, token: str, column: str) -> None:
        if column not in ("device_hash", "reader_hash"):
            raise ValueError("invalid credential column")
        row = self.db.execute(
            f"SELECT salt, {column} FROM installations WHERE installation_id = ?",
            (installation_id,),
        ).fetchone()
        if row is None:
            raise RelayError("NOT_FOUND", "installation was not found")
        salt, expected = row
        supplied = _token_hash(token, salt)
        if not hmac.compare_digest(expected, supplied):
            raise RelayError("UNAUTHORIZED", "relay credential is invalid")

    def put_snapshot(self, installation_id: str, device_token: str, envelope: dict[str, Any]) -> None:
        self._authorize(installation_id, device_token, "device_hash")
        if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "snapshot"}:
            raise RelayError("INVALID_ENVELOPE", "relay envelope does not match schema")
        if envelope.get("schema_version") != 1:
            raise RelayError("INVALID_ENVELOPE", "unsupported relay envelope version")
        snapshot = _validate_snapshot(envelope.get("snapshot"))
        payload = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False)
        self.db.execute(
            """
            INSERT INTO snapshots (installation_id, received_at, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(installation_id) DO UPDATE SET
                received_at = excluded.received_at,
                payload = excluded.payload
            """,
            (installation_id, _now_iso(), payload),
        )
        self.db.commit()

    def get_snapshot(
        self,
        installation_id: str,
        reader_token: str,
        *,
        now: datetime | None = None,
        max_age_seconds: int = DEFAULT_RELAY_FRESHNESS_SECONDS,
    ) -> dict[str, Any]:
        self._authorize(installation_id, reader_token, "reader_hash")
        row = self.db.execute(
            "SELECT received_at, payload FROM snapshots WHERE installation_id = ?",
            (installation_id,),
        ).fetchone()
        if row is None:
            return {"status": "NO_SNAPSHOT", "snapshot": None}

        received_at, payload = row
        snapshot = json.loads(payload)
        captured = _parse_iso(snapshot.get("snapshot_at")) or _parse_iso(received_at)
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        age = None if captured is None else max(0.0, (current - captured).total_seconds())
        relay_freshness = "UNKNOWN" if age is None else ("FRESH" if age <= max_age_seconds else "STALE")
        return {
            "status": "OK",
            "relay_freshness": relay_freshness,
            "relay_age_seconds": age,
            "received_at": received_at,
            "snapshot": snapshot,
        }

    def chat_tool_snapshot(self, installation_id: str, reader_token: str) -> dict[str, Any]:
        """Server-side implementation behind get_quota_snapshot().

        The future MCP/app adapter authenticates the ChatGPT connection and
        resolves installation_id + reader_token before calling this method.
        Those values are never model-visible tool arguments.
        """
        return self.get_snapshot(installation_id, reader_token)


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="regulator-relay-test-") as tmp:
        store = RelayStore(Path(tmp) / "relay.sqlite3")
        creds = store.provision_installation("test-installation")
        assert creds.device_token != creds.reader_token

        envelope = {
            "schema_version": 1,
            "snapshot": {
                "schema_version": 1,
                "allowance_domain": "WORK_CODEX",
                "source": "CODEXBAR_OAUTH",
                "sensor": "CODEXBAR",
                "snapshot_at": "2026-09-07T00:00:00Z",
                "freshness": "FRESH",
                "age_seconds": 10.0,
                "weekly_meter_semantics": "USED",
                "weekly_used": 35.0,
                "weekly_reset": "2026-09-12T10:00:00Z",
                "five_hour_used": 12.0,
                "five_hour_reset": "2026-09-07T03:00:00Z",
                "other_windows": [],
            },
        }
        store.put_snapshot(creds.installation_id, creds.device_token, envelope)
        result = store.get_snapshot(creds.installation_id, creds.reader_token)
        assert result["status"] == "OK"
        assert result["snapshot"]["weekly_used"] == 35.0

        try:
            store.get_snapshot(creds.installation_id, creds.device_token)
        except RelayError as exc:
            assert exc.code == "UNAUTHORIZED"
        else:
            raise AssertionError("device credential was accepted as reader credential")

        unsafe = {
            "schema_version": 1,
            "snapshot": dict(envelope["snapshot"], oauth_token="do-not-store"),
        }
        try:
            store.put_snapshot(creds.installation_id, creds.device_token, unsafe)
        except RelayError as exc:
            assert exc.code == "UNSAFE_SNAPSHOT_FIELDS"
        else:
            raise AssertionError("credential-like snapshot field was stored")

        row = store.db.execute("SELECT device_hash, reader_hash FROM installations").fetchone()
        assert row is not None
        assert creds.device_token not in row
        assert creds.reader_token not in row
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Regulator v3.0 quota relay core")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("quota relay self-test OK")
        return
    parser.error("This module is a relay core; deploy it through an authenticated HTTPS app adapter.")


if __name__ == "__main__":
    main()
