# OpenAI Work + Codex Regulator

**Version:** v2.0

`openai-work-codex-regulator` — quota-aware operational skill для выбора и контроля ChatGPT Work и Codex без дублирования agentic runs, бесконтрольного расхода общей квоты и необоснованной эскалации к самым дорогим моделям.

## v2.0: GPT-6 Astra major update

v2.0 перестраивает model/execution policy под GPT-6 Astra и текущую архитектуру ChatGPT Work + Codex.

Главные изменения:

- Astra больше не трактуется как ещё один `Luna / Terra / Sol` tier: это отдельный `MODEL_PROFILE=ASTRA` для hardest end-to-end work;
- Astra не является default. Для неё требуется `ASTRA_JUSTIFIED=YES`, bounded scope и доказательство, что tiered model недостаточна или создаст больше rework/burn;
- отделён `Chat / GPT-6 Pro` allowance от shared `Work + Codex` allowance через `ALLOWANCE_DOMAIN`;
- добавлены Astra-specific quota/burn gates: Astra может расходовать Work/Codex allowance быстрее, чем GPT-5.6 Sol; Fast требует отдельного cost justification;
- добавлен Codex client-readiness gate для Astra (`CODEX_CLIENT_ASTRA_READY`), потому что доступ зависит не только от plan/UI, но и от совместимой версии клиента;
- добавлена steering policy: mid-turn изменение требований повторно проверяет gate, scope, class и approvals;
- добавлен `SAFETY_STATE=PAUSED_FOR_REVIEW`: safety pause/stop Astra нельзя обходить повтором через другую surface/model;
- добавлен Astra cyber-sensitive authorization gate: более высокая capability никогда не расширяет разрешённый target/scope;
- сохранены `ONE_GATE = ONE_PRIMARY_SURFACE`, class 0–4, read-only-first для class 4, exact write scope, human approvals, prompt-injection defense, burn attribution и two-attempt rule;
- добавлена нормативная ссылка `references/09_ASTRA_EXECUTION.md` и новый набор regression tests.

## Главная модель принятия решения

```text
Chat = orchestration / planning / review / bounded lookup
Work = browser / research / connected apps / deliverables / scheduled work
Codex = code / terminal / repo / tests / server

Work + Codex = shared agentic allowance domain
Chat Pro-model allowance != Work/Codex allowance
```

Один gate имеет одну primary surface. Полный дубль Work ↔ Codex запрещён без отдельной VERIFY-цели.

## Model routing

Обычная маршрутизация сохраняет tiered family:

```text
Luna  = economy / high-volume routine extraction
Terra = balanced default for most research / implementation
Sol   = quality-first consequential synthesis
```

Astra находится над этой осью как exceptional profile:

```text
MODEL_PROFILE=ASTRA
ASTRA_JUSTIFIED=YES
ASTRA_SCOPE_BOUND=<bounded end-to-end gate>
```

Использовать Astra, когда задача действительно требует сложной многошаговой orchestration, heterogeneous tool use, длинной цепочки зависимостей или consequential synthesis, где более лёгкий путь создаёт существенный риск повторных дорогостоящих проходов.

Не выбирать Astra только потому, что задача важная, новая модель доступна или пользователь хочет «самое сильное».

Подробности: `references/08_MODEL_TIER_ROUTING.md` и `references/09_ASTRA_EXECUTION.md`.

## Quick start

```text
Используй openai-work-codex-regulator.
Определи, нужен ли здесь ChatGPT Work или Codex, выбери минимально достаточный model profile/tier/effort, проверь allowance domain, quota/runway и сформируй один bounded pass.

Задача: <описание>
```

## Перед тяжёлым Work/Codex pass

```text
SNAPSHOT_AT=<time>
PLAN=<plan|unknown>
ALLOWANCE_DOMAIN=WORK_CODEX
5h used/reset: <если показано>
Weekly used/reset: <если показано>
Credit balance: <если показано>
Auto top-up: ON/OFF/unknown
Paid credits allowed: YES/NO
Project runway: <Pmin..Pmax>

MODEL_AVAILABILITY_SNAPSHOT=<UI/source/time|unknown>
MODEL_PROFILE=<TIERED|ASTRA|OTHER|UNKNOWN>
MODEL_TIER=<LUNA|TERRA|SOL|N/A|OTHER|UNKNOWN>
EFFORT=<current available effort>
WHY_THIS_MODEL=<bounded reason>
FALLBACK_MODEL=<profile/tier/effort|none|unknown>
```

При Astra дополнительно:

```text
ASTRA_JUSTIFIED=<YES|NO>
ASTRA_SCOPE_BOUND=<exact gate>
CODEX_CLIENT_ASTRA_READY=<YES|NO|UNKNOWN|N/A>
SAFETY_STATE=<NORMAL|PAUSED_FOR_REVIEW|BLOCKED|UNKNOWN>
```

## Структура

```text
SKILL.md                            executable synthesis
references/01..08                  core normative rules
references/09_ASTRA_EXECUTION.md   Astra admission / steering / safety contract
references/SOURCE_MAP.md           official source provenance
docs/USAGE.md                      practical guide
docs/ARCHITECTURE.md               decision architecture
docs/RELEASE_PROCESS.md            release checklist and automation
tests/TEST_CASES.md                 regression cases
scripts/validate_repo.py            repository validation
scripts/package_release.py          release ZIP + clean round-trip validation
```

## Product facts

Model names, rollout, client minimums, rate multipliers and plan availability are time-sensitive. `references/SOURCE_MAP.md` records first-party OpenAI sources verified for v2.0 on 2026-09-05. Actual account/workspace UI remains authoritative for personal remaining usage and current availability.

## Validation

```bash
python3 scripts/validate_repo.py
python3 scripts/package_release.py
```
