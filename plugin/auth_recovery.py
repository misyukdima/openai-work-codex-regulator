#!/usr/bin/env python3
"""Fail-closed recovery policy for the v3 quota Plugin backend.

A provider-neutral backend cannot guarantee recovery if an upstream refresh token
was rotated remotely and the worker crashed before the updated `auth.json` was
resealed. The safe contract is bounded retry for transport failures, then
explicit reauthorization. Unknown/corrupt auth never becomes stale quota or
synthetic zero usage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import time
from typing import Any

try:
    from plugin.quota_backend import CodexProtocolError, CodexProtocolTimeout
    from plugin.quota_service import AuthorizationRequired, PluginRequestContext, QuotaService
    from plugin.sealed_auth_store import InvalidAuthBlob, SealedAuthNotFound
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.quota_backend import CodexProtocolError, CodexProtocolTimeout
    from plugin.quota_service import AuthorizationRequired, PluginRequestContext, QuotaService
    from plugin.sealed_auth_store import InvalidAuthBlob, SealedAuthNotFound


class RecoveryAction(str, Enum):
    RETRY = "RETRY"
    NEEDS_REAUTH = "NEEDS_REAUTH"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    code: str


class ReauthorizationRequired(RuntimeError):
    """Public-safe signal that trusted Connect/Auth must run again."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"quota authorization requires reconnect: {code}")


class QuotaTemporarilyUnavailable(RuntimeError):
    """Public-safe failure after bounded recovery attempts."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"quota telemetry temporarily unavailable: {code}")


_AUTH_REJECTION_MARKERS = (
    "authentication required",
    "not authenticated",
    "unauthorized",
    "authentication_required",
)

_TRANSIENT_TRANSPORT_MARKERS = (
    "codex app-server exited",
    "codex app-server closed stdout",
)


def classify_recovery(exc: BaseException) -> RecoveryDecision:
    """Map internal failures to bounded public recovery actions.

    String inspection is deliberately limited to known official-backend error
    classes and fixed markers. Raw provider messages are never returned to the
    caller or model.
    """
    if isinstance(exc, (AuthorizationRequired, SealedAuthNotFound)):
        return RecoveryDecision(RecoveryAction.NEEDS_REAUTH, "AUTH_MISSING")
    if isinstance(exc, InvalidAuthBlob):
        return RecoveryDecision(RecoveryAction.NEEDS_REAUTH, "AUTH_CORRUPT")
    if isinstance(exc, CodexProtocolError):
        message = str(exc).lower()
        if any(marker in message for marker in _AUTH_REJECTION_MARKERS):
            return RecoveryDecision(RecoveryAction.NEEDS_REAUTH, "AUTH_REJECTED")
        return RecoveryDecision(RecoveryAction.UNAVAILABLE, "UPSTREAM_PROTOCOL")
    if isinstance(exc, CodexProtocolTimeout):
        return RecoveryDecision(RecoveryAction.RETRY, "UPSTREAM_TIMEOUT")
    if isinstance(exc, OSError):
        return RecoveryDecision(RecoveryAction.RETRY, "UPSTREAM_IO")
    if isinstance(exc, RuntimeError):
        message = str(exc).lower()
        if any(marker in message for marker in _TRANSIENT_TRANSPORT_MARKERS):
            return RecoveryDecision(RecoveryAction.RETRY, "UPSTREAM_PROCESS")
    return RecoveryDecision(RecoveryAction.UNAVAILABLE, "BACKEND_FAILURE")


class RecoveringQuotaService:
    """Wrap QuotaService with one bounded, evidence-preserving retry policy."""

    def __init__(
        self,
        base_service: QuotaService,
        *,
        max_transient_retries: int = 1,
        retry_delay_seconds: float = 0.0,
    ) -> None:
        if max_transient_retries < 0 or max_transient_retries > 1:
            raise ValueError("v3 recovery policy allows at most one transient retry")
        if retry_delay_seconds < 0 or retry_delay_seconds > 2.0:
            raise ValueError("retry delay must be bounded to 0..2 seconds")
        self.base_service = base_service
        self.max_transient_retries = max_transient_retries
        self.retry_delay_seconds = retry_delay_seconds

    @property
    def auth_store(self) -> Any:
        return self.base_service.auth_store

    def get_quota_snapshot(self, context: PluginRequestContext) -> dict[str, Any]:
        attempts = 0
        while True:
            try:
                return self.base_service.get_quota_snapshot(context)
            except Exception as exc:
                decision = classify_recovery(exc)
                if decision.action == RecoveryAction.NEEDS_REAUTH:
                    raise ReauthorizationRequired(decision.code) from None
                if decision.action == RecoveryAction.RETRY and attempts < self.max_transient_retries:
                    attempts += 1
                    if self.retry_delay_seconds:
                        time.sleep(self.retry_delay_seconds)
                    continue
                code = (
                    f"{decision.code}_RETRY_EXHAUSTED"
                    if decision.action == RecoveryAction.RETRY
                    else decision.code
                )
                raise QuotaTemporarilyUnavailable(code) from None

    def revoke(self, context: PluginRequestContext) -> bool:
        return self.base_service.revoke(context)


class _SequenceService:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.auth_store = object()

    def get_quota_snapshot(self, context: PluginRequestContext) -> dict[str, Any]:
        self.calls += 1
        if not self.outcomes:
            raise AssertionError("unexpected recovery call")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def revoke(self, context: PluginRequestContext) -> bool:
        return True


def self_test() -> None:
    import json

    from plugin.sealed_auth_store import (
        InMemoryBlobStore,
        ReversibleTestCipher,
        SealedSubjectAuthStore,
    )

    context = PluginRequestContext("recovery-subject")

    assert classify_recovery(AuthorizationRequired("x")).code == "AUTH_MISSING"
    assert classify_recovery(InvalidAuthBlob("x")).code == "AUTH_CORRUPT"
    auth_rejected = CodexProtocolError(
        "account/rateLimits/read failed: code=-1 message=authentication required"
    )
    assert classify_recovery(auth_rejected).code == "AUTH_REJECTED"
    assert classify_recovery(CodexProtocolTimeout("x")).action == RecoveryAction.RETRY

    transient = _SequenceService(
        [CodexProtocolTimeout("first"), {"weekly_used": 23, "five_hour_used": None}]
    )
    recovered = RecoveringQuotaService(transient, max_transient_retries=1)
    assert recovered.get_quota_snapshot(context)["weekly_used"] == 23
    assert transient.calls == 2

    exhausted = _SequenceService([CodexProtocolTimeout("one"), CodexProtocolTimeout("two")])
    try:
        RecoveringQuotaService(exhausted).get_quota_snapshot(context)
    except QuotaTemporarilyUnavailable as exc:
        assert exc.code == "UPSTREAM_TIMEOUT_RETRY_EXHAUSTED"
        assert "one" not in str(exc) and "two" not in str(exc)
    else:
        raise AssertionError("bounded retry exhaustion must fail closed")
    assert exhausted.calls == 2

    rejected = _SequenceService([auth_rejected])
    try:
        RecoveringQuotaService(rejected).get_quota_snapshot(context)
    except ReauthorizationRequired as exc:
        assert exc.code == "AUTH_REJECTED"
        assert "authentication required" not in str(exc).lower()
    else:
        raise AssertionError("rejected auth must require reconnect")
    assert rejected.calls == 1

    unknown = _SequenceService([ValueError("provider detail that must stay internal")])
    try:
        RecoveringQuotaService(unknown).get_quota_snapshot(context)
    except QuotaTemporarilyUnavailable as exc:
        assert exc.code == "BACKEND_FAILURE"
        assert "provider detail" not in str(exc)
    else:
        raise AssertionError("unknown failure must fail closed")
    assert unknown.calls == 1

    # A backend crash/exception after changing temporary auth.json must not mark
    # that partial state as durable success. Context-manager exceptional exit
    # keeps the prior sealed blob and removes the temporary plaintext directory.
    pepper = b"r" * 32
    store = SealedSubjectAuthStore(
        pepper=pepper,
        blob_store=InMemoryBlobStore(),
        cipher=ReversibleTestCipher(),
    )
    subject = "crash-recovery-subject"
    with store.authorization_session(subject) as auth_context:
        (auth_context.codex_home / "auth.json").write_text(
            json.dumps({"auth_mode": "chatgpt", "generation": 0}),
            encoding="utf-8",
        )

    crash_home: Path | None = None
    try:
        with store.materialize(subject) as auth_context:
            crash_home = auth_context.codex_home
            (auth_context.codex_home / "auth.json").write_text(
                json.dumps({"auth_mode": "chatgpt", "generation": 1}),
                encoding="utf-8",
            )
            raise RuntimeError("simulated worker crash")
    except RuntimeError as exc:
        assert str(exc) == "simulated worker crash"
    else:
        raise AssertionError("simulated backend crash must propagate")
    assert crash_home is not None and not crash_home.exists()

    with store.materialize(subject) as auth_context:
        durable = json.loads((auth_context.codex_home / "auth.json").read_text(encoding="utf-8"))
        assert durable["generation"] == 0

    print("auth_recovery_self_test=ok")


if __name__ == "__main__":
    self_test()
