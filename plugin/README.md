# Regulator Quota Plugin backend

Server-side read-only часть v3.0 для ChatGPT Web. Model-facing surface намеренно минимален:

```text
get_quota_snapshot()
```

Skill остаётся control plane. Plugin не выбирает Work/Codex, не меняет model/effort, не рассчитывает admission и не выполняет платные действия.

## Что уже доказано

P0 от 7 сентября 2026 года прошёл на реальном аккаунте ChatGPT Plus. Одноразовый remote runner запустил официальный `codex app-server`, выполнил managed ChatGPT authorization, дождался authenticated `account/updated`, вызвал `account/rateLimits/read`, получил фактический `codex` quota snapshot и удалил временный auth state.

```text
P0_SERVER_SIDE_PLUS_QUOTA=PROVEN
```

Отдельно в CI проходят:

- exact-pinned MCP transport на `mcp==2.1.1` / `mcp-types==2.1.1`;
- OIDC/JWKS resource-server verifier на `PyJWT[crypto]==2.13.0`;
- IdP discovery preflight;
- production runtime composition;
- strict v3 release contract на **240** последовательных regression scenarios.

Эти проверки доказывают backend/transport/configuration contract. Они не заменяют реальный OAuth tenant, публичный HTTPS deployment и ChatGPT Connect/Auth E2E.

## Model-facing MCP boundary

### `mcp_transport.py`

Официальный low-level MCP `Server` выбран намеренно. Для `get_quota_snapshot()` неожиданные model arguments нельзя тихо отбросить до security boundary.

```text
POST /mcp
  ↓
OAuth bearer gate
  ↓
verified AccessToken
  ↓
issuer + audience/resource + quota:read + exp/nbf + subject
  ↓
trusted Plugin subject
  ↓
QuotaToolHandler.call(..., raw_arguments)
```

Canonical tool annotations:

```text
readOnlyHint=true
destructiveHint=false
idempotentHint=true
openWorldHint=false
```

OAuth scope:

```text
quota:read
```

Python MCP SDK `v2.1.1` не имеет typed top-level `securitySchemes` field в Tool model. Endpoint защищён OAuth целиком; canonical policy дополнительно зеркалируется в `_meta.securitySchemes` по authenticated-Python pattern OpenAI.

### `get_quota_snapshot.tool.json`

Machine-readable contract:

- input строго `{}`;
- `additionalProperties=false`;
- output по allow-list schema;
- OAuth `quota:read`;
- closed-world read-only annotations.

MCP OAuth и Codex quota authorization — разные границы. Валидный bearer token идентифицирует caller нашего MCP resource server, но не является Codex quota credential. Если MCP identity валидна, а Codex auth ещё нет, transport возвращает:

```text
QUOTA_AUTH_REQUIRED
NEEDS_QUOTA_AUTH
```

## OAuth resource-server verification

### `oidc_token_verifier.py`

Production-shaped `TokenVerifier` проверяет:

- exact HTTPS issuer;
- exact MCP resource/audience;
- required `quota:read` scope;
- signature, `exp`, `nbf`, issuer и audience;
- explicit asymmetric algorithm allow-list;
- обязательный bounded `kid`;
- отсутствие token-directed `jku`/`x5u` key lookup;
- bounded JWK-set cache;
- обязательный стабильный `sub`;
- privacy-minimized downstream claims.

Репозиторий не реализует authorization server, user/password database, signing keys или refresh-token issuer.

## IdP deployment boundary

### `idp_preflight.py`

До старта production MCP preflight получает OAuth/OIDC metadata и fail-closed проверяет:

```text
issuer exact + HTTPS
authorization endpoint HTTPS
token endpoint HTTPS
JWKS HTTPS
PKCE S256
quota:read advertised
CIMD | DCR | reviewed predefined client
```

Preflight не делает недоказанных выводов о runtime behavior. Четыре свойства остаются только live gates:

```text
resource parameter echoed and bound to access-token audience
exact ChatGPT redirect URI allow-listed
authorized token accepted by public /mcp
wrong-resource token rejected by public /mcp
```

### `production_runtime.py`

Runtime composition связывает:

```text
REGULATOR_OIDC_* configuration
        ↓
IdP metadata preflight
        ↓
OIDCJWKSTokenVerifier
        ↓
MCPTransportConfig
        ↓
public Streamable HTTP app
```

Если metadata не проходит preflight, MCP app не строится.

Первая staging-цель — Auth0. Это deployment choice, а не зависимость core: runtime остаётся provider-neutral.

Безопасный шаблон: `deployment/auth0-staging.example.json`.

Maintainer flow: `docs/IDP_DEPLOYMENT.md`.

## Credential lifecycle

### `quota_backend.py`

- минимальный JSON-RPC client для official `codex app-server`;
- managed ChatGPT auth primitive для development/P0;
- readiness boundary `login/completed → account/updated → rateLimits/read`;
- выбор `codex` bucket;
- duration-based window normalization;
- missing-window semantics;
- secret-field exclusion.

### `subject_store.py`

Raw Plugin identity не используется как path. Внутренний key выводится через HMAC-SHA256 с server-held pepper.

Development store помечен `production_safe=False`.

### `sealed_auth_store.py`

```text
opaque subject key
  ↓
sealed auth.json blob at rest
  ↓
private temporary CODEX_HOME
  ↓
official Codex read / refresh
  ↓
validate + reseal updated auth.json
  ↓
guaranteed plaintext cleanup
```

`SealedBlobStore` и `EnvelopeCipher` являются injected adapters. Репозиторный test cipher не считается production cryptography.

### `authorization_coordinator.py`

Отдельный trusted quota-account Connect/Auth state machine:

```text
begin
  ↓
STARTING
  ↓
WAITING_USER
  ↓
AUTHORIZED | CANCELLED | EXPIRED | FAILED
```

Coordinator переиспользует один pending flow для одного subject, subject-binds authorization id, закрывает live client на cancel и не допускает последующего восстановления credentials после revoke.

### `auth_concurrency.py`

Сериализует authorization, quota read и revoke по одному opaque subject key и защищает managed refresh state от lost-update race.

In-process provider подходит только для CI/single-worker. Production требует audited cross-worker lease provider.

### `auth_recovery.py`

Fail-closed recovery policy:

- transient failure получает bounded retry;
- corrupt/missing/rejected auth → `NEEDS_REAUTH`;
- abnormal materialization exit не reseal частично обновлённый plaintext;
- unknown provider exception не превращается в quota snapshot и не выходит наружу как raw detail.

### `production_vault.py`

Production composition требует одновременно:

- durable blob provider с atomic replacement;
- external KMS/envelope crypto provider;
- cross-worker subject lease provider.

Отсутствие любого из этих свойств блокирует production gate.

### `quota_service.py`

Trust boundary между MCP transport и quota backend:

- model arguments не содержат identity;
- `authenticated_subject` приходит только из trusted transport;
- quota read выполняется внутри subject-bound auth materialization;
- subject A не может использовать auth state subject B;
- internal subject key/path не возвращается модели.

## Plugin package

Package skeleton:

```text
.codex-plugin/plugin.json
skills/openai-work-codex-regulator/SKILL.md
```

`skills/.../SKILL.md` обязан быть byte-for-byte равен корневому `SKILL.md`.

`.app.json` отсутствует намеренно до реальной регистрации MCP connection в ChatGPT. После регистрации платформа должна вернуть настоящий `plugin_asdk_app...` id; только тогда package получает app mapping.

## Что ещё отсутствует

Release gates:

1. реальный Auth0 development tenant;
2. публичный HTTPS `/mcp` staging deployment;
3. live IdP preflight против настоящего tenant;
4. точный ChatGPT redirect URI из app management;
5. resource→audience binding E2E;
6. зарегистрированный ChatGPT MCP connection и настоящий `plugin_asdk_app...` id;
7. ChatGPT Web Connect/Auth E2E на поддерживаемом plan/workspace;
8. audited subject-to-account binding E2E;
9. реальный KMS/secret provider deployment;
10. реальный cross-worker lease provider;
11. token refresh/revocation/logout E2E;
12. crash/partial-write recovery на выбранном durable backend;
13. cross-subject isolation под нагрузкой;
14. threat model и security review.

До закрытия этих gates feature-ветка остаётся development-only.

## Проверка

```bash
python3 scripts/validate_repo.py
python3 scripts/validate_plugin_package.py
python3 scripts/validate_v3_release_contract.py
python3 plugin/quota_backend.py --self-test
python3 plugin/subject_store.py
python3 plugin/quota_service.py
python3 plugin/sealed_auth_store.py
python3 plugin/authorization_coordinator.py
python3 plugin/auth_concurrency.py
python3 plugin/auth_recovery.py
python3 plugin/production_vault.py
python3 -m pip install -r plugin/requirements-mcp.txt
python3 plugin/mcp_transport.py --self-test
python3 -m pip install -r plugin/requirements-auth.txt
python3 plugin/oidc_token_verifier.py --self-test
python3 plugin/idp_preflight.py --self-test
python3 plugin/production_runtime.py --self-test
python3 scripts/package_release.py
```

Текущий regression suite содержит **240 последовательных сценариев**.
