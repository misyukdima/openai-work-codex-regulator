<div align="center">

# OpenAI Work + Codex Regulator

**Skill-регулятор для ChatGPT, Work и Codex: управляет общей квотой, темпом работы, выбором модели и границами каждого запуска.**

[![Разработка](https://img.shields.io/badge/development-v3.0-8250df)](CHANGELOG.md#30--in-development)
[![Stable](https://img.shields.io/badge/stable-v2.2-0969da)](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2)
[![Проверка](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml/badge.svg)](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml)
[![Тесты](https://img.shields.io/badge/regression_tests-135-success)](tests/)

[Последний стабильный релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/latest) · [Как использовать](docs/USAGE.md) · [Архитектура](docs/ARCHITECTURE.md) · [История изменений](CHANGELOG.md)

</div>

> **v3.0 находится в разработке в отдельной feature-ветке.** Стабильный `main` и опубликованный релиз остаются на `v2.2` до завершения реализации, Pull Request и review.

## Что это

`openai-work-codex-regulator` управляет агентской работой между тремя поверхностями ChatGPT:

- **Chat** — предпочтительный control plane: планирует, проверяет и оркестрирует;
- **Work** берёт длинные браузерные и многошаговые задачи;
- **Codex** работает с кодом, репозиториями, терминалом, тестами и деплоем.

Регулятор решает, куда отправить следующий gate, какую модель и effort выбрать, сколько общей Work/Codex-квоты разумно потратить сейчас и когда выгоднее продолжить работу другим способом.

Главная идея: квота нужна не ради самой экономии. Она должна дожить до reset, но рабочий процесс тоже не должен вставать без веской причины.

## Что меняется в v3.0

До `v2.2` актуальный quota snapshot обычно приходил от пользователя или из текущего контекста. Это работало, но заставляло человека периодически открывать Usage, смотреть проценты/reset и переносить их в разговор.

`v3.0` меняет сам UX:

```text
AUTO_QUOTA_TELEMETRY=DEFAULT
MANUAL_QUOTA_INPUT=FALLBACK_ONLY
CHATGPT_PRIMARY_ORCHESTRATOR=YES
ZERO_MAINTENANCE_USER_SETUP=REQUIRED
```

В нормальном сценарии ChatGPT сам получает свежую quota telemetry через доступный connected tool, перед quota-sensitive запуском обновляет controller state и продолжает orchestration. Ручной snapshot остаётся аварийным fallback, а не обязанностью пользователя.

При этом математика `v2.2` не выбрасывается. Epoch-anchored trajectory, bounded future advance, burn estimator, 5h breaker, hard quality floor и баланс `QUOTA_50_PACE_50` остаются decision engine.

## Почему нужен отдельный telemetry layer

Browser/cloud ChatGPT не может просто «вылезти» на компьютер пользователя, запустить локальный `codexbar` или прочитать `127.0.0.1`.

Поэтому архитектура строится так:

```text
local quota sensor
        ↓
sanitized snapshot
        ↓
Chat-accessible connected app/tool
        ↓
ChatGPT regulator
        ↓
v2.2 quota controller
        ↓
Work / Codex
```

```text
CHAT_LOCALHOST_ASSUMPTION=FORBIDDEN
CHAT_LOCAL_SHELL_ASSUMPTION=FORBIDDEN
```

ChatGPT остаётся мозгом системы. Telemetry provider — только датчик.

## CodexBar в v3.0

CodexBar используется как первый reference sensor, потому что умеет отдавать Codex usage в структурированном JSON. Но это **не обязательная пользовательская зависимость** и не новый quota controller.

Ветка уже содержит `scripts/quota_telemetry.py`, который:

- принимает CodexBar-compatible JSON;
- нормализует weekly и 5h windows;
- классифицирует окна по длительности, а не по `primary/secondary`;
- отслеживает freshness;
- не читает OAuth tokens/cookies сам;
- не принимает решения о запуске Work/Codex.

Ключевой invariant:

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
```

```text
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
```

## Как принимается решение

```text
запрос
  ↓
класс риска + требуемый gate
  ↓
Chat / Work / Codex
  ↓
automatic quota refresh when needed
  ↓
minimum sufficient model
  ↓
safety + permissions + quality
  ↓
weekly quota trajectory
  ↓
quota risk ↔ workflow pace risk
  ↓
launch / launch with advance / productive alternative / defer / stop
```

Для обычного запуска действует 24-часовой look-ahead. Если pass дороже текущего базового headroom, регулятор может рассмотреть bounded advance из будущего окна. Верхняя граница остаётся жёсткой: высокий pace risk не превращает недельную квоту в безлимитную.

## Control plane и execution plane

```text
Chat + regulator
      ↓
quota telemetry / routing / model / admission
      ↓
self-contained handoff
      ↓
Work или Codex
      ↓
execution + evidence
      ↓
Chat принимает следующее решение
```

Downstream executor получает цель, fact pack, read/write scope, no-touch, tests, rollback и stop conditions. Внутренняя математика квоты и telemetry plumbing остаются у оркестратора.

```text
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

Прямой запуск regulator в Codex или Work остаётся поддержанным standalone-режимом. Это portability feature, а не отказ от ChatGPT-first архитектуры.

## Zero-maintenance цель

Финальная `v3.0` не считается готовой, если обычному пользователю для штатной установки приходится:

- открывать Terminal;
- устанавливать Homebrew;
- отдельно настраивать CodexBar;
- править JSON/YAML;
- копировать OAuth/API tokens;
- вручную настраивать localhost или tunnel;
- разбираться в MCP;
- периодически сообщать ChatGPT состояние квоты.

Технические debug/fallback пути могут существовать для разработчиков, но не должны становиться обычным onboarding.

## Что лежит в репозитории

```text
SKILL.md                              основной исполняемый контракт
references/                           нормативные правила
  01_SURFACE_ROUTING.md               Chat / Work / Codex routing
  02_SHARED_QUOTA_AND_CREDITS.md      общая квота и credits
  03_TASK_CLASSIFICATION.md           классы риска 0-4
  04_RUNWAY_AND_BURN.md               runway и burn accounting
  05_WORK_BROWSER_AND_ACTIONS.md      браузер и внешние действия
  06_CODEX_TECHNICAL_WORK.md          код, Git, серверы, deploy
  07_FAILURES_AND_RECOVERY.md         ошибки и recovery
  08_MODEL_TIER_ROUTING.md            Luna / Terra / Sol
  09_ASTRA_EXECUTION.md               Astra admission
  10_WEEKLY_QUOTA_CONTROLLER.md       недельный quota controller
  11_ORCHESTRATION_AND_HANDOFF.md     self-contained handoff
  12_AUTONOMOUS_QUOTA_TELEMETRY.md    автоматическая quota telemetry
  SOURCE_MAP.md                       provenance

docs/                                 архитектура и использование
scripts/
  weekly_quota_controller.py          математический decision engine
  quota_telemetry.py                  telemetry normalizer
tests/                                regression cases
```

## Проверка ветки v3.0

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

Ветка `v3.0` должна пройти **135 regression tests** до Pull Request в `main`.

## Текущее состояние разработки

Уже реализовано на feature-ветке:

- v3.0 telemetry policy;
- ChatGPT-first/cloud-local boundary;
- manual-as-fallback semantics;
- normalized quota tool contract;
- CodexBar-compatible normalizer;
- freshness/window classification;
- regression coverage и validator integration.

До merge/release readiness ещё нужен конечный zero-friction Chat-accessible companion/app transport. Пока этот слой не реализован и не проверен end-to-end, `v3.0` не должна сливаться в `main`.

## История версий

| Версия | Что изменилось | Статус |
| --- | --- | --- |
| **v3.0** | Autonomous quota telemetry, ChatGPT-first bridge contract, manual fallback, zero-maintenance UX | В разработке |
| **v2.2** | Баланс квоты и рабочего темпа, cumulative trajectory, bounded future advance, независимый downstream executor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2) |
| **v2.1** | Адаптивный недельный quota controller, burn estimation, 24h control slice, quality floor | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.1) |
| **v2.0** | Отдельный профиль Astra, allowance domains, steering и safety-pause semantics | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.0) |
| **v1.2** | Маршрутизация Luna / Terra / Sol и выбор effort по сложности задачи | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.2) |
| **v1.1** | Quota-saving routing, prompt-injection защита, account checks и release hardening | [Релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.1) |
| **v1.0** | Первая версия: surface routing, shared pool, risk classes, browser/Codex discipline | [CHANGELOG](CHANGELOG.md#10--2026-08-21) |

## Документация

- [SKILL.md](SKILL.md) — основной исполняемый регламент.
- [docs/USAGE.md](docs/USAGE.md) — рабочие паттерны.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — устройство регулятора.
- [references/12_AUTONOMOUS_QUOTA_TELEMETRY.md](references/12_AUTONOMOUS_QUOTA_TELEMETRY.md) — контракт автономной telemetry.
- [references/SOURCE_MAP.md](references/SOURCE_MAP.md) — provenance и времязависимые факты.
- [SECURITY.md](SECURITY.md) — политика безопасности.
- [CONTRIBUTING.md](CONTRIBUTING.md) — правила изменений.

## Важное про квоту

Regulator не угадывает расход по токенам и не обещает точный burn заранее. Автоматизация v3.0 меняет способ доставки фактического meter state в control plane, а не превращает приблизительные расчёты в источник истины.

---

<p align="center">
  <sub>В разработке: <strong>v3.0</strong> · stable: <strong>v2.2</strong> · 135 regression-сценариев</sub>
</p>
