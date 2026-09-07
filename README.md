<div align="center">

# OpenAI Work + Codex Regulator

**Skill для ChatGPT Web, который оркестрирует Work/Codex и учитывает их общую квоту без регулярного копирования процентов в чат.**

[![Разработка](https://img.shields.io/badge/development-v3.0-8250df)](CHANGELOG.md#30--in-development)
[![Stable](https://img.shields.io/badge/stable-v2.2-0969da)](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2)
[![Проверка](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml/badge.svg)](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml)
[![Тесты](https://img.shields.io/badge/regression_tests-170-success)](tests/)

[Последний стабильный релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/latest) · [Использование](docs/USAGE.md) · [Архитектура](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)

</div>

> **v3.0 разрабатывается в `feat/v3-autonomous-quota-telemetry`.** `main` и stable release остаются на `v2.2` до E2E, security review, Pull Request и review.

## Что это

`openai-work-codex-regulator` работает **только в ChatGPT Web**. ChatGPT остаётся control plane: понимает задачу, выбирает Chat, Work или Codex, решает quota/model/admission и формирует self-contained handoff.

Work и Codex ничего не устанавливают и не загружают из этого репозитория. Для них skill уже превратил задачу в готовый execution packet.

```text
SKILL_RUNTIME=CHATGPT_WEB_ONLY
CONTROL_PLANE_OWNER=CHAT
WORK_CODEX_ROLE=EXECUTION_PLANE
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

Главная цель не «экономить любой ценой», а сохранить Work/Codex allowance до reset и при этом не останавливать полезную работу без веской причины.

## Как должен выглядеть v3.0 для пользователя

```text
GitHub Release ZIP
        ↓
прикрепить ZIP в ChatGPT Web
        ↓
начать работу
        ↓
quota-sensitive момент
        ↓
Quota Plugin уже подключён?
        ├─ да  → get_quota_snapshot()
        └─ нет → ChatGPT показывает Connect / Auth
                         ↓
                    подтверждение
                         ↓
                  get_quota_snapshot()
```

Обязательная настройка skill заканчивается на загрузке ZIP. Plugin подключается только тогда, когда quota впервые действительно нужна.

```text
USER_SETUP_AFTER_ZIP=NONE
PLUGIN_AUTH=JUST_IN_TIME
LOCAL_SOFTWARE_REQUIRED=NO
OS_DEPENDENCY=NO
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
```

В production path нет Companion, CodexBar, Terminal, Homebrew, localhost, tunnel или отдельной настройки под Windows/macOS/Linux.

## Что уже доказано на практике

7 сентября 2026 года прошёл P0 на реальном аккаунте ChatGPT Plus.

Одноразовый удалённый runner:

1. скачал pinned официальный OpenAI Codex CLI;
2. запустил `codex app-server` в изолированном временном auth state;
3. выполнил managed ChatGPT authorization;
4. дождался `account/login/completed`, затем authenticated `account/updated`;
5. вызвал `account/rateLimits/read`;
6. получил фактический Plus `codex` quota snapshot;
7. сохранил только sanitized proof;
8. удалил временный auth state.

```text
P0_SERVER_SIDE_PLUS_QUOTA=PROVEN
```

Это снимает главный feasibility risk: точную Plus quota можно получить на server side без локального агента на компьютере пользователя.

P0 также подтвердил важный edge case: weekly window может прийти без 5-hour window. В таком случае Regulator возвращает `UNAVAILABLE/null`, а не придумывает `0%`.

## Архитектура v3.0

```text
┌────────────────────────────────────────────┐
│                ChatGPT Web                 │
│                                            │
│  Regulator Skill                           │
│  routing · model · admission · quota math  │
└──────────────────────┬─────────────────────┘
                       │ get_quota_snapshot()
                       ▼
┌────────────────────────────────────────────┐
│         Regulator Quota Plugin/App         │
│                                            │
│  authenticated subject · read only         │
└──────────────────────┬─────────────────────┘
                       ▼
┌────────────────────────────────────────────┐
│          server-side quota backend         │
│                                            │
│  subject isolation · official Codex RPC    │
└──────────────────────┬─────────────────────┘
                       ▼
              account/rateLimits/read
                       ↓
                normalized facts
                       ↓
              v2.2 quota controller
```

Plugin является датчиком, а не вторым контроллером.

```text
QUOTA_PLUGIN=READ_ONLY
PLUGIN_DECISION_AUTHORITY=NONE
```

## Server-side backend

`plugin/quota_backend.py` содержит доказанный core для official `codex app-server`:

- managed auth readiness boundary;
- read-only `account/rateLimits/read`;
- выбор `codex` bucket;
- duration-based window semantics;
- missing-window handling;
- allow-listed normalized output;
- secret-field exclusion.

Особенно важен порядок после авторизации:

```text
account/login/completed(success=true)
        ↓
account/updated(authMode != null)
        ↓
account/rateLimits/read
```

P0 показал, что чтение сразу после `login/completed` может попасть в короткий race до auth reload. Поэтому backend ждёт реальное account readiness event, а не добавляет случайный sleep.

## Subject isolation

Следующий production risk уже вынесен в отдельный boundary.

`plugin/subject_store.py` не использует raw ChatGPT identity как имя каталога. Внутренний key выводится из trusted subject через HMAC-SHA256 с server-held pepper:

```text
trusted Plugin subject
        ↓ HMAC(server pepper)
opaque subject key
        ↓
isolated auth context
```

`plugin/quota_service.py` принимает identity только через trusted `PluginRequestContext`. Model-facing tool по-прежнему получает пустой input schema и не может подставить другой `subject`, `email`, `account_id` или token.

Development store намеренно помечен:

```text
production_safe = False
```

Он проверяет isolation/revoke/path safety в CI, но не притворяется production KMS. Перед релизом нужен отдельный audited persistent vault.

## Canonical tool contract

```text
get_quota_snapshot()
```

Ноль model-provided identity arguments. Сервер сам связывает authenticated Plugin subject с авторизованным quota account.

Tool не умеет:

- покупать credits;
- запускать paid reset;
- менять spending controls;
- выполнять generic Codex RPC;
- запускать shell;
- выбирать Work/Codex или model tier.

Machine-readable contract: `plugin/get_quota_snapshot.tool.json`.

## Нормализация quota

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

Нельзя считать, что `primary=5h`, `secondary=weekly` или наоборот. Смысл определяется фактической длительностью окна.

## Контроллер v2.2 остаётся ядром

`v3.0` не переписывает уже проверенную математику.

Сохраняются:

- один quota epoch и cumulative trajectory;
- 24h normal look-ahead;
- bounded future advance до 72h той же trajectory;
- conservative observed-burn estimator;
- `PENDING_BURN`;
- независимый 5h breaker, когда 5h telemetry реально известна;
- `QUALITY_FLOOR=NON_NEGOTIABLE`;
- баланс `QUOTA_50_PACE_50` после hard gates.

Automatic telemetry меняет acquisition, а не admission math.

## Handoff в Work и Codex

```text
ChatGPT Regulator
        ↓
goal + fact pack + scope + no-touch
        ↓
tests/evidence + rollback + stop conditions
        ↓
Work или Codex
        ↓
execution + evidence
        ↓
ChatGPT принимает следующее решение
```

В ordinary executor packet не попадают Plugin credentials, quota epoch, trajectory headroom, telemetry plumbing или внутренние quota/pace scores.

## Безопасность

Production release должен доказать:

```text
SUBJECT_ACCOUNT_BINDING_AUDITED=YES
CREDENTIAL_ISOLATION_AUDITED=YES
ENCRYPTION_AT_REST_REQUIRED=YES
TOKEN_REFRESH_TESTED=YES
TOKEN_REVOCATION_TESTED=YES
LOGOUT_PATH_TESTED=YES
CROSS_SUBJECT_READ=FORBIDDEN
SILENT_ACCOUNT_SWITCH=FORBIDDEN
```

P0 использовал ephemeral auth и удалил его после проверки. Это хороший proof для acquisition, но не модель долгоживущего credential storage.

## Текущее состояние

| Слой | Статус | Что есть сейчас |
| --- | --- | --- |
| v2.2 quota controller | ✅ | deterministic decision engine |
| quota normalization | ✅ | weekly/5h/other/missing semantics |
| server-side Plus P0 | ✅ | exact `codex` quota read через official Codex |
| Plugin backend core | ✅ | read-only JSON-RPC + normalized output |
| subject isolation core | ✅ | opaque HMAC keys, scoped contexts/revoke, model identity override blocked |
| ChatGPT Web Connect/Auth E2E | 🟡 | ещё нужен реальный Plugin/App integration test |
| production credential vault | 🟡 | interface есть, audited KMS/secret adapter ещё не выбран/реализован |
| security review | 🟡 | release gate |
| v3.0 release | ⛔ | PR в `main` пока рано |

## Что лежит в репозитории

```text
SKILL.md
references/
  10_WEEKLY_QUOTA_CONTROLLER.md
  11_ORCHESTRATION_AND_HANDOFF.md
  12_AUTONOMOUS_QUOTA_TELEMETRY.md
  13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md
  SOURCE_MAP.md

docs/
  USAGE.md
  ARCHITECTURE.md

scripts/
  weekly_quota_controller.py
  quota_telemetry.py

plugin/
  quota_backend.py
  subject_store.py
  quota_service.py
  get_quota_snapshot.tool.json

experiments/
  p0_headless_quota_probe.py

tests/
  TEST_CASES.md
  TEST_CASES_V2_2.md
  TEST_CASES_V3_0.md
  TEST_CASES_V3_0_SECURITY.md
```

Ранние `companion/` и `relay/` компоненты могут оставаться в feature-ветке только как research history. Validator и release contract больше от них не зависят.

## Проверка

```bash
python3 scripts/validate_repo.py
python3 plugin/quota_backend.py --self-test
python3 plugin/subject_store.py
python3 plugin/quota_service.py
python3 scripts/package_release.py
```

Сейчас regression suite содержит **170 последовательных сценариев**.

## История версий

| Версия | Что изменилось | Статус |
| --- | --- | --- |
| **v3.0** | ChatGPT Web-only control plane, exact server-side quota telemetry, just-in-time Plugin auth, subject-isolated backend | В разработке |
| **v2.2** | Баланс quota/workflow pace, cumulative trajectory, bounded future advance, independent executor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2) |
| **v2.1** | Adaptive weekly controller, burn estimation, 5h breaker, quality floor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.1) |
| **v2.0** | Astra profile, allowance domains, steering и safety semantics | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.0) |
| **v1.2** | Luna / Terra / Sol routing и effort selection | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.2) |
| **v1.1** | Quota-saving routing, security и release hardening | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.1) |
| **v1.0** | Surface routing, shared pool, risk classes, execution discipline | [CHANGELOG](CHANGELOG.md#10--2026-08-21) |

## Документация

- [SKILL.md](SKILL.md): executable ChatGPT Web contract.
- [docs/USAGE.md](docs/USAGE.md): рабочий сценарий.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): архитектура v3.0.
- [references/12_AUTONOMOUS_QUOTA_TELEMETRY.md](references/12_AUTONOMOUS_QUOTA_TELEMETRY.md): automatic telemetry semantics.
- [references/13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md](references/13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md): Plugin/backend security boundary.
- [references/SOURCE_MAP.md](references/SOURCE_MAP.md): provenance.
- [SECURITY.md](SECURITY.md): политика безопасности.
- [CONTRIBUTING.md](CONTRIBUTING.md): правила изменений.

## Важное про точность

Regulator не превращает неизвестное значение в удобную цифру. Missing window остаётся `UNAVAILABLE`, stale snapshot остаётся `STALE`, а delayed post-pass meter остаётся `PENDING_BURN`, пока не появится достаточное evidence.

Автоматизация убирает ручную рутину, а не требования к доказательности.

---

<p align="center">
  <sub>development: <strong>v3.0</strong> · stable: <strong>v2.2</strong> · 170 regression-сценариев</sub>
</p>
