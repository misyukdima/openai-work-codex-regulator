# Changelog

## 3.0 — in development

Major ChatGPT Web orchestration release with automatic Work/Codex quota telemetry.

### Runtime and product boundary

- Fixed the v3.0 runtime to **ChatGPT Web only**. Work and Codex are execution surfaces that receive self-contained handoffs; neither executor needs the regulator skill installed.
- Made automatic Work/Codex quota telemetry the normal control-plane path with `AUTO_QUOTA_TELEMETRY=DEFAULT`; manual snapshots remain fallback only.
- Defined the end-user onboarding target as `GitHub Release ZIP → attach in ChatGPT Web → work` with no Companion, CodexBar, Terminal, Homebrew, localhost, tunnel or OS-specific setup.
- Added just-in-time Plugin/App connection: ChatGPT asks for Connect/Auth only when a quota-sensitive decision first needs `get_quota_snapshot()`.

### Server-side quota proof and backend

- Proved the server-side Plus quota path in P0 on 2026-09-07. An ephemeral remote runner used the pinned official OpenAI Codex CLI, completed managed ChatGPT authorization, waited for authenticated `account/updated`, called `account/rateLimits/read`, received an exact Plus `codex` quota snapshot and deleted temporary auth state.
- Confirmed missing-window semantics: weekly telemetry may exist without a 5-hour window. Missing values stay `UNAVAILABLE/null`; v3 never fabricates `0%`.
- Added `plugin/quota_backend.py` with the proven auth-readiness boundary, `codex` bucket selection, duration-based window normalization and secret-field exclusion.
- Added exact zero-argument `plugin/get_quota_snapshot.tool.json`; model input cannot select a subject, account, workspace or credential.

### Credential isolation and recovery

- Added HMAC-based subject isolation and trusted `PluginRequestContext`; raw Plugin identity does not become a path and cross-subject auth reuse fails closed.
- Added `plugin/sealed_auth_store.py`: durable auth is a sealed `auth.json` blob, plaintext exists only in a private temporary `CODEX_HOME`, refreshed state is resealed after successful operations and plaintext is removed afterward.
- Kept production cryptography outside the repository. `plugin/production_vault.py` requires an injected durable provider, external KMS/envelope provider and cross-worker lease provider; repository test doubles remain `production_safe=False`.
- Added `plugin/authorization_coordinator.py` for JIT quota-account authorization, subject-bound pending flows, cancel/revoke ordering and scoped cleanup.
- Added `plugin/auth_concurrency.py` to serialize authorize/read/revoke per opaque subject and prevent lost refresh-state updates.
- Added `plugin/auth_recovery.py`: bounded transient retry, `NEEDS_REAUTH` for corrupt/missing/rejected auth, no partial reseal after abnormal materialization exit and no raw provider errors in model-visible quota output.

### Official MCP transport and Plugin package

- Added Streamable HTTP MCP transport in `plugin/mcp_transport.py` on the official Python MCP SDK.
- The transport uses the low-level `Server`, mounts `/mcp`, requires OAuth scope `quota:read`, validates the verified bearer principal and preserves raw tool arguments until the security boundary rejects unexpected input.
- Changed the quota tool to a closed-world contract: `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=false`.
- Exact MCP runtime pins are `mcp==2.1.1` and `mcp-types==2.1.1`; GitHub Actions installs those versions and runs the real transport self-test.
- Added OpenAI-compatible Python auth metadata handling: OAuth is authoritative server-wide and the canonical `securitySchemes` policy is mirrored in `_meta.securitySchemes` while the SDK lacks a typed top-level field.
- Added `.codex-plugin/plugin.json` plus `skills/openai-work-codex-regulator/SKILL.md`; packaged skill content must remain byte-for-byte equal to root `SKILL.md`.
- Deliberately omitted `.app.json` until ChatGPT returns a real registered connection id beginning `plugin_asdk_app...`.

### OIDC/JWKS verification

- Added `plugin/oidc_token_verifier.py`, a production-shaped OAuth resource-server adapter.
- Enforced exact HTTPS issuer/resource/JWKS configuration, explicit asymmetric algorithms, mandatory `kid`, no token-directed `jku`/`x5u`, required `quota:read`, `exp/nbf/iss/aud` validation, stable `sub`, privacy-minimized downstream claims and bounded JWKS caching.
- Exact direct dependency is `PyJWT[crypto]==2.13.0`.
- Verification fails closed; the repository does not become an authorization server, password database, token issuer or signing-key owner.

### IdP deployment preflight

- Added `plugin/idp_preflight.py` to validate OAuth/OIDC discovery metadata before production MCP startup.
- Preflight requires exact HTTPS issuer, HTTPS authorization/token/JWKS endpoints, PKCE `S256`, advertised `quota:read`, and a valid client registration mode: CIMD, DCR or explicitly reviewed predefined client.
- Added `plugin/production_runtime.py` to compose metadata preflight → `OIDCJWKSTokenVerifier` → MCP transport from provider-neutral `REGULATOR_OIDC_*` configuration.
- Chose Auth0 as the first staging target without making Auth0 a core dependency.
- Added `deployment/auth0-staging.example.json`, a secret-free maintainer profile. Validator checks actual JSON key names for secret fields instead of false-positive substring matching in documentation values.
- Added `docs/IDP_DEPLOYMENT.md` with the manual staging sequence and explicit live evidence gates.
- Static preflight intentionally does **not** claim success for resource→audience binding, exact ChatGPT redirect allowlisting, authorized public `/mcp` access or wrong-resource rejection. Those remain live E2E gates.

### Validation and regression coverage

- Added `scripts/validate_plugin_package.py` and strict `scripts/validate_v3_release_contract.py`; release ZIP validation runs the dependency-free contracts both before packaging and after clean extraction.
- Fixed regression validation so shard filenames do not control global numbering.
- Expanded the feature branch to **240 contiguous regression scenarios**, including Web-only runtime, P0 normalization, subject isolation, sealed auth, JIT authorization, concurrency, recovery, MCP identity, OIDC verification and IdP deployment preflight.
- Added dedicated CI gates for repository/package/release validation, quota backend, sealed auth, authorization coordinator, concurrency, recovery, production vault, pinned MCP runtime, OIDC verifier, IdP discovery preflight and production runtime composition.
- Early CodexBar/Companion/relay work remains research history only and is not a release prerequisite.

### Controller continuity

- Preserved the v2.2 epoch-anchored trajectory, observed-burn estimator, equal quota/pace priority, hard quality floor, independent 5h breaker and bounded future advance as the mathematical decision engine.

> Development gate: server-side Plus quota acquisition, credential lifecycle, concurrency/recovery, official MCP transport, OIDC resource-server verification, Plugin package structure and static IdP deployment preflight are implemented and regression-tested. v3.0 remains development-only until a real Auth0 development tenant and public HTTPS MCP staging deployment pass live OAuth/resource/redirect checks, ChatGPT returns a real `plugin_asdk_app...` connection id and Connect/Auth E2E succeeds, production KMS and cross-worker lease providers are deployed, refresh/revoke/logout and crash recovery are verified on that infrastructure, and security review is complete before Pull Request to `main`.

## 2.2 — 2026-09-06

Balanced quota-and-workflow orchestration release based on real v2.1 field testing.

- Replaced the fixed 24h slice as a hard admission boundary with one epoch-anchored cumulative quota trajectory.
- Kept 24h as normal look-ahead while adding bounded future advance up to 72h of the same trajectory.
- Added equal-priority quota/pace balancing after hard safety and quality gates.
- Added `LAUNCH_WITH_ADVANCE`, progress-preserving fallback paths and `MEANINGFUL_PROGRESS_WITHOUT_AGENTIC`.
- Split ChatGPT control plane from downstream Work/Codex execution plane; handoffs are self-contained and executors do not need the regulator skill.
- Retained the hard quality floor, independent 5h circuit breaker, paid-reset authorization gates, robust observed-burn estimator and aggregate shared-pool accounting.
- Added tests 96–115 and validator coverage for executor independence, bounded advance, quality/5h protection, pending telemetry and productive alternatives.

## 2.1 — 2026-09-05

Adaptive weekly quota controller release.

- Added `references/10_WEEKLY_QUOTA_CONTROLLER.md`, quota epochs, rolling pacing, dynamic reserve release and the quality floor.
- Added conservative pass-burn estimation, aggregate continuity accounting, 5h circuit-breaker handling, `PENDING_BURN`, scheduled-work reservations and continuity feasibility checks.
- Added paid weekly reset policy and executable controller reference `scripts/weekly_quota_controller.py`.
- Added tests 76–95 and corresponding validator gates.

## 2.0 — 2026-09-05

Major Astra architecture release.

- Added `MODEL_PROFILE=ASTRA`, Astra justification/scope gates, allowance-domain separation and steering transaction semantics.
- Added safety-pause recovery, cyber-sensitive authorization posture, long-context discipline and dedicated Astra execution reference.
- Added tests 61–75 and v2.0 source/validator updates.

## 1.2 — 2026-08-22

Model-tier routing release.

- Added durable Luna / Terra / Sol capability roles, effort selection, fallback rules and mixed-tier policy.
- Added tests 51–60.

## 1.1 — 2026-08-22

Quota-saving routing and security hardening release.

- Added bounded Chat routing, safety/account/download gates, shared-pool attribution, paid-credit eligibility, capability snapshots and scheduled-task hardening.
- Added tests 37–50.

## 1.0 — 2026-08-21

Initial release.

- Added Chat / Work / Codex routing, shared agentic pool, quota snapshot, project runway, execution discipline, risk classes and failure recovery.
