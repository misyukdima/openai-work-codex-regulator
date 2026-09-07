#!/usr/bin/env python3
"""Build a portable release ZIP and validate it with a clean round-trip.

Steps:
 1. run dependency-free repository and Plugin-package validators on source;
 2. build dist/openai-work-codex-regulator-v<VERSION>.zip with a top-level
    openai-work-codex-regulator/ directory (no .git, caches, secrets, archives);
 3. unpack the ZIP into a fresh temporary directory;
 4. run both dependency-free validators FROM the unpacked artifact;
 5. confirm the file set survived the round-trip exactly.

Runtime MCP validation remains a CI/deployment gate because it intentionally
uses exact-pinned external SDK dependencies. This script validates the portable
artifact without installing packages or using network access.

Exits non-zero on any failure. Does not publish anything.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = "openai-work-codex-regulator"

EXCLUDE_DIRS = {".git", "__pycache__", "dist", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store"}
VALIDATORS = (
    "scripts/validate_repo.py",
    "scripts/validate_plugin_package.py",
)


def fail(msg):
    print(f"release validation FAILED: {msg}")
    sys.exit(1)


def collect_files(root):
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.name in EXCLUDE_FILES or path.suffix == ".zip":
            continue
        if path.name.startswith(".env"):
            continue
        if not rel.as_posix().isascii():
            fail(f"non-ASCII filename: {rel.as_posix()}")
        files.append(rel)
    return files


def run_validator(root, rel, label):
    result = subprocess.run(
        [sys.executable, str(root / rel)],
        capture_output=True,
        text=True,
        cwd=root,
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip())
        fail(label)


def main():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    # 1. source tree validation
    for rel in VALIDATORS:
        run_validator(ROOT, rel, f"source validator: {rel}")

    files = collect_files(ROOT)
    if not files:
        fail("no files to package")

    # 2. build the ZIP
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    zip_path = dist / f"{SKILL_DIR}-v{version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(ROOT / rel, f"{SKILL_DIR}/{rel.as_posix()}")
    print(f"built {zip_path.relative_to(ROOT)} ({len(files)} files)")

    # 3–5. clean round-trip
    with tempfile.TemporaryDirectory(prefix="openai-regulator-release-") as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        unpacked = Path(tmp) / SKILL_DIR
        if not unpacked.is_dir():
            fail("archive missing top-level skill directory")

        roundtrip = sorted(
            p.relative_to(unpacked).as_posix() for p in unpacked.rglob("*") if p.is_file()
        )
        expected = sorted(rel.as_posix() for rel in files)
        if roundtrip != expected:
            missing = set(expected) - set(roundtrip)
            extra = set(roundtrip) - set(expected)
            fail(f"round-trip file mismatch: missing={sorted(missing)} extra={sorted(extra)}")

        for rel in VALIDATORS:
            run_validator(unpacked, rel, f"unpacked artifact validator: {rel}")

    print(
        f"release artifact OK — {zip_path.relative_to(ROOT)} passed clean ZIP round-trip "
        f"with repository + Plugin-package validation"
    )


if __name__ == "__main__":
    main()
