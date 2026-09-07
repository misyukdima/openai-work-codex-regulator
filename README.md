<div align="center">

# OpenAI Work + Codex Regulator

**Skill для ChatGPT Web, который оркестрирует Work/Codex и автоматически учитывает их общую квоту без регулярного копирования процентов в чат.**

[![Разработка](https://img.shields.io/badge/development-v3.0-8250df)](CHANGELOG.md#30--in-development)
[![Stable](https://img.shields.io/badge/stable-v2.2-0969da)](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2)
[![Проверка](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml/badge.svg)](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml)
[![Тесты](https://img.shields.io/badge/regression_tests-218-success)](tests/)

[Последний стабильный релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/latest) · [Использование](docs/USAGE.md) · [Архитектура](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)

</div>

> **v3.0 разрабатывается в `feat/v3-autonomous-quota-telemetry`.** `main` и stable release остаются на `v2.2` до реального ChatGPT Web E2E, security review, Pull Request и review.

## Что это

`openai-work-codex-regulator` работает **только в ChatGPT Web**. ChatGPT остаётся control plane: понимает задачу, выбирает Chat, Work или Codex, принимает quota/model/admission-решение и формирует self-contained handoff.

Work и Codex ничего не устанавливают и не загружают из этого репозитория. Для них skill уже превратил задачу в готовый execution packet.

```text
SKILL_RUNTIME=CHATGPT_WEB_ONLY
CONTROL_PLANE_OWNER=CHAT
WORK_CODEX_ROLE=EXECUTION_PLANE
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

Цель регулятора не в экономии ради экономии. Work/Codex allowance должен дожить до reset, но полезная работа не должна останавливаться без достаточной причины.

## UX v3.0

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
        └─ нет → Connect / Auth
                         ↓
                    подтверждение
                         ↓
                  get_quota_snapshot()
```

Обязательная настройка skill заканчивается на загрузке ZIP. Plugin подключается только тогда, когда quota впервые нужна для реального решения.

```text
USER_SETUP_AFTER_ZIP=NONE
PLUGIN_AUTH=JUST_IN_TIME
LOCAL_SOFTWARE_REQUIRED=NO
OS_DEPENDENCY=NO
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
```

В production path нет Companion, CodexBar, Terminal, Homebrew, localhost, tunnel или отдельной настройки под Windows, macOS и Linux.

## Что уже доказано на практике

7 сентября 2026 года прошёл P0 на реальном аккаунте ChatGPT Plus.

Одноразовый remote runner:

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

Это снимает главный feasibility risk: точную Plus quota можно получить server-side без локального агента на компьютере пользователя.

P0 также подтвердил edge case: weekly window может прийти без 5-hour window. В таком случае Regulator возвращает `UNAVAILABLE/null`, а не придумывает `0%`.

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
│      Streamable HTTP MCP Plugin/App        │
│                                            │
│  OAuth bearer · quota:read · read only     │
└──────────────────────┬─────────────────────┘
                       ▼
┌────────────────────────────────────────────┐
│          server-side quota backend         │
│                                            │
│  subject isolation · sealed auth · lease   │
│  official Codex RPC                        │
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

## Официальный MCP transport

`plugin/mcp_transport.py` реализует production-shaped transport на официальном MCP Python SDK.

```text
POST /mcp
   ↓
OAuth bearer gate
   ↓
verified AccessToken
   ↓ issuer + audience/resource + scope + exp/nbf + subject
trusted Plugin subject
   ↓
get_quota_snapshot({})
```

Transport намеренно использует low-level `Server`, а не high-level tool argument parser. Это важно для zero-argument contract: неожиданный `{"subject":"..."}` должен дойти до `QuotaToolHandler` и быть отвергнут, а не тихо исчезнуть при разборе аргументов.

Canonical tool:

```text
name = get_quota_snapshot
input = {}
scope = quota:read
readOnlyHint = true
destructiveHint = false
idempotentHint = true
openWorldHint = false
```

MCP dependencies закреплены точно:

```text
mcp==2.1.1
mcp-types==2.1.1
```

SDK сам монтирует Streamable HTTP endpoint и RFC 9728 protected-resource metadata. Репозиторий не реализует собственный OAuth/JWT provider: production получает reviewed `TokenVerifier` и внешний authorization server через deployment composition.

Python SDK `v2.1.1` пока не предоставляет typed top-level `securitySchemes` в Tool model. Поэтому OAuth остаётся обязательным на всём `/mcp`, а canonical policy дополнительно зеркалируется в `_meta.securitySchemes` по официальному authenticated-Python pattern OpenAI. Это compatibility layer, а не замена server-side проверки bearer token.

## Plugin package

Feature-ветка уже содержит официальный package skeleton:

```text
.codex-plugin/
  plugin.json

skills/
  openai-work-codex-regulator/
    SKILL.md
```

Packaged `SKILL.md` должен быть byte-for-byte равен корневому `SKILL.md`; отдельный validator проверяет это в CI и внутри release ZIP.

`.app.json` пока **намеренно отсутствует**. Его нельзя заполнять выдуманным идентификатором: связь с MCP добавляется только после реальной регистрации connection в ChatGPT и получения технического `plugin_asdk_app...` ID.

## Server-side backend

`plugin/quota_backend.py` содержит доказанный core для official `codex app-server`:

- managed auth readiness boundary;
- read-only `account/rateLimits/read`;
- выбор `codex` bucket;
- duration-based window semantics;
- missing-window handling;
- allow-listed normalized output;
- secret-field exclusion.

После авторизации порядок принципиален:

```text
account/login/completed(success=true)
        ↓
account/updated(authMode != null)
        ↓
account/rateLimits/read
```

P0 показал, что чтение сразу после `login/completed` может попасть в короткий race до auth reload. Backend ждёт реальное account readiness event вместо случайного sleep.

## JIT Connect/Auth

`plugin/authorization_coordinator.py` отделяет quota-account authorization от model-facing quota tool.

```text
STARTING
   ↓
WAITING_USER
   ↓
AUTHORIZED | CANCELLED | EXPIRED | FAILED
```

Повторный Connect одного subject переиспользует один pending flow. Authorization id привязан к trusted subject server-side. Cancel закрывает live auth client, а revoke сначала дожидается остановки активного worker и только затем удаляет durable auth.

MCP OAuth и Codex quota authorization — разные trust boundaries. Валидный MCP bearer идентифицирует caller для нашего backend; он не является Codex quota credential. Если MCP identity уже подтверждена, но Codex auth отсутствует, tool возвращает отдельное состояние `QUOTA_AUTH_REQUIRED / NEEDS_QUOTA_AUTH`.

## Credential isolation

Raw Plugin identity не становится именем каталога или объекта. `plugin/subject_store.py` выводит внутренний key через HMAC-SHA256 с server-held pepper:

```text
trusted Plugin subject
        ↓ HMAC(server pepper)
opaque subject key
        ↓
isolated auth state
```

`plugin/sealed_auth_store.py` хранит durable auth как sealed blob и materialize plaintext только на время операции:

```text
sealed auth.json at rest
        ↓
private temporary CODEX_HOME
        ↓
official Codex read / refresh
        ↓
reseal updated auth.json
        ↓
plaintext cleanup
```

Репозиторий не реализует собственную production-криптографию. `plugin/production_vault.py` принимает внешний audited durable store и внешний KMS/envelope provider. Test cipher намеренно помечен `production_safe=False`.

## Concurrency и recovery

`plugin/auth_concurrency.py` сериализует authorization, quota read и revoke по одному opaque subject key. Это защищает managed refresh state от lost-update race.

```text
subject A: authorize / read / revoke → one subject lease
subject B: authorize / read / revoke → independent subject lease
```

`InProcessSubjectLeaseProvider` годится только для CI/single-worker. Production требует audited cross-worker lease provider, а durable storage обязан гарантировать atomic replacement sealed blob.

`plugin/auth_recovery.py` отдельно фиксирует fail-closed recovery:

- transient transport failure получает bounded retry;
- corrupt/missing/rejected auth переходит в `NEEDS_REAUTH`;
- аварийный выход до reseal не сохраняет частично обновлённый plaintext;
- неизвестная provider error не превращается в quota snapshot и не утекает в MCP result.

## Нормализация quota

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

`primary` и `secondary` сами по себе ничего не доказывают. Смысл определяется фактической длительностью окна.

## Контроллер v2.2 остаётся ядром

Automatic telemetry меняет acquisition, а не admission math. Сохраняются:

- один quota epoch и cumulative trajectory;
- 24h normal look-ahead;
- bounded future advance до 72h той же trajectory;
- conservative observed-burn estimator;
- `PENDING_BURN`;
- независимый 5h breaker, когда 5h telemetry известна;
- `QUALITY_FLOOR=NON_NEGOTIABLE`;
- баланс `QUOTA_50_PACE_50` после hard gates.

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

В ordinary executor packet не попадают Plugin credentials, MCP plumbing, quota epoch, trajectory headroom или внутренние quota/pace scores.

## Текущее состояние

| Слой | Статус | Что есть сейчас |
| --- | --- | --- |
| v2.2 quota controller | ✅ | deterministic decision engine |
| quota normalization | ✅ | weekly/5h/other/missing semantics |
| server-side Plus P0 | ✅ | exact `codex` quota read через official Codex |
| quota backend core | ✅ | official Codex JSON-RPC + normalized output |
| subject isolation | ✅ | opaque HMAC keys, model identity override blocked |
| sealed auth lifecycle | ✅ | temporary plaintext, reseal, cleanup |
| JIT quota authorization coordinator | ✅ | subject-bound pending flow, cancel/revoke ordering |
| same-subject serialization | ✅ | lease-protected authorize/read/revoke contract |
| fail-closed auth recovery | ✅ | bounded retry, NEEDS_REAUTH, no partial reseal |
| MCP transport | ✅ | Streamable HTTP `/mcp`, bearer principal validation, `quota:read`, exact zero-arg tool |
| Plugin package skeleton | ✅ | `.codex-plugin/plugin.json` + mirrored skill, no fake app id |
| MCP runtime CI | ✅ | exact `mcp==2.1.1` transport self-test passes |
| production vault contract | ✅ | external durable store + crypto + cross-worker lease required |
| real OAuth/IdP + TokenVerifier deployment | 🟡 | deployment/security gate |
| real KMS/secret provider deployment | 🟡 | provider-independent contract готов, deployment не выбран |
| real cross-worker lease deployment | 🟡 | release gate |
| registered ChatGPT MCP connection | 🟡 | нужен реальный `plugin_asdk_app...` ID; `.app.json` до этого отсутствует |
| ChatGPT Web Connect/Auth E2E | 🟡 | plan/workspace-dependent integration test |
| refresh/revoke/logout + crash recovery E2E | 🟡 | на выбранной production infrastructure |
| threat model / security review | 🟡 | release gate |
| v3.0 release | ⛔ | PR в `main` пока рано |

## Что лежит в репозитории

```text
.codex-plugin/
  plugin.json

skills/
  openai-work-codex-regulator/
    SKILL.md

SKILL.md
references/
  10_WEEKLY_QUOTA_CONTROLLER.md
  11_ORCHESTRATION_AND_HANDOFF.md
  12_AUTONOMOUS_QUOTA_TELEMETRY.md
  13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md
  SOURCE_MAP.md

scripts/
  weekly_quota_controller.py
  quota_telemetry.py
  validate_repo.py
  validate_plugin_package.py
  package_release.py

plugin/
  quota_backend.py
  subject_store.py
  quota_service.py
  sealed_auth_store.py
  authorization_coordinator.py
  auth_concurrency.py
  auth_recovery.py
  production_vault.py
  mcp_transport.py
  get_quota_snapshot.tool.json
  requirements-mcp.txt

tests/
  TEST_CASES.md
  TEST_CASES_V2_2.md
  TEST_CASES_V3_0.md
  TEST_CASES_V3_0_SECURITY.md
  TEST_CASES_V3_0_CONCURRENCY.md
  TEST_CASES_V3_0_RECOVERY.md
  TEST_CASES_V3_0_MCP.md
```

Ранние `companion/` и `relay/` компоненты могут оставаться в feature-ветке только как research history. Validator и release contract от них не зависят.

## Проверка

```bash
python3 scripts/validate_repo.py
python3 scripts/validate_plugin_package.py
python3 plugin/quota_backend.py --self-test
python3 plugin/sealed_auth_store.py
python3 plugin/authorization_coordinator.py
python3 plugin/auth_concurrency.py
python3 plugin/auth_recovery.py
python3 plugin/production_vault.py
python3 -m pip install -r plugin/requirements-mcp.txt
python3 plugin/mcp_transport.py --self-test
python3 scripts/package_release.py
```

Сейчас regression suite содержит **218 последовательных сценариев**.

## История версий

| Версия | Что изменилось | Статус |
| --- | --- | --- |
| **v3.0** | ChatGPT Web-only control plane, exact server-side quota telemetry, sealed auth, concurrency/recovery, official MCP transport и Plugin package | В разработке |
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

Regulator не превращает неизвестное значение в удобную цифру. Missing window остаётся `UNAVAILABLE`, stale snapshot остаётся `STALE`, delayed post-pass meter остаётся `PENDING_BURN`, а недействительная или потерянная authorization — `NEEDS_REAUTH`, пока не появится достаточное evidence.

Автоматизация убирает ручную рутину, а не требования к доказательности.

---

<p align="center">
  <sub>development: <strong>v3.0</strong> · stable: <strong>v2.2</strong> · 218 regression-сценариев</sub>
</p>
