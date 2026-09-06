<div align="center">

# OpenAI Work + Codex Regulator

**Skill-регулятор для ChatGPT, Work и Codex: держит под контролем общую квоту, темп работы, выбор модели и границы каждого запуска.**

[![Версия](https://img.shields.io/badge/версия-v2.2-0969da)](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2)
[![Проверка](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml/badge.svg)](https://github.com/misyukdima/openai-work-codex-regulator/actions/workflows/validate.yml)
[![Тесты](https://img.shields.io/badge/regression_tests-115-success)](tests/)

[Последний релиз](https://github.com/misyukdima/openai-work-codex-regulator/releases/latest) · [Как использовать](docs/USAGE.md) · [Архитектура](docs/ARCHITECTURE.md) · [История изменений](CHANGELOG.md)

</div>

## Что это

`openai-work-codex-regulator` управляет агентской работой между тремя поверхностями ChatGPT:

- **Chat** планирует, проверяет и оркестрирует;
- **Work** берёт длинные браузерные и многошаговые задачи;
- **Codex** работает с кодом, репозиториями, терминалом, тестами и деплоем.

Регулятор решает, куда отправить следующий gate, какую модель и effort выбрать, сколько общей Work/Codex-квоты разумно потратить сейчас и когда выгоднее продолжить работу другим способом.

Главная идея проста: квота нужна не ради самой экономии. Она должна дожить до reset, но рабочий процесс тоже не должен вставать без веской причины.

## Зачем он нужен

Без регулятора длинный проект легко уходит в одну из двух крайностей. Либо Work/Codex быстро съедают недельный лимит, либо система начинает слишком беречь остаток и откладывает полезную работу.

Проект держит середину:

- считает Work и Codex общей `ALLOWANCE_DOMAIN=WORK_CODEX`;
- сохраняет `QUALITY_FLOOR=NON_NEGOTIABLE`;
- балансирует сохранение квоты и темп проекта как `QUOTA_50_PACE_50`;
- не заставляет downstream Codex или Work иметь этот skill;
- передаёт между поверхностями компактный self-contained handoff;
- сохраняет scope, permissions, rollback, tests и evidence как обязательные границы.

## Актуальная версия: v2.2

`v2.2` появилась после полевых тестов `v2.1`. Предыдущий контроллер слишком жёстко воспринимал 24-часовое окно и мог отправить проект ждать сутки, хотя критический путь уже был заблокирован.

Теперь 24 часа служат обычным ориентиром, а не таймером ожидания. Контроллер строит одну недельную cumulative trajectory и, когда это оправдано, может взять ограниченную часть будущего headroom. Решение сравнивает два риска: что случится с квотой, если запустить pass сейчас, и что случится с проектом, если его отложить.

Второе заметное изменение касается orchestration. Если регулятор загружен в Chat, а реализация уходит в Codex, Chat сам принимает quota/model/admission-решение. Codex получает готовый execution packet и не обязан искать или устанавливать `openai-work-codex-regulator`.

Подробнее: [CHANGELOG v2.2](CHANGELOG.md#22--2026-09-06) и [контракт handoff](references/11_ORCHESTRATION_AND_HANDOFF.md).

## Как принимается решение

```text
запрос
  ↓
класс риска + требуемый gate
  ↓
Chat / Work / Codex
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

Это одна из главных частей `v2.2`.

```text
Chat + regulator
      ↓
quota / routing / model / admission
      ↓
self-contained handoff
      ↓
Work или Codex
      ↓
execution + evidence
      ↓
Chat принимает следующее решение
```

Downstream executor получает цель, fact pack, read/write scope, no-touch, tests, rollback и stop conditions. Внутренняя математика квоты остаётся у оркестратора.

```text
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

## Установка

1. Откройте [Releases](https://github.com/misyukdima/openai-work-codex-regulator/releases/latest).
2. Скачайте `openai-work-codex-regulator-v2.2.zip`.
3. Распакуйте архив в каталог skills вашей рабочей среды.
4. Entry point проекта: `openai-work-codex-regulator/SKILL.md`.

К каждому современному релизу приложен SHA-256 checksum, чтобы архив можно было проверить после скачивания.

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
  SOURCE_MAP.md                       first-party источники

docs/                                 архитектура и использование
scripts/                              validation и controller tooling
tests/                                regression cases
```

## Проверка репозитория

```bash
python3 scripts/validate_repo.py
python3 scripts/weekly_quota_controller.py \
  --anchor-weekly-used 0 \
  --anchor-hours-to-reset 168 \
  --hours-to-reset-now 168 \
  --current-weekly-used 0 \
  --self-test
python3 scripts/package_release.py
```

Текущая ветка `main` проверяется GitHub Actions. В `v2.2` набор содержит **115 regression tests**, включая сценарии с quota trajectory, future advance и Chat -> Codex handoff без установленного downstream skill.

## История версий

| Версия | Что изменилось | Релиз |
| --- | --- | --- |
| **v2.2** | Баланс квоты и рабочего темпа, cumulative trajectory, bounded future advance, независимый downstream executor | [Открыть](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.2) |
| **v2.1** | Адаптивный недельный quota controller, burn estimation, 24h control slice, quality floor | [Открыть](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.1) |
| **v2.0** | Отдельный профиль Astra, allowance domains, steering и safety-pause semantics | [Открыть](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v2.0) |
| **v1.2** | Маршрутизация Luna / Terra / Sol и выбор effort по сложности задачи | [Открыть](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.2) |
| **v1.1** | Quota-saving routing, prompt-injection защита, account checks и release hardening | [Открыть](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v1.1) |
| **v1.0** | Первая версия: surface routing, shared pool, risk classes, browser/Codex discipline | [CHANGELOG](CHANGELOG.md#10--2026-08-21) |

Полная техническая история хранится в [CHANGELOG.md](CHANGELOG.md).

## Документация

- [SKILL.md](SKILL.md) - основной исполняемый регламент.
- [docs/USAGE.md](docs/USAGE.md) - примеры использования и рабочие паттерны.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - устройство регулятора.
- [references/SOURCE_MAP.md](references/SOURCE_MAP.md) - карта first-party OpenAI источников и времязависимых фактов.
- [SECURITY.md](SECURITY.md) - правила безопасности.
- [CONTRIBUTING.md](CONTRIBUTING.md) - правила изменений в репозитории.

## Важное про квоту

Регулятор не угадывает расход по токенам и не обещает точный burn заранее. Для реального остатка и времени reset источником истины остаются текущий first-party интерфейс OpenAI и данные аккаунта. Внутренняя математика проекта нужна для планирования между подтверждёнными снимками usage.

---

<p align="center">
  <sub>Текущая версия: <strong>v2.2</strong> · проверено 115 regression-сценариями</sub>
</p>
