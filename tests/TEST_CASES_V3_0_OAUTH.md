# v3.0 OAuth / OIDC regression cases

These cases extend the contiguous v3.0 suite after the MCP transport checkpoint.

## Test 219 — External OAuth verifier is a resource-server adapter

The repository may verify bearer access tokens but must not become an authorization server, password database, refresh-token issuer or signing-key owner.

Expected: `plugin/oidc_token_verifier.py` implements the MCP `TokenVerifier` boundary only.

## Test 220 — Issuer, audience and JWKS endpoints are server-configured HTTPS URLs

Production OIDC configuration must reject non-HTTPS issuer, audience/resource and JWKS URLs.

Expected: invalid transport configuration fails before serving requests.

## Test 221 — JWT algorithms are explicitly asymmetric

A token header may not choose an arbitrary verification algorithm.

Expected: only an explicit asymmetric allow-list such as RS/PS/ES families is accepted; HS algorithms fail closed before key lookup.

## Test 222 — Signing key lookup requires kid and ignores token-directed key URLs

The backend must not follow attacker-controlled `jku` or `x5u` headers.

Expected: a non-empty bounded `kid` is required and the JWKS URL comes only from trusted server configuration.

## Test 223 — Exact issuer binding

A cryptographically valid token from another issuer is not a valid Plugin principal.

Expected: issuer mismatch returns no `AccessToken`.

## Test 224 — Exact resource/audience binding

A bearer minted for another API cannot be replayed against the quota MCP endpoint.

Expected: audience mismatch returns no `AccessToken`.

## Test 225 — quota:read scope is mandatory

Identity alone does not grant quota access.

Expected: missing required scope returns no `AccessToken` even when signature, issuer and audience are valid.

## Test 226 — Token lifetime is enforced

Expired or not-yet-active bearer tokens cannot become trusted Plugin subjects.

Expected: `exp` and `nbf` are verified with only bounded configured leeway.

## Test 227 — Stable subject is mandatory

MCP identity must not degrade to client id, email, display name or a synthetic anonymous principal.

Expected: missing/blank/oversized `sub` fails closed.

## Test 228 — Verified claims are privacy-minimized

OIDC providers may place email/profile/custom claims in access tokens.

Expected: the MCP `AccessToken` retains only claims needed by the downstream trust boundary; profile/email fields are not propagated.

## Test 229 — JWKS rotation does not use indefinite per-key caching

A retired signing key must not remain accepted forever merely because a process is long lived.

Expected: configured JWK-set cache has a bounded TTL and PyJWT per-key LRU caching is disabled.

## Test 230 — Verification failure does not disclose raw token/provider details

Malformed tokens, network/JWKS failures and signature errors are authentication failures, not model-visible diagnostics.

Expected: verifier returns `None`; raw bearer value and provider exception text are never returned through the MCP tool.
