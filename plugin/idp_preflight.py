#!/usr/bin/env python3
"""OAuth/OIDC discovery preflight for the v3 ChatGPT MCP deployment.

This module validates authorization-server metadata before a deployment is
allowed to expose the Regulator MCP resource. It intentionally does not create
clients, issue tokens, manage users, or implement an authorization server.

Static discovery can prove advertised capabilities. It cannot prove custom API
scope grantability, the live ChatGPT flow, exact redirect allow-listing, or
resource-to-audience binding; those remain explicit E2E gates.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_REQUIRED_SCOPES = ("quota:read",)
MAX_METADATA_BYTES = 512 * 1024
COMPATIBLE_PUBLIC_CLIENT_AUTH = frozenset({"none", "private_key_jwt"})
REGISTRATION_MODES = frozenset({"cimd", "dcr", "predefined"})


class IdPPreflightError(RuntimeError):
    """Raised when provider metadata cannot satisfy the deployment contract."""


class MetadataFetcher(Protocol):
    def fetch_json(self, url: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class IDPPreflightConfig:
    issuer_url: str
    metadata_url: str
    resource_url: str
    client_registration_mode: str = "cimd"
    required_scopes: tuple[str, ...] = DEFAULT_REQUIRED_SCOPES
    require_rfc9207_issuer_identification: bool = True
    predefined_client_reviewed: bool = False
    network_timeout_seconds: float = 5.0
    max_metadata_bytes: int = MAX_METADATA_BYTES

    def __post_init__(self) -> None:
        _require_https_url(self.issuer_url, "issuer_url")
        _require_https_url(self.metadata_url, "metadata_url")
        _require_https_url(self.resource_url, "resource_url")

        if self.client_registration_mode not in REGISTRATION_MODES:
            raise IdPPreflightError(
                "client_registration_mode must be cimd, dcr, or predefined"
            )
        if not self.required_scopes:
            raise IdPPreflightError("at least one required OAuth scope is required")
        if len(set(self.required_scopes)) != len(self.required_scopes):
            raise IdPPreflightError("required OAuth scopes must be unique")
        for scope in self.required_scopes:
            if not scope or scope.strip() != scope or any(ch.isspace() for ch in scope):
                raise IdPPreflightError("OAuth scopes must be non-empty tokens")
        if not (0.5 <= self.network_timeout_seconds <= 30.0):
            raise IdPPreflightError("network timeout must be between 0.5 and 30 seconds")
        if not (16 * 1024 <= self.max_metadata_bytes <= 2 * 1024 * 1024):
            raise IdPPreflightError("metadata response size bound is invalid")
        if (
            self.client_registration_mode == "predefined"
            and not self.predefined_client_reviewed
        ):
            raise IdPPreflightError(
                "predefined client mode requires an explicit reviewed deployment decision"
            )


def _require_https_url(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise IdPPreflightError(f"{label} must be a non-empty URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise IdPPreflightError(f"{label} must be an absolute https URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise IdPPreflightError(
            f"{label} must not contain credentials, query or fragment"
        )


class HTTPSMetadataFetcher:
    """Fetch only the server-configured metadata URL with strict size/time bounds."""

    def __init__(self, config: IDPPreflightConfig):
        self._config = config

    def fetch_json(self, url: str) -> dict[str, Any]:
        if url != self._config.metadata_url:
            raise IdPPreflightError("metadata fetch target differs from configured URL")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "openai-work-codex-regulator-v3-idp-preflight",
            },
        )
        try:
            with urlopen(request, timeout=self._config.network_timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                if content_type not in {
                    "application/json",
                    "application/oauth-authz-server+json",
                }:
                    raise IdPPreflightError(
                        f"unexpected metadata content type: {content_type}"
                    )
                body = response.read(self._config.max_metadata_bytes + 1)
        except IdPPreflightError:
            raise
        except Exception as exc:
            raise IdPPreflightError("authorization-server metadata fetch failed") from exc

        if len(body) > self._config.max_metadata_bytes:
            raise IdPPreflightError("authorization-server metadata exceeds size limit")
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise IdPPreflightError(
                "authorization-server metadata is not valid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise IdPPreflightError(
                "authorization-server metadata must be a JSON object"
            )
        return parsed


def _require_metadata_https(metadata: dict[str, Any], field: str) -> str:
    value = metadata.get(field)
    if not isinstance(value, str):
        raise IdPPreflightError(f"metadata missing {field}")
    _require_https_url(value, f"metadata.{field}")
    return value


def _string_set(value: Any, field: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise IdPPreflightError(f"metadata {field} must be an array of strings")
    return {item for item in value if item}


def _optional_string_set(value: Any, field: str) -> tuple[set[str], bool]:
    if value is None:
        return set(), False
    return _string_set(value, field), True


def validate_metadata(
    metadata: dict[str, Any],
    config: IDPPreflightConfig,
) -> dict[str, Any]:
    issuer = metadata.get("issuer")
    if issuer != config.issuer_url:
        raise IdPPreflightError(
            "metadata issuer does not exactly match configured issuer"
        )

    authorization_endpoint = _require_metadata_https(
        metadata, "authorization_endpoint"
    )
    token_endpoint = _require_metadata_https(metadata, "token_endpoint")
    jwks_uri = _require_metadata_https(metadata, "jwks_uri")

    pkce_methods = _string_set(
        metadata.get("code_challenge_methods_supported"),
        "code_challenge_methods_supported",
    )
    if "S256" not in pkce_methods:
        raise IdPPreflightError("authorization server must advertise PKCE S256")

    # RFC 8414/OIDC discovery is not a reliable registry for provider-specific
    # custom API permissions. Auth0, for example, can issue a custom API scope
    # that is configured on the target API without listing it in the OIDC
    # `scopes_supported` array. Absence therefore cannot be treated as proof
    # that the scope is unavailable. The live authorize/token exchange remains
    # authoritative and must prove that every required scope is granted.
    scopes, scopes_field_present = _optional_string_set(
        metadata.get("scopes_supported"), "scopes_supported"
    )
    required_scope_set = set(config.required_scopes)
    advertised_required_scopes = sorted(required_scope_set & scopes)
    missing_advertised_scopes = sorted(required_scope_set - scopes)
    required_scope_advertisement = (
        "ADVERTISED" if not missing_advertised_scopes else "NOT_ADVERTISED"
    )

    token_auth_methods = _string_set(
        metadata.get("token_endpoint_auth_methods_supported"),
        "token_endpoint_auth_methods_supported",
    )
    compatible_methods = token_auth_methods & COMPATIBLE_PUBLIC_CLIENT_AUTH
    if not compatible_methods:
        raise IdPPreflightError(
            "authorization server has no compatible token endpoint auth method"
        )

    mode = config.client_registration_mode
    registration_endpoint: str | None = None
    if mode == "cimd":
        if metadata.get("client_id_metadata_document_supported") is not True:
            raise IdPPreflightError(
                "CIMD mode requires client_id_metadata_document_supported=true"
            )
    elif mode == "dcr":
        registration_endpoint = _require_metadata_https(
            metadata, "registration_endpoint"
        )

    if config.require_rfc9207_issuer_identification:
        if metadata.get("authorization_response_iss_parameter_supported") is not True:
            raise IdPPreflightError(
                "RFC 9207 issuer identification must be advertised for this deployment"
            )

    grant_types = metadata.get("grant_types_supported")
    if grant_types is not None:
        grants = _string_set(grant_types, "grant_types_supported")
        if "authorization_code" not in grants:
            raise IdPPreflightError("authorization_code grant is not advertised")

    response_types = metadata.get("response_types_supported")
    if response_types is not None:
        responses = _string_set(response_types, "response_types_supported")
        if "code" not in responses:
            raise IdPPreflightError(
                "authorization code response type is not advertised"
            )

    return {
        "status": "PASS",
        "issuer": issuer,
        "authorization_endpoint": authorization_endpoint,
        "token_endpoint": token_endpoint,
        "jwks_uri": jwks_uri,
        "resource": config.resource_url,
        "required_scopes": list(config.required_scopes),
        "scopes_supported_field_present": scopes_field_present,
        "required_scope_advertisement": required_scope_advertisement,
        "advertised_required_scopes": advertised_required_scopes,
        "missing_advertised_scopes": missing_advertised_scopes,
        "pkce": "S256",
        "client_registration_mode": mode,
        "compatible_token_endpoint_auth_methods": sorted(compatible_methods),
        "registration_endpoint": registration_endpoint,
        "rfc9207_issuer_identification": bool(
            metadata.get("authorization_response_iss_parameter_supported")
        ),
        "static_preflight_proves": [
            "metadata issuer/endpoints",
            "PKCE S256 advertisement",
            "required-scope discovery advertisement status only",
            "registration-mode metadata",
        ],
        "live_e2e_required": [
            "required_scope_requested_and_granted_in_access_token",
            "resource_parameter_echoed_and_bound_to_access_token_audience",
            "exact_chatgpt_redirect_uri_allowlisted",
            "real_chatgpt_connection_registration",
            "connect_authorize_token_exchange",
        ],
    }


def run_preflight(
    config: IDPPreflightConfig,
    *,
    fetcher: MetadataFetcher | None = None,
) -> dict[str, Any]:
    source = fetcher or HTTPSMetadataFetcher(config)
    metadata = source.fetch_json(config.metadata_url)
    return validate_metadata(metadata, config)


def self_test() -> None:
    # Model the observed Auth0 shape: the custom API permission is configured on
    # the resource server but is not necessarily listed in OIDC discovery.
    base_metadata = {
        "issuer": "https://tenant.example/",
        "authorization_endpoint": "https://tenant.example/authorize",
        "token_endpoint": "https://tenant.example/oauth/token",
        "jwks_uri": "https://tenant.example/.well-known/jwks.json",
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["openid", "profile", "email"],
        "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
        "client_id_metadata_document_supported": True,
        "registration_endpoint": "https://tenant.example/oidc/register",
        "authorization_response_iss_parameter_supported": True,
        "grant_types_supported": ["authorization_code"],
        "response_types_supported": ["code"],
    }

    class StaticFetcher:
        def __init__(self, metadata: dict[str, Any]):
            self.metadata = metadata
            self.calls: list[str] = []

        def fetch_json(self, url: str) -> dict[str, Any]:
            self.calls.append(url)
            return dict(self.metadata)

    config = IDPPreflightConfig(
        issuer_url="https://tenant.example/",
        metadata_url="https://tenant.example/.well-known/openid-configuration",
        resource_url="https://quota.example/mcp",
        client_registration_mode="cimd",
    )
    fetcher = StaticFetcher(base_metadata)
    report = run_preflight(config, fetcher=fetcher)
    assert report["status"] == "PASS"
    assert report["pkce"] == "S256"
    assert report["resource"] == "https://quota.example/mcp"
    assert report["required_scope_advertisement"] == "NOT_ADVERTISED"
    assert report["missing_advertised_scopes"] == ["quota:read"]
    assert (
        "required_scope_requested_and_granted_in_access_token"
        in report["live_e2e_required"]
    )
    assert fetcher.calls == [config.metadata_url]

    advertised = dict(base_metadata)
    advertised["scopes_supported"] = ["openid", "quota:read"]
    advertised_report = run_preflight(config, fetcher=StaticFetcher(advertised))
    assert advertised_report["required_scope_advertisement"] == "ADVERTISED"
    assert advertised_report["missing_advertised_scopes"] == []

    no_scope_field = dict(base_metadata)
    no_scope_field.pop("scopes_supported")
    no_scope_report = run_preflight(config, fetcher=StaticFetcher(no_scope_field))
    assert no_scope_report["scopes_supported_field_present"] is False
    assert no_scope_report["required_scope_advertisement"] == "NOT_ADVERTISED"

    def expect_failure(
        metadata: dict[str, Any], cfg: IDPPreflightConfig = config
    ) -> None:
        try:
            run_preflight(cfg, fetcher=StaticFetcher(metadata))
        except IdPPreflightError:
            return
        raise AssertionError("invalid IdP metadata unexpectedly passed")

    bad = dict(base_metadata)
    bad["issuer"] = "https://other.example/"
    expect_failure(bad)

    bad = dict(base_metadata)
    bad["code_challenge_methods_supported"] = ["plain"]
    expect_failure(bad)

    bad = dict(base_metadata)
    bad["client_id_metadata_document_supported"] = False
    expect_failure(bad)

    dcr_config = IDPPreflightConfig(
        issuer_url=config.issuer_url,
        metadata_url=config.metadata_url,
        resource_url=config.resource_url,
        client_registration_mode="dcr",
    )
    dcr_report = run_preflight(dcr_config, fetcher=StaticFetcher(base_metadata))
    assert dcr_report["registration_endpoint"] == base_metadata["registration_endpoint"]

    bad = dict(base_metadata)
    bad.pop("registration_endpoint")
    expect_failure(bad, dcr_config)

    try:
        IDPPreflightConfig(
            issuer_url=config.issuer_url,
            metadata_url=config.metadata_url,
            resource_url=config.resource_url,
            client_registration_mode="predefined",
        )
        raise AssertionError("unreviewed predefined client must fail")
    except IdPPreflightError:
        pass

    bad = dict(base_metadata)
    bad["authorization_response_iss_parameter_supported"] = False
    expect_failure(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--issuer")
    parser.add_argument("--metadata-url")
    parser.add_argument("--resource")
    parser.add_argument(
        "--client-registration-mode",
        choices=sorted(REGISTRATION_MODES),
        default="cimd",
    )
    parser.add_argument("--predefined-client-reviewed", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("IdP discovery preflight self-test OK")
    else:
        if not args.issuer or not args.metadata_url or not args.resource:
            parser.error("--issuer, --metadata-url and --resource are required")
        cfg = IDPPreflightConfig(
            issuer_url=args.issuer,
            metadata_url=args.metadata_url,
            resource_url=args.resource,
            client_registration_mode=args.client_registration_mode,
            predefined_client_reviewed=args.predefined_client_reviewed,
        )
        print(json.dumps(run_preflight(cfg), indent=2, ensure_ascii=False))
