# Companion + Chat bridge contract

**Policy version:** v3.0  
**Status:** normative

This reference defines how automatic local Work/Codex telemetry reaches the preferred ChatGPT control plane without requiring the user to copy quota values manually.

## 1. Architectural invariant

ChatGPT is the preferred orchestrator, but ordinary cloud/browser ChatGPT cannot assume access to the user's local shell, local filesystem or `127.0.0.1`.

```text
CHATGPT_PRIMARY_ORCHESTRATOR=YES
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
REMOTE_CHAT_TELEMETRY_PATH=REQUIRED
```

Therefore the normal v3.0 path is:

```text
local quota sensor
  -> Regulator Companion
  -> authenticated HTTPS relay/app
  -> get_quota_snapshot()
  -> ChatGPT regulator control plane
  -> v2.2 quota decision engine
  -> Work / Codex executor
```

A local MCP server or Secure MCP Tunnel may be supported as an optional transport where the product/account supports it, but v3.0 cannot require that path for ordinary users.

## 2. User experience requirement

Normal installation must not require the user to:

- open Terminal;
- install Homebrew;
- install CodexBar separately;
- edit JSON/YAML/config files;
- copy OAuth/API/session tokens;
- configure localhost ports;
- configure an MCP tunnel manually;
- repeatedly open Usage and paste quota percentages into ChatGPT.

```text
ZERO_MAINTENANCE_USER_SETUP=REQUIRED
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
```

The target onboarding is an app-style flow:

```text
install -> connect/sign in -> ready
```

Technical recovery may expose more detail only when automatic repair cannot resolve the problem.

## 3. Companion responsibilities

The local Companion may:

1. discover a bundled or installed supported quota sensor;
2. read current local telemetry;
3. normalize it through the regulator telemetry schema;
4. publish only the sanitized snapshot to the authenticated relay;
5. refresh before/after relevant agentic work and on a bounded background cadence;
6. surface simple connection/health state to the user.

The Companion must not:

- decide Chat/Work/Codex routing;
- calculate quota/pace admission independently;
- purchase credits or trigger resets;
- send prompts/chat history/source code to the relay;
- upload OAuth tokens, cookies or raw auth files;
- treat a provider-specific guard recommendation as regulator policy.

```text
COMPANION_ROLE=SENSOR_TRANSPORT_ONLY
```

## 4. CodexBar reference sensor

CodexBar is the first reference sensor because it already exposes structured Work/Codex usage from the local account state.

The v3.0 product must not require users to install or configure CodexBar manually. Acceptable implementations include:

- shipping a compatible helper inside the Companion bundle;
- using an already installed CodexBar helper when present;
- replacing it later with another verified local provider behind the same normalized schema.

The skill depends on the telemetry contract, not on a CodexBar executable name.

```text
SENSOR_IMPLEMENTATION=PLUGGABLE
CODEXBAR_USER_PREREQUISITE=NO
```

When CodexBar is used, prefer its explicit read-only Codex OAuth usage mode. Raw OAuth credentials remain local.

## 5. Companion -> relay payload

Only the normalized quota envelope may cross the local/remote boundary:

```json
{
  "schema_version": 1,
  "snapshot": {
    "schema_version": 1,
    "allowance_domain": "WORK_CODEX",
    "source": "CODEXBAR_OAUTH",
    "sensor": "CODEXBAR",
    "snapshot_at": "...",
    "freshness": "FRESH",
    "age_seconds": 0,
    "weekly_meter_semantics": "USED",
    "weekly_used": 42,
    "weekly_reset": "...",
    "five_hour_used": 18,
    "five_hour_reset": "...",
    "other_windows": []
  }
}
```

Forbidden payload classes include:

```text
OAuth/access/refresh tokens
browser cookies/session cookies
passwords
raw auth files
prompt/chat history
source files
customer data
unneeded account identity/PII
```

## 6. Relay security boundary

The remote relay is a transport/cache, not an orchestrator.

```text
RELAY_ROLE=READ_ONLY_TELEMETRY_CACHE
```

Required properties:

- HTTPS for production transport;
- separate device-write and Chat-reader credentials;
- credentials stored only as hashes or delegated to a production identity provider;
- bounded snapshot size;
- latest-snapshot replacement rather than indefinite raw history by default;
- no OpenAI OAuth credentials stored at the relay;
- no credit/reset/spending mutation endpoints in the quota telemetry surface;
- freshness recomputed server-side when the snapshot is read.

Production identity/auth may be implemented by the ChatGPT app platform or another audited identity layer. The model must never receive raw relay credentials.

## 7. ChatGPT tool contract

The canonical tool is:

```text
get_quota_snapshot()
```

It intentionally takes no model-provided installation id, token, email or account identifier.

The connected app/server resolves the authenticated installation server-side and returns only the latest sanitized snapshot.

Reference machine-readable schema:

```text
relay/get_quota_snapshot.tool.json
```

The tool is read-only. It must not expose provider pacing/guard policy, purchase actions or reset actions.

## 8. Refresh lifecycle

For ChatGPT-first orchestration:

```text
before quota-sensitive Work/Codex admission
  -> get_quota_snapshot()

after meaningful Work/Codex completion
  -> refresh telemetry when available

if prior aggregate burn may still be pending
  -> refresh before another large future advance
```

Background collection exists to keep Chat reads fresh, but the skill does not require an API call on every ordinary conversational turn.

## 9. Failure behavior

Normal automatic path:

```text
FRESH snapshot -> use it
STALE snapshot -> request/trigger refresh before large quota-sensitive launch
NO_SNAPSHOT / NOT_CONNECTED -> preserve useful Chat work; repair automatic telemetry
AUTO path unavailable and quota-sensitive decision blocked -> manual first-party snapshot may be requested as fallback
```

The user must not become the normal transport between Usage UI and ChatGPT.

## 10. Standalone modes

Direct Codex/Work use remains supported.

```text
ORCHESTRATION_MODE=CHATGPT_PRIMARY   -> remote Chat-readable tool is normal path
ORCHESTRATION_MODE=CODEX_STANDALONE -> local provider may be read directly
ORCHESTRATION_MODE=WORK_STANDALONE  -> connected remote provider may be read directly
```

The normalized quota schema and v2.2 decision engine remain the same in every mode.

## 11. Reference implementation

Current executable reference components:

```text
scripts/quota_telemetry.py         provider payload normalization
companion/quota_companion.py       local sensor + sanitized publish boundary
relay/quota_relay.py               remote cache/auth boundary
relay/get_quota_snapshot.tool.json Chat-facing read-only tool schema
scripts/weekly_quota_controller.py quota/pace decision engine
```

These components are reference implementation and validation targets. Release-ready v3.0 additionally requires a novice-friendly packaged Companion and deployed/authenticated Chat-accessible app path; source code alone does not satisfy the zero-friction acceptance criterion.
