# v3.0 MCP transport and Plugin packaging regressions

## Test 201 — canonical MCP endpoint is Streamable HTTP
**Input:** deploy the quota transport through the official MCP SDK.  
**Expected:** the model-facing server is mounted at `/mcp` using Streamable HTTP; no localhost bridge or custom browser transport is part of the product contract.

## Test 202 — quota MCP input schema is exactly empty
**Input:** inspect `get_quota_snapshot` as advertised by the transport.  
**Expected:** `inputSchema` is an object with `properties={}` and `additionalProperties=false`.

## Test 203 — raw unexpected model arguments reach the rejection boundary
**Input:** call the MCP tool with `{"subject":"other-user"}`.  
**Expected:** low-level transport passes raw arguments to `QuotaToolHandler`; the call fails as `INVALID_TOOL_ARGUMENTS` instead of silently dropping the field.

## Test 204 — quota tool is read-only and closed-world
**Input:** inspect canonical safety annotations.  
**Expected:** `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=false`.

## Test 205 — MCP endpoint requires quota read scope
**Input:** build the production-shaped MCP app.  
**Expected:** server-wide OAuth requires `quota:read`; the tool cannot be reached through an unauthenticated production endpoint.

## Test 206 — trusted identity comes only from verified bearer context
**Input:** a verified access token has matching issuer/resource/scope and a non-empty subject.  
**Expected:** transport derives the internal authenticated subject from issuer + token subject; model arguments never choose identity.

## Test 207 — bearer token without subject fails closed
**Input:** verified token object has no stable subject.  
**Expected:** quota call fails as MCP authorization invalid; no anonymous/shared subject is invented.

## Test 208 — issuer mismatch fails closed
**Input:** token verifier returns a token whose `iss` does not exactly match configured issuer.  
**Expected:** transport rejects the principal before quota service invocation.

## Test 209 — resource/audience mismatch fails closed
**Input:** token is valid for another resource.  
**Expected:** transport rejects it; a token minted for another MCP server cannot read quota.

## Test 210 — insufficient OAuth scope fails closed
**Input:** bearer token lacks `quota:read`.  
**Expected:** transport refuses the principal even if a custom verifier accidentally returned it as otherwise valid.

## Test 211 — expired or not-yet-valid token fails closed
**Input:** verified token is expired or has a future `nbf`.  
**Expected:** quota handler is not called.

## Test 212 — MCP errors do not leak provider internals
**Input:** quota backend raises an unexpected exception containing provider detail.  
**Expected:** MCP result reports generic `QUOTA_UNAVAILABLE`; raw exception text is absent.

## Test 213 — missing Codex quota authorization is distinct from MCP OAuth
**Input:** MCP bearer identity is valid but subject has no sealed Codex auth state.  
**Expected:** tool returns `QUOTA_AUTH_REQUIRED` / `NEEDS_QUOTA_AUTH`; it does not reinterpret that state as an MCP bearer failure or zero usage.

## Test 214 — official SDK publishes protected-resource metadata
**Input:** build the authenticated Streamable HTTP app with `AuthSettings` and a `TokenVerifier`.  
**Expected:** `/mcp` and `/.well-known/oauth-protected-resource/mcp` are both mounted by the official SDK.

## Test 215 — Python security scheme compatibility is explicit
**Input:** Python MCP SDK 2.1.1 lacks a typed top-level `securitySchemes` field.  
**Expected:** endpoint auth remains server-wide and authoritative; canonical OAuth policy is mirrored in `_meta.securitySchemes` using the OpenAI authenticated-Python compatibility pattern, with no claim that the SDK emitted a typed field.

## Test 216 — MCP SDK dependency is exact-pinned
**Input:** inspect `plugin/requirements-mcp.txt`.  
**Expected:** `mcp==2.1.1` and `mcp-types==2.1.1` are exact pins; ranges such as `>=` are not accepted for the transport gate.

## Test 217 — plugin package has official skill layout
**Input:** inspect `.codex-plugin/plugin.json`.  
**Expected:** stable plugin name/version are present, `skills` points to `./skills/`, and `skills/openai-work-codex-regulator/SKILL.md` is byte-for-byte equal to root `SKILL.md`.

## Test 218 — no fabricated app connection id
**Input:** MCP server has not yet been registered in ChatGPT developer/plugin management.  
**Expected:** `.app.json` is absent and plugin manifest has no `apps` mapping. A `plugin_asdk_app...` identifier is added only after the platform returns a real connection ID.
