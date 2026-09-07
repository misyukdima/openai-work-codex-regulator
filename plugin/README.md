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

Отдельно в CI уже проходит production-shaped MCP transport на exact-pinned `mcp==2.1.1` / `mcp-types==2.1.1`: Streamable HTTP `/mcp`, bearer principal validation, RFC 9728 protected-resource metadata и точный zero-argument tool contract.

P0 доказывает acquisition path. MCP self-test доказывает transport contract. Ни один из этих тестов сам по себе не заменяет production OAuth/IdP, credential vault и реальный ChatGPT Connect/Auth E2E.

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

Production app строится через `Server.streamable_http_app(...)` с injected `TokenVerifier` и `AuthSettings`. SDK монтирует bearer gate и RFC 9728 metadata route.

Transport не реализует OAuth authorization server, JWT signing или identity-provider database. Эти обязанности остаются у отдельного reviewed provider.

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

Python MCP SDK `v2.1.1` не имеет typed top-level `securitySchemes` field в Tool model. Endpoint поэтому защищён OAuth целиком; canonical policy дополнительно зеркалируется в `_meta.securitySchemes` по authenticated-Python pattern OpenAI. Никакого утверждения, что SDK v2.1.1 сам публикует typed field, нет.

### `get_quota_snapshot.tool.json`

Machine-readable contract:

- input — строго `{}`;
- `additionalProperties=false`;
- output — allow-listed schema;
- OAuth `quota:read`;
- closed-world read-only annotations.

MCP OAuth и Codex quota authorization — разные границы. Валидный bearer token идентифицирует caller нашего MCP resource server, но не является Codex quota credential. Если MCP identity валидна, а Codex auth ещё нет, transport возвращает отдельное состояние:

```text
QUOTA_AUTH_REQUIRED
NEEDS_QUOTA_AUTH
```

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

Development store помечен:

```text
production_safe = False
```

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

`SealedBlobStore` и `EnvelopeCipher` являются injected adapters. Репозиторный `ReversibleTestCipher` не является шифрованием и специально имеет `production_safe=False`.

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

Coordinator:

- переиспользует один pending flow при повторном Connect одного subject;
- привязывает authorization id к trusted subject server-side;
- не раскрывает чужой session id как existence oracle;
- держит live `codex app-server` только на время device-code flow;
- на cancel закрывает live client;
- revoke сначала останавливает активный worker, затем удаляет durable auth;
- очищает raw subject из terminal in-memory record.

Текущий coordinator является pinned-worker core. Multi-replica authorization routing/lease остаётся deployment gate.

### `auth_concurrency.py`

Сериализует authorization, quota read и revoke по одному opaque subject key и защищает managed refresh state от lost-update race.

`InProcessSubjectLeaseProvider` нужен только для CI/single-worker и имеет `production_safe=False`. Production должен предоставить audited cross-worker lease provider.

### `auth_recovery.py`

Fail-closed recovery policy:

- transient failure получает bounded retry;
- corrupt/missing/rejected auth → `NEEDS_REAUTH`;
- abnormal materialization exit не reseal частично обновлённый plaintext;
- unknown provider exception не превращается в quota snapshot и не выходит наружу как raw detail.

### `production_vault.py`

Production composition требует одновременно:

- `DurableBlobProvider` с atomic replacement;
- `EnvelopeCryptoProvider` с reviewed KMS/envelope cryptography;
- `SubjectLeaseProvider` с cross-worker serialization.

`build_production_auth_store()` fail-closed, если хотя бы один обязательный provider не production-safe.

### `quota_service.py`

Фиксирует trust boundary между MCP transport и quota backend:

- model arguments не содержат identity;
- `PluginRequestContext.authenticated_subject` приходит только из trusted transport;
- quota read выполняется внутри `auth_store.materialize(subject)`;
- unbound subject получает `AuthorizationRequired`;
- subject A не может использовать auth state subject B;
- internal subject key/path не возвращается модели.

## Plugin package

Package skeleton уже находится в репозитории:

```text
.codex-plugin/plugin.json
skills/openai-work-codex-regulator/SKILL.md
```

`skills/.../SKILL.md` обязан быть byte-for-byte равен корневому `SKILL.md`.

`.app.json` отсутствует намеренно до реальной регистрации MCP connection в ChatGPT. После регистрации платформа должна вернуть настоящий `plugin_asdk_app...` id; только тогда package получает app mapping.

## Что ещё отсутствует

Release gates:

1. production OAuth/IdP + reviewed `TokenVerifier`;
2. зарегистрированный ChatGPT MCP connection и настоящий `plugin_asdk_app...` id;
3. ChatGPT Web Connect/Auth E2E на поддерживаемом plan/workspace;
4. audited subject-to-account binding E2E;
5. реальный KMS/secret provider deployment;
6. реальный cross-worker lease provider;
7. encryption key rotation policy;
8. token refresh/revocation/logout E2E;
9. crash/partial-write recovery на выбранном durable backend;
10. multi-replica authorization routing/lease;
11. cross-subject isolation под нагрузкой;
12. threat model и security review.

До закрытия этих gates feature-ветка остаётся development-only.

## Проверка

Dependency-free gates:

```bash
python3 scripts/validate_repo.py
python3 scripts/validate_plugin_package.py
python3 plugin/quota_backend.py --self-test
python3 plugin/subject_store.py
python3 plugin/quota_service.py
python3 plugin/sealed_auth_store.py
python3 plugin/authorization_coordinator.py
python3 plugin/auth_concurrency.py
python3 plugin/auth_recovery.py
python3 plugin/production_vault.py
```

MCP runtime gate:

```bash
python3 -m pip install -r plugin/requirements-mcp.txt
python3 plugin/mcp_transport.py --self-test
```

Release artifact gate:

```bash
python3 scripts/package_release.py
```

Текущий regression suite содержит **218 последовательных сценариев**.
