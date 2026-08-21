# Release process

## Versioning

The repository uses `major.minor` skill versions.

- **major** — incompatible redesign of the regulator or normative architecture;
- **minor** — meaningful behavior, quota, safety or workflow extension that preserves the main architecture;
- documentation-only repository changes do not require a skill version bump unless they change executable behavior.

## Release checklist

1. Confirm `VERSION` matches the intended release.
2. Confirm README shows the same version.
3. Confirm `CHANGELOG.md` contains the release entry.
4. Confirm every normative reference used by the release is listed in `SKILL.md`.
5. Confirm `references/SOURCE_MAP.md` covers new or changed rules and carries a fresh verification date.
6. Confirm regression tests cover the changed behavior.
7. Run:

   ```bash
   python3 scripts/validate_repo.py
   python3 scripts/package_release.py
   ```

8. Review the diff for secrets, current account screenshots and temporary quota values.
9. Commit to `main` only after validation succeeds.
10. Merge/push the validated release state to `main`, then run the `Publish GitHub release` workflow manually (`workflow_dispatch`). Releases are created only by this deliberate action, never automatically on push.

## Release artifact

For portable skill installation, package the skill directory contents without `.git`, local caches or secrets. Generated ZIP archives should normally remain release artifacts rather than tracked source files.

Normative files must use ASCII filenames so the ZIP survives cross-platform round-trips.

## Local release validation

`python3 scripts/package_release.py` builds `dist/openai-work-codex-regulator-v<VERSION>.zip`, unpacks it into a clean temporary directory and runs the repository validator from the unpacked artifact. A release candidate must pass this round-trip before any GitHub release is created.

## Automated GitHub release

The `Publish GitHub release` workflow runs only on manual `workflow_dispatch` from `refs/heads/main` — a release is a deliberate human action after a validated push, never an automatic reaction to a `main` push; a dispatch from any other ref fails closed. The workflow re-runs repository validation, reads `VERSION`, fails closed if the release or tag `v<version>` already exists, builds the artifact through the single packaging path (`scripts/package_release.py`, which also performs the clean ZIP round-trip), writes a SHA-256 checksum for that validated artifact, extracts the matching changelog section as release notes, and creates the private GitHub Release/tag `v<version>` with the `dist/` ZIP and checksum attached.

An existing release or tag is never deleted, moved or overwritten by the workflow — not even to "repair" it. If publication of a new release fails partway, the workflow stops and a human decides on recovery. A corrected release must use a new skill version unless the maintainer explicitly chooses a different recovery procedure.
