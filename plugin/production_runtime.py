#!/usr/bin/env python3
"""Production composition for the v3 authenticated MCP quota resource server.

The repository owns resource-server validation and quota logic. It does not own
an OAuth authorization server. Deployment injects an established IdP whose
metadata passes `idp_preflight`, plus the existing quota handler/vault stack.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from typing import Any, Mapping

try:
    from plugin.idp_preflight import (
        IDPPreflightConfig,
        IdPPreflightError,
        MetadataFetcher,
        run_preflight,
    )
    from plugin.mcp_transport import MCPTransportConfig, build_app
    from plugin.oidc_token_verifier import OIDCVerifierConfig, OIDCJWKSTokenVerifier
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.idp_preflight import (
        IDPPreflightConfig,
        IdPPreflightError,
        MetadataFetcher,
        run_preflight,
    )
    from plugin.mcp_transport import MCPTransportConfig, build_app
    from plugin.oidc_token_verifier import OIDCVerifierConfig, OIDCJWKSTokenVerifier


REQUIRED_SCOPE = "quota:read"
FORBIDDEN_RESOURCE_SERVER_SECRETS = (
    "REGULATOR_OIDC_CLIENT_SECRET",
    "REGULATOR_OAUTH_CLIENT_SECRET",
)


class ProductionRuntimeConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProductionRuntimeConfig:
    issuer_url: str
    metadata_url: str
    resource_url: str
    client_registration_mode: str = "cimd"
    predefined_client_reviewed: bool = False
    require_rfc9207_issuer_identification: bool = True

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "ProductionRuntimeConfig":
        env = dict(os.environ if environment is None else environment)

        leaked = [
            name for name in FORBIDDEN_RESOURCE_SERVER_SECRETS if env.get(name)
        ]
        if leaked:
            raise ProductionRuntimeConfigurationError(
                "OAuth client secrets do not belong in the MCP resource-server runtime"
            )

        required = {
            "issuer_url": env.get("REGULATOR_OIDC_ISSUER_URL", ""),
            "metadata_url": env.get("REGULATOR_OIDC_METADATA_URL", ""),
            "resource_url": env.get("REGULATOR_MCP_RESOURCE_URL", ""),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ProductionRuntimeConfigurationError(
                "missing runtime setting(s): " + ", ".join(sorted(missing))
            )

        mode = env.get(
            "REGULATOR_OIDC_CLIENT_REGISTRATION_MODE", "cimd"
        ).strip().lower()
        reviewed = env.get(
            "REGULATOR_OIDC_PREDEFINED_CLIENT_REVIEWED", ""
        ).lower() in {"1", "true", "yes"}
        require_rfc9207 = env.get(
            "REGULATOR_OIDC_REQUIRE_RFC9207_ISSUER_IDENTIFICATION",
            "true",
        ).lower() not in {"0", "false", "no"}

        return cls(
            issuer_url=required["issuer_url"],
            metadata_url=required["metadata_url"],
            resource_url=required["resource_url"],
            client_registration_mode=mode,
            predefined_client_reviewed=reviewed,
            require_rfc9207_issuer_identification=require_rfc9207,
        )


@dataclass(frozen=True)
class ProductionRuntimeComponents:
    preflight_report: dict[str, Any]
    token_verifier: OIDCJWKSTokenVerifier
    transport_config: MCPTransportConfig


def build_runtime_components(
    config: ProductionRuntimeConfig,
    *,
    metadata_fetcher: MetadataFetcher | None = None,
) -> ProductionRuntimeComponents:
    preflight_config = IDPPreflightConfig(
        issuer_url=config.issuer_url,
        metadata_url=config.metadata_url,
        resource_url=config.resource_url,
        client_registration_mode=config.client_registration_mode,
        required_scopes=(REQUIRED_SCOPE,),
        require_rfc9207_issuer_identification=(
            config.require_rfc9207_issuer_identification
        ),
        predefined_client_reviewed=config.predefined_client_reviewed,
    )
    report = run_preflight(preflight_config, fetcher=metadata_fetcher)

    jwks_uri = report.get("jwks_uri")
    if not isinstance(jwks_uri, str):
        raise ProductionRuntimeConfigurationError("preflight report missing jwks_uri")

    verifier = OIDCJWKSTokenVerifier(
        OIDCVerifierConfig(
            issuer_url=config.issuer_url,
            audience=config.resource_url,
            jwks_url=jwks_uri,
            required_scopes=(REQUIRED_SCOPE,),
        )
    )
    transport = MCPTransportConfig(
        issuer_url=config.issuer_url,
        resource_server_url=config.resource_url,
        required_scopes=(REQUIRED_SCOPE,),
    )
    return ProductionRuntimeComponents(
        preflight_report=report,
        token_verifier=verifier,
        transport_config=transport,
    )


def build_production_app(
    handler: Any,
    config: ProductionRuntimeConfig,
    *,
    metadata_fetcher: MetadataFetcher | None = None,
):
    components = build_runtime_components(
        config,
        metadata_fetcher=metadata_fetcher,
    )
    return build_app(
        handler,
        components.transport_config,
        token_verifier=components.token_verifier,
    )


def self_test() -> None:
    metadata = {
        "issuer": "https://tenant.example/",
        "authorization_endpoint": "https://tenant.example/authorize",
        "token_endpoint": "https://tenant.example/oauth/token",
        "jwks_uri": "https://tenant.example/.well-known/jwks.json",
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["openid", "quota:read"],
        "token_endpoint_auth_methods_supported": ["none"],
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
        "grant_types_supported": ["authorization_code"],
        "response_types_supported": ["code"],
    }

    class StaticFetcher:
        def fetch_json(self, url: str) -> dict[str, Any]:
            assert url == "https://tenant.example/.well-known/openid-configuration"
            return dict(metadata)

    env = {
        "REGULATOR_OIDC_ISSUER_URL": "https://tenant.example/",
        "REGULATOR_OIDC_METADATA_URL": (
            "https://tenant.example/.well-known/openid-configuration"
        ),
        "REGULATOR_MCP_RESOURCE_URL": "https://quota.example/mcp",
        "REGULATOR_OIDC_CLIENT_REGISTRATION_MODE": "cimd",
    }
    config = ProductionRuntimeConfig.from_environment(env)
    components = build_runtime_components(config, metadata_fetcher=StaticFetcher())
    assert components.preflight_report["status"] == "PASS"
    assert components.transport_config.required_scopes == ("quota:read",)
    assert components.token_verifier.config.audience == "https://quota.example/mcp"
    assert components.token_verifier.config.jwks_url == metadata["jwks_uri"]

    bad = dict(env)
    bad["REGULATOR_OIDC_CLIENT_SECRET"] = "must-never-be-here"
    try:
        ProductionRuntimeConfig.from_environment(bad)
        raise AssertionError("resource-server client secret must be rejected")
    except ProductionRuntimeConfigurationError:
        pass

    missing = dict(env)
    del missing["REGULATOR_MCP_RESOURCE_URL"]
    try:
        ProductionRuntimeConfig.from_environment(missing)
        raise AssertionError("missing resource URL must fail")
    except ProductionRuntimeConfigurationError:
        pass

    predefined = dict(env)
    predefined["REGULATOR_OIDC_CLIENT_REGISTRATION_MODE"] = "predefined"
    try:
        cfg = ProductionRuntimeConfig.from_environment(predefined)
        build_runtime_components(cfg, metadata_fetcher=StaticFetcher())
        raise AssertionError("unreviewed predefined client must fail")
    except IdPPreflightError:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("Production runtime composition self-test OK")
    else:
        parser.error(
            "only --self-test is supported here; deployment imports build_production_app"
        )
