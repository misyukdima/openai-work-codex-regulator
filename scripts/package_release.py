#!/usr/bin/env python3
"""Build a portable release ZIP and validate it with a clean round-trip.

The source tree and the unpacked artifact must both pass:
- historical repository validation;
- Plugin package validation;
- strict v3 release-contract validation.

This command does not publish anything.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = "openai-work-codex-regulator"
VALIDATORS = (
    "scripts/validate_repo.py",
    "scripts/validate_plugin_package.py",
    "scripts/validate_v3_release_contract.py",
)

EXCLUDE_DIRS = {".git", "__pycache__", "dist", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store"}


def fail(msg: str) -> None:
    print(f"release validation FAILED: {msg}")
    sys.exit(1)


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
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


def run_validators(root: Path, label: str) -> None:
    for rel in VALIDATORS:
        path = root / rel
        if not path.is_file():
            fail(f"{label}: missing validator {rel}")
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.returncode != 0:
            if result.stderr.strip():
                print(result.stderr.strip())
            fail(f"{label}: {rel}")


def main() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    # 1. Validate the source tree before packaging.
    run_validators(ROOT, "source tree")

    files = collect_files(ROOT)
    if not files:
        fail("no files to package")

    # 2. Build the ZIP with one stable top-level directory.
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    zip_path = dist / f"{SKILL_DIR}-v{version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(ROOT / rel, f"{SKILL_DIR}/{rel.as_posix()}")
    print(f"built {zip_path.relative_to(ROOT)} ({len(files)} files)")

    # 3. Clean round-trip: file set and all dependency-free validators must
    # survive exactly as they will in the GitHub Release artifact.
    with tempfile.TemporaryDirectory(prefix="openai-regulator-release-") as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        unpacked = Path(tmp) / SKILL_DIR
        if not unpacked.is_dir():
            fail("archive missing top-level skill directory")

        roundtrip = sorted(
            p.relative_to(unpacked).as_posix()
            for p in unpacked.rglob("*")
            if p.is_file()
        )
        expected = sorted(rel.as_posix() for rel in files)
        if roundtrip != expected:
            missing = set(expected) - set(roundtrip)
            extra = set(roundtrip) - set(expected)
            fail(
                "round-trip file mismatch: "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )

        run_validators(unpacked, "unpacked artifact")

    print(
        f"release artifact OK — {zip_path.relative_to(ROOT)} "
        "passed clean ZIP round-trip"
    )


if __name__ == "__main__":
    main()
