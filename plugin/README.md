# Regulator Quota Plugin backend

Этот каталог содержит server-side read-only часть v3.0 для ChatGPT Web.

Model-facing surface намеренно минимален:

```text
get_quota_snapshot()
```

Skill остаётся control plane. Plugin не выбирает Work/Codex, не меняет model/effort, не рассчитывает admission и не выполняет платные действия.

## Что уже доказано

P0 от 7 сентября 2026 года прошёл на реальном аккаунте ChatGPT Plus. Одноразовый удалённый runner запустил официальный `codex app-server`, выполнил managed ChatGPT authorization, дождался authenticated `account/updated`, вызвал `account/rateLimits/read`, получил фактический `codex` quota snapshot и удалил временный auth state.

```text
P0_SERVER_SIDE_PLUS_QUOTA=PROVEN
```

P0 доказывает acquisition path, но не является production credential store.

## Модули

### `quota_backend.py`

- минимальный JSON-RPC client для официального `codex app-server`;
- managed ChatGPT auth primitive для development/P0;
- readiness boundary `login/completed → account/updated → rateLimits/read`;
- выбор `codex` bucket;
- duration-based window normalization;
- missing-window semantics;
- secret-field exclusion;
- deterministic self-test без сети и credentials.

### `subject_store.py`

Определяет `SubjectAuthStore` boundary и development-only `EphemeralSubjectAuthStore`.

Raw ChatGPT subject не используется как path. Внутренний key выводится через HMAC-SHA256 с server-held pepper:

```text
trusted subject
  ↓ HMAC(server pepper)
opaque subject key
  ↓
isolated auth context
```

Ephemeral store специально помечен:

```text
production_safe = False
```

Он нужен для CI/P0/P1 и не делает заявления об encryption at rest или production persistence.

### `quota_service.py`

Фиксирует trust boundary между ChatGPT Plugin transport и quota backend:

- model arguments не содержат identity;
- `PluginRequestContext.authenticated_subject` приходит только из trusted transport;
- unbound subject получает `AuthorizationRequired`;
- subject A не может использовать auth state subject B;
- revoke удаляет только связанный subject context;
- internal subject key/path никогда не возвращается модели.

### `get_quota_snapshot.tool.json`

Machine-readable model-facing contract. `inputSchema` пуст и запрещает дополнительные свойства. Tool read-only и non-destructive.

## Что пока намеренно отсутствует

Репозиторий ещё не содержит production HTTP/MCP deployment, persistent credential vault или identity provider adapter.

Release gates:

1. ChatGPT Web Connect/Auth E2E;
2. audited subject-to-account binding;
3. production KMS/secret-backed `SubjectAuthStore`;
4. encryption at rest;
5. token refresh/revocation/logout;
6. cross-subject isolation under concurrency;
7. freshness/retry/error mapping;
8. threat model и security review.

До закрытия этих gates feature-ветка остаётся development-only.

## Проверка

```bash
python3 plugin/quota_backend.py --self-test
python3 plugin/subject_store.py
python3 plugin/quota_service.py
python3 scripts/validate_repo.py
```

Все проверки детерминированы и не требуют реальных OpenAI credentials.
