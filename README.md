<div align="center">

# OpenAI Work + Codex Regulator

**Skill для ChatGPT Web, который оркестрирует Work/Codex и автоматически учитывает их общую квоту без регулярного копирования процентов в чат.**

[![Разработка](https://img.shields.io/badge/development-v3.0-8250df)](CHANGELOG.md#30--in-development)
[![Stable](https://img.shields.io/badge/stable-v2.2-0969da)](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2)
[![Проверка](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml/badge.svg)](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml)
[![Тесты](https://img.shields.io/badge/regression_tests-240-success)](tests/)

[Последний стабильный релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/latest) · [Использование](docs/USAGE.md) · [Архитектура](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)

</div>

> **v3.0 разрабатывается в `feat/v3-autonomous-quota-telemetry`.** `main` и stable release остаются на `v2.2` до реального ChatGPT Web E2E, security review, Pull Request и review.

## Что это

`openai-work-codex-regulator` работает **только в ChatGPT Web**. ChatGPT остаётся control plane: понимает задачу, выбирает Chat, Work или Codex, принимает quota/model/admission-решение и формирует self-contained handoff.

Work и Codex ничего не устанавливают и не загружают из этого репозитория. Для них skill уже подготовил execution packet.

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

## MCP transport

`plugin/mcp_transport.py` реализует production-shaped Streamable HTTP transport на официальном MCP Python SDK.

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

Transport использует low-level `Server`, чтобы неожиданный `{"subject":"..."}` дошёл до security boundary и был отвергнут, а не исчез при разборе аргументов.

## OIDC/JWKS verifier

`plugin/oidc_token_verifier.py` закрывает resource-server сторону production OAuth без превращения репозитория в authorization server.

Проверяются:

- точный HTTPS issuer;
- точный audience/resource;
- `quota:read`;
- `exp` и `nbf`;
- explicit asymmetric algorithm allow-list;
- обязательный `kid`;
- отказ от token-supplied `jku`/`x5u`;
- bounded JWKS cache;
- обязательный стабильный `sub`;
- privacy-minimized downstream claims.

Direct dependency:

```text
PyJWT[crypto]==2.13.0
```

Ошибки подписи, discovery/JWKS и parsing fail-closed и не становятся model-visible diagnostics.

## IdP deployment preflight

`plugin/idp_preflight.py` и `plugin/production_runtime.py` закрывают следующий слой между статическим OIDC verifier и реальным deployment.

Первая staging-цель — **Auth0**, но runtime остаётся provider-neutral и читает только `REGULATOR_OIDC_*` / `REGULATOR_MCP_RESOURCE_URL`.

Preflight проверяет до старта MCP:

```text
exact HTTPS issuer
authorization_endpoint=https
 token_endpoint=https
jwks_uri=https
PKCE S256
quota:read
CIMD | DCR | reviewed predefined client
```

При этом статический preflight не подменяет live verification. Отдельными обязательными E2E gates остаются:

```text
resource parameter echoed and bound to access-token audience
exact ChatGPT redirect URI allow-listed
authorized token accepted by public /mcp
wrong-resource token rejected by public /mcp
```

Без этих доказательств deployment не считается production-ready.

Безопасный пример staging-профиля лежит в `deployment/auth0-staging.example.json`. В репозитории нет tenant-specific `client_secret`, access/refresh tokens или private keys.

Подробный maintainer flow: [`docs/IDP_DEPLOYMENT.md`](docs/IDP_DEPLOYMENT.md).

## Plugin package

Feature-ветка содержит официальный package skeleton:

```text
.codex-plugin/
  plugin.json

skills/
  openai-work-codex-regulator/
    SKILL.md
```

Packaged `SKILL.md` должен быть byte-for-byte равен корневому `SKILL.md`.

`.app.json` пока **намеренно отсутствует**. Его нельзя заполнять выдуманным идентификатором: связь с MCP добавляется только после реальной регистрации connection в ChatGPT и получения настоящего `plugin_asdk_app...` ID.

## Credential lifecycle

Server-side слой включает:

- `plugin/quota_backend.py` — official `codex app-server`, auth readiness, `account/rateLimits/read`, normalization;
- `plugin/subject_store.py` — opaque HMAC subject keys;
- `plugin/sealed_auth_store.py` — sealed `auth.json`, temporary `CODEX_HOME`, reseal и cleanup;
- `plugin/authorization_coordinator.py` — JIT quota-account authorization;
- `plugin/auth_concurrency.py` — same-subject serialization;
- `plugin/auth_recovery.py` — bounded retry, `NEEDS_REAUTH`, no partial reseal;
- `plugin/production_vault.py` — external durable store + KMS/envelope crypto + cross-worker lease contract.

Репозиторий не реализует собственную production-криптографию и не хранит provider secrets.

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
| MCP transport | ✅ | Streamable HTTP `/mcp`, bearer boundary, exact zero-arg tool |
| OIDC/JWKS verifier | ✅ | issuer/audience/scope/lifetime/algorithm verification |
| IdP discovery preflight | ✅ | PKCE/scope/endpoints/registration-mode checks |
| production runtime composition | ✅ | fail-closed metadata preflight before MCP startup |
| Auth0 staging profile | ✅ | secret-free provider profile and live-gate checklist |
| strict v3 release validator | ✅ | 240 contiguous regressions + MCP/OIDC/IdP/package gates |
| Plugin package skeleton | ✅ | `.codex-plugin/plugin.json` + mirrored skill, no fake app id |
| real Auth0 tenant + public HTTPS MCP | 🟡 | следующий ручной staging gate |
| real KMS/secret provider deployment | 🟡 | provider-independent contract готов |
| real cross-worker lease deployment | 🟡 | release gate |
| registered ChatGPT MCP connection | 🟡 | нужен настоящий `plugin_asdk_app...` ID |
| ChatGPT Web Connect/Auth E2E | 🟡 | plan/workspace-dependent integration test |
| refresh/revoke/logout + crash recovery E2E | 🟡 | на выбранной production infrastructure |
| threat model / security review | 🟡 | release gate |
| v3.0 release | ⛔ | PR в `main` пока рано |

## Проверка

```bash
python3 scripts/validate_repo.py
python3 scripts/validate_plugin_package.py
python3 scripts/validate_v3_release_contract.py
python3 plugin/quota_backend.py --self-test
python3 plugin/sealed_auth_store.py
python3 plugin/authorization_coordinator.py
python3 plugin/auth_concurrency.py
python3 plugin/auth_recovery.py
python3 plugin/production_vault.py
python3 -m pip install -r plugin/requirements-mcp.txt
python3 plugin/mcp_transport.py --self-test
python3 -m pip install -r plugin/requirements-auth.txt
python3 plugin/oidc_token_verifier.py --self-test
python3 plugin/idp_preflight.py --self-test
python3 plugin/production_runtime.py --self-test
python3 scripts/package_release.py
```

Сейчас regression suite содержит **240 последовательных сценариев**.

## История версий

| Версия | Что изменилось | Статус |
| --- | --- | --- |
| **v3.0** | ChatGPT Web-only control plane, exact server-side quota telemetry, sealed auth, official MCP transport, OIDC/JWKS verification и IdP deployment preflight | В разработке |
| **v2.2** | Баланс quota/workflow pace, cumulative trajectory, bounded future advance, independent executor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2) |
| **v2.1** | Adaptive weekly controller, burn estimation, 5h breaker, quality floor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.1) |
| **v2.0** | Astra profile, allowance domains, steering и safety semantics | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.0) |
| **v1.2** | Luna / Terra / Sol routing и effort selection | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.2) |
| **v1.1** | Quota-saving routing, security и release hardening | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.1) |
| **v1.0** | Surface routing, shared pool, risk classes, execution discipline | [CHANGELOG](CHANGELOG.md#10--2026-08-21) |

## Документация

- [SKILL.md](SKILL.md) — executable ChatGPT Web contract.
- [docs/USAGE.md](docs/USAGE.md) — рабочий сценарий.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура v3.0.
- [docs/IDP_DEPLOYMENT.md](docs/IDP_DEPLOYMENT.md) — maintainer-side OAuth/IdP staging.
- [references/12_AUTONOMOUS_QUOTA_TELEMETRY.md](references/12_AUTONOMOUS_QUOTA_TELEMETRY.md) — automatic telemetry semantics.
- [references/13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md](references/13_CHATGPT_PLUGIN_AND_QUOTA_BACKEND.md) — Plugin/backend security boundary.
- [references/SOURCE_MAP.md](references/SOURCE_MAP.md) — provenance.
- [SECURITY.md](SECURITY.md) — политика безопасности.
- [CONTRIBUTING.md](CONTRIBUTING.md) — правила изменений.

## Важное про точность

Regulator не превращает неизвестное значение в удобную цифру. Missing window остаётся `UNAVAILABLE`, stale snapshot остаётся `STALE`, delayed post-pass meter остаётся `PENDING_BURN`, а недействительная или потерянная authorization — `NEEDS_REAUTH`, пока не появится достаточное evidence.

Автоматизация убирает ручную рутину, а не требования к доказательности.

---

<p align="center">
  <sub>development: <strong>v3.0</strong> · stable: <strong>v2.2</strong> · 240 regression-сценариев</sub>
</p>
