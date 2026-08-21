# Changelog

## 1.1 — 2026-08-22

Quota-saving routing, security and release-hardening release. Architecture of v1.0 preserved.

- Added bounded Chat policy (`CHAT_BOUNDED_WEB`) so simple lookups, attached-file summaries and simple artifacts from supplied content stay in CHAT instead of burning an agentic pass.
- Added `WHY_AGENTIC` / `VALUE_OUTPUT` gate before expensive agentic passes, and `USER_SURFACE_OVERRIDE=YES` for explicit user insistence after one quota-saving warning.
- Added untrusted-content / prompt-injection doctrine for Work/browser/connected apps (third-party content is data, not instructions).
- Added account/browser identity checks before external browser actions.
- Added download ≠ execution safety rule for scripts/executables/installers/macros/unknown archives.
- Generalized burn attribution: `OTHER_SHARED_POOL_ACTIVITY` + `ATTRIBUTION=CLEAN|MIXED|UNKNOWN`; external tools (Kimi, Skyvern) do not contaminate OpenAI attribution.
- Split paid-credit authorization from feature eligibility: `CREDIT_ELIGIBILITY_WORK` / `CREDIT_ELIGIBILITY_CODEX`; UNKNOWN eligibility → PREPARE + first-party UI check.
- Added optional capability/permission snapshot (`WORK_CLOUD`, `WORK_LOCAL`, `CODEX_LOCAL`, `BROWSER_ACCESS`, `NETWORK_ACCESS`, connected-app permission).
- Added quota snapshot freshness policy per class (no ritual snapshot for class 0–1 and bounded low-burn class 2).
- Hardened Scheduled Tasks: measured manual burn, frequency tied to signal change rate, weekly/monthly burn estimate, stop/disable after 2–3 identical scheduled failures.
- Added context budget discipline (compact handoff, no re-reading unchanged documents, no cross-surface repeated research).
- Added regression tests 37–50; validator now enforces contiguous numbering and >= 50 tests.
- Validator v1.1: README/CHANGELOG version sync, v1.1 invariants, SOURCE_MAP verification date, required first-party sources, stale model-name scan, extended secret scan, ASCII filename check.
- Added `scripts/package_release.py` with clean ZIP round-trip validation.
- Added GitHub scaffolding: `.gitattributes`, CODEOWNERS, issue/PR templates, validate/release workflows, CONTRIBUTING.md, docs/RELEASE_PROCESS.md.
- Re-verified first-party OpenAI sources (2026-08-22), added the official built-in browser safety article to SOURCE_MAP.
- Hardened release pipeline before first publication: manual `workflow_dispatch` trigger instead of automatic release on push; fail-closed when the release or tag for the current VERSION already exists (no delete/re-tag/overwrite); releases may only be published from `refs/heads/main`; single packaging path — the workflow uses `scripts/package_release.py` and publishes its validated `dist/` artifact instead of a duplicate `git archive`.

## 1.0 — 2026-08-21

Initial release.

- Added Chat / Work / Codex surface routing.
- Added shared agentic pool / credit architecture.
- Added first-party quota snapshot and paid-credit policy.
- Added project runway and observed-burn discipline.
- Added Work browser/action and Scheduled Task rules.
- Added Codex repository/server/Git discipline.
- Added class 0–4 risk model.
- Added Fast/Ultra/model escalation controls.
- Added failure, anti-bot, duplicate-pass and result-verification rules.
- Added official OpenAI source map and regression tests.
