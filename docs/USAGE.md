# Использование openai-work-codex-regulator v3.0

> `v3.0` находится в разработке. Stable release пока остаётся `v2.2`.

## 1. Базовый вызов

Нормальный сценарий больше не требует вручную прикладывать quota snapshot:

```text
Используй openai-work-codex-regulator.
Оркестрируй задачу через ChatGPT, Work и Codex.
Задача: <описание>
```

При quota-sensitive решении regulator сам должен получить актуальный Work/Codex snapshot через доступный telemetry tool.

```text
CHATGPT_PRIMARY_ORCHESTRATOR=YES
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
```

## 2. Что пользователь делает с квотой

В штатном режиме — ничего.

Не нужно периодически:

- открывать Usage;
- смотреть weekly percentage;
- копировать reset time;
- пересчитывать remaining/used;
- отправлять эти значения ChatGPT после каждого pass.

Manual snapshot остаётся допустимым fallback, если automatic telemetry недоступна именно тогда, когда без свежей квоты нельзя безопасно принять следующее agentic-решение.

## 3. Что делает ChatGPT

В нормальном `CHATGPT_PRIMARY` режиме:

```text
user goal
  ↓
ChatGPT regulator
  ↓
quota-sensitive decision?
  ├─ no  → обычная Chat work
  └─ yes → get_quota_snapshot()
               ↓
          normalized telemetry
               ↓
          v2.2 controller
               ↓
          Work / Codex / alternative
```

ChatGPT остаётся control plane. Connected telemetry app/tool только предоставляет meter state.

## 4. Cloud/local boundary

Browser/cloud ChatGPT не должен делать вид, что умеет напрямую вызвать локальный CodexBar или прочитать localhost пользователя.

```text
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN
```

Для Chat автоматическая квота должна приходить через доступный connected app/tool. В локальном Codex standalone тот же normalized contract может заполняться напрямую локальным adapter, если shell/tool access реально существует.

## 5. Normalized quota snapshot

Минимальный успешный snapshot:

```text
ALLOWANCE_DOMAIN=WORK_CODEX
SNAPSHOT_AT=<timestamp>
QUOTA_TELEMETRY_SOURCE=<provider>
QUOTA_TELEMETRY_STATE=FRESH
WEEKLY_METER_SEMANTICS=USED
WEEKLY_USED=<percent>
WEEKLY_RESET=<timestamp|unknown>
FIVE_HOUR_USED=<percent|unknown>
FIVE_HOUR_RESET=<timestamp|unknown>
```

Token/rate-card conversion не нужен и не используется.

## 6. Когда telemetry обновляется

Regulator не должен опрашивать meter на каждое сообщение.

Обновление нужно:

```text
AUTO_QUOTA_REFRESH=BEFORE_AGENTIC_PASS
AUTO_QUOTA_REFRESH=AFTER_MEANINGFUL_AGENTIC_PASS
AUTO_QUOTA_REFRESH=WHEN_PENDING_BURN_MATTERS
AUTO_QUOTA_REFRESH=WHEN_SNAPSHOT_STALE
AUTO_QUOTA_REFRESH=ON_RESET_OR_EPOCH_SUSPECTED
```

Это снижает лишний шум и оставляет автоматизацию там, где она влияет на реальное решение.

## 7. Если automatic telemetry недоступна

Не спрашивать manual quota немедленно, если можно продолжить полезную Chat work.

Порядок:

1. продолжить planning/review/handoff, если это двигает проект;
2. повторить automatic telemetry, когда quota снова станет decision-critical;
3. только если следующий Work/Codex pass нельзя безопасно admitted без свежего snapshot, попросить user-provided first-party state;
4. после восстановления automatic telemetry вернуться к normal path.

```text
MANUAL_QUOTA_INPUT_REQUIRED=NO
MANUAL_QUOTA_INPUT_ACCEPTED=YES
```

## 8. Telemetry freshness

```text
QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>
```

- `FRESH` — можно использовать для quota-sensitive admission;
- `STALE` — сначала попытаться обновить;
- `UNAVAILABLE` — automatic source временно недоступен;
- `CONFLICT` — reset/account epoch выглядит противоречиво;
- `UNKNOWN` — semantics нельзя нормализовать без догадок.

Нельзя превращать stale/unknown snapshot в «актуальный» только потому, что он удобен для продолжения работы.

## 9. CodexBar reference adapter

Для разработки `v3.0` первый reference sensor — CodexBar-compatible JSON.

Нормализатор:

```bash
python3 scripts/quota_telemetry.py --input snapshot.json --pretty
```

Self-test:

```bash
python3 scripts/quota_telemetry.py --self-test
```

Важно: это developer/debug path, а не финальный onboarding пользователя.

Window semantics определяются по длительности:

```text
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
```

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
```

`primary` и `secondary` сами по себе ничего не доказывают.

## 10. Что telemetry provider не делает

Provider не решает:

- запускать ли Work/Codex;
- использовать ли future advance;
- какой model tier выбрать;
- насколько критичен workflow pace;
- покупать ли credits/reset.

Даже если сторонний provider имеет собственный `guard`/pacing, regulator не использует его как admission policy.

## 11. v2.2 controller остаётся ядром

Для свежего normalized snapshot работает прежняя математика:

```text
one epoch anchor
→ 24h normal look-ahead
→ bounded 72h future advance
→ quota risk vs pace risk
```

Fresh-week reference для `U0=0`, `H0=168h`, zero reservations/buffer:

```text
BASE_ACTION_HEADROOM_PP ≈ 12.8571
MAX_ADVANCE_HEADROOM_PP ≈ 38.5714
```

Первое — normal 24h target. Второе — bounded maximum advance horizon, а не новый daily budget.

## 12. Equal-priority admission

```text
PACE_RISK_IF_DEFER = NONE|LOW|MEDIUM|HIGH|CRITICAL
```

```text
NONE=0.00
LOW=0.25
MEDIUM=0.50
HIGH=0.75
CRITICAL=1.00
```

Если pass помещается в normal headroom → `LAUNCH_BASE`.

Если требует future advance:

```text
QUOTA_RISK_IF_LAUNCH = needed_advance / borrowable_extra
```

При:

```text
QUOTA_RISK_IF_LAUNCH <= PACE_RISK_IF_DEFER
```

и pass внутри max-advance horizon → `LAUNCH_WITH_ADVANCE`.

## 13. Pending meter

После meaningful Work/Codex pass automatic refresh может сразу показать тот же percentage. Это не означает burn=0, если aggregate reporting может отставать.

```text
PENDING_BURN=YES
```

Большой новый future advance не stack'ится поверх такого unknown burn. Полезная Chat preparation/review при этом продолжается.

Поздний fresh snapshot внутри того же epoch может разрешить pending state и дать observed aggregate delta.

## 14. Chat → Codex handoff

```text
CONTROL_PLANE_OWNER=CHAT
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

Chat решает quota/model/admission. Codex получает готовый execution packet и не должен искать/загружать regulator.

Не включать в обычный Codex prompt:

```text
QUOTA_EPOCH_ID
telemetry source/plumbing
trajectory headroom
quota/pace risk
paid-reset state
```

Передавать только goal/fact pack/scope/tests/rollback/stop conditions.

## 15. Codex packet example

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

## 16. Standalone Codex / Work

Прямой вызов regulator остаётся поддержанным:

```text
ORCHESTRATION_MODE=CODEX_STANDALONE
```

или:

```text
ORCHESTRATION_MODE=WORK_STANDALONE
```

В таком режиме текущая surface может быть `CONTROL_PLANE_OWNER` для локального pass и использовать доступный telemetry adapter/tool. Последующие cross-surface handoffs всё равно self-contained.

## 17. Zero-maintenance onboarding

Финальная v3.0 не считается готовой, если обычная установка требует Terminal, Homebrew, ручной установки CodexBar, редактирования JSON/YAML, token copy/paste, настройки localhost/tunnel или регулярных quota-сообщений.

До выполнения этого критерия feature-ветка остаётся development и не должна считаться release-ready.

## 18. Reference calculator

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

Главная цель v3.0 — убрать quota bookkeeping из внимания пользователя, не перенося orchestration из ChatGPT в telemetry provider и не ослабляя математические/безопасностные гарантии v2.2.
