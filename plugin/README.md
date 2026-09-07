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

Фиксирует credential lifecycle без собственной production-криптографии:

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

Отдельный trusted Connect/Auth state machine. Он не расширяет model-facing quota tool.

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

Текущая реализация является pinned-worker core. Multi-replica routing/lease для живого authorization process остаётся отдельным deployment gate.

### `auth_concurrency.py`

Сериализует authorization, quota read и revoke по одному opaque subject key. Это защищает managed refresh state от lost-update race.

```text
subject A quota read ─┐
subject A refresh     ├─ one subject lease
subject A revoke     ─┘

subject B operation     independent lease
```

`InProcessSubjectLeaseProvider` нужен только для CI/single-worker P1 и имеет `production_safe=False`. Production должен предоставить audited cross-worker lease provider; при таймауте операция fail-closed и не продолжает работу без блокировки.

### `production_vault.py`

Связывает sealed lifecycle с внешней production-инфраструктурой:

- `DurableBlobProvider` отвечает за durable object/secret storage;
- `EnvelopeCryptoProvider` отвечает за audited KMS/envelope cryptography;
- `SubjectLeaseProvider` отвечает за cross-worker serialization;
- durable provider обязан подтверждать atomic object replacement;
- object key строится только из валидированного opaque subject key;
- crypto provider обязан объявить `key_reference` и `algorithm_id`;
- `build_production_auth_store()` fail-closed, если хотя бы один обязательный provider не production-safe.

Сам репозиторий не реализует production cipher, не хранит encryption keys и не реализует самодельный distributed lock.

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

В official file-mode managed auth хранится в `$CODEX_HOME/auth.json`; Codex сам обновляет этот record при refresh. Backend не обязан держать постоянный plaintext Codex home: он materialize один private auth file на время операции и reseal обновлённую версию после успешного выхода.

Per-subject lease нужен поверх этого lifecycle, потому что два одновременных materialize одного subject иначе могут начать с одной версии auth state и позже перезаписать друг друга.

## Что ещё отсутствует

Release gates:

1. ChatGPT Web Connect/Auth E2E;
2. audited subject-to-account binding;
3. реальный audited KMS/secret provider deployment;
4. реальный audited cross-worker lease provider;
5. encryption key rotation policy;
6. token refresh/revocation/logout E2E;
7. crash/partial-write recovery на выбранном durable backend;
8. multi-replica authorization routing/lease;
9. cross-subject isolation под нагрузкой;
10. threat model и security review.

До закрытия этих gates feature-ветка остаётся development-only.

## Проверка

```bash
python3 plugin/quota_backend.py --self-test
python3 plugin/subject_store.py
python3 plugin/quota_service.py
python3 plugin/sealed_auth_store.py
python3 plugin/authorization_coordinator.py
python3 plugin/auth_concurrency.py
python3 plugin/production_vault.py
python3 scripts/validate_repo.py
```

Все текущие self-tests детерминированы и не требуют реальных OpenAI credentials.
