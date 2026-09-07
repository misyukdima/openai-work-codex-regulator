<div align="center">

# OpenAI Work + Codex Regulator

**Skill для ChatGPT Web, который управляет Work/Codex как исполнительными поверхностями и учитывает их общую квоту без ручного переписывания процентов в чат.**

[![Разработка](https://img.shields.io/badge/development-v3.0-8250df)](CHANGELOG.md#30--in-development)
[![Stable](https://img.shields.io/badge/stable-v2.2-0969da)](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2)
[![Проверка](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml/badge.svg)](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml)
[![Тесты](https://img.shields.io/badge/regression_tests-160-success)](tests/)

[Последний стабильный релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/latest) · [Как использовать](docs/USAGE.md) · [Архитектура](docs/ARCHITECTURE.md) · [История изменений](CHANGELOG.md)

</div>

> **v3.0 разрабатывается в `feat/v3-autonomous-quota-telemetry`.** `main` и опубликованный релиз остаются на `v2.2` до полного E2E, Pull Request и review.

## Что это

`openai-work-codex-regulator` работает в **ChatGPT Web**. Skill загружается в ChatGPT, а Work и Codex остаются исполнительными поверхностями: получают от ChatGPT самостоятельный handoff с целью, ограничениями, тестами и stop conditions.

```text
SKILL_RUNTIME=CHATGPT_WEB_ONLY
CONTROL_PLANE_OWNER=CHATGPT
WORK_CODEX_ROLE=EXECUTION_PLANE
EXECUTOR_SKILL_REQUIRED=NO
```

Регулятор выбирает поверхность, модель и effort, оценивает общий Work/Codex allowance и не даёт экономии квоты останавливать полезную работу без причины.

Математика `v2.2` сохраняется: epoch-anchored trajectory, burn estimation, bounded future advance, hard quality floor и баланс `QUOTA_50_PACE_50` остаются decision engine. `v3.0` меняет прежде всего способ получения meter state.

## Целевой UX v3.0

Для обычного пользователя установка должна закончиться почти сразу:

```text
GitHub Release ZIP
        ↓
прикрепить ZIP в ChatGPT Web
        ↓
ChatGPT читает SKILL.md и начинает работу
        ↓
quota-sensitive момент
        ↓
Regulator Quota Plugin уже подключён?
        ├─ да  → get_quota_snapshot()
        └─ нет → ChatGPT показывает Connect / authorization
                         ↓
                  одно подтверждение
                         ↓
                  get_quota_snapshot()
```

Никаких локальных Companion, CodexBar, Terminal, Homebrew, localhost, Tailscale или ручного ввода quota snapshot в штатном сценарии.

```text
USER_SETUP_AFTER_ZIP=NONE
PLUGIN_AUTH=JUST_IN_TIME
LOCAL_SOFTWARE_REQUIRED=NO
OS_DEPENDENCY=NO
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
```

## Что уже доказано на практике

7 сентября 2026 года P0 прошёл на реальном аккаунте ChatGPT Plus.

Одноразовый удалённый GitHub Actions runner:

1. скачал pinned официальный OpenAI Codex CLI;
2. запустил `codex app-server` в изолированном `CODEX_HOME`;
3. выполнил официальный ChatGPT device authorization;
4. дождался `account/updated`, то есть активного managed auth state;
5. вызвал `account/rateLimits/read`;
6. получил фактический Plus quota snapshot;
7. сохранил только обезличенный proof;
8. удалил временный auth state.

P0 подтвердил главное: **удалённый backend может получить точное состояние персональной Work/Codex квоты Plus без локального агента на компьютере пользователя.**

Ответ OpenAI содержал `planType=plus`, отдельный `codex` rate-limit bucket, семидневное окно `10080` минут, `usedPercent`, `resetsAt` и состояние credits. Пятичасовое окно в конкретном snapshot отсутствовало. Regulator обязан трактовать такое поле как `UNAVAILABLE`, а не дорисовывать значение.

```text
P0_SERVER_SIDE_PLUS_QUOTA=PROVEN
FALSE_PRECISION=FORBIDDEN
MISSING_WINDOW=UNAVAILABLE
```

Исследовательский harness лежит в `experiments/`. Это доказательство технической возможности, а не production auth service.

## Архитектура, к которой идёт v3.0

```text
┌─────────────────────────────────────────────┐
│                ChatGPT Web                  │
│                                             │
│  Regulator Skill                            │
│  routing · model · admission · quota math   │
└──────────────────────┬──────────────────────┘
                       │ read only, when needed
                       ▼
┌─────────────────────────────────────────────┐
│          Regulator Quota Plugin/App         │
│                                             │
│  get_quota_snapshot()                       │
│  no routing · no admission · no purchases   │
└──────────────────────┬──────────────────────┘
                       │ authenticated backend
                       ▼
┌─────────────────────────────────────────────┐
│          Official OpenAI Codex              │
│                                             │
│  codex app-server                           │
│  account/rateLimits/read                    │
└──────────────────────┬──────────────────────┘
                       │ normalized facts
                       ▼
               v2.2 quota controller
```

Plugin здесь только источник фактов. Он не выбирает Work/Codex, не определяет модель и не решает, можно ли запускать pass.

```text
QUOTA_PLUGIN=READ_ONLY
PLUGIN_DECISION_AUTHORITY=NONE
CHATGPT_CONTROL_PLANE=YES
```

## Почему мы отказались от локального Companion

Ранний прототип v3.0 исследовал `CodexBar → Companion → relay → ChatGPT`. Он помог проверить нормализацию окон, freshness, pairing и границы секретов, но не соответствует финальному UX.

После P0 локальный слой больше не нужен для основного сценария. Windows, macOS и Linux не должны иметь отдельные продуктовые ветки только ради quota telemetry. Skill живёт в ChatGPT Web, Plugin работает как удалённый read-only bridge.

Код ранних прототипов пока остаётся в feature-ветке как research material. Перед PR мы либо вынесем его из production path, либо удалим после того, как новый Plugin backend закроет те же проверяемые свойства.

## Нормализация quota

Regulator не связывает смысл окна с полями `primary` и `secondary`. Классификация опирается на фактическую длительность:

```text
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

Ключевой invariant:

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
```

`scripts/quota_telemetry.py` остаётся чистым нормализатором. Он не авторизует пользователя, не покупает credits и не принимает admission decisions.

## Как принимается решение

```text
запрос пользователя
        ↓
класс риска + требуемый gate
        ↓
нужен ли quota snapshot сейчас?
        ↓
get_quota_snapshot() при необходимости
        ↓
minimum sufficient model
        ↓
safety + permissions + quality
        ↓
weekly quota trajectory
        ↓
quota risk ↔ workflow pace risk
        ↓
launch / advance / productive alternative / defer / stop
```

Обычный Chat-анализ не должен опрашивать quota без причины. Refresh нужен перед существенным Work/Codex pass, после него, при stale snapshot, pending burn или смене quota epoch.

## Handoff в Work и Codex

Skill не устанавливается в Work или Codex. ChatGPT передаёт исполнителю self-contained пакет:

```text
ChatGPT + Regulator
        ↓
цель + fact pack + scope + no-touch
        ↓
tests + rollback + stop conditions
        ↓
Work или Codex
        ↓
execution + evidence
        ↓
ChatGPT принимает следующее решение
```

```text
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

Так orchestration остаётся в одном месте, а downstream executor не обязан знать внутреннюю quota math.

## Безопасность telemetry

Production path должен оставаться минимальным и read-only:

- Plugin возвращает только данные, нужные controller;
- model не получает OAuth tokens, cookies и raw auth files;
- `get_quota_snapshot()` не принимает email, installation id или token как model-provided arguments;
- telemetry path не умеет покупать credits, запускать paid reset или менять spending controls;
- stale snapshot никогда не выдаётся за fresh;
- отсутствие окна не превращается в выдуманный процент.

P0 специально использовал временный `CODEX_HOME` и удалил его после теста. Для production Plugin отдельным release gate остаётся безопасный credential lifecycle: тестовый runner не считается моделью хранения пользовательской авторизации.

## Текущее состояние v3.0

| Слой | Статус | Что доказано |
| --- | --- | --- |
| v2.2 quota controller | ✅ | математический decision engine сохраняется |
| telemetry normalization | ✅ | duration-based windows, freshness, missing-window semantics |
| server-side Plus quota P0 | ✅ | официальный Codex backend вернул фактический quota snapshot |
| read-only Plugin contract | 🟡 | интерфейс `get_quota_snapshot()` определён, production integration впереди |
| ChatGPT Web Connect/Auth E2E | 🟡 | целевой UX определён; нужен реальный Plugin/App integration test |
| production credential lifecycle | 🟡 | P0 был ephemeral; постоянный безопасный auth backend ещё не release-ready |
| release v3.0 | ⛔ | до E2E, security review и PR в `main` |

`v3.0` не будет сливаться в `main`, пока Plugin не пройдёт настоящий путь ChatGPT Web → Connect/Auth → exact quota → controller без локальной установки и ручного quota bookkeeping.

## Что лежит в репозитории

```text
SKILL.md                              основной контракт ChatGPT Web
references/                           нормативные правила
  01_SURFACE_ROUTING.md               Chat / Work / Codex routing
  02_SHARED_QUOTA_AND_CREDITS.md      общая квота и credits
  03_TASK_CLASSIFICATION.md           классы риска 0–4
  04_RUNWAY_AND_BURN.md               runway и burn accounting
  05_WORK_BROWSER_AND_ACTIONS.md      браузер и внешние действия
  06_CODEX_TECHNICAL_WORK.md          код, Git, серверы, deploy
  07_FAILURES_AND_RECOVERY.md         ошибки и recovery
  08_MODEL_TIER_ROUTING.md            Luna / Terra / Sol
  09_ASTRA_EXECUTION.md               Astra admission
  10_WEEKLY_QUOTA_CONTROLLER.md       недельный quota controller
  11_ORCHESTRATION_AND_HANDOFF.md     self-contained handoff
  12_AUTONOMOUS_QUOTA_TELEMETRY.md    automatic telemetry contract
  SOURCE_MAP.md                       provenance

docs/                                 использование и архитектура
scripts/
  weekly_quota_controller.py          математический decision engine
  quota_telemetry.py                  telemetry normalizer
experiments/
  p0_headless_quota_probe.py          доказанный headless Plus P0
tests/
  TEST_CASES.md                       базовые regression cases
  TEST_CASES_V2_2.md                  v2.2 additions
  TEST_CASES_V3_0.md                  v3.0 additions
```

Ранние `companion/` и relay-компоненты пока сохраняются только как исследовательская ветка. Они не определяют целевой пользовательский путь v3.0.

## Проверка ветки

```bash
python3 scripts/validate_repo.py
python3 scripts/quota_telemetry.py --self-test
python3 scripts/weekly_quota_controller.py \
  --anchor-weekly-used 0 \
  --anchor-hours-to-reset 168 \
  --hours-to-reset-now 168 \
  --current-weekly-used 0 \
  --self-test
python3 scripts/package_release.py
```

Сейчас regression-набор содержит **160 последовательных сценариев**. Это текущий baseline ветки, а не финальное число для релиза.

## История версий

| Версия | Что изменилось | Статус |
| --- | --- | --- |
| **v3.0** | ChatGPT Web control plane, automatic exact quota telemetry, just-in-time Plugin auth, manual fallback | В разработке |
| **v2.2** | Баланс квоты и рабочего темпа, cumulative trajectory, bounded future advance, независимый downstream executor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2) |
| **v2.1** | Адаптивный недельный quota controller, burn estimation, 24h control slice, quality floor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.1) |
| **v2.0** | Профиль Astra, allowance domains, steering и safety-pause semantics | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.0) |
| **v1.2** | Маршрутизация Luna / Terra / Sol и выбор effort по сложности | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.2) |
| **v1.1** | Quota-saving routing, prompt-injection защита, account checks и release hardening | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.1) |
| **v1.0** | Первая версия: surface routing, shared pool, risk classes, browser/Codex discipline | [CHANGELOG](CHANGELOG.md#10--2026-08-21) |

## Документация

- [SKILL.md](SKILL.md) — исполняемый регламент ChatGPT Web.
- [docs/USAGE.md](docs/USAGE.md) — рабочие сценарии.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — устройство регулятора.
- [references/12_AUTONOMOUS_QUOTA_TELEMETRY.md](references/12_AUTONOMOUS_QUOTA_TELEMETRY.md) — контракт automatic telemetry.
- [references/SOURCE_MAP.md](references/SOURCE_MAP.md) — provenance и времязависимые факты.
- [SECURITY.md](SECURITY.md) — политика безопасности.
- [CONTRIBUTING.md](CONTRIBUTING.md) — правила изменений.

## Важное про квоту

Regulator не угадывает неизвестный meter state. Exact telemetry означает только фактические поля, которые вернул источник. Если окно не пришло, оно остаётся `UNAVAILABLE`. Если snapshot устарел, он становится `STALE`. Если post-pass meter ещё не обновился, сохраняется `PENDING_BURN`.

Это принципиальная граница v3.0: автоматизация убирает ручную рутину, но не создаёт ложную точность.

---

<p align="center">
  <sub>В разработке: <strong>v3.0</strong> · stable: <strong>v2.2</strong> · 160 regression-сценариев</sub>
</p>
