# Official source map

**Skill release:** 3.0  
**Verified:** 2026-09-07

Time-sensitive product facts must be checked against current first-party OpenAI documentation, official OpenAI source code or actual account/workspace behavior. Controller mathematics and regulator policy are internal project rules, not OpenAI limits.

## ChatGPT / Work / Codex roles

Sources:

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

v3.0 product rule:

- the regulator skill runs only in ChatGPT Web;
- ChatGPT owns routing and admission;
- Work and Codex are execution surfaces and receive self-contained handoffs;
- executor skill installation is not required.

The Web-only runtime boundary is an internal product decision, not a claim that OpenAI forbids other uses of files or skills elsewhere.

## Shared Work/Codex allowance

Sources:

- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/12642688

Operational consequences:

- `ALLOWANCE_DOMAIN=WORK_CODEX` when current first-party state confirms the shared pool;
- Work↔Codex is not treated as a quota bypass;
- burn depends on task/model/context/tooling and is not derived from a universal token coefficient;
- aggregate meter state remains the continuity source.

## Usage reporting

Source:

- https://help.openai.com/en/articles/20001478-reviewing-work-and-codex-usage-and-using-personal-analytics-in-chatgpt-desktop

Operational consequences:

- use fresh first-party/authorized meter state when available;
- reporting can lag, so unchanged immediate post-pass telemetry may remain `PENDING_BURN=YES`;
- safe Chat progress is not blocked solely by pending aggregate reporting.

## ChatGPT Plugins / connected apps

Sources:

- https://help.openai.com/en/articles/20001256
- https://help.openai.com/en/articles/11487775-connectors-in-chatgpt
- https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt-beta

Operational consequences for v3.0:

- ChatGPT must not be designed around direct access to the user's localhost or local shell;
- Plugin/App availability, connection and authorization are plan/workspace/platform dependent;
- the regulator does not bypass Connect/Auth;
- developer testing availability can differ from public installed-app availability.

Normative Plugin contract: `references/13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md`.

## Official Plugin packaging and MCP transport

Sources:

- https://developers.openai.com/plugins/build/mcp-server
- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/build/plugins
- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/openai/openai-apps-sdk-examples

Verified implementation facts on 2026-09-07:

- Plugin MCP servers use Streamable HTTP, conventionally at `/mcp`;
- user-specific MCP data is protected with OAuth and resource-server verification;
- the official MCP Python SDK can mount the bearer gate and RFC 9728 protected-resource metadata from `AuthSettings` + `TokenVerifier`;
- `get_access_token()` exposes verified HTTP access-token context inside a tool handler;
- the quota tool is closed-world and read-only: `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=false`;
- production quota scope is `quota:read`;
- Python MCP SDK `v2.1.1` does not provide a typed top-level `securitySchemes` field on its Tool model. OpenAI's authenticated Python example mirrors the policy in `_meta.securitySchemes`; endpoint authorization remains authoritative;
- a model-visible zero-argument tool must preserve raw arguments until the regulator rejection boundary, so v3 uses the low-level MCP `Server`;
- Plugin packages use `.codex-plugin/plugin.json` and bundled skills under `skills/<skill-name>/SKILL.md`;
- `.app.json` is added only after ChatGPT registers the MCP connection and returns a real technical ID beginning `plugin_asdk_app...`.

Pinned transport dependencies:

```text
mcp==2.1.1
mcp-types==2.1.1
```

Implementation references:

- `plugin/mcp_transport.py`
- `plugin/get_quota_snapshot.tool.json`
- `plugin/requirements-mcp.txt`
- `.codex-plugin/plugin.json`
- `scripts/validate_plugin_package.py`

## OAuth / IdP requirements for ChatGPT MCP

Primary source:

- https://developers.openai.com/plugins/build/auth

Verified on 2026-09-07:

- ChatGPT acts as the OAuth client for the MCP resource server;
- the MCP resource server must publish protected-resource metadata;
- the authorization server must publish OAuth/OIDC discovery metadata;
- ChatGPT sends the MCP resource as the OAuth `resource` parameter;
- that resource must be carried through authorization and token exchange and normally bound into the access-token audience;
- authorization-code flow uses PKCE and requires `S256` in metadata;
- ChatGPT supports CIMD, DCR and predefined clients; CIMD is the preferred registration method when supported and selected;
- the exact production redirect URI comes from the ChatGPT app management page and must be allow-listed by the authorization server;
- after OAuth, the MCP server remains responsible for token signature, issuer, audience, expiry and scope validation on each request;
- OpenAI recommends an established identity provider instead of implementing authentication from scratch;
- OpenAI's current provider guidance explicitly includes Auth0 and describes its MCP support for metadata discovery, CIMD registration, API security and token exchange.

These facts support the staging direction:

```text
FIRST_STAGING_IDP=AUTH0
CORE_IDP_DEPENDENCY=NONE
```

Auth0 is the first tested deployment target, not a hard dependency of the regulator core.

Implementation references:

- `plugin/oidc_token_verifier.py`
- `plugin/idp_preflight.py`
- `plugin/production_runtime.py`
- `deployment/auth0-staging.example.json`
- `docs/IDP_DEPLOYMENT.md`
- `tests/TEST_CASES_V3_0_OAUTH.md`
- `tests/TEST_CASES_V3_0_IDP.md`

Static preflight proves metadata/configuration compatibility only. It does **not** prove these live properties:

```text
resource_parameter_echoed_and_bound_to_access_token_audience
exact_chatgpt_redirect_uri_allowlisted
authorized_token_accepted_by_public_mcp
wrong_resource_token_rejected_by_public_mcp
```

Those remain mandatory E2E gates.

## Registered ChatGPT connection

Source:

- https://developers.openai.com/plugins/build/plugins

Verified on 2026-09-07:

- developer-mode registration requires the actual MCP server URL and connection details;
- after ChatGPT creates the connection, its technical ID starts with `plugin_asdk_app`;
- `.app.json` should map to that real ID;
- `.codex-plugin/plugin.json` then references the app mapping;
- the repository must not invent a placeholder app ID before registration.

## OIDC/JWKS verifier

Implementation: `plugin/oidc_token_verifier.py`.

Internal production contract:

```text
HTTPS issuer only
HTTPS audience/resource only
HTTPS JWKS only
explicit asymmetric algorithms only
kid required
jku/x5u not followed
quota:read required
exp/nbf/iss/aud/signature verified
stable sub required
privacy-minimized claims
bounded JWKS caching
fail closed
```

Pinned dependency:

```text
PyJWT[crypto]==2.13.0
```

The repository verifies resource-server bearer tokens; it does not become an OAuth authorization server or signing-key owner.

## Official Codex app-server quota path

Primary implementation evidence:

- https://github.com/openai/codex
- https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md
- https://github.com/openai/codex/blob/main/codex-rs/app-server/src/request_processors/account_processor.rs
- https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/src/protocol/common.rs

Relevant official app-server operations include managed ChatGPT login/account state and `account/rateLimits/read`.

Important sequencing confirmed from official source:

```text
account/login/completed
  ↓
auth manager reload
  ↓
account/updated
```

Therefore v3 backend waits for authenticated `account/updated` before reading rate limits.

Reference implementation: `plugin/quota_backend.py`.

## P0 server-side Plus proof

Internal reproducible evidence:

- `.github/workflows/p0-headless-quota-probe.yml`
- `experiments/p0_headless_quota_probe.py`
- successful feature-branch run on 2026-09-07 after auth-readiness fix

P0 established that an ephemeral remote backend can:

- launch pinned official Codex;
- complete managed ChatGPT authorization for a Plus account;
- call `account/rateLimits/read` after account readiness;
- receive a `codex` rate-limit snapshot with actual usage/reset fields;
- emit only sanitized proof;
- delete temporary auth state afterward.

```text
P0_SERVER_SIDE_PLUS_QUOTA=PROVEN
```

P0 proves acquisition feasibility only. Persistent credentials, cross-user isolation, refresh/revoke and ChatGPT Web Plugin E2E remain separate release gates.

## Window semantics

Internal normalization policy:

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

P0 confirmed that an exact response can omit a 5h window while returning weekly quota. Missing fields remain unavailable; the regulator does not manufacture 0% usage.

Reference parsers:

- `scripts/quota_telemetry.py`
- `plugin/quota_backend.py`

## v3.0 autonomous quota telemetry

Normative source: `references/12_AUTONOMOUS_QUOTA_TELEMETRY.md`.

```text
SKILL_RUNTIME=CHATGPT_WEB_ONLY
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
USER_SETUP_AFTER_ZIP=NONE
PLUGIN_AUTH=JUST_IN_TIME
LOCAL_SOFTWARE_REQUIRED=NO
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN
```

The Plugin is a read-only fact provider. Routing, model selection, quota/pace balancing and admission remain in ChatGPT.

## Plugin/backend security boundary

Normative source: `references/13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md`.

```text
QUOTA_PLUGIN=READ_ONLY
PLUGIN_DECISION_AUTHORITY=NONE
SUBJECT_ACCOUNT_BINDING_AUDITED=YES
CROSS_SUBJECT_READ=FORBIDDEN
SILENT_ACCOUNT_SWITCH=FORBIDDEN
```

Production release additionally requires audited credential isolation, encryption at rest, token refresh/revocation/logout behavior, cross-worker serialization and live IdP/MCP E2E. The model-facing `get_quota_snapshot()` accepts no model-provided identity or secret arguments.

## Paid weekly reset

Source:

- https://help.openai.com/en/articles/20001507-paid-weekly-work-and-codex-rate-limit-resets

Operational consequences:

- `PAID_WEEKLY_RESET_ALLOWED=NO` by default;
- purchase/reset is a separate class-4 money action;
- applying a reset creates a new quota epoch;
- quota Plugin has no purchase/reset tool.

## Chat allowance separation

Sources:

- https://help.openai.com/en/articles/20001354-gpt-56-and-gpt-6-pro-in-chatgpt
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

Operational consequence:

- Chat-model allowance is not treated as spare Work/Codex allowance;
- `ALLOWANCE_DOMAIN=WORK_CODEX|CHAT_PRO|API|UNKNOWN` stays explicit.

## v2.2 controller retained in v3.0

Normative source: `references/10_WEEKLY_QUOTA_CONTROLLER.md`.

```text
BASE_WEEKLY_RESERVE_PP = 10
RESERVE_FRACTION_CAP = 0.50
RESERVE_RELEASE_HOURS = 72
BASE_LOOKAHEAD_HOURS = 24
MAX_ADVANCE_HOURS = 72
BALANCED_PRIORITY=QUOTA_50_PACE_50
```

Internal policy:

- one absolute epoch-anchored cumulative trajectory;
- 24h is normal look-ahead, not a hard sleep timer;
- future advance is bounded to 72h of the same anchored trajectory;
- quota risk of launch is compared with pace risk of deferral after hard gates;
- quality, safety and confirmed 5h constraints remain above balancing.

These constants are regulator policy, not OpenAI product limits.

## Self-contained handoff

Normative source: `references/11_ORCHESTRATION_AND_HANDOFF.md` as retained v2.2 execution-packet design, overridden by the v3 runtime owner where necessary.

v3.0 binding:

```text
CONTROL_PLANE_OWNER=CHAT
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

Work/Codex receives goal, fact pack, scope, tests/evidence, rollback and stop conditions. Plugin credentials and internal quota math are not copied into executor prompts.

## Internal policy summary

Internal regulator policies include class 0–4, `ONE_GATE = ONE_PRIMARY_SURFACE`, ChatGPT Web-only control plane, automatic read-only quota Plugin with manual fallback, duration-based window semantics, pending-burn handling, equal quota/pace priority, anchored weekly trajectory, bounded future advance, robust burn estimation, quality floor, self-contained executor handoff, no downstream skill dependency, paid spend disabled by default, exact Git staging and explicit release/security gates.
