#!/usr/bin/env python3
"""Trusted transport boundary for the Regulator quota Plugin.

The model-facing tool has zero arguments. A ChatGPT Plugin/App transport must
authenticate the caller first and pass the trusted subject to this service out
of band. This module deliberately contains no HTTP framework and no production
identity provider assumptions.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Callable, Protocol

# Support both package import (validator/tests) and direct development self-test.
try:
    from plugin.quota_backend import CodexAppServer, normalize_rate_limits
    from plugin.subject_store import SubjectAuthStore
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.quota_backend import CodexAppServer, normalize_rate_limits
    from plugin.subject_store import SubjectAuthStore


class AuthorizationRequired(RuntimeError):
    """No bound backend auth state exists for the authenticated Plugin subject."""


class InvalidToolArguments(ValueError):
    """The model attempted to supply arguments to the zero-argument quota tool."""


@dataclass(frozen=True)
class PluginRequestContext:
    """Trusted identity context produced by the Plugin transport, not the model."""

    authenticated_subject: str


class RateLimitReader(Protocol):
    def read_rate_limits(self) -> dict[str, Any]:
        ...


ReaderFactory = Callable[[str], AbstractContextManager[RateLimitReader]]


def default_reader_factory(codex_home: str) -> AbstractContextManager[RateLimitReader]:
    return CodexAppServer(codex_home=codex_home)


class QuotaService:
    """Read-only quota service behind the ChatGPT Plugin tool."""

    def __init__(
        self,
        *,
        auth_store: SubjectAuthStore,
        reader_factory: ReaderFactory = default_reader_factory,
    ) -> None:
        self.auth_store = auth_store
        self.reader_factory = reader_factory

    def get_quota_snapshot(self, context: PluginRequestContext) -> dict[str, Any]:
        subject = context.authenticated_subject
        if not self.auth_store.exists(subject):
            raise AuthorizationRequired("Plugin subject has no authorized quota session")

        auth_context = self.auth_store.open(subject)
        # subject_key/codex_home stay server-side. Neither appears in the result.
        with self.reader_factory(str(auth_context.codex_home)) as reader:
            raw = reader.read_rate_limits()
        snapshot = normalize_rate_limits(raw)

        forbidden_result_fields = {
            "subject",
            "subject_key",
            "authenticated_subject",
            "codex_home",
            "account_id",
            "workspace_id",
        }
        leaked = forbidden_result_fields.intersection(snapshot)
        if leaked:
            raise RuntimeError(f"identity field escaped quota normalization: {sorted(leaked)}")
        return snapshot

    def revoke(self, context: PluginRequestContext) -> bool:
        """Server-side revoke primitive; never exposed as the quota read tool."""
        return self.auth_store.revoke(context.authenticated_subject)


class QuotaToolHandler:
    """Adapter for the model-facing `get_quota_snapshot()` tool."""

    TOOL_NAME = "get_quota_snapshot"

    def __init__(self, service: QuotaService) -> None:
        self.service = service

    def call(
        self,
        context: PluginRequestContext,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        args = arguments or {}
        if args != {}:
            raise InvalidToolArguments("get_quota_snapshot accepts no model-provided arguments")
        return self.service.get_quota_snapshot(context)


# ---------- deterministic self-test ----------

class _FakeReader:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeReader":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read_rate_limits(self) -> dict[str, Any]:
        return self.payload


def self_test() -> None:
    from plugin.subject_store import EphemeralSubjectAuthStore

    pepper = b"p" * 32
    subject_a = "plugin-subject-a"
    subject_b = "plugin-subject-b"

    payload = {
        "ordinaryUsageAllowed": True,
        "rateLimitsByLimitId": {
            "codex": {
                "limitId": "codex",
                "planType": "plus",
                "primary": {
                    "usedPercent": 27,
                    "windowDurationMins": 10080,
                    "resetsAt": 2000000000,
                },
            }
        },
    }

    def fake_factory(_: str) -> _FakeReader:
        return _FakeReader(payload)

    with EphemeralSubjectAuthStore(pepper=pepper) as store:
        service = QuotaService(auth_store=store, reader_factory=fake_factory)
        tool = QuotaToolHandler(service)

        # No subject binding exists before authorization.
        try:
            tool.call(PluginRequestContext(subject_a))
        except AuthorizationRequired:
            pass
        else:
            raise AssertionError("unbound subject must require authorization")

        store.open(subject_a)
        result = tool.call(PluginRequestContext(subject_a), {})
        assert result["weekly_used"] == 27
        assert result["plan_type"] == "plus"
        serialized = repr(result)
        assert subject_a not in serialized
        assert "subject_key" not in result
        assert "codex_home" not in result

        # Model cannot override or select identity through tool arguments.
        for bad_args in (
            {"subject": subject_b},
            {"email": "other@example.com"},
            {"account_id": "other"},
            {"token": "opaque"},
        ):
            try:
                tool.call(PluginRequestContext(subject_a), bad_args)
            except InvalidToolArguments:
                pass
            else:
                raise AssertionError(f"model identity override must fail: {bad_args}")

        # Subject B is still unauthorized even though A has state.
        try:
            tool.call(PluginRequestContext(subject_b))
        except AuthorizationRequired:
            pass
        else:
            raise AssertionError("cross-subject auth reuse must fail")

        assert service.revoke(PluginRequestContext(subject_a)) is True
        try:
            tool.call(PluginRequestContext(subject_a))
        except AuthorizationRequired:
            pass
        else:
            raise AssertionError("revoked subject must require authorization")

    print("quota_service_self_test=ok")


if __name__ == "__main__":
    self_test()
