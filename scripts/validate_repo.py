#!/usr/bin/env python3
"""Repository validator for openai-work-codex-regulator v2.x."""
from pathlib import Path
import importlib.util
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "SKILL.md", "README.md", "VERSION", "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md", ".gitattributes",
    "docs/USAGE.md", "docs/ARCHITECTURE.md", "docs/RELEASE_PROCESS.md",
    "references/01_SURFACE_ROUTING.md", "references/02_SHARED_QUOTA_AND_CREDITS.md",
    "references/03_TASK_CLASSIFICATION.md", "references/04_RUNWAY_AND_BURN.md",
    "references/05_WORK_BROWSER_AND_ACTIONS.md", "references/06_CODEX_TECHNICAL_WORK.md",
    "references/07_FAILURES_AND_RECOVERY.md", "references/08_MODEL_TIER_ROUTING.md",
    "references/09_ASTRA_EXECUTION.md", "references/10_WEEKLY_QUOTA_CONTROLLER.md", "references/SOURCE_MAP.md",
    "tests/TEST_CASES.md", "scripts/weekly_quota_controller.py",
    ".github/CODEOWNERS", ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/bug.md",
    ".github/ISSUE_TEMPLATE/rule-change.md", ".github/workflows/validate.yml", ".github/workflows/release.yml",
]

SKILL_INVARIANTS = [
    "name: openai-work-codex-regulator", "ONE_GATE = ONE_PRIMARY_SURFACE", "QUALITY_FLOOR=NON_NEGOTIABLE",
    "PAID_CREDITS_ALLOWED=NO", "PAID_WEEKLY_RESET_ALLOWED=NO", "SURFACE: CHATGPT_WORK", "SURFACE: CODEX",
    "STOP AFTER REPORT", "git add .", "CHAT_BOUNDED_WEB", "WHY_AGENTIC", "VALUE_OUTPUT",
    "USER_SURFACE_OVERRIDE=YES", "ALLOWANCE_DOMAIN=<WORK_CODEX|CHAT_PRO|API|UNKNOWN>",
    "WEEKLY_METER_SEMANTICS=<USED|REMAINING|UNKNOWN>", "QUOTA_EPOCH_ID", "CONTROL_SLICE_BUDGET_PP",
    "CONTROL_SLICE_START_WEEKLY_USED_PP", "EFFECTIVE_SLICE_HEADROOM_PP", "BURN_ESTIMATE_WEEKLY_PP",
    "CONTINUITY_FEASIBLE", "PENDING_BURN", "OTHER_SHARED_POOL_ACTIVITY", "ATTRIBUTION=CLEAN|MIXED|UNKNOWN",
    "CREDIT_ELIGIBILITY_WORK", "CREDIT_ELIGIBILITY_CODEX", "WORK_CLOUD=ON|OFF|UNKNOWN",
    "MODEL_PROFILE=<TIERED|ASTRA|OTHER|UNKNOWN>", "MODEL_TIER=<LUNA|TERRA|SOL|N/A|OTHER|UNKNOWN>",
    "ASTRA_JUSTIFIED=YES", "ASTRA_SCOPE_BOUND", "CODEX_CLIENT_ASTRA_READY", "STEERING_SCOPE_EFFECT",
    "SAFETY_STATE=<NORMAL|PAUSED_FOR_REVIEW|BLOCKED|UNKNOWN>", "CYBER_SCOPE_AUTHORIZATION",
    "LONG_CONTEXT_JUSTIFIED", "INJECTION_ATTEMPT", "Downloading ≠ permission to execute",
]

MODEL_ROUTER_INVARIANTS = [
    "MODEL_PROFILE=<TIERED|ASTRA|OTHER|UNKNOWN>", "MODEL_TIER=<LUNA|TERRA|SOL|N/A|OTHER|UNKNOWN>",
    "LUNA — economy / high-volume routine work", "TERRA — balanced default", "SOL — quality-first consequential synthesis",
    "ASTRA_JUSTIFIED=YES", "WHY_MAX", "FAST_REQUIRED=YES", "Astra is not a fourth tier",
]

ASTRA_INVARIANTS = [
    "ASTRA_JUSTIFIED=YES", "ASTRA_SCOPE_BOUND", "ALLOWANCE_DOMAIN=WORK_CODEX", "CODEX_CLIENT_ASTRA_READY",
    "STEERING_SCOPE_EFFECT", "SAFETY_STATE=<NORMAL|PAUSED_FOR_REVIEW|BLOCKED|UNKNOWN>",
    "CYBER_SCOPE_AUTHORIZATION", "LONG_CONTEXT_JUSTIFIED=YES", "ONE_GATE = ONE_PRIMARY_SURFACE",
]

WEEKLY_CONTROLLER_INVARIANTS = [
    "QUALITY_FLOOR=NON_NEGOTIABLE", "WEEKLY_METER_SEMANTICS=<USED|REMAINING>", "QUOTA_EPOCH_ID",
    "BASE_WEEKLY_RESERVE_PP = 10", "RESERVE_FRACTION_CAP = 0.50", "RESERVE_RELEASE_HOURS = 72",
    "CONTROL_SLICE_HOURS = 24", "CONTROL_SLICE_BUDGET_PP", "CONTROL_SLICE_START_WEEKLY_USED_PP",
    "EFFECTIVE_SLICE_HEADROOM_PP", "BURN_ESTIMATE_WEEKLY_PP", "BURN_HISTORY_COMPATIBLE",
    "PENDING_BURN=<YES|NO>", "PAID_WEEKLY_RESET_ALLOWED=NO", "QUOTA_DECISION=DEFER_FOR_QUALITY",
    "CONTINUITY_FEASIBLE", "SCHEDULED_WEEKLY_COMMITMENT_PP",
]

REQUIRED_SOURCES = [
    "https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex",
    "https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan",
    "https://help.openai.com/en/articles/12642688",
    "https://help.openai.com/en/articles/20001277-using-the-built-in-browser-in-the-chatgpt-desktop-app",
    "https://help.openai.com/en/articles/20001354-gpt-56-and-gpt-6-pro-in-chatgpt",
    "https://help.openai.com/en/articles/11481834-chatgpt-rate-card",
    "https://help.openai.com/en/articles/12003714-chatgpt-business-models-and-limits",
    "https://help.openai.com/en/articles/20001415-chatgpt-rate-card-enterprise-token-based-pricing",
    "https://help.openai.com/en/articles/20001507-paid-weekly-work-and-codex-rate-limit-resets",
    "https://help.openai.com/en/articles/20001478-reviewing-work-and-codex-usage-and-using-personal-analytics-in-chatgpt-desktop",
    "https://openai.com/products/release-notes/", "https://openai.com/index/gpt-6-astra/",
    "https://openai.com/index/safety-overview-gpt-6-astra/",
    "https://developers.openai.com/api/docs/models/gpt-6-astra",
    "https://developers.openai.com/api/docs/guides/latest-model",
]

MIN_TESTS = 95
GENERATION_NEUTRAL_FILES = [
    "SKILL.md", "references/01_SURFACE_ROUTING.md", "references/03_TASK_CLASSIFICATION.md",
    "references/04_RUNWAY_AND_BURN.md", "references/05_WORK_BROWSER_AND_ACTIONS.md",
    "references/06_CODEX_TECHNICAL_WORK.md", "references/07_FAILURES_AND_RECOVERY.md",
    "references/10_WEEKLY_QUOTA_CONTROLLER.md",
]
MODEL_NAME_PATTERNS = [
    (r"\bGPT-\d", "hardcoded GPT-* generation name"), (r"\bgpt-\d", "hardcoded gpt-* generation id"),
    (r"\bo[34](?:-[a-z0-9]+)?\b", "hardcoded o3/o4 model name"),
]
SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9_-]{20,}", "possible OpenAI secret"), (r"gh[pousr]_[A-Za-z0-9]{36,}", "possible GitHub token"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "possible GitHub fine-grained token"),
    (r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", "possible AWS access key"),
    (r"BEGIN (?:OPENSSH|RSA|EC|DSA|PGP) PRIVATE KEY", "private key"),
    (r"Bearer [A-Za-z0-9._~+/=-]{20,}", "possible bearer token"),
]

errors = []

def read(rel):
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""

for rel in REQUIRED:
    if not (ROOT / rel).is_file(): errors.append(f"missing: {rel}")

version = read("VERSION").strip()
if not re.fullmatch(r"\d+\.\d+", version): errors.append("VERSION must be major.minor")
if version and not version.startswith("2."): errors.append("v2 validator requires VERSION 2.x")
readme = read("README.md")
if version and f"v{version}" not in readme: errors.append(f"README.md does not mention current version v{version}")
changelog = read("CHANGELOG.md")
if version and not re.search(rf"^##\s+{re.escape(version)}\b", changelog, re.M): errors.append(f"CHANGELOG.md missing heading for version {version}")

raw_tests = read("tests/TEST_CASES.md")
numbers = [int(n) for n in re.findall(r"^## Test (\d+)\b", raw_tests, re.M)]
if not numbers:
    errors.append("no numbered tests found in tests/TEST_CASES.md")
else:
    if numbers != list(range(1, max(numbers) + 1)): errors.append("tests are not numbered contiguously from 1")
    if len(numbers) < MIN_TESTS: errors.append(f"tests count {len(numbers)} < {MIN_TESTS}")

for needle in SKILL_INVARIANTS:
    if needle not in read("SKILL.md"): errors.append(f"SKILL.md missing required rule: {needle}")
for needle in MODEL_ROUTER_INVARIANTS:
    if needle not in read("references/08_MODEL_TIER_ROUTING.md"): errors.append(f"model router missing required rule: {needle}")
for needle in ASTRA_INVARIANTS:
    if needle not in read("references/09_ASTRA_EXECUTION.md"): errors.append(f"Astra execution reference missing required rule: {needle}")
for needle in WEEKLY_CONTROLLER_INVARIANTS:
    if needle not in read("references/10_WEEKLY_QUOTA_CONTROLLER.md"): errors.append(f"weekly quota controller missing required rule: {needle}")

source_map = read("references/SOURCE_MAP.md")
if not re.search(r"\*\*Verified:\*\*\s*\d{4}-\d{2}-\d{2}", source_map): errors.append("SOURCE_MAP.md missing verification date")
if "**Skill release:** 2.1" not in source_map: errors.append("SOURCE_MAP.md is not marked for release 2.1")
for url in REQUIRED_SOURCES:
    if url not in source_map: errors.append(f"SOURCE_MAP missing official source: {url}")

for rel in GENERATION_NEUTRAL_FILES:
    text = read(rel)
    for pattern, label in MODEL_NAME_PATTERNS:
        if re.search(pattern, text): errors.append(f"{rel} contains {label}; move dated model facts to 02/08/09/SOURCE_MAP/tests/changelog")

controller_path = ROOT / "scripts" / "weekly_quota_controller.py"
if controller_path.is_file():
    try:
        spec = importlib.util.spec_from_file_location("weekly_quota_controller_validation", controller_path)
        if spec is None or spec.loader is None: raise RuntimeError("cannot load controller module spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.self_test()
    except Exception as exc:
        errors.append(f"weekly quota controller self-test failed: {exc}")

scan_targets = set()
for glob in ("*.md", "*.py", "*.yml", "*.yaml", "*.toml", "*.txt"):
    scan_targets.update(ROOT.rglob(glob))
for path in sorted(scan_targets):
    if not path.is_file(): continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text): errors.append(f"{path.relative_to(ROOT)} contains {label}")

for path in sorted(ROOT.rglob("*")):
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith(".git/") or not path.is_file(): continue
    if not rel.isascii(): errors.append(f"non-ASCII filename (not portable): {rel}")

if errors:
    print("Repository validation FAILED")
    for error in errors: print(f"- {error}")
    sys.exit(1)

print(f"Repository validation OK — openai-work-codex-regulator v{version} ({len(numbers)} tests, Astra + adaptive weekly controller present)")
