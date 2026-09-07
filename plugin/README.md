# Regulator Quota Plugin backend

Этот каталог содержит серверную read-only часть v3.0. Она нужна только для одного действия ChatGPT Web:

```text
get_quota_snapshot()
```

Skill остаётся control plane. Plugin не выбирает Work/Codex, не меняет модель, не рассчитывает admission и не выполняет платные действия.

## Что уже доказано

P0 от 7 сентября 2026 года прошёл на реальном аккаунте ChatGPT Plus. Одноразовый удалённый runner запустил официальный `codex app-server`, выполнил managed ChatGPT authorization, дождался `account/updated` и успешно вызвал `account/rateLimits/read`.

После теста временный `CODEX_HOME` был удалён. P0 подтверждает server-side чтение фактической Plus quota, но не определяет production credential lifecycle.

## Код

`quota_backend.py` содержит:

- минимальный JSON-RPC client для официального `codex app-server`;
- managed ChatGPT device authorization для development/P0;
- обязательное ожидание `account/updated` после `account/login/completed`;
- read-only `account/rateLimits/read`;
- нормализацию `codex` bucket в контракт Regulator;
- duration-based классификацию окон;
- fail-closed semantics для отсутствующего 5h/weekly окна;
- self-test без сети и без OpenAI credentials.

`get_quota_snapshot.tool.json` фиксирует model-facing tool contract. У tool нет model-provided identity arguments: пользователя должен разрешать authenticated Plugin/App context на сервере.

## Что намеренно не реализовано

Этот модуль не поднимает публичный HTTP/MCP server и не хранит долгоживущие OpenAI credentials.

До release нужны отдельные доказательства:

1. ChatGPT Web Connect/Auth E2E;
2. audited subject-to-account binding;
3. production credential store и rotation/revocation;
4. isolation между пользователями;
5. freshness/retry policy;
6. logout/revoke path;
7. security review и threat model.

Пока эти gates не закрыты, код здесь считается backend core, а не готовым публичным Plugin.

## Проверка

```bash
python3 plugin/quota_backend.py --self-test
```

Self-test не обращается в сеть и не требует авторизации.
