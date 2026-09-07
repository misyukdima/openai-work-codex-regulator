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

P0 доказывает acquisition path, но не является production credential store.

## Модули

### `quota_backend.py`

- минимальный JSON-RPC client для official `codex app-server`;
- managed ChatGPT auth primitive для development/P0;
- readiness boundary `login/completed → account/updated → rateLimits/read`;
- выбор `codex` bucket;
- duration-based window normalization;
- missing-window semantics;
- secret-field exclusion.

### `subject_store.py`

Определяет trusted subject boundary. Raw ChatGPT identity не используется как path: внутренний key выводится через HMAC-SHA256 с server-held pepper.

Development store помечен:

```text
production_safe = False
```

Он нужен для CI/P0/P1 и не делает заявления об encryption at rest.

### `sealed_auth_store.py`

Фиксирует production-oriented credential lifecycle без собственной криптографии:

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

`SealedBlobStore` и `EnvelopeCipher` — injected adapters. Реальный production adapter должен использовать audited KMS/secret infrastructure и выставлять `production_safe=True` только после review.

Репозиторный `ReversibleTestCipher` **не является шифрованием** и специально имеет `production_safe=False`. `require_production_safe()` обязан отвергать его в production.

### `quota_service.py`

Фиксирует trust boundary между ChatGPT Plugin transport и quota backend:

- model arguments не содержат identity;
- `PluginRequestContext.authenticated_subject` приходит только из trusted transport;
- quota read выполняется внутри `auth_store.materialize(subject)`;
- unbound subject получает `AuthorizationRequired`;
- subject A не может использовать auth state subject B;
- internal subject key/path не возвращается модели.

### `get_quota_snapshot.tool.json`

Machine-readable model-facing contract. `inputSchema` пуст и запрещает дополнительные свойства. Tool read-only и non-destructive.

## Почему seal/unseal подходит official Codex

В official file-mode managed auth хранится в `$CODEX_HOME/auth.json`; Codex сам обновляет этот record при refresh. Поэтому backend не обязан держать постоянный plaintext Codex home. Он может materialize один private auth file на время операции и reseal обновлённую версию после успешного выхода.

Это архитектурное решение всё равно требует настоящего production KMS/secret adapter и отдельного concurrency/crash review.

## Что ещё отсутствует

Release gates:

1. ChatGPT Web Connect/Auth E2E;
2. audited subject-to-account binding;
3. production KMS/secret-backed sealed blob store;
4. encryption/key rotation policy;
5. token refresh/revocation/logout E2E;
6. concurrent calls for one subject;
7. crash/partial-write recovery;
8. cross-subject isolation under load;
9. threat model и security review.

До закрытия этих gates feature-ветка остаётся development-only.

## Проверка

```bash
python3 plugin/quota_backend.py --self-test
python3 plugin/subject_store.py
python3 plugin/quota_service.py
python3 plugin/sealed_auth_store.py
python3 scripts/validate_repo.py
```

Все текущие self-tests детерминированы и не требуют реальных OpenAI credentials.
