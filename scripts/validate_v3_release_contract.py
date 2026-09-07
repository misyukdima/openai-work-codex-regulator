#!/usr/bin/env python3
"""Strict v3 release-contract validator.

The historical repository validator intentionally remains generation-wide. This
validator is the v3 development/release gate for the ChatGPT Web Plugin path and
must move forward with every new security/transport/deployment layer.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
MIN_V3_TESTS = 240

REQUIRED = [
    ".codex-plugin/plugin.json",
    "skills/openai-work-codex-regulator/SKILL.md",
    "plugin/get_quota_snapshot.tool.json",
    "plugin/mcp_transport.py",
    "plugin/oidc_token_verifier.py",
    "plugin/idp_preflight.py",
    "plugin/production_runtime.py",
    "plugin/requirements-mcp.txt",
    "plugin/requirements-auth.txt",
    "scripts/validate_plugin_package.py",
    "scripts/validate_v3_release_contract.py",
    "docs/IDP_DEPLOYMENT.md",
    "deployment/auth0-staging.example.json",
    "tests/TEST_CASES_V3_0_MCP.md",
    "tests/TEST_CASES_V3_0_OAUTH.md",
    "tests/TEST_CASES_V3_0_IDP.md",
]

errors: list[str] = []


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else ""


for rel in REQUIRED:
    if not (ROOT / rel).is_file():
        errors.append(f"missing v3 release file: {rel}")

all_numbers: list[int] = []
for path in sorted((ROOT / "tests").glob("TEST_CASES*.md")):
    nums = [
        int(n)
        for n in re.findall(
            r"^## Test (\d+)\b",
            path.read_text(encoding="utf-8"),
            re.M,
        )
    ]
    if nums != sorted(nums):
        errors.append(f"{path.relative_to(ROOT)} test numbers are not increasing")
    all_numbers.extend(nums)

numbers = sorted(all_numbers)
if not numbers:
    errors.append("no regression tests found")
else:
    if len(numbers) != len(set(numbers)):
        errors.append("duplicate regression test numbers across shards")
    if numbers != list(range(1, max(numbers) + 1)):
        errors.append("regression tests are not contiguous from 1")
    if len(numbers) < MIN_V3_TESTS:
        errors.append(f"v3 test count {len(numbers)} < {MIN_V3_TESTS}")

mcp_requirements = [
    line.strip()
    for line in read("plugin/requirements-mcp.txt").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
if mcp_requirements != ["mcp==2.1.1", "mcp-types==2.1.1"]:
    errors.append("MCP direct dependencies must remain exact-pinned at v2.1.1")

auth_requirements = [
    line.strip()
    for line in read("plugin/requirements-auth.txt").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
if auth_requirements != ["PyJWT[crypto]==2.13.0"]:
    errors.append("OAuth verifier direct dependency must remain exact-pinned")

try:
    tool = json.loads(read("plugin/get_quota_snapshot.tool.json"))
    if tool.get("name") != "get_quota_snapshot":
        errors.append("canonical quota tool name drifted")
    input_schema = tool.get("inputSchema") or {}
    if (
        input_schema.get("properties") != {}
        or input_schema.get("additionalProperties") is not False
    ):
        errors.append("quota tool must remain exact zero-argument")
    annotations = tool.get("annotations") or {}
    expected_annotations = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    for key, expected in expected_annotations.items():
        if annotations.get(key) is not expected:
            errors.append(f"quota tool annotation drifted: {key}")
    if tool.get("securitySchemes") != [
        {"type": "oauth2", "scopes": ["quota:read"]}
    ]:
        errors.append("quota tool OAuth security scheme drifted")
except Exception as exc:
    errors.append(f"quota tool JSON invalid: {exc}")

mcp = read("plugin/mcp_transport.py")
for needle in [
    'MCP_PATH = "/mcp"',
    'DEFAULT_REQUIRED_SCOPES = ("quota:read",)',
    "get_access_token()",
    "trusted_subject_from_access_token",
    "InvalidVerifiedPrincipal",
    '"securitySchemes": _security_schemes(contract)',
    "params.arguments",
    "stateless_http=True",
    "TokenVerifier",
]:
    if needle not in mcp:
        errors.append(f"MCP transport missing marker: {needle}")

oidc = read("plugin/oidc_token_verifier.py")
for needle in [
    "class OIDCJWKSTokenVerifier(TokenVerifier)",
    "PyJWKClient",
    "cache_keys=False",
    "cache_jwk_set=True",
    'DEFAULT_SCOPES = ("quota:read",)',
    '"jku" in header',
    '"x5u" in header',
    '"require": ["exp", "iss", "sub", "aud"]',
    "verify_signature",
    "verify_exp",
    "verify_nbf",
    "verify_aud",
    "verify_iss",
    "minimized_claims",
    "return None",
]:
    if needle not in oidc:
        errors.append(f"OIDC verifier missing marker: {needle}")

preflight = read("plugin/idp_preflight.py")
for needle in [
    "class IDPPreflightConfig",
    'client_registration_mode: str = "cimd"',
    '"code_challenge_methods_supported"',
    '"S256"',
    '"scopes_supported"',
    '"quota:read"',
    '"client_id_metadata_document_supported"',
    '"registration_endpoint"',
    '"authorization_response_iss_parameter_supported"',
    '"resource_parameter_echoed_and_bound_to_access_token_audience"',
    '"exact_chatgpt_redirect_uri_allowlisted"',
]:
    if needle not in preflight:
        errors.append(f"IdP preflight missing marker: {needle}")

runtime = read("plugin/production_runtime.py")
for needle in [
    "class ProductionRuntimeConfig",
    "REGULATOR_OIDC_ISSUER_URL",
    "REGULATOR_OIDC_METADATA_URL",
    "REGULATOR_MCP_RESOURCE_URL",
    "REGULATOR_OIDC_CLIENT_SECRET",
    "REGULATOR_OAUTH_CLIENT_SECRET",
    "run_preflight",
    "OIDCJWKSTokenVerifier",
    "MCPTransportConfig",
    "build_production_app",
]:
    if needle not in runtime:
        errors.append(f"production runtime missing marker: {needle}")

try:
    profile = json.loads(read("deployment/auth0-staging.example.json"))
    if profile.get("provider") != "auth0":
        errors.append("staging profile provider must be auth0")
    if profile.get("required_scope") != "quota:read":
        errors.append("staging profile required scope drifted")
    if profile.get("pkce") != "S256":
        errors.append("staging profile PKCE drifted")
    if profile.get("secrets_in_repository") is not False:
        errors.append("staging profile must explicitly forbid repository secrets")
    serialized = json.dumps(profile).lower()
    for secret_marker in [
        "client_secret",
        "access_token",
        "refresh_token",
        "private_key",
    ]:
        if secret_marker in serialized:
            errors.append(
                f"staging profile must not contain secret field: {secret_marker}"
            )
except Exception as exc:
    errors.append(f"Auth0 staging profile invalid: {exc}")

workflow = read(".github/workflows/validate.yml")
for needle in [
    "Validate v3 release contract",
    "Install pinned OAuth verifier dependencies",
    "Validate OIDC/JWKS token verifier",
    "Validate IdP discovery preflight",
    "Validate production runtime composition",
    "plugin/requirements-auth.txt",
    "plugin/oidc_token_verifier.py --self-test",
    "plugin/idp_preflight.py --self-test",
    "plugin/production_runtime.py --self-test",
]:
    if needle not in workflow:
        errors.append(f"CI workflow missing v3 auth/deployment gate: {needle}")

plugin_manifest = read(".codex-plugin/plugin.json")
if "plugin_asdk_app" in plugin_manifest:
    errors.append("plugin manifest must not fabricate a registered app id")
if (ROOT / ".app.json").exists() and "plugin_asdk_app" not in read(".app.json"):
    errors.append(".app.json exists without a real plugin_asdk_app id")

if errors:
    print("v3 release-contract validation FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print(
    "v3 release-contract validation OK — "
    f"{len(numbers)} contiguous tests, MCP + OIDC/JWKS + IdP gates present"
)
