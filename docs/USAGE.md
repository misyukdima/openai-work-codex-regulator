# Использование openai-work-codex-regulator v2.1

## 1. Базовый вызов

```text
Используй openai-work-codex-regulator.
Нужно сохранить Work/Codex capacity на весь текущий weekly reset window, не снижая качество.
Определи surface/model, построи или обнови adaptive weekly control slice и подготовь один bounded pass.

Задача: <описание>
```

## 2. Что дать регулятору

Для полноценного weekly control достаточно актуального first-party snapshot:

```text
Weekly used: <percent>
Weekly reset: <timestamp / duration>
5h used/reset: <если показано>
Usage meter semantics: USED / REMAINING
Meter granularity: <если видно>
```

Если UI показывает remaining, регулятор явно преобразует его к used.

Не нужны token-count estimates или rate-card conversions.

## 3. Fresh-week example

Пусть:

```text
Weekly used = 0%
Reset = 168h
```

v2.1 держит early reserve 10pp и планирует первый 24h slice:

```text
(100 - 10) * 24 / 168
= 12.857142857 pp
```

Это не permanent daily limit. Через 24h controller смотрит фактический meter и строит следующий slice.

## 4. Stateful slice

После создания slice сохраняются:

```text
QUOTA_EPOCH_ID=...
CONTROL_SLICE_ID=...
CONTROL_SLICE_START_WEEKLY_USED_PP=...
CONTROL_SLICE_BUDGET_PP=...
```

Если бюджет 12.86pp и за первый pass meter вырос на 5pp, remaining slice headroom примерно:

```text
12.86 - 5 = 7.86 pp
```

до meter-granularity buffer.

Не пересчитывать новый полный дневной бюджет сразу после pass.

## 5. После каждого meaningful pass

Получить свежий aggregate snapshot и обновить:

```text
WEEKLY_USED_NOW=
SLICE_SPENT_PP=
EFFECTIVE_SLICE_HEADROOM_PP=
POST_PASS_METER_STATE=UPDATED|PENDING|UNKNOWN
PENDING_BURN=YES|NO
```

Если meter ещё plausibly не отразил run, большой следующий pass не стартует.

## 6. Burn history

Для похожих passes сохранять до пяти наблюдений:

```text
surface
role/class
model profile/tier
reasoning/speed posture
task shape
weekly pp delta
attribution label
```

Пример:

```text
Samples: 3, 4, 4, 5, 6 pp
Meter granularity: 1 pp
```

Регулятор построит conservative `B_SAFE` по median/MAD/P80 rule.

Это planning estimate, не гарантия точного расхода.

## 7. Если истории нет

Для class 2 при достаточном headroom выбрать smallest useful quality-sufficient calibration gate, затем измерить aggregate burn.

Для class 3–4/Astra + tight headroom:

```text
ПОДГОТОВКА / ПЕРЕНОС
```

не запуск вслепую.

## 8. Quality floor

Всегда:

```text
QUALITY_FLOOR=NON_NEGOTIABLE
```

Если desired pass слишком дорог для текущего slice, сначала:

- reuse compact handoff;
- убрать duplicate research/audits;
- сократить лишний context/output;
- batch dependent steps внутри same gate;
- использовать cheaper tier/effort только если он всё ещё достаточен;
- перенести lower-value work.

Не убирать required tests/sources и не выбирать insufficient model.

Если high-quality pass всё равно не помещается:

```text
QUOTA_DECISION=DEFER_FOR_QUALITY
```

## 9. Under-spend / over-spend

### Under-spend

Потратили меньше текущего slice → следующий 24h envelope станет больше, потому что больше quota останется на меньшее число часов.

### Over-spend

Потратили больше → следующий envelope уменьшается, а текущий controller может перейти:

```text
WEEKLY_QUOTA_MODE=RECOVERY
```

Не выдавать себе новый полный дневной budget для компенсации.

## 10. Weekly reset

При подтверждённом reset:

```text
QUOTA_EPOCH_EVENT=RESET
```

Дальше:

1. получить fresh first-party meter/reset;
2. создать новый `QUOTA_EPOCH_ID`;
3. discard old control slice;
4. revalidate burn-history compatibility;
5. сохранить project gates/evidence.

## 11. Paid instant reset

Default:

```text
PAID_WEEKLY_RESET_ALLOWED=NO
```

Если пользователь отдельно разрешает покупку, это отдельное class-4 money action.

После реально применённого reset controller строится заново; old schedule не переносится.

## 12. 5-hour window

5h и weekly percentages нельзя сравнивать напрямую.

Если UI показывает 5h meter, controller проверяет две независимые constraints:

```text
weekly B_SAFE <= weekly headroom
AND
5h B_SAFE <= 5h headroom
```

Heavy pass может быть weekly-affordable, но всё равно не помещаться в текущий 5h window.

## 13. Scheduled Tasks

Recurring work резервирует capacity:

```text
SCHEDULED_WEEKLY_COMMITMENT_PP=
EXPECTED_SCHEDULED_BURN_BEFORE_SLICE_END_PP=
```

Interactive headroom уменьшается заранее, чтобы один и тот же allowance не был обещан двум задачам.

## 14. Astra

Astra остаётся exceptional profile.

Quota pressure не означает автоматический downgrade. Если Astra объективно minimum sufficient, а current slice не вмещает pass, нужно quality-preserving scope reduction или defer.

## 15. Reference calculator

Fresh week:

```bash
python3 scripts/weekly_quota_controller.py \
  --weekly-used 0 \
  --hours-to-reset 168 \
  --self-test
```

Existing slice plus burn history:

```bash
python3 scripts/weekly_quota_controller.py \
  --weekly-used 37 \
  --hours-to-reset 96 \
  --slice-start-used 34 \
  --current-used 37 \
  --meter-granularity 1 \
  --samples 3,4,4,5,6
```

## 16. Decision card fields

Для cost-sensitive Work/Codex pass полезно видеть:

```text
Quota epoch
Weekly used/reset
Control slice budget
Slice spent
Effective slice headroom
Pending burn
5h status
B_SAFE + confidence
Continuity feasible
Quality floor
Model profile/tier/effort
```

Главная цель — не «использовать одинаковый процент каждый день», а поддерживать максимально полезную и качественную работу в течение всего weekly window через feedback и re-planning.
