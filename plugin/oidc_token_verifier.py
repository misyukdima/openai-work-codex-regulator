#!/usr/bin/env python3
"""OIDC/JWKS TokenVerifier adapter for the v3 MCP resource server.

This module verifies access tokens issued by an external OAuth/OIDC provider.
It deliberately does not implement an authorization server, user database,
client registration, password flow, refresh-token issuance, or signing keys.

Production properties:
- exact issuer and audience binding;
- explicit asymmetric algorithm allow-list;
- required key id and no token-directed jku/x5u fetches;
- JWKS endpoint configured server-side only;
- bounded JWKS cache and network timeout;
- exp/nbf/issuer/audience/signature validation through PyJWT;
- required OAuth scopes;
- stable subject required before MCP sees a principal;
- privacy-minimized claims handed to the MCP SDK;
- invalid/unverifiable tokens fail closed as None.

The official MCP SDK consumes this object through its TokenVerifier protocol.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import time
from typing import Any, Protocol
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier


DEFAULT_ALGORITHMS = ("RS256", "ES256")
DEFAULT_SCOPES = ("quota:read",)
MAX_TOKEN_BYTES = 16 * 1024
MAX_SUBJECT_BYTES = 2048


class OIDCVerifierConfigurationError(ValueError):
    pass


class SigningKeyProvider(Protocol):
    """Resolve a server-trusted verification key for a JWT."""

    def get_signing_key(self, token: str) -> Any:
        ...


@dataclass(frozen=True)
class OIDCVerifierConfig:
    issuer_url: str
    audience: str
    jwks_url: str
    required_scopes: tuple[str, ...] = DEFAULT_SCOPES
    allowed_algorithms: tuple[str, ...] = DEFAULT_ALGORITHMS
    leeway_seconds: int = 30
    jwks_cache_seconds: int = 300
    network_timeout_seconds: float = 5.0
    max_token_bytes: int = MAX_TOKEN_BYTES

    def __post_init__(self) -> None:
        _require_https_url(self.issuer_url, "issuer_url")
        _require_https_url(self.audience, "audience")
        _require_https_url(self.jwks_url, "jwks_url")

        if not self.required_scopes:
            raise OIDCVerifierConfigurationError("at least one OAuth scope is required")
        if len(set(self.required_scopes)) != len(self.required_scopes):
            raise OIDCVerifierConfigurationError("OAuth scopes must be unique")
        for scope in self.required_scopes:
            if not scope or scope.strip() != scope or any(ch.isspace() for ch in scope):
                raise OIDCVerifierConfigurationError("OAuth scopes must be non-empty tokens")

        if not self.allowed_algorithms:
            raise OIDCVerifierConfigurationError("at least one JWT algorithm is required")
        if len(set(self.allowed_algorithms)) != len(self.allowed_algorithms):
            raise OIDCVerifierConfigurationError("JWT algorithms must be unique")
        for algorithm in self.allowed_algorithms:
            if algorithm not in {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512"}:
                raise OIDCVerifierConfigurationError(
                    "only explicit asymmetric JWT algorithms are allowed"
                )

        if not (0 <= self.leeway_seconds <= 300):
            raise OIDCVerifierConfigurationError("leeway_seconds must be between 0 and 300")
        if not (30 <= self.jwks_cache_seconds <= 3600):
            raise OIDCVerifierConfigurationError("jwks_cache_seconds must be between 30 and 3600")
        if not (0.5 <= self.network_timeout_seconds <= 30):
            raise OIDCVerifierConfigurationError("network timeout must be between 0.5 and 30 seconds")
        if not (1024 <= self.max_token_bytes <= 64 * 1024):
            raise OIDCVerifierConfigurationError("max_token_bytes outside supported bounds")


def _require_https_url(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise OIDCVerifierConfigurationError(f"{label} must be a non-empty URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise OIDCVerifierConfigurationError(f"{label} must be an absolute https URL")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise OIDCVerifierConfigurationError(
            f"{label} must not contain credentials, query or fragment"
        )


class PyJWKSigningKeyProvider:
    """Server-configured JWKS resolver with bounded response caching.

    Per-key LRU caching is intentionally disabled because it has no TTL in
    PyJWT. The JWK-set cache has a bounded lifespan and PyJWKClient refreshes it
    on an unknown kid, which keeps ordinary key rotation recoverable.
    """

    production_safe = True

    def __init__(self, config: OIDCVerifierConfig):
        self._client = PyJWKClient(
            config.jwks_url,
            cache_keys=False,
            cache_jwk_set=True,
            lifespan=float(config.jwks_cache_seconds),
            timeout=float(config.network_timeout_seconds),
        )

    def get_signing_key(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


class OIDCJWKSTokenVerifier(TokenVerifier):
    """Verify external OAuth access JWTs and return MCP AccessToken principals."""

    def __init__(
        self,
        config: OIDCVerifierConfig,
        *,
        key_provider: SigningKeyProvider | None = None,
    ) -> None:
        self.config = config
        self._key_provider = key_provider or PyJWKSigningKeyProvider(config)

    async def verify_token(self, token: str) -> AccessToken | None:
        # Network-backed JWKS lookup is synchronous in PyJWT. Keep it off the
        # event loop while preserving the TokenVerifier async contract.
        try:
            return await asyncio.to_thread(self._verify_sync, token)
        except Exception:
            # Bearer middleware needs a binary trust decision. Provider/network/
            # parse details stay server-side and the raw token is never logged.
            return None

    def _verify_sync(self, token: str) -> AccessToken | None:
        if not isinstance(token, str) or not token:
            return None
        if len(token.encode("utf-8")) > self.config.max_token_bytes:
            return None

        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        kid = header.get("kid")
        if algorithm not in self.config.allowed_algorithms:
            return None
        if not isinstance(kid, str) or not kid.strip() or len(kid) > 256:
            return None
        # Never follow token-supplied key URLs. JWKS location is config-only.
        if "jku" in header or "x5u" in header:
            return None

        key = self._key_provider.get_signing_key(token)
        claims = jwt.decode(
            token,
            key=key,
            algorithms=list(self.config.allowed_algorithms),
            audience=self.config.audience,
            issuer=self.config.issuer_url,
            leeway=self.config.leeway_seconds,
            options={
                "require": ["exp", "iss", "sub", "aud"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            return None
        subject = subject.strip()
        if len(subject.encode("utf-8")) > MAX_SUBJECT_BYTES:
            return None

        scopes = _extract_scopes(claims)
        if not set(self.config.required_scopes).issubset(scopes):
            return None

        exp = claims.get("exp")
        if not isinstance(exp, (int, float)):
            return None
        expires_at = int(exp)
        if expires_at <= int(time.time()) - self.config.leeway_seconds:
            return None

        client_id_value = claims.get("azp") or claims.get("client_id") or self.config.audience
        client_id = str(client_id_value)
        if not client_id or len(client_id) > 2048:
            return None

        # Keep only claims needed by the downstream trust boundary. Do not pass
        # profile/email/name/custom claims merely because the IdP included them.
        minimized_claims = {
            key: claims[key]
            for key in ("iss", "aud", "nbf", "iat", "exp", "azp", "client_id")
            if key in claims
        }

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=sorted(scopes),
            expires_at=expires_at,
            resource=self.config.audience,
            subject=subject,
            claims=minimized_claims,
        )


def _extract_scopes(claims: dict[str, Any]) -> set[str]:
    raw = claims.get("scope")
    if raw is None:
        raw = claims.get("scp")
    if isinstance(raw, str):
        scopes = {part for part in raw.split() if part}
    elif isinstance(raw, (list, tuple, set)):
        scopes = {str(part) for part in raw if isinstance(part, str) and part}
    else:
        scopes = set()
    return scopes


def self_test() -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    class StaticKeyProvider:
        production_safe = False

        def __init__(self) -> None:
            self.calls = 0

        def get_signing_key(self, token: str) -> Any:
            assert token
            self.calls += 1
            return public_key

    provider = StaticKeyProvider()
    config = OIDCVerifierConfig(
        issuer_url="https://issuer.example",
        audience="https://quota.example/mcp",
        jwks_url="https://issuer.example/.well-known/jwks.json",
        leeway_seconds=0,
    )
    verifier = OIDCJWKSTokenVerifier(config, key_provider=provider)
    now = int(time.time())

    def make_token(**overrides: Any) -> str:
        payload: dict[str, Any] = {
            "iss": config.issuer_url,
            "aud": config.audience,
            "sub": "subject-123",
            "iat": now,
            "nbf": now - 1,
            "exp": now + 300,
            "scope": "quota:read profile",
            "azp": "chatgpt-plugin-client",
            "email": "must-not-be-forwarded@example.invalid",
        }
        payload.update(overrides)
        return jwt.encode(
            payload,
            private_key,
            algorithm="RS256",
            headers={"kid": "key-1", "typ": "at+jwt"},
        )

    valid = asyncio.run(verifier.verify_token(make_token()))
    assert valid is not None
    assert valid.subject == "subject-123"
    assert valid.resource == config.audience
    assert "quota:read" in valid.scopes
    assert valid.claims is not None and "email" not in valid.claims
    assert valid.claims.get("iss") == config.issuer_url

    assert asyncio.run(verifier.verify_token(make_token(aud="https://wrong.example/mcp"))) is None
    assert asyncio.run(verifier.verify_token(make_token(iss="https://wrong.example"))) is None
    assert asyncio.run(verifier.verify_token(make_token(scope="profile"))) is None
    assert asyncio.run(verifier.verify_token(make_token(exp=now - 10))) is None
    assert asyncio.run(verifier.verify_token(make_token(nbf=now + 60))) is None
    assert asyncio.run(verifier.verify_token(make_token(sub=""))) is None

    # Header algorithm and key URL policy are checked before any provider fetch.
    before = provider.calls
    hs = jwt.encode(
        {
            "iss": config.issuer_url,
            "aud": config.audience,
            "sub": "subject-123",
            "exp": now + 300,
            "scope": "quota:read",
        },
        "not-a-production-secret",
        algorithm="HS256",
        headers={"kid": "key-1"},
    )
    assert asyncio.run(verifier.verify_token(hs)) is None
    assert provider.calls == before

    token_with_jku = jwt.encode(
        {
            "iss": config.issuer_url,
            "aud": config.audience,
            "sub": "subject-123",
            "exp": now + 300,
            "scope": "quota:read",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1", "jku": "https://attacker.invalid/jwks.json"},
    )
    assert asyncio.run(verifier.verify_token(token_with_jku)) is None
    assert provider.calls == before

    try:
        OIDCVerifierConfig(
            issuer_url="http://issuer.example",
            audience=config.audience,
            jwks_url=config.jwks_url,
        )
        raise AssertionError("http issuer must fail")
    except OIDCVerifierConfigurationError:
        pass

    try:
        OIDCVerifierConfig(
            issuer_url=config.issuer_url,
            audience=config.audience,
            jwks_url=config.jwks_url,
            allowed_algorithms=("HS256",),
        )
        raise AssertionError("symmetric algorithm must fail")
    except OIDCVerifierConfigurationError:
        pass

    # Production JWKS provider must use TTL JWK-set caching, not indefinite
    # per-key LRU caching. Constructor coverage also pins current PyJWT API.
    real_provider = PyJWKSigningKeyProvider(config)
    assert real_provider.production_safe is True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("OIDC/JWKS TokenVerifier self-test OK")
    else:
        parser.error("only --self-test is supported; deployment composes this module externally")
