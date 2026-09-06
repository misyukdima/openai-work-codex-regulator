# Использование openai-work-codex-regulator v2.2

## 1. Базовый вызов

```text
Используй openai-work-codex-regulator.
Сохраняй недельную Work/Codex квоту, но не останавливай critical path только из-за nominal 24h target.
Квота и темп работы имеют равный приоритет после hard safety/quality gates.
Задача: <описание>
```

## 2. Минимальный quota snapshot

```text
Weekly used/remaining: <percent>
Weekly reset: <timestamp/duration>
5h used/reset: <если показано>
Meter semantics: USED / REMAINING
Meter granularity: <если известно>
```

Token/rate-card conversion не нужен.

## 3. Что изменилось с v2.1

v2.1 фиксировал 24h slice и мог выдать `DEFER_FOR_QUALITY`, если хороший pass был чуть дороже текущего slice.

v2.2 использует absolute trajectory:

```text
one epoch anchor
→ 24h normal look-ahead
→ bounded 72h future advance
→ quota risk vs pace risk
```

Поэтому 24h больше не является обязательным ожиданием.

## 4. Fresh-week reference

Для `U0=0`, `H0=168h`, zero reservations/buffer:

```text
BASE_ACTION_HEADROOM_PP ≈ 12.8571
MAX_ADVANCE_HEADROOM_PP ≈ 38.5714
```

Первое — нормальный 24h target. Второе — абсолютный максимум bounded advance horizon, а не новый daily budget.

## 5. Equal-priority admission

Определить:

```text
PACE_RISK_IF_DEFER = NONE|LOW|MEDIUM|HIGH|CRITICAL
```

Соответствия:

```text
NONE=0.00
LOW=0.25
MEDIUM=0.50
HIGH=0.75
CRITICAL=1.00
```

Если pass помещается в normal 24h headroom → `LAUNCH_BASE`.

Если требует future advance:

```text
QUOTA_RISK_IF_LAUNCH =
  needed_advance / borrowable_extra
```

При:

```text
QUOTA_RISK_IF_LAUNCH <= PACE_RISK_IF_DEFER
```

и pass внутри max-advance horizon → `LAUNCH_WITH_ADVANCE`.

## 6. Pace-risk examples

- LOW — есть полезная независимая работа; сутки почти ничего не ломают.
- MEDIUM — задержка создаёт rework/throughput penalty, но critical path не закрыт.
- HIGH — gate блокирует дальнейшую реализацию или создаёт заметный idle window.
- CRITICAL — incident/deadline/revenue/production/reputation window под риском.

## 7. Если launch не проходит

Не переходить сразу к ожиданию:

1. убрать duplicate work/context;
2. reuse accepted facts;
3. quality-preserving split/batch;
4. продолжить Chat planning/review/handoff;
5. использовать уже разрешённый non-shared external tool;
6. только затем defer.

```text
MEANINGFUL_PROGRESS_WITHOUT_AGENTIC=YES|NO|UNKNOWN
```

## 8. Chat → Codex handoff

Если regulator работает в Chat:

```text
CONTROL_PLANE_OWNER=CHAT
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

Chat сам решает quota/model/admission. Codex получает готовый execution packet и не должен искать/загружать regulator.

Не включать в обычный Codex prompt:

```text
QUOTA_EPOCH_ID
trajectory headroom
quota/pace risk
paid-reset state
```

Передавать только goal/fact pack/scope/tests/rollback/stop conditions.

## 9. Codex packet example

```text
PASS_ID: <id>
SURFACE: CODEX
ROLE: IMPL
GATE: <one gate>
MODE: BOUNDED_MUTATION
STOP AFTER REPORT.

GOAL:
<goal>

ROOT / REPO / ENVIRONMENT:
<state>

CONTEXT / FACT PACK:
<accepted facts>

READ SCOPE:
<paths>

WRITE SCOPE:
<paths/actions>

NO-TOUCH:
<paths/services/secrets>

ORDER:
1. baseline
2. minimal sufficient change
3. tests
4. diff
5. report

TESTS:
<commands>

ROLLBACK:
<point>

STOP IF:
<drift/scope expansion/safety issue>
```

## 10. Direct Codex use

Если skill установлен и прямо вызван внутри Codex, Codex может быть собственным `CONTROL_PLANE_OWNER`. Но последующие cross-surface handoffs всё равно self-contained.

## 11. Pending meter

`PENDING_BURN=YES` блокирует новый большой future advance до plausibly updated aggregate telemetry. Это не блокирует полезную Chat preparation/review.

## 12. Quality and 5h

`QUALITY_FLOOR=NON_NEGOTIABLE` и отдельный 5h circuit breaker стоят выше quota/pace balancing. Высокая срочность не разрешает insufficient model, missing tests или обход локального limit.

## 13. Reference calculator

```bash
python3 scripts/weekly_quota_controller.py \
  --anchor-weekly-used 0 \
  --anchor-hours-to-reset 168 \
  --hours-to-reset-now 168 \
  --current-weekly-used 0 \
  --samples 18,19,20 \
  --pace-risk HIGH \
  --self-test
```

Главная цель v2.2 — максимизировать устойчивый полезный прогресс в пределах недельной shared allowance, не отдавая автоматический приоритет ни экономии квоты, ни скорости процесса.
