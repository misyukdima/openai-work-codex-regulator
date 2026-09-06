#!/usr/bin/env python3
"""Repository validator for openai-work-codex-regulator v3.x."""
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
    "references/09_ASTRA_EXECUTION.md", "references/10_WEEKLY_QUOTA_CONTROLLER.md",
    "references/11_ORCHESTRATION_AND_HANDOFF.md", "references/12_AUTONOMOUS_QUOTA_TELEMETRY.md",
    "references/SOURCE_MAP.md",
    "tests/TEST_CASES.md", "tests/TEST_CASES_V2_2.md", "tests/TEST_CASES_V3_0.md",
    "scripts/weekly_quota_controller.py", "scripts/quota_telemetry.py",
    ".github/CODEOWNERS", ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/bug.md",
    ".github/ISSUE_TEMPLATE/rule-change.md", ".github/workflows/validate.yml", ".github/workflows/release.yml",
]

SKILL_INVARIANTS = [
    "name: openai-work-codex-regulator",
    "ONE_GATE = ONE_PRIMARY_SURFACE",
    "QUALITY_FLOOR=NON_NEGOTIABLE",
    "BALANCED_PRIORITY=QUOTA_50_PACE_50",
    "HANDOFF_SELF_CONTAINED=YES",
    "EXECUTOR_SKILL_REQUIRED=NO",
    "CONTROL_PLANE_OWNER=<CHAT|WORK|CODEX>",
    "CHATGPT_PRIMARY_ORCHESTRATOR=YES",
    "AUTO_QUOTA_TELEMETRY=DEFAULT",
    "MANUAL_QUOTA_INPUT=FALLBACK_ONLY",
    "ZERO_MAINTENANCE_USER_SETUP=REQUIRED",
    "CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN",
    "CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN",
    "QUOTA_TOOL=get_quota_snapshot",
    "QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>",
    "PAID_CREDITS_ALLOWED=NO",
    "PAID_WEEKLY_RESET_ALLOWED=NO",
    "ALLOWANCE_DOMAIN=<WORK_CODEX|CHAT_PRO|API|UNKNOWN>",
    "WEEKLY_METER_SEMANTICS=<USED|REMAINING|UNKNOWN>",
    "QUOTA_EPOCH_ID",
    "TRAJECTORY_ANCHOR_WEEKLY_USED_PP",
    "BASE_ACTION_HEADROOM_PP",
    "MAX_ADVANCE_HEADROOM_PP",
    "PACE_RISK_IF_DEFER",
    "QUOTA_RISK_IF_LAUNCH",
    "QUOTA_DECISION=LAUNCH_WITH_ADVANCE",
    "MEANINGFUL_PROGRESS_WITHOUT_AGENTIC",
    "BURN_ESTIMATE_WEEKLY_PP",
    "PENDING_BURN",
    "WORK_CLOUD=ON|OFF|UNKNOWN",
    "MODEL_PROFILE=<TIERED|ASTRA|OTHER|UNKNOWN>",
    "MODEL_TIER=<LUNA|TERRA|SOL|N/A|OTHER|UNKNOWN>",
    "ASTRA_JUSTIFIED=YES",
    "CODEX_CLIENT_ASTRA_READY=YES|NO|UNKNOWN|N/A",
    "INJECTION_ATTEMPT",
    "Downloading ≠ permission to execute",
    "RATE_WINDOW_POSITION_IS_NOT_SEMANTICS",
    "SURFACE: CHATGPT_WORK",
    "SURFACE: CODEX",
    "STOP AFTER REPORT",
    "git add .",
    "CHAT_BOUNDED_WEB",
    "WHY_AGENTIC",
    "VALUE_OUTPUT",
]

ROUTING_INVARIANTS = [
    "USER_SURFACE_OVERRIDE=YES",
    "CONTROL_PLANE_OWNER=CHAT",
    "HANDOFF_SELF_CONTAINED=YES",
    "EXECUTOR_SKILL_REQUIRED=NO",
    "MEANINGFUL_PROGRESS_WITHOUT_AGENTIC",
]

MODEL_ROUTER_INVARIANTS = [
    "MODEL_PROFILE=<TIERED|ASTRA|OTHER|UNKNOWN>",
    "MODEL_TIER=<LUNA|TERRA|SOL|N/A|OTHER|UNKNOWN>",
    "LUNA — economy / high-volume routine work",
    "TERRA — balanced default",
    "SOL — quality-first consequential synthesis",
    "ASTRA_JUSTIFIED=YES",
    "WHY_MAX",
    "FAST_REQUIRED=YES",
    "Astra is not a fourth tier",
]

ASTRA_INVARIANTS = [
    "ASTRA_JUSTIFIED=YES", "ASTRA_SCOPE_BOUND", "ALLOWANCE_DOMAIN=WORK_CODEX", "CODEX_CLIENT_ASTRA_READY",
    "STEERING_SCOPE_EFFECT", "SAFETY_STATE=<NORMAL|PAUSED_FOR_REVIEW|BLOCKED|UNKNOWN>",
    "CYBER_SCOPE_AUTHORIZATION", "LONG_CONTEXT_JUSTIFIED=YES", "ONE_GATE = ONE_PRIMARY_SURFACE",
]

CONTROLLER_INVARIANTS = [
    "QUALITY_FLOOR=NON_NEGOTIABLE",
    "WEEKLY_METER_SEMANTICS=<USED|REMAINING>",
    "QUOTA_EPOCH_ID",
    "BASE_WEEKLY_RESERVE_PP = 10",
    "RESERVE_FRACTION_CAP = 0.50",
    "RESERVE_RELEASE_HOURS = 72",
    "BASE_LOOKAHEAD_HOURS = 24",
    "MAX_ADVANCE_HOURS = 72",
    "BALANCED_PRIORITY=QUOTA_50_PACE_50",
    "BASE_ACTION_HEADROOM_PP",
    "MAX_ADVANCE_HEADROOM_PP",
    "BORROWABLE_EXTRA_PP",
    "PACE_RISK_IF_DEFER",
    "QUOTA_RISK_IF_LAUNCH",
    "QUOTA_DECISION=LAUNCH_WITH_ADVANCE",
    "PENDING_BURN=<YES|NO>",
    "SCHEDULED_WEEKLY_COMMITMENT_PP",
]

HANDOFF_INVARIANTS = [
    "CONTROL_PLANE_OWNER=<CHAT|WORK|CODEX>",
    "HANDOFF_SELF_CONTAINED=YES",
    "EXECUTOR_SKILL_REQUIRED=NO",
    "Control-plane-only state",
    "Executor-relevant state",
    "EFFICIENCY_POSTURE=MINIMIZE_WASTE_WITHOUT_QUALITY_LOSS",
]

TELEMETRY_INVARIANTS = [
    "CHATGPT_PRIMARY_ORCHESTRATOR=YES",
    "AUTO_QUOTA_TELEMETRY=DEFAULT",
    "MANUAL_QUOTA_INPUT=FALLBACK_ONLY",
    "ZERO_MAINTENANCE_USER_SETUP=REQUIRED",
    "CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN",
    "CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN",
    "get_quota_snapshot()",
    "RATE_WINDOW_POSITION_IS_NOT_SEMANTICS",
    "300 minutes   → FIVE_HOUR",
    "10080 minutes → WEEKLY",
    "QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>",
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
    "https://help.openai.com/en/articles/20001256",
    "https://help.openai.com/en/articles/11487775-connectors-in-chatgpt",
    "https://openai.com/products/release-notes/",
    "https://openai.com/index/gpt-6-astra/",
    "https://openai.com/index/safety-overview-gpt-6-astra/",
    "https://developers.openai.com/api/docs/models/gpt-6-astra",
    "https://developers.openai.com/api/docs/guides/latest-model",
]

MIN_TESTS = 135
GENERATION_NEUTRAL_FILES = [
    "SKILL.md", "references/01_SURFACE_ROUTING.md", "references/03_TASK_CLASSIFICATION.md",
    "references/04_RUNWAY_AND_BURN.md", "references/05_WORK_BROWSER_AND_ACTIONS.md",
    "references/06_CODEX_TECHNICAL_WORK.md", "references/07_FAILURES_AND_RECOVERY.md",
    "references/10_WEEKLY_QUOTA_CONTROLLER.md", "references/11_ORCHESTRATION_AND_HANDOFF.md",
    "references/12_AUTONOMOUS_QUOTA_TELEMETRY.md",
]
MODEL_NAME_PATTERNS = [
    (r"\bGPT-\d", "hardcoded GPT-* generation name"),
    (r"\bgpt-\d", "hardcoded gpt-* generation id"),
    (r"\bo[34](?:-[a-z0-9]+)?\b", "hardcoded o3/o4 model name"),
]
SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9_-]{20,}", "possible OpenAI secret"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "possible GitHub token"),
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
    if not (ROOT / rel).is_file():
        errors.append(f"missing: {rel}")

version = read("VERSION").strip()
if not re.fullmatch(r"\d+\.\d+", version):
    errors.append("VERSION must be major.minor")
if version and not version.startswith("3."):
    errors.append("v3 validator requires VERSION 3.x")

readme = read("README.md")
if version and f"v{version}" not in readme:
    errors.append(f"README.md does not mention current version v{version}")
changelog = read("CHANGELOG.md")
if version and not re.search(rf"^##\s+{re.escape(version)}\b", changelog, re.M):
    errors.append(f"CHANGELOG.md missing heading for version {version}")

raw_tests = (
    read("tests/TEST_CASES.md")
    + "\n" + read("tests/TEST_CASES_V2_2.md")
    + "\n" + read("tests/TEST_CASES_V3_0.md")
)
numbers = [int(n) for n in re.findall(r"^## Test (\d+)\b", raw_tests, re.M)]
if not numbers:
    errors.append("no numbered tests found")
else:
    if numbers != list(range(1, max(numbers) + 1)):
        errors.append("tests are not numbered contiguously from 1 across base + version additions")
    if len(numbers) < MIN_TESTS:
        errors.append(f"tests count {len(numbers)} < {MIN_TESTS}")

for needle in SKILL_INVARIANTS:
    if needle not in read("SKILL.md"):
        errors.append(f"SKILL.md missing required rule: {needle}")
for needle in ROUTING_INVARIANTS:
    if needle not in read("references/01_SURFACE_ROUTING.md"):
        errors.append(f"surface routing missing required rule: {needle}")
for needle in MODEL_ROUTER_INVARIANTS:
    if needle not in read("references/08_MODEL_TIER_ROUTING.md"):
        errors.append(f"model router missing required rule: {needle}")
for needle in ASTRA_INVARIANTS:
    if needle not in read("references/09_ASTRA_EXECUTION.md"):
        errors.append(f"Astra execution reference missing required rule: {needle}")
for needle in CONTROLLER_INVARIANTS:
    if needle not in read("references/10_WEEKLY_QUOTA_CONTROLLER.md"):
        errors.append(f"weekly controller missing required rule: {needle}")
for needle in HANDOFF_INVARIANTS:
    if needle not in read("references/11_ORCHESTRATION_AND_HANDOFF.md"):
        errors.append(f"handoff reference missing required rule: {needle}")
for needle in TELEMETRY_INVARIANTS:
    if needle not in read("references/12_AUTONOMOUS_QUOTA_TELEMETRY.md"):
        errors.append(f"autonomous telemetry reference missing required rule: {needle}")

source_map = read("references/SOURCE_MAP.md")
if not re.search(r"\*\*Verified:\*\*\s*\d{4}-\d{2}-\d{2}", source_map):
    errors.append("SOURCE_MAP.md missing verification date")
if "**Skill release:** 3.0" not in source_map:
    errors.append("SOURCE_MAP.md is not marked for release 3.0")
for url in REQUIRED_SOURCES:
    if url not in source_map:
        errors.append(f"SOURCE_MAP missing official source: {url}")

for rel in GENERATION_NEUTRAL_FILES:
    text = read(rel)
    for pattern, label in MODEL_NAME_PATTERNS:
        if re.search(pattern, text):
            errors.append(f"{rel} contains {label}; move dated model facts to dated model/source references")

# Ordinary executor templates must remain independent from controller installation,
# automatic telemetry plumbing and internal quota math.
skill = read("SKILL.md")
executor_sections = []
for start_heading, end_heading in [
    ("## 19. Work executor packet", "## 20. Codex executor packet"),
    ("## 20. Codex executor packet", "## 21. Telemetry provider discipline"),
]:
    start = skill.find(start_heading)
    end = skill.find(end_heading)
    if start < 0 or end < 0 or end <= start:
        errors.append(f"cannot extract executor template section: {start_heading}")
        continue
    executor_sections.append(skill[start:end])

FORBIDDEN_EXECUTOR_LEAKS = [
    "QUOTA_EPOCH_ID",
    "TRAJECTORY_ANCHOR_",
    "BASE_ACTION_HEADROOM_PP",
    "MAX_ADVANCE_HEADROOM_PP",
    "PACE_RISK_IF_DEFER",
    "QUOTA_RISK_IF_LAUNCH",
    "BORROWABLE_EXTRA_PP",
    "PAID_WEEKLY_RESET_ALLOWED",
    "QUOTA_TELEMETRY_SOURCE",
    "QUOTA_TELEMETRY_STATE",
    "get_quota_snapshot",
    "openai-work-codex-regulator",
]
for section in executor_sections:
    for needle in FORBIDDEN_EXECUTOR_LEAKS:
        if needle in section:
            errors.append(f"executor template leaks control-plane dependency/state: {needle}")


def run_module_self_test(path: Path, module_name: str, label: str) -> None:
    if not path.is_file():
        return
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load module spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.self_test()
    except Exception as exc:
        errors.append(f"{label} self-test failed: {exc}")


run_module_self_test(
    ROOT / "scripts" / "weekly_quota_controller.py",
    "weekly_quota_controller_validation",
    "weekly quota controller",
)
run_module_self_test(
    ROOT / "scripts" / "quota_telemetry.py",
    "quota_telemetry_validation",
    "quota telemetry",
)

scan_targets = set()
for glob in ("*.md", "*.py", "*.yml", "*.yaml", "*.toml", "*.txt"):
    scan_targets.update(ROOT.rglob(glob))
for path in sorted(scan_targets):
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            errors.append(f"{path.relative_to(ROOT)} contains {label}")

for path in sorted(ROOT.rglob("*")):
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith(".git/") or not path.is_file():
        continue
    if not rel.isascii():
        errors.append(f"non-ASCII filename (not portable): {rel}")

if errors:
    print("Repository validation FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print(
    f"Repository validation OK — openai-work-codex-regulator v{version} "
    f"({len(numbers)} tests, autonomous telemetry + balanced controller + self-contained handoff present)"
)
