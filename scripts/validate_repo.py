#!/usr/bin/env python3
"""Repository validator for openai-work-codex-regulator.

Checks (v1.1):
 1. required repository files exist;
 2. VERSION is major.minor;
 3. README reflects the current VERSION;
 4. CHANGELOG contains a heading for the current VERSION;
 5. regression tests are numbered contiguously;
 6. regression test count >= 50;
 7. expected normative references exist;
 8. mandatory v1.1 invariants are present in SKILL.md;
 9. SOURCE_MAP contains a verification date;
10. mandatory first-party OpenAI sources are listed in SOURCE_MAP;
11. no stale hardcoded model names in normative logic
    (SOURCE_MAP / tests / changelog are allowed historical/source context);
12. basic secret scanning;
13. all tracked filenames are ASCII (ZIP portability).
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "SKILL.md",
    "README.md",
    "VERSION",
    "CHANGELOG.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    ".gitattributes",
    "docs/USAGE.md",
    "docs/ARCHITECTURE.md",
    "docs/RELEASE_PROCESS.md",
    "references/01_SURFACE_ROUTING.md",
    "references/02_SHARED_QUOTA_AND_CREDITS.md",
    "references/03_TASK_CLASSIFICATION.md",
    "references/04_RUNWAY_AND_BURN.md",
    "references/05_WORK_BROWSER_AND_ACTIONS.md",
    "references/06_CODEX_TECHNICAL_WORK.md",
    "references/07_FAILURES_AND_RECOVERY.md",
    "references/SOURCE_MAP.md",
    "tests/TEST_CASES.md",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug.md",
    ".github/ISSUE_TEMPLATE/rule-change.md",
    ".github/workflows/validate.yml",
    ".github/workflows/release.yml",
]

SKILL_INVARIANTS = [
    "name: openai-work-codex-regulator",
    "ONE_GATE = ONE_PRIMARY_SURFACE",
    "PAID_CREDITS_ALLOWED=NO",
    "SURFACE: CHATGPT_WORK",
    "SURFACE: CODEX",
    "STOP AFTER REPORT",
    "git add .",
    # v1.1 invariants
    "CHAT_BOUNDED_WEB",
    "WHY_AGENTIC",
    "VALUE_OUTPUT",
    "USER_SURFACE_OVERRIDE=YES",
    "OTHER_SHARED_POOL_ACTIVITY",
    "ATTRIBUTION=CLEAN|MIXED|UNKNOWN",
    "CREDIT_ELIGIBILITY_WORK",
    "CREDIT_ELIGIBILITY_CODEX",
    "WORK_CLOUD=ON|OFF|UNKNOWN",
    "INJECTION_ATTEMPT",
    "Downloading ≠ permission to execute",
]

REQUIRED_SOURCES = [
    "https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex",
    "https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan",
    "https://help.openai.com/en/articles/20001106-codex-rate-card",
    "https://help.openai.com/en/articles/12642688",
    "https://help.openai.com/en/articles/20001277-using-the-built-in-browser-in-the-chatgpt-desktop-app",
]

MIN_TESTS = 50

# Files where model names are allowed as historical/source/test context.
MODEL_NAME_ALLOWED = {
    "references/SOURCE_MAP.md",
    "tests/TEST_CASES.md",
    "CHANGELOG.md",
}
MODEL_NAME_PATTERNS = [
    (r"\bGPT-\d", "hardcoded GPT-* model name"),
    (r"\bgpt-\d", "hardcoded gpt-* model name"),
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
SECRET_SCAN_GLOBS = ("*.md", "*.py", "*.yml", "*.yaml", "*.toml", "*.txt")

errors = []


def read(rel):
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


# 1 + 7. required files (includes normative references)
for rel in REQUIRED:
    if not (ROOT / rel).is_file():
        errors.append(f"missing: {rel}")

# 2. VERSION format
version = read("VERSION").strip()
if not re.fullmatch(r"\d+\.\d+", version):
    errors.append("VERSION must be major.minor")

# 3. README reflects current VERSION
readme = read("README.md")
if version and f"v{version}" not in readme:
    errors.append(f"README.md does not mention current version v{version}")

# 4. CHANGELOG contains heading for current VERSION
changelog = read("CHANGELOG.md")
if version and not re.search(rf"^##\s+{re.escape(version)}\b", changelog, re.M):
    errors.append(f"CHANGELOG.md missing heading for version {version}")

# 5 + 6. tests numbering and count
tests = read("tests/TEST_CASES.md")
numbers = [int(n) for n in re.findall(r"^## Test (\d+)\b", tests, re.M)]
if numbers:
    if numbers != list(range(1, max(numbers) + 1)):
        errors.append("tests are not numbered contiguously from 1")
    if len(numbers) < MIN_TESTS:
        errors.append(f"tests count {len(numbers)} < {MIN_TESTS}")
else:
    errors.append("no numbered tests found in tests/TEST_CASES.md")

# 8. SKILL.md invariants
skill = read("SKILL.md")
for needle in SKILL_INVARIANTS:
    if needle not in skill:
        errors.append(f"SKILL.md missing required rule: {needle}")

# 9 + 10. SOURCE_MAP verification date and first-party sources
source_map = read("references/SOURCE_MAP.md")
if not re.search(r"\*\*Verified:\*\*\s*\d{4}-\d{2}-\d{2}", source_map):
    errors.append("SOURCE_MAP.md missing verification date")
for url in REQUIRED_SOURCES:
    if url not in source_map:
        errors.append(f"SOURCE_MAP missing official source: {url}")

# 11. no stale hardcoded model names in normative logic
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or path.suffix != ".md":
        continue
    rel = path.relative_to(ROOT).as_posix()
    if rel in MODEL_NAME_ALLOWED or rel.startswith(".github/"):
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern, label in MODEL_NAME_PATTERNS:
        if re.search(pattern, text):
            errors.append(f"{rel} contains {label} (move to SOURCE_MAP/tests context)")

# 12. basic secret scanning
scan_targets = []
for glob in SECRET_SCAN_GLOBS:
    scan_targets.extend(ROOT.rglob(glob))
for path in sorted(set(scan_targets)):
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            errors.append(f"{path.relative_to(ROOT)} contains {label}")

# 13. ASCII filenames for portability
for path in sorted(ROOT.rglob("*")):
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith(".git/") or not path.is_file():
        continue
    if not rel.isascii():
        errors.append(f"non-ASCII filename (not portable): {rel}")

if errors:
    print("Repository validation FAILED")
    for e in errors:
        print(f"- {e}")
    sys.exit(1)

print(f"Repository validation OK — openai-work-codex-regulator v{version} ({len(numbers)} tests)")
