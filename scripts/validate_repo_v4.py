#!/usr/bin/env python3
"""Repository validator for openai-work-codex-regulator v4.x."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
errors=[]

def read(rel):
    p=ROOT/rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""

required=["SKILL.md","skills/openai-work-codex-regulator/SKILL.md","README.md","CHANGELOG.md","VERSION",".codex-plugin/plugin.json","references/08_MODEL_REASONING_ROUTER.md","references/14_WORK_SCHEDULE_RUNWAY.md","references/MODEL_CAPABILITY_SNAPSHOT.json","references/SOURCE_MAP.md","scripts/v4_quota_controller.py","scripts/validate_v4_routing.py","scripts/validate_release_contract.py","tests/fixtures/v4_routing_evals.json","tests/TEST_CASES_V4_0_ROUTING.md","plugin/get_quota_snapshot.tool.json","plugin/deployment_providers.py","deployment/crypto_helper.py","scripts/validate_production_providers.py"]
for rel in required:
    if not (ROOT/rel).is_file(): errors.append(f"missing: {rel}")

version=read("VERSION").strip()
if not version.startswith("4."): errors.append(f"v4 validator requires VERSION 4.x, got {version!r}")

try:
    manifest=json.loads(read(".codex-plugin/plugin.json"))
    if manifest.get("version")!=f"{version}.0": errors.append("plugin manifest version must match VERSION")
except Exception as exc: errors.append(f"plugin manifest invalid: {exc}")

skill=read("SKILL.md")
if skill!=read("skills/openai-work-codex-regulator/SKILL.md"): errors.append("skill mirror mismatch")
for marker in ["CHATGPT_PRIMARY_ORCHESTRATOR=YES","CONTROL_PLANE_OWNER=CHAT","WORK_CODEX_ROLE=EXECUTION_PLANE","QUALITY_FLOOR=NON_NEGOTIABLE","QUOTA_CONTINUITY=UNTIL_RESET","TASK_DURATION_LIMIT=NONE","WORKDAY_START_LOCAL=09:00","WORKDAY_SOFT_END_LOCAL=22:00","WORKDAY_HARD_END_LOCAL=23:00","USER_CONFIGURABLE_WORKDAY=YES","ACTIVE_LIMITS=DERIVED_FROM_CURRENT_SNAPSHOT","SECONDARY_LIMIT_DECISION=NOT_APPLICABLE_FROM_CURRENT_SNAPSHOT","MODEL_ID=<canonical id|UNKNOWN>","CAPABILITY_FAILURE != REASONING_DEPTH_FAILURE","UNKNOWN_IS_NOT_ZERO=YES","UNKNOWN_IS_NOT_UNAVAILABLE=YES"]:
    if marker not in skill: errors.append(f"SKILL missing v4 invariant: {marker}")
for forbidden in ["MODEL_PROFILE=<TIERED|ASTRA","MODEL_TIER=<LUNA|TERRA","TERRA — balanced default"]:
    if forbidden in skill: errors.append(f"obsolete active routing marker: {forbidden}")

nums=[]
for p in sorted((ROOT/"tests").glob("TEST_CASES*.md")):
    local=[int(x) for x in re.findall(r"^## Test (\d+)\b",p.read_text(encoding="utf-8"),re.M)]
    if local!=sorted(local): errors.append(f"{p.relative_to(ROOT)} numbering")
    nums.extend(local)
nums=sorted(nums)
if not nums or nums!=list(range(1,max(nums)+1)): errors.append("tests must be contiguous from 1")
if nums and max(nums)<289: errors.append("v4 routing tests incomplete")

for rel in ["references/MODEL_CAPABILITY_SNAPSHOT.json","tests/fixtures/v4_routing_evals.json"]:
    try: json.loads(read(rel))
    except Exception as exc: errors.append(f"{rel} invalid JSON: {exc}")

crypto=read("deployment/crypto_helper.py")
for marker in ["/usr/bin/systemd-creds","SO_PEERCRED","CLIENT_IO_TIMEOUT_SECONDS","stat.S_ISSOCK","stat.S_ISLNK","_cleanup_socket"]:
    if marker not in crypto: errors.append(f"crypto helper missing {marker}")
for forbidden in ["--no-ask-password","cmd_compat",".resolve()"]:
    if forbidden in crypto: errors.append(f"crypto helper forbidden marker {forbidden}")

try:
    tool=json.loads(read("plugin/get_quota_snapshot.tool.json"))
    if (tool.get("inputSchema") or {}).get("properties")!={}: errors.append("quota tool must remain zero-argument")
    ann=tool.get("annotations") or {}
    if ann.get("readOnlyHint") is not True or ann.get("destructiveHint") is not False: errors.append("quota tool annotations drifted")
except Exception as exc: errors.append(f"quota tool invalid: {exc}")

def self_test(rel,name):
    p=ROOT/rel
    if not p.is_file(): return
    try:
        spec=importlib.util.spec_from_file_location(name,p)
        if spec is None or spec.loader is None: raise RuntimeError("cannot load")
        mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod); mod.self_test()
    except Exception as exc: errors.append(f"{rel} self-test failed: {exc}")

for rel,name in [("scripts/v4_quota_controller.py","v4_quota_controller_validation"),("scripts/weekly_quota_controller.py","weekly_quota_controller_validation"),("plugin/quota_backend.py","quota_backend_validation"),("plugin/subject_store.py","subject_store_validation"),("plugin/quota_service.py","quota_service_validation"),("plugin/sealed_auth_store.py","sealed_auth_store_validation"),("plugin/authorization_coordinator.py","authorization_coordinator_validation"),("plugin/auth_concurrency.py","auth_concurrency_validation"),("plugin/production_vault.py","production_vault_validation"),("scripts/validate_production_providers.py","production_providers_validation")]:
    self_test(rel,name)

patterns=[r"sk-[A-Za-z0-9_-]{20,}",r"gh[pousr]_[A-Za-z0-9]{36,}",r"github_pat_[A-Za-z0-9_]{22,}",r"BEGIN (?:OPENSSH|RSA|EC|DSA|PGP) PRIVATE KEY"]
for p in ROOT.rglob("*"):
    if not p.is_file() or ".git" in p.parts or p.suffix.lower() not in {".md",".py",".json",".yml",".yaml",".txt",".toml",".sh"}: continue
    t=p.read_text(encoding="utf-8",errors="ignore")
    for pat in patterns:
        if re.search(pat,t): errors.append(f"{p.relative_to(ROOT)} possible secret pattern")

if errors:
    print("Repository validation FAILED")
    for e in errors: print(f"- {e}")
    raise SystemExit(1)
print(f"Repository validation OK — openai-work-codex-regulator v{version} ({len(nums)} tests)")
