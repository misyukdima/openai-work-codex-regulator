#!/usr/bin/env python3
"""Generation-neutral release contract for v4 and later."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
errors=[]

def read(rel):
    p=ROOT/rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""

version=read("VERSION").strip()
if version!="4.0": errors.append(f"expected VERSION 4.0, got {version!r}")

required=["SKILL.md","skills/openai-work-codex-regulator/SKILL.md","references/MODEL_CAPABILITY_SNAPSHOT.json","references/08_MODEL_REASONING_ROUTER.md","references/14_WORK_SCHEDULE_RUNWAY.md","scripts/v4_quota_controller.py","scripts/validate_repo_v4.py","scripts/validate_v4_routing.py","tests/fixtures/v4_routing_evals.json","tests/TEST_CASES_V4_0_ROUTING.md","plugin/mcp_transport.py","plugin/oidc_token_verifier.py","plugin/idp_preflight.py","plugin/production_runtime.py","plugin/deployment_providers.py","deployment/crypto_helper.py"]
for rel in required:
    if not (ROOT/rel).is_file(): errors.append(f"missing release file: {rel}")

if read("SKILL.md")!=read("skills/openai-work-codex-regulator/SKILL.md"): errors.append("skill mirror mismatch")
try:
    cap=json.loads(read("references/MODEL_CAPABILITY_SNAPSHOT.json"))
    if cap.get("release_target")!="4.0": errors.append("capability snapshot target")
except Exception as exc: errors.append(f"capability snapshot invalid: {exc}")

workflow=read(".github/workflows/validate.yml")
for marker in ["Validate v4 repository","Validate v4 adaptive routing","Validate release contract","scripts/validate_repo_v4.py","scripts/validate_v4_routing.py","scripts/validate_release_contract.py"]:
    if marker not in workflow: errors.append(f"workflow missing {marker}")

package=read("scripts/package_release.py")
for marker in ["scripts/validate_repo_v4.py","scripts/validate_v4_routing.py","scripts/validate_release_contract.py"]:
    if marker not in package: errors.append(f"package missing {marker}")

nums=[]
for p in (ROOT/"tests").glob("TEST_CASES*.md"):
    nums += [int(n) for n in re.findall(r"^## Test (\d+)\b",p.read_text(encoding="utf-8"),re.M)]
nums.sort()
if nums!=list(range(1,290)): errors.append(f"release tests must be exactly 1..289, got {len(nums)}")

if errors:
    print("release-contract validation FAILED")
    for e in errors: print(f"- {e}")
    raise SystemExit(1)
print("release-contract validation OK — v4 routing, runway, plugin security and packaging gates present")
