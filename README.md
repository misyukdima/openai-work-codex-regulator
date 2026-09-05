# OpenAI Work + Codex Regulator

**Version:** v2.1

`openai-work-codex-regulator` — quota-aware operational skill для ChatGPT Work и Codex. Он выбирает правильную surface/model configuration, удерживает Work и Codex внутри общей agentic allowance и теперь управляет недельной квотой как адаптивной системой, рассчитанной на работу на протяжении всего reset window.

## v2.1: adaptive weekly quota controller

Главное изменение v2.1 — недельная квота больше не планируется статическим делением остатка.

```text
weekly meter
→ quota epoch
→ fixed rolling 24h control slice
→ observed shared-pool burn
→ conservative pass estimate
→ quality-floor admission
→ feedback re-plan
```

Контроллер:

- нормализует `WEEKLY_USED` / `WEEKLY_REMAINING` по фактической подписи UI;
- использует реальный `WEEKLY_RESET`, а не предполагаемый календарный понедельник;
- создаёт `QUOTA_EPOCH_ID` и полностью re-anchor после reset/plan/allowance change;
- держит до 10 percentage points risk reserve, но никогда больше 50% текущего остатка;
- линейно освобождает reserve в последние 72 часа, чтобы buffer не оставался неиспользованным;
- задаёт fixed 24h `CONTROL_SLICE_BUDGET_PP`;
- не выдаёт новый полный дневной budget после каждого pass;
- измеряет total shared Work/Codex burn по aggregate weekly meter;
- строит conservative `B_SAFE` по максимум пяти сопоставимым наблюдениям;
- учитывает meter granularity и pending/lagged usage;
- отдельно проверяет 5-hour window;
- резервирует Scheduled Task burn;
- не понижает качество ради экономии.

Подробная математика: `references/10_WEEKLY_QUOTA_CONTROLLER.md`.

Reference calculator:

```bash
python3 scripts/weekly_quota_controller.py \
  --weekly-used 37 \
  --hours-to-reset 96
```

## Quality floor

v2.1 вводит обязательный:

```text
QUALITY_FLOOR=NON_NEGOTIABLE
```

Если нужный pass не помещается в текущий quota slice, регулятор сначала уменьшает waste:

- reuse compact handoff;
- убирает duplicate research/audits/agents;
- сокращает non-decision-critical context;
- выбирает cheaper tier/effort только если он всё ещё independently sufficient;
- переносит lower-value work.

Он не должен:

- убирать обязательные sources/tests;
- использовать stale evidence вместо fresh;
- запускать заведомо слабую модель;
- принимать incomplete gate только ради того, чтобы «что-то сделать сегодня».

Если quality-sufficient pass не помещается:

```text
QUOTA_DECISION=DEFER_FOR_QUALITY
```

## Work + Codex shared allowance

Для agentic work:

```text
ALLOWANCE_DOMAIN=WORK_CODEX
```

Work и Codex не являются независимыми недельными корзинами. Любой подтверждённый consumer той же shared allowance уменьшает текущий slice headroom.

Отдельные Chat-model allowances и API billing не используются как запас или коэффициент Work/Codex quota.

## Core routing

```text
Chat  = orchestration / review / bounded lookup
Work  = multi-step browser/research/apps/deliverables/actions
Codex = repo/code/terminal/tests/server/deploy

ONE_GATE = ONE_PRIMARY_SURFACE
```

Model architecture v2 сохраняется:

```text
MODEL_PROFILE=TIERED
  LUNA  = high-volume routine work
  TERRA = balanced default
  SOL   = consequential synthesis

MODEL_PROFILE=ASTRA
  exceptional bounded end-to-end execution
```

Astra требует отдельного admission contract; quota pressure не является основанием искусственно понижать model capability ниже minimum sufficient.

## Weekly controller fields

```text
QUOTA_EPOCH_ID=
WEEKLY_USED=
WEEKLY_RESET=
HOURS_TO_WEEKLY_RESET=
CONTROL_SLICE_ID=
CONTROL_SLICE_START_WEEKLY_USED_PP=
CONTROL_SLICE_BUDGET_PP=
SLICE_SPENT_PP=
EFFECTIVE_SLICE_HEADROOM_PP=
BURN_ESTIMATE_WEEKLY_PP=
BURN_ESTIMATE_CONFIDENCE=
CONTINUITY_FEASIBLE=
QUALITY_FLOOR=NON_NEGOTIABLE
```

## Exact first-day example

Для fresh normalized 7-day weekly window:

```text
WEEKLY_USED = 0
WEEKLY_REMAINING = 100
HOURS_TO_RESET = 168
BASE_WEEKLY_RESERVE_PP = 10

schedulable early allowance = 90 pp

first 24h envelope =
90 * 24 / 168
= 12.857142857 pp
```

Reserve постепенно освобождается в последние 72 часа. Если фактический burn ниже plan — future daily envelopes растут. Если выше — уменьшаются.

Это feedback control: он не предполагает фиксированную цену одного pass.

## Reset behavior

Любой reset/allowance change создаёт новый quota epoch.

Платный weekly reset по умолчанию запрещён:

```text
PAID_WEEKLY_RESET_ALLOWED=NO
```

Если пользователь отдельно разрешает покупку, это class-4 money action. После применения reset старый slice ledger уничтожается и controller строится заново из current first-party UI.

## Repository structure

```text
SKILL.md
references/
  01_SURFACE_ROUTING.md
  02_SHARED_QUOTA_AND_CREDITS.md
  03_TASK_CLASSIFICATION.md
  04_RUNWAY_AND_BURN.md
  05_WORK_BROWSER_AND_ACTIONS.md
  06_CODEX_TECHNICAL_WORK.md
  07_FAILURES_AND_RECOVERY.md
  08_MODEL_TIER_ROUTING.md
  09_ASTRA_EXECUTION.md
  10_WEEKLY_QUOTA_CONTROLLER.md
  SOURCE_MAP.md
docs/
scripts/
  validate_repo.py
  package_release.py
  weekly_quota_controller.py
tests/TEST_CASES.md
```

## Validation

```bash
python3 scripts/validate_repo.py
python3 scripts/weekly_quota_controller.py \
  --weekly-used 0 \
  --hours-to-reset 168 \
  --self-test
python3 scripts/package_release.py
```

The repository validator runs the weekly-controller self-test as part of v2.1 validation.

## Product facts

Usage/reset/model facts are time-sensitive. First-party account UI remains authoritative for actual remaining usage and reset timestamps.

`references/SOURCE_MAP.md` records the official OpenAI sources re-verified for v2.1 on 2026-09-05.
