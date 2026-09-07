#!/usr/bin/env python3
"""Dependency-free validation of the v3 MCP transport/package contract."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def read(rel: str) -> str:
    path = ROOT / rel
    require(path.is_file(), f"missing: {rel}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    try:
        version = read("VERSION").strip()
        manifest = json.loads(read(".codex-plugin/plugin.json"))
        contract = json.loads(read("plugin/get_quota_snapshot.tool.json"))
        requirements = [
            line.strip()
            for line in read("plugin/requirements-mcp.txt").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        transport = read("plugin/mcp_transport.py")
        tests = read("tests/TEST_CASES_V3_0_MCP.md")
        source_map = read("references/SOURCE_MAP.md")

        require(manifest.get("name") == "openai-work-codex-regulator", "plugin manifest name drift")
        require(manifest.get("version") == f"{version}.0", "plugin manifest version must match VERSION as semver")
        require(manifest.get("skills") == "./skills/", "plugin manifest skills path must be ./skills/")
        require("apps" not in manifest, "apps mapping is forbidden until a real registered MCP connection exists")
        require(not (ROOT / ".app.json").exists(), ".app.json must not exist before real MCP connection registration")

        root_skill = read("SKILL.md")
        packaged_skill = read("skills/openai-work-codex-regulator/SKILL.md")
        require(root_skill == packaged_skill, "packaged skill must be byte-for-byte equal to root SKILL.md")

        require(contract.get("name") == "get_quota_snapshot", "canonical MCP tool name drift")
        require(
            contract.get("inputSchema") == {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "canonical quota tool must be exact zero-argument schema",
        )
        require(
            contract.get("securitySchemes") == [
                {"type": "oauth2", "scopes": ["quota:read"]}
            ],
            "canonical quota tool must require quota:read OAuth scope",
        )
        require(
            contract.get("annotations") == {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            "canonical quota tool annotations drifted",
        )
        require(
            (contract.get("outputSchema") or {}).get("additionalProperties") is False,
            "canonical quota output must remain allow-listed",
        )

        require(
            requirements == ["mcp==2.1.1", "mcp-types==2.1.1"],
            "MCP transport dependencies must be exact-pinned to 2.1.1",
        )
        require(not any(">=" in line or "~=" in line for line in requirements), "MCP dependency ranges are forbidden")

        for marker in [
            "from mcp.server import Server, ServerRequestContext",
            "get_access_token",
            "TokenVerifier",
            "AuthSettings",
            'MCP_PATH = "/mcp"',
            'DEFAULT_REQUIRED_SCOPES = ("quota:read",)',
            "additionalProperties",
            '"securitySchemes"',
            "open_world_hint=annotations.get(\"openWorldHint\")",
            "stateless_http=True",
            "InvalidToolArguments",
            "trusted_subject_from_access_token",
            "MCP authorization could not be verified.",
            "Never expose raw provider/Codex/vault errors through MCP.",
        ]:
            require(marker in transport, f"MCP transport missing marker: {marker}")

        numbers = [int(n) for n in re.findall(r"^## Test (\d+)\b", tests, re.M)]
        require(numbers == list(range(201, 219)), "MCP regression shard must contain tests 201-218")

        for url in [
            "https://developers.openai.com/plugins/build/mcp-server",
            "https://developers.openai.com/plugins/build/auth",
            "https://developers.openai.com/plugins/build/plugins",
            "https://github.com/modelcontextprotocol/python-sdk",
            "https://github.com/openai/openai-apps-sdk-examples",
        ]:
            require(url in source_map, f"SOURCE_MAP missing current MCP/Plugin source: {url}")

    except (ValidationError, json.JSONDecodeError) as exc:
        print("Plugin package validation FAILED")
        print(f"- {exc}")
        return 1

    print(
        "Plugin package validation OK — official layout, exact zero-arg quota tool, "
        "server-wide OAuth contract, pinned MCP SDK and no fabricated app connection"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
