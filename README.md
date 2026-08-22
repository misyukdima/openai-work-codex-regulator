# OpenAI Work + Codex Regulator

**Version:** v1.2

`openai-work-codex-regulator` — quota-aware operational skill для выбора и контроля ChatGPT Work и Codex без дублирования agentic runs и бесконтрольного расхода общей квоты.

## Что контролирует

- routing между `CHAT`, `WORK`, `CODEX`, включая bounded Chat вместо дорогого agentic pass;
- gate `WHY_AGENTIC` / `VALUE_OUTPUT` и explicit `USER_SURFACE_OVERRIDE`;
- capability-tier routing `LUNA / TERRA / SOL` с отдельным effort/fallback и запретом постоянного generation hardcode;
- общий agentic usage / credit pool Work + Codex и других supported features;
- 5h/weekly/credits snapshot, когда они показаны аккаунтом, и его freshness по классу задачи;
- capability/permission state поверхности (Work Cloud/Local, Codex Local, browser, network);
- paid credits / Auto top-up policy и отдельную credit eligibility конкретной feature;
- project runway и burn ledger с атрибуцией `CLEAN / MIXED / UNKNOWN`;
- task classes 0–4;
- Fast / max / Ultra / model escalation;
- parallel agents;
- Work browser research, external actions, untrusted content / prompt injection, account identity, download safety;
- Scheduled Tasks, включая runaway protection;
- Codex repo/server/git/deploy discipline;
- failure handling и result verification.

## Главная идея

```text
Chat = orchestration / planning / review / bounded lookup
Work = browser / research / connected apps / deliverables / scheduled work
Codex = code / terminal / repo / tests / server

Work + Codex = shared agentic pool
```

Один gate имеет одну primary surface. Полный дубль Work ↔ Codex запрещён без отдельной VERIFY-цели. Простая задача, которую обычный Chat решает своими web/file возможностями, не должна автоматически уходить в Work.

Для Work/Codex v1.2 добавляет отдельный model-tier router:

```text
Luna  = economy / high-volume routine extraction
Terra = balanced default for most research / implementation
Sol   = quality-first consequential synthesis
```

Конкретный generation ID не является постоянной политикой: актуальная модель и effort берутся из текущего account/workspace UI и свежей first-party документации. Подробности — `references/08_MODEL_TIER_ROUTING.md`.

## Quick start

```text
Используй openai-work-codex-regulator.
Определи, нужен ли здесь ChatGPT Work или Codex, выбери минимально достаточный model tier/effort, проверь quota/runway и сформируй один bounded pass.

Задача: <описание>
```

## Перед тяжёлым pass

Желательно приложить актуальный first-party snapshot из `Settings → Usage / Usage Dashboard`:

```text
5h used/reset: <если показано>
Weekly used/reset: <если показано>
Credit balance: <если показано>
Auto top-up: ON/OFF
Paid credits allowed: YES/NO
Project runway: <например 4–6 pass>
```

Если поле не показано — пишется `unknown`; skill не должен его выдумывать. Для class 0–1 и bounded low-burn class 2 snapshot не является ритуалом — см. `references/02_SHARED_QUOTA_AND_CREDITS.md`.

Для cost-sensitive class 2–4 Work/Codex pass также фиксируется:

```text
MODEL_AVAILABILITY_SNAPSHOT=<UI/source/time|unknown>
MODEL_TIER=<LUNA|TERRA|SOL|OTHER|UNKNOWN>
EFFORT=<available effort>
WHY_THIS_MODEL=<bounded reason>
FALLBACK_MODEL=<tier/effort|none|unknown>
```

## После pass

```text
Проверь результат по openai-work-codex-regulator.

PASS_ID: ...
Отчёт агента: ...
Usage before: ...
Usage after: ...
```

## Структура

```text
SKILL.md                     executable synthesis
references/                  normative rules + official source map
references/08_MODEL_TIER_ROUTING.md  model/effort router
docs/USAGE.md                practical guide
docs/ARCHITECTURE.md         decision architecture
docs/RELEASE_PROCESS.md      release checklist and automation
tests/TEST_CASES.md          regression cases (60)
scripts/validate_repo.py     repository validation
scripts/package_release.py   release ZIP + clean round-trip validation
```

## Product facts

Product/limit/model facts are time-sensitive. `references/SOURCE_MAP.md` records the official OpenAI sources verified for v1.2 (2026-08-22). Account UI always wins for personal remaining usage and actual model/effort availability.

## Validation

```bash
python3 scripts/validate_repo.py      # source tree validation
python3 scripts/package_release.py    # release ZIP + clean round-trip validation
```
