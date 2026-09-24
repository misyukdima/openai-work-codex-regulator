#!/usr/bin/env python3
"""Official Streamable HTTP MCP transport for the v3 quota Plugin.

This layer is intentionally narrow:
- one model-visible tool: get_quota_snapshot;
- exact zero-argument input schema from the canonical tool contract;
- server-wide OAuth bearer gate supplied by the official MCP SDK;
- trusted identity resolved only from a verified AccessToken;
- quota facts delegated to the existing QuotaToolHandler;
- no OAuth authorization server, JWT implementation, Codex credential logic,
  routing, model selection, admission, purchases, or shell access.

Production injects a reviewed TokenVerifier. The repository does not implement
an identity provider or accept caller-supplied bearer-token parsing as proof.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Protocol
from urllib.parse import urlparse

from mcp.server import Server, ServerRequestContext
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)
from pydantic import AnyHttpUrl

try:
    from plugin.quota_service import (
        AuthorizationRequired,
        InvalidToolArguments,
        PluginRequestContext,
        QuotaToolHandler,
    )
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.quota_service import (
        AuthorizationRequired,
        InvalidToolArguments,
        PluginRequestContext,
        QuotaToolHandler,
    )


TOOL_CONTRACT_PATH = Path(__file__).with_name("get_quota_snapshot.tool.json")
MCP_PATH = "/mcp"
DEFAULT_REQUIRED_SCOPES = ("quota:read",)
SERVER_NAME = "openai-work-codex-regulator-quota"
SERVER_VERSION = "3.0.0"


class MCPTransportConfigurationError(RuntimeError):
    pass


class InvalidVerifiedPrincipal(RuntimeError):
    pass


class QuotaHandler(Protocol):
    def call(
        self,
        context: PluginRequestContext,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class MCPTransportConfig:
    issuer_url: str
    resource_server_url: str
    required_scopes: tuple[str, ...] = DEFAULT_REQUIRED_SCOPES
    allowed_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        issuer = _validated_url(self.issuer_url, "issuer_url", allow_local_http=True)
        resource = _validated_url(
            self.resource_server_url,
            "resource_server_url",
            allow_local_http=True,
        )
        if resource.path.rstrip("/") != MCP_PATH:
            raise MCPTransportConfigurationError(
                f"resource_server_url must end with {MCP_PATH}"
            )
        if not self.required_scopes:
            raise MCPTransportConfigurationError("at least one OAuth scope is required")
        if len(set(self.required_scopes)) != len(self.required_scopes):
            raise MCPTransportConfigurationError("OAuth scopes must be unique")
        for scope in self.required_scopes:
            if not scope or scope.strip() != scope or any(ch.isspace() for ch in scope):
                raise MCPTransportConfigurationError("OAuth scopes must be non-empty tokens")
        if issuer.query or issuer.fragment or resource.query or resource.fragment:
            raise MCPTransportConfigurationError("issuer/resource URLs must not contain query or fragment")


def _validated_url(value: str, label: str, *, allow_local_http: bool) -> Any:
    if not isinstance(value, str) or not value.strip():
        raise MCPTransportConfigurationError(f"{label} must be a non-empty URL")
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise MCPTransportConfigurationError(f"{label} must be absolute")
    host = (parsed.hostname or "").lower()
    local = host in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (allow_local_http and parsed.scheme == "http" and local):
        raise MCPTransportConfigurationError(
            f"{label} must use https outside local development"
        )
    return parsed


def load_tool_contract() -> dict[str, Any]:
    contract = json.loads(TOOL_CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract.get("name") != "get_quota_snapshot":
        raise MCPTransportConfigurationError("canonical quota tool has unexpected name")
    return contract


def _security_schemes(contract: dict[str, Any]) -> list[dict[str, Any]]:
    schemes = contract.get("securitySchemes")
    if schemes != [{"type": "oauth2", "scopes": ["quota:read"]}]:
        raise MCPTransportConfigurationError("canonical quota tool OAuth scheme drifted")
    return [dict(scheme) for scheme in schemes]


def build_tool_definition() -> Tool:
    """Build exact model-visible tool metadata from the canonical JSON contract.

    MCP Python v2.1.1 does not expose a typed top-level `securitySchemes` Tool
    field. OpenAI's authenticated Python example mirrors the scheme in `_meta`,
    while this server also enforces OAuth for the entire MCP endpoint. If the SDK
    gains a typed field later, migration must be explicit and regression-tested.
    """
    contract = load_tool_contract()
    annotations = contract.get("annotations") or {}
    return Tool(
        name=contract["name"],
        title="Read Work/Codex quota",
        description=contract["description"],
        input_schema=contract["inputSchema"],
        output_schema=contract["outputSchema"],
        annotations=ToolAnnotations(
            read_only_hint=annotations.get("readOnlyHint"),
            destructive_hint=annotations.get("destructiveHint"),
            idempotent_hint=annotations.get("idempotentHint"),
            open_world_hint=annotations.get("openWorldHint"),
        ),
        _meta={"securitySchemes": _security_schemes(contract)},
    )


def _audience_matches(token: AccessToken, expected: str) -> bool:
    if token.resource is not None and str(token.resource) == expected:
        return True
    claims = token.claims or {}
    aud = claims.get("aud")
    if isinstance(aud, str):
        return aud == expected
    if isinstance(aud, (list, tuple)):
        return expected in {str(item) for item in aud}
    return False


def trusted_subject_from_access_token(
    token: AccessToken | None,
    config: MCPTransportConfig,
    *,
    now: int | None = None,
) -> str:
    """Resolve a stable trusted subject from an already verified bearer token.

    The injected TokenVerifier remains responsible for signature validation.
    This boundary independently fails closed on issuer, resource/audience, expiry,
    scopes and missing subject before the quota service sees an identity.
    """
    if token is None:
        raise InvalidVerifiedPrincipal("verified access token is missing")

    subject = token.subject.strip() if isinstance(token.subject, str) else ""
    if not subject or len(subject.encode("utf-8")) > 2048:
        raise InvalidVerifiedPrincipal("verified token subject is missing or invalid")

    claims = token.claims or {}
    issuer = claims.get("iss")
    if issuer != config.issuer_url:
        raise InvalidVerifiedPrincipal("verified token issuer does not match configured issuer")

    if not _audience_matches(token, config.resource_server_url):
        raise InvalidVerifiedPrincipal("verified token audience/resource mismatch")

    scope_set = set(token.scopes or [])
    if not set(config.required_scopes).issubset(scope_set):
        raise InvalidVerifiedPrincipal("verified token lacks required quota scope")

    current = int(time.time()) if now is None else int(now)
    if token.expires_at is not None and int(token.expires_at) <= current:
        raise InvalidVerifiedPrincipal("verified token is expired")
    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and int(nbf) > current:
        raise InvalidVerifiedPrincipal("verified token is not active yet")

    # Issuer + subject is the identity namespace. SubjectAuthStore applies the
    # server-held HMAC pepper before any durable path/key is derived.
    return f"{config.issuer_url}\x1f{subject}"


def _error_result(message: str, code: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        is_error=True,
        _meta={"regulator/error_code": code},
    )


def dispatch_tool_call(
    handler: QuotaHandler,
    config: MCPTransportConfig,
    token: AccessToken | None,
    tool_name: str,
    arguments: dict[str, Any] | None,
) -> CallToolResult:
    if tool_name != "get_quota_snapshot":
        return _error_result("Unknown quota tool.", "UNKNOWN_TOOL")

    try:
        subject = trusted_subject_from_access_token(token, config)
    except InvalidVerifiedPrincipal:
        return _error_result(
            "MCP authorization could not be verified.",
            "MCP_AUTH_INVALID",
        )

    try:
        snapshot = handler.call(
            PluginRequestContext(authenticated_subject=subject),
            arguments,
        )
    except InvalidToolArguments:
        return _error_result(
            "get_quota_snapshot accepts no arguments.",
            "INVALID_TOOL_ARGUMENTS",
        )
    except AuthorizationRequired:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text="Quota account authorization is required.",
                )
            ],
            is_error=True,
            _meta={
                "regulator/error_code": "QUOTA_AUTH_REQUIRED",
                "regulator/auth_state": "NEEDS_QUOTA_AUTH",
            },
        )
    except Exception:
        # Never expose raw provider/Codex/vault errors through MCP.
        return _error_result(
            "Quota telemetry is temporarily unavailable.",
            "QUOTA_UNAVAILABLE",
        )

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text="Current Work/Codex quota snapshot retrieved.",
            )
        ],
        structured_content=snapshot,
    )


def build_server(handler: QuotaHandler, config: MCPTransportConfig) -> Server:
    async def list_tools(
        ctx: ServerRequestContext,
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        del ctx, params
        return ListToolsResult(tools=[build_tool_definition()])

    async def call_tool(
        ctx: ServerRequestContext,
        params: CallToolRequestParams,
    ) -> CallToolResult:
        del ctx
        return dispatch_tool_call(
            handler,
            config,
            get_access_token(),
            params.name,
            params.arguments,
        )

    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def _transport_security(config: MCPTransportConfig) -> TransportSecuritySettings:
    parsed = urlparse(config.resource_server_url)
    assert parsed.netloc
    origin = f"{parsed.scheme}://{parsed.netloc}"
    origins = [origin, *config.allowed_origins]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[parsed.netloc],
        allowed_origins=list(dict.fromkeys(origins)),
    )


def build_app(
    handler: QuotaHandler,
    config: MCPTransportConfig,
    *,
    token_verifier: TokenVerifier,
):
    """Build the production-shaped stateless Streamable HTTP ASGI app.

    The official SDK mounts `/mcp`, the bearer authorization gate and RFC 9728
    protected-resource metadata. The authorization server itself is deliberately
    external to this module.
    """
    if token_verifier is None:
        raise MCPTransportConfigurationError("production MCP transport requires TokenVerifier")

    server = build_server(handler, config)
    return server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        transport_security=_transport_security(config),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(config.issuer_url),
            resource_server_url=AnyHttpUrl(config.resource_server_url),
            required_scopes=list(config.required_scopes),
        ),
        token_verifier=token_verifier,
    )


class _FakeQuotaService:
    def __init__(self) -> None:
        self.last_subject: str | None = None
        self.raise_authorization = False
        self.raise_unexpected = False

    def get_quota_snapshot(self, context: PluginRequestContext) -> dict[str, Any]:
        self.last_subject = context.authenticated_subject
        if self.raise_authorization:
            raise AuthorizationRequired("test-only authorization state")
        if self.raise_unexpected:
            raise RuntimeError("SECRET_TEST_PROVIDER_DETAIL")
        return {
            "schema_version": 1,
            "allowance_domain": "WORK_CODEX",
            "source": "OPENAI_CODEX_APP_SERVER",
            "snapshot_at": "2026-09-07T09:55:00+00:00",
            "freshness": "FRESH",
            "weekly_meter_semantics": "USED",
            "weekly_used": 31,
            "weekly_reset": 2000000000,
            "five_hour_used": None,
            "five_hour_reset": None,
            "other_windows": [],
            "plan_type": "plus",
            "ordinary_usage_allowed": True,
            "credits": {"has_credits": False, "unlimited": False, "balance": 0},
        }


class _NeverCalledVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        raise AssertionError("self-test must not parse a live bearer token")


def _test_token(config: MCPTransportConfig, **overrides: Any) -> AccessToken:
    values: dict[str, Any] = {
        "token": "test-only-opaque",
        "client_id": "test-client",
        "scopes": list(config.required_scopes),
        "expires_at": 2000000000,
        "resource": config.resource_server_url,
        "subject": "user-123",
        "claims": {
            "iss": config.issuer_url,
            "aud": config.resource_server_url,
        },
    }
    values.update(overrides)
    return AccessToken(**values)


def self_test() -> None:
    config = MCPTransportConfig(
        issuer_url="https://auth.example.test",
        resource_server_url="https://quota.example.test/mcp",
    )
    contract = load_tool_contract()
    assert contract["inputSchema"] == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    assert contract["annotations"] == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }

    tool = build_tool_definition()
    assert tool.name == "get_quota_snapshot"
    assert tool.input_schema == contract["inputSchema"]
    assert tool.output_schema == contract["outputSchema"]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False
    assert tool.annotations.idempotent_hint is True
    assert tool.annotations.open_world_hint is False
    serialized_tool = tool.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert serialized_tool["_meta"]["securitySchemes"] == [
        {"type": "oauth2", "scopes": ["quota:read"]}
    ]

    service = _FakeQuotaService()
    handler = QuotaToolHandler(service)  # type: ignore[arg-type]
    token = _test_token(config)
    result = dispatch_tool_call(handler, config, token, "get_quota_snapshot", {})
    assert result.is_error is not True
    assert result.structured_content is not None
    assert result.structured_content["weekly_used"] == 31
    assert service.last_subject == f"{config.issuer_url}\x1fuser-123"
    assert "user-123" not in repr(result)

    bad_args = dispatch_tool_call(
        handler,
        config,
        token,
        "get_quota_snapshot",
        {"subject": "other-user"},
    )
    assert bad_args.is_error is True
    assert bad_args.meta["regulator/error_code"] == "INVALID_TOOL_ARGUMENTS"

    for bad_token in (
        _test_token(config, subject=""),
        _test_token(config, scopes=[]),
        _test_token(config, resource="https://other.example.test/mcp", claims={"iss": config.issuer_url}),
        _test_token(config, claims={"iss": "https://wrong.example.test", "aud": config.resource_server_url}),
        _test_token(config, expires_at=1),
    ):
        rejected = dispatch_tool_call(
            handler,
            config,
            bad_token,
            "get_quota_snapshot",
            {},
        )
        assert rejected.is_error is True
        assert rejected.meta["regulator/error_code"] == "MCP_AUTH_INVALID"

    service.raise_authorization = True
    needs_auth = dispatch_tool_call(handler, config, token, "get_quota_snapshot", {})
    assert needs_auth.is_error is True
    assert needs_auth.meta["regulator/auth_state"] == "NEEDS_QUOTA_AUTH"
    service.raise_authorization = False

    service.raise_unexpected = True
    unavailable = dispatch_tool_call(handler, config, token, "get_quota_snapshot", {})
    assert unavailable.is_error is True
    assert unavailable.meta["regulator/error_code"] == "QUOTA_UNAVAILABLE"
    assert "SECRET_TEST_PROVIDER_DETAIL" not in repr(unavailable)

    app = build_app(handler, config, token_verifier=_NeverCalledVerifier())
    paths = {getattr(route, "path", None) for route in app.routes}
    assert MCP_PATH in paths
    assert "/.well-known/oauth-protected-resource/mcp" in paths

    for bad_url in (
        "http://quota.example.test/mcp",
        "https://quota.example.test/not-mcp",
    ):
        try:
            MCPTransportConfig(
                issuer_url="https://auth.example.test",
                resource_server_url=bad_url,
            )
        except MCPTransportConfigurationError:
            pass
        else:
            raise AssertionError(f"invalid resource URL must fail: {bad_url}")

    print("mcp_transport_self_test=ok")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    parser.error("this module is composed by the deployment entrypoint; use --self-test")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
