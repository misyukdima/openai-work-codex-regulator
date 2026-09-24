# Changelog

## 4.0 — 2026-09-24

- Reframed the skill around ChatGPT as primary orchestrator and Work/Codex as execution planes.
- Added GPT-6 Astra/Sol/Luna quality-first adaptive routing.
- Separated capability escalation from reasoning-depth escalation.
- Added user-configurable active working hours; default 09:00–23:00 local with 22:00 as normal soft end.
- Replaced wall-clock quota pacing with active-working-minute weekly runway.
- Removed any static assumption that Plus must expose a five-hour window: secondary windows are enforced only when the normalized current-account snapshot reports them.
- Preserved the non-negotiable quality floor: quota pressure may choose only among independently sufficient candidates.
- Added machine-readable model capability snapshot and deterministic routing fixtures.
- Added generation-neutral v4 release validation and ZIP round-trip validation.
- Carried forward the v3 development line's read-only quota telemetry, subject-isolated auth, production provider and crypto-helper hardening.

v3.1 was cancelled and never published. v2.2 was the last previously published stable release.
