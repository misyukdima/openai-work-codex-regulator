# v3.0 IdP / deployment regressions

## Test 231 — exact authorization-server issuer
Given configured issuer `I`, discovered metadata must report the exact same `issuer`. A different issuer fails the preflight.

## Test 232 — PKCE S256 is mandatory
The authorization-server metadata must advertise `S256` in `code_challenge_methods_supported`. `plain` alone is insufficient.

## Test 233 — quota scope must be advertised
The authorization-server metadata must advertise `quota:read`. Missing scope support fails before deployment.

## Test 234 — CIMD capability must be explicit
When `client_registration_mode=cimd`, metadata must advertise `client_id_metadata_document_supported=true` and a compatible token-endpoint authentication method.

## Test 235 — DCR requires a secure registration endpoint
When `client_registration_mode=dcr`, metadata must include an absolute HTTPS `registration_endpoint`.

## Test 236 — predefined clients require review
`client_registration_mode=predefined` is accepted only after an explicit reviewed deployment decision. The repository cannot silently assume or invent a predefined client.

## Test 237 — RFC 9207 issuer identification is a deployment gate
When stable issuer identification is required, metadata must advertise `authorization_response_iss_parameter_supported=true`. Advertising the flag does not replace the live redirect/auth-response E2E test.

## Test 238 — MCP resource-server runtime rejects OAuth client secrets
`REGULATOR_OIDC_CLIENT_SECRET` and `REGULATOR_OAUTH_CLIENT_SECRET` are invalid in the MCP resource-server runtime. Authorization-server credentials remain outside this process and outside the repository.

## Test 239 — static discovery does not claim live resource binding
A successful metadata preflight still reports live E2E gates for `resource` propagation, access-token audience binding, exact ChatGPT redirect allow-listing and the real Connect/token exchange.

## Test 240 — app binding requires a real ChatGPT connection id
`.app.json` remains absent until ChatGPT registers the MCP connection and returns a genuine technical id beginning `plugin_asdk_app...`. Placeholder ids fail the release contract.
