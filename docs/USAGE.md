# Использование openai-work-codex-regulator v4.0

v4.0 предназначен прежде всего для ChatGPT как control plane. Work и Codex получают self-contained execution packet и не обязаны загружать skill.

## Быстрый старт

1. Установите release ZIP как skill в ChatGPT.
2. Работайте с проектом обычным образом.
3. Когда решение зависит от Work/Codex allowance, ChatGPT использует read-only get_quota_snapshot() при доступном подключении.
4. Если автоматическая telemetry недоступна и без quota state нельзя безопасно решить следующий pass, допускается ручной first-party snapshot.

По умолчанию дополнительной настройки после установки не требуется.

## Рабочее окно

Default local schedule:

```text
09:00 start
22:00 normal soft end
23:00 hard end
MON-SUN active
```

Пользователь может явно задать другой диапазон и активные дни. Это schedule для распределения недельной квоты, а не лимит длительности задачи.

## Quota behavior

Основной runway — weekly allowance до reset. Skill ориентируется на фактически нормализованный snapshot аккаунта.

Если snapshot содержит weekly window и не содержит 5-hour/secondary window, v4 работает weekly-only. Отсутствующее окно не превращается в 0%, exhaustion или искусственный blocker.

Если дополнительное окно реально присутствует, оно учитывается независимо; проценты разных окон не складываются.

## Quality-first routing

ChatGPT сначала определяет минимально достаточное качество, затем выбирает surface, capability и reasoning. Экономия применяется только среди кандидатов, которые уже проходят quality floor.

Стартовая policy:
- Luna Low — mechanical;
- Luna Medium — routine;
- Sol Medium — professional;
- Sol High — complex reasoning-depth;
- Astra Low/Medium — capability/breadth escalation;
- Astra High — critical/high-error-cost.

Current model picker/account state важнее статического snapshot.

## Рабочий цикл

```text
ChatGPT
  -> understand gate
  -> inspect quota when decision-sensitive
  -> compute active-time runway
  -> choose Work or Codex
  -> choose sufficient model/reasoning
  -> handoff
  -> receive evidence
  -> verify
  -> refresh burn/quota when useful
  -> next gate
```

## Safety

Quota Plugin read-only. Skill не покупает credits, не выполняет paid reset, не расширяет permissions и не передаёт credentials downstream executor.

Для mutation сохраняются точные target/write scope, rollback, tests и STOP_IF boundaries.
