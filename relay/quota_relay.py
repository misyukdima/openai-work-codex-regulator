#!/usr/bin/env python3
"""Read-only remote quota relay core for regulator v3.0.

The relay stores only sanitized quota snapshots. Device and reader credentials
are separate and stored as hashes. ChatGPT-facing adapters resolve an
authenticated subject server-side; the model never supplies relay credentials,
installation ids or account identifiers to get_quota_snapshot().

The pairing flow is intentionally device-code-like:

1. Companion starts pairing and receives an opaque verifier + device token.
2. Companion opens the HTTPS connect URL in the user's browser.
3. The authenticated web/app layer claims the pairing for its subject identity.
4. Companion polls pairing status with the verifier until CLAIMED.
5. ChatGPT app resolves subject -> installation on the server and reads quota.

No copy/paste token is required from the user.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

MAX_SNAPSHOT_BYTES = 32 * 1024
DEFAULT_RELAY_FRESHNESS_SECONDS = 15 * 60
DEFAULT_PAIRING_TTL_SECONDS = 10 * 60


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


@dataclass(frozen=True)
class PairingStart:
    pairing_id: str
    pairing_verifier: str
    installation_id: str
    device_token: str
    connect_url: str
    expires_at: str


def _token_hash(token: str, salt: str) -> str:
    return hashlib.sha256((salt + "\0" + token).encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_iso() -> str:
    return _iso(_utc_now())


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
    forbidden_fragments = (
        "token",
        "cookie",
        "password",
        "secret",
        "authorization",
        "email",
        "auth_file",
        "auth.json",
    )

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
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id TEXT PRIMARY KEY,
                installation_id TEXT NOT NULL UNIQUE REFERENCES installations(installation_id) ON DELETE CASCADE,
                bound_at TEXT NOT NULL
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS pairings (
                pairing_id TEXT PRIMARY KEY,
                verifier_salt TEXT NOT NULL,
                verifier_hash TEXT NOT NULL,
                installation_id TEXT NOT NULL UNIQUE REFERENCES installations(installation_id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                claimed_subject_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _insert_installation(
        self,
        installation_id: str,
        device_token: str,
        reader_token: str,
    ) -> InstallationCredentials:
        salt = secrets.token_urlsafe(18)
        try:
            self.db.execute(
                "INSERT INTO installations VALUES (?, ?, ?, ?, ?)",
                (
                    installation_id,
                    salt,
                    _token_hash(device_token, salt),
                    _token_hash(reader_token, salt),
                    _now_iso(),
                ),
            )
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            raise RelayError("INSTALLATION_EXISTS", "installation id already exists") from exc
        return InstallationCredentials(installation_id, device_token, reader_token)

    def provision_installation(self, installation_id: str | None = None) -> InstallationCredentials:
        ident = installation_id or secrets.token_urlsafe(18)
        return self._insert_installation(
            ident,
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
        )

    def start_pairing(
        self,
        connect_base_url: str,
        *,
        ttl_seconds: int = DEFAULT_PAIRING_TTL_SECONDS,
        now: datetime | None = None,
    ) -> PairingStart:
        if not connect_base_url.lower().startswith("https://"):
            raise RelayError("INSECURE_CONNECT_URL", "pairing connect URL must use HTTPS")

        current = (now or _utc_now()).astimezone(timezone.utc)
        pairing_id = secrets.token_urlsafe(18)
        verifier = secrets.token_urlsafe(32)
        verifier_salt = secrets.token_urlsafe(18)
        installation_id = secrets.token_urlsafe(18)
        device_token = secrets.token_urlsafe(32)
        reader_token = secrets.token_urlsafe(32)
        self._insert_installation(installation_id, device_token, reader_token)

        expires = current + timedelta(seconds=max(60, int(ttl_seconds)))
        self.db.execute(
            "INSERT INTO pairings VALUES (?, ?, ?, ?, 'PENDING', ?, NULL, ?)",
            (
                pairing_id,
                verifier_salt,
                _token_hash(verifier, verifier_salt),
                installation_id,
                _iso(expires),
                _iso(current),
            ),
        )
        self.db.commit()
        connect_url = connect_base_url.rstrip("/") + "/connect?" + urlencode({"pairing": pairing_id})
        return PairingStart(
            pairing_id=pairing_id,
            pairing_verifier=verifier,
            installation_id=installation_id,
            device_token=device_token,
            connect_url=connect_url,
            expires_at=_iso(expires),
        )

    def _pairing_row(self, pairing_id: str):
        return self.db.execute(
            """
            SELECT verifier_salt, verifier_hash, installation_id, status,
                   expires_at, claimed_subject_id
            FROM pairings WHERE pairing_id = ?
            """,
            (pairing_id,),
        ).fetchone()

    def _assert_pairing_not_expired(self, expires_at: str, now: datetime | None = None) -> None:
        expiry = _parse_iso(expires_at)
        current = (now or _utc_now()).astimezone(timezone.utc)
        if expiry is None or current >= expiry:
            raise RelayError("PAIRING_EXPIRED", "pairing request expired")

    def pairing_status(
        self,
        pairing_id: str,
        pairing_verifier: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        row = self._pairing_row(pairing_id)
        if row is None:
            raise RelayError("PAIRING_NOT_FOUND", "pairing request was not found")
        salt, expected, installation_id, status, expires_at, _subject = row
        if not hmac.compare_digest(expected, _token_hash(pairing_verifier, salt)):
            raise RelayError("PAIRING_UNAUTHORIZED", "pairing verifier is invalid")
        if status == "PENDING":
            self._assert_pairing_not_expired(expires_at, now=now)
        return {
            "status": status,
            "installation_id": installation_id if status == "CLAIMED" else None,
            "expires_at": expires_at,
        }

    def claim_pairing(
        self,
        pairing_id: str,
        authenticated_subject_id: str,
        *,
        now: datetime | None = None,
    ) -> str:
        """Bind a browser/app-authenticated subject to a pending installation.

        authenticated_subject_id comes from the production identity layer. It is
        server-side context, not model text and not a user-entered pairing token.
        """
        if not authenticated_subject_id:
            raise RelayError("SUBJECT_REQUIRED", "authenticated subject identity is required")
        row = self._pairing_row(pairing_id)
        if row is None:
            raise RelayError("PAIRING_NOT_FOUND", "pairing request was not found")
        _salt, _expected, installation_id, status, expires_at, claimed_subject = row
        if status == "CLAIMED":
            if claimed_subject == authenticated_subject_id:
                return installation_id
            raise RelayError("PAIRING_ALREADY_CLAIMED", "pairing request belongs to another subject")
        self._assert_pairing_not_expired(expires_at, now=now)

        try:
            self.db.execute(
                "INSERT INTO subjects VALUES (?, ?, ?)",
                (authenticated_subject_id, installation_id, _now_iso()),
            )
        except sqlite3.IntegrityError as exc:
            raise RelayError("SUBJECT_ALREADY_BOUND", "subject or installation is already bound") from exc
        self.db.execute(
            "UPDATE pairings SET status = 'CLAIMED', claimed_subject_id = ? WHERE pairing_id = ?",
            (authenticated_subject_id, pairing_id),
        )
        self.db.commit()
        return installation_id

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

    def _read_snapshot(
        self,
        installation_id: str,
        *,
        now: datetime | None = None,
        max_age_seconds: int = DEFAULT_RELAY_FRESHNESS_SECONDS,
    ) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT received_at, payload FROM snapshots WHERE installation_id = ?",
            (installation_id,),
        ).fetchone()
        if row is None:
            return {"status": "NO_SNAPSHOT", "snapshot": None}

        received_at, payload = row
        snapshot = json.loads(payload)
        captured = _parse_iso(snapshot.get("snapshot_at")) or _parse_iso(received_at)
        current = (now or _utc_now()).astimezone(timezone.utc)
        age = None if captured is None else max(0.0, (current - captured).total_seconds())
        relay_freshness = "UNKNOWN" if age is None else ("FRESH" if age <= max_age_seconds else "STALE")
        return {
            "status": "OK",
            "relay_freshness": relay_freshness,
            "relay_age_seconds": age,
            "received_at": received_at,
            "snapshot": snapshot,
        }

    def get_snapshot(
        self,
        installation_id: str,
        reader_token: str,
        *,
        now: datetime | None = None,
        max_age_seconds: int = DEFAULT_RELAY_FRESHNESS_SECONDS,
    ) -> dict[str, Any]:
        self._authorize(installation_id, reader_token, "reader_hash")
        return self._read_snapshot(
            installation_id,
            now=now,
            max_age_seconds=max_age_seconds,
        )

    def chat_tool_snapshot_for_subject(
        self,
        authenticated_subject_id: str,
        *,
        now: datetime | None = None,
        max_age_seconds: int = DEFAULT_RELAY_FRESHNESS_SECONDS,
    ) -> dict[str, Any]:
        """Server-side implementation behind zero-argument get_quota_snapshot()."""
        row = self.db.execute(
            "SELECT installation_id FROM subjects WHERE subject_id = ?",
            (authenticated_subject_id,),
        ).fetchone()
        if row is None:
            return {"status": "NOT_CONNECTED", "snapshot": None}
        return self._read_snapshot(
            row[0],
            now=now,
            max_age_seconds=max_age_seconds,
        )


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

        row = store.db.execute("SELECT device_hash, reader_hash FROM installations WHERE installation_id = ?", (creds.installation_id,)).fetchone()
        assert row is not None
        assert creds.device_token not in row
        assert creds.reader_token not in row

        # One-click pairing: no token copy/paste between browser and Companion.
        fixed_now = datetime(2026, 9, 7, 0, 0, tzinfo=timezone.utc)
        pairing = store.start_pairing("https://relay.example.test", now=fixed_now)
        assert pairing.connect_url.startswith("https://relay.example.test/connect?pairing=")
        pending = store.pairing_status(pairing.pairing_id, pairing.pairing_verifier, now=fixed_now)
        assert pending["status"] == "PENDING"
        assert pending["installation_id"] is None

        try:
            store.pairing_status(pairing.pairing_id, "wrong-verifier", now=fixed_now)
        except RelayError as exc:
            assert exc.code == "PAIRING_UNAUTHORIZED"
        else:
            raise AssertionError("invalid pairing verifier was accepted")

        subject = "subject-fixture-001"
        claimed_installation = store.claim_pairing(pairing.pairing_id, subject, now=fixed_now)
        assert claimed_installation == pairing.installation_id
        claimed = store.pairing_status(pairing.pairing_id, pairing.pairing_verifier, now=fixed_now)
        assert claimed["status"] == "CLAIMED"
        assert claimed["installation_id"] == pairing.installation_id

        store.put_snapshot(pairing.installation_id, pairing.device_token, envelope)
        chat_read = store.chat_tool_snapshot_for_subject(subject, now=fixed_now)
        assert chat_read["status"] == "OK"
        assert chat_read["snapshot"]["weekly_used"] == 35.0
        assert store.chat_tool_snapshot_for_subject("unknown-subject")["status"] == "NOT_CONNECTED"

        # Pairing verifier is stored only as a hash.
        verifier_row = store.db.execute(
            "SELECT verifier_hash FROM pairings WHERE pairing_id = ?",
            (pairing.pairing_id,),
        ).fetchone()
        assert verifier_row is not None
        assert pairing.pairing_verifier not in verifier_row
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
