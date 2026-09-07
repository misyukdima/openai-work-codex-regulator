# Использование openai-work-codex-regulator v3.0

> `v3.0` разрабатывается в отдельной feature-ветке. Stable release пока остаётся `v2.2`.

## 1. Установка

Целевой сценарий для обычного пользователя:

```text
1. Скачать ZIP из GitHub Releases.
2. Прикрепить ZIP в ChatGPT Web.
3. Продолжить работу в этом чате.
```

На этом обязательная настройка skill заканчивается.

```text
SKILL_RUNTIME=CHATGPT_WEB_ONLY
USER_SETUP_AFTER_ZIP=NONE
LOCAL_SOFTWARE_REQUIRED=NO
OS_DEPENDENCY=NO
```

Skill не устанавливается в Work или Codex.

## 2. Базовый вызов

После загрузки ZIP пользователь формулирует задачу обычным языком. Regulator сам выбирает Chat, Work или Codex и формирует handoff, когда отдельная execution surface действительно нужна.

```text
user goal
  ↓
ChatGPT regulator
  ↓
Chat / Work / Codex
```

Work и Codex получают self-contained packet и не обязаны знать о regulator skill.

## 3. Что пользователь делает с квотой

В штатном режиме ничего.

Не нужно периодически:

- открывать Usage;
- копировать weekly percentage;
- переносить reset time;
- пересчитывать remaining/used;
- отправлять meter state после каждого pass.

```text
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
```

## 4. Когда появляется Plugin

Plugin не нужно подключать сразу после ZIP, если quota ещё не влияет на решение.

```text
quota-sensitive decision?
  ├─ no  → ChatGPT продолжает работу
  └─ yes → Regulator Quota Plugin connected?
              ├─ yes → get_quota_snapshot()
              └─ no  → ChatGPT показывает Connect/Auth
```

После штатной one-time authorization последующие quota reads должны происходить без ручного переноса процентов.

```text
PLUGIN_AUTH=JUST_IN_TIME
```

## 5. Normalized quota snapshot

Минимальный model-facing snapshot:

```text
ALLOWANCE_DOMAIN=WORK_CODEX
SNAPSHOT_AT=<timestamp>
QUOTA_TELEMETRY_SOURCE=<provider>
QUOTA_TELEMETRY_STATE=<FRESH|STALE|UNAVAILABLE|CONFLICT|UNKNOWN>
WEEKLY_METER_SEMANTICS=USED
WEEKLY_USED=<percent|unknown>
WEEKLY_RESET=<timestamp|unknown>
FIVE_HOUR_USED=<percent|unknown>
FIVE_HOUR_RESET=<timestamp|unknown>
```

Если 5h или weekly окно не пришло, поле остаётся unknown/null. `0%` нельзя подставлять вместо отсутствующего значения.

## 6. Window semantics

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

`primary` и `secondary` сами по себе ничего не доказывают.

## 7. Когда telemetry обновляется

```text
AUTO_QUOTA_REFRESH=BEFORE_AGENTIC_PASS
AUTO_QUOTA_REFRESH=AFTER_MEANINGFUL_AGENTIC_PASS
AUTO_QUOTA_REFRESH=WHEN_PENDING_BURN_MATTERS
AUTO_QUOTA_REFRESH=WHEN_SNAPSHOT_STALE
AUTO_QUOTA_REFRESH=ON_RESET_OR_EPOCH_SUSPECTED
```

Обычный Chat turn не требует quota fetch, если meter state не влияет на текущее решение.

## 8. Если Plugin недоступен

Regulator не должен сразу превращать это в пользовательскую рутину.

Порядок:

1. продолжить полезный Chat planning/review/handoff;
2. повторить automatic telemetry, когда quota снова станет decision-critical;
3. если следующий Work/Codex pass нельзя безопасно решить без свежего meter, запросить manual first-party snapshot;
4. после восстановления Plugin вернуться к automatic path.

```text
MANUAL_QUOTA_INPUT_REQUIRED=NO
MANUAL_QUOTA_INPUT_ACCEPTED=YES
```

## 9. Что доказано в P0

На feature-ветке уже проверено server-side получение Plus quota через официальный Codex app-server. После managed authorization backend дождался authenticated `account/updated`, вызвал `account/rateLimits/read`, получил фактический `codex` rate-limit snapshot и удалил временный auth state.

Это development proof, а не пользовательская инструкция. Обычный пользователь v3.0 не должен вводить device code в GitHub Actions.

## 10. v2.2 controller остаётся ядром

Automatic telemetry только доставляет meter state. Admission math остаётся прежней:

```text
one quota epoch
→ 24h normal look-ahead
→ bounded 72h future advance
→ quota risk vs pace risk
```

Fresh-week reference при `U0=0`, `H0=168h`, zero reservations/buffer:

```text
BASE_ACTION_HEADROOM_PP ≈ 12.8571
MAX_ADVANCE_HEADROOM_PP ≈ 38.5714
```

Первое число задаёт normal pacing target, второе ограничивает maximum future advance. Это не два независимых бюджета.

## 11. Equal-priority admission

```text
PACE_RISK_IF_DEFER = NONE|LOW|MEDIUM|HIGH|CRITICAL
NONE=0.00
LOW=0.25
MEDIUM=0.50
HIGH=0.75
CRITICAL=1.00
```

Если pass помещается в normal headroom, используется normal launch. Если нужен future advance:

```text
QUOTA_RISK_IF_LAUNCH = needed_advance / borrowable_extra
```

`LAUNCH_WITH_ADVANCE` допустим только внутри max horizon и когда quota risk не выше pace risk.

## 12. Pending meter

Если immediate post-pass snapshot не изменился, это не обязательно burn=0.

```text
PENDING_BURN=YES
```

До разрешения pending state не stack'ить новый большой future advance. Chat preparation/review при этом может продолжаться.

## 13. Chat → Work handoff

```text
PASS_ID: <id>
SURFACE: CHATGPT_WORK
ROLE: <RESEARCH|ACTION|VERIFY|MONITOR>
GATE: <one gate>
MODE: <READ_ONLY|BOUNDED_ACTION>
STOP AFTER REPORT.

GOAL:
<one verifiable outcome>

CONTEXT / FACT PACK:
<accepted facts>

READ / ACTION SCOPE:
<allowed sites, apps, files, actions>

NO-TOUCH:
<forbidden actions/accounts/data>

EVIDENCE:
<what proves the gate>

STOP IF:
<drift, auth mismatch, safety issue, scope expansion>
```

## 14. Chat → Codex handoff

```text
PASS_ID: <id>
SURFACE: CODEX
ROLE: <IMPL|VERIFY|DEPLOY>
GATE: <one gate>
MODE: <READ_ONLY|BOUNDED_MUTATION>
STOP AFTER REPORT.

GOAL:
<one verifiable outcome>

ROOT / REPO / ENVIRONMENT:
<known state>

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
2. minimum sufficient change
3. tests
4. diff
5. report

ROLLBACK:
<point>

STOP IF:
<drift, failed gate, unknown target, scope expansion>
```

Не включать в обычный Work/Codex packet quota epoch, Plugin plumbing, tokens, trajectory headroom или внутренние quota/pace scores.

## 15. Plugin backend для разработчиков

Deterministic backend self-test:

```bash
python3 plugin/quota_backend.py --self-test
```

Pure telemetry normalizer:

```bash
python3 scripts/quota_telemetry.py --self-test
```

Controller self-test:

```bash
python3 scripts/weekly_quota_controller.py \
  --anchor-weekly-used 0 \
  --anchor-hours-to-reset 168 \
  --hours-to-reset-now 168 \
  --current-weekly-used 0 \
  --self-test
```

Эти команды нужны разработчикам репозитория, не обычному пользователю skill.

## 16. Release gate

Feature-ветка остаётся development-only, пока не пройдёт реальный ChatGPT Web E2E:

```text
ZIP → ChatGPT Web → Connect/Auth → get_quota_snapshot() → controller → Work/Codex handoff
```

Дополнительно обязательны cross-subject isolation, credential refresh/revoke, read-only tool audit и security review. Только после этого создаётся Pull Request в `main`.
