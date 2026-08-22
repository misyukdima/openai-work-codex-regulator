# Model tier routing

**Policy version:** v1.2  
**Verified:** 2026-08-22

Эта ссылка задаёт нормативный выбор capability tier и reasoning effort для ChatGPT Work и Codex. Она дополняет раздел 10 `SKILL.md`: постоянные generation-specific model IDs не хардкодятся, а выбор делается по durable capability tier, фактической доступности в текущем UI и задаче.

## 1. Source-backed facts

По официальной документации OpenAI семейство GPT-5.6 использует три capability tier:

- `Sol` — flagship tier;
- `Terra` — balanced/lower-cost tier для everyday work;
- `Luna` — fastest / lowest-cost tier.

OpenAI отдельно описывает Sol/Terra/Luna как durable capability tiers: номер поколения может меняться, а названия tier могут развиваться независимо. Поэтому skill может использовать `SOL|TERRA|LUNA` как устойчивые роли маршрутизации, но не должен навсегда зашивать конкретный `GPT-x.y-*` generation ID.

На дату проверки Plus/Pro/Business/Enterprise в ChatGPT Work и Codex могут выбирать Sol, Terra и Luna и доступный effort; фактический account/workspace UI остаётся источником истины. `max` и `ultra` являются time-sensitive режимами и используются только если реально доступны текущему plan/product.

Текущие rate cards подтверждают существенную разницу расхода между tier. Числа не являются постоянным operational threshold: перед cost-sensitive pass использовать свежую first-party rate card / account UI.

## 2. Normalized model snapshot

Перед class 2–4 Work/Codex pass, когда выбор модели заметно влияет на burn или качество, фиксировать:

```text
MODEL_AVAILABILITY_SNAPSHOT=<UI/source/time|unknown>
MODEL_TIER=<LUNA|TERRA|SOL|OTHER|UNKNOWN>
EFFORT=<light|medium|high|extra-high|max|ultra|other|unknown>
WHY_THIS_MODEL=<one bounded reason>
FALLBACK_MODEL=<tier/effort|none|unknown>
MODEL_COST_POSTURE=<ECONOMY|BALANCED|QUALITY_FIRST>
```

Не придумывать доступность tier/effort. Если UI не показывает вариант — считать его недоступным для текущего pass.

## 3. Default routing policy

### LUNA — economy / high-volume routine work

Предпочитать `LUNA`, когда основная ценность — объём, скорость и дешёвая обработка, а каждая единица работы низкорисковая и проверяемая:

- массовый reconnaissance по заранее заданным surfaces;
- SERP/URL discovery;
- extraction из большого числа однотипных страниц;
- первичная фильтрация и дедупликация кандидатов;
- классификация по заранее заданной schema;
- recurring monitoring с простым meaningful-change filter;
- механическое структурирование уже собранного evidence.

Типичный effort: `medium`; `high` — только при доказанной неоднозначности классификации.

Не использовать Luna как автоматический выбор для legal/security/production synthesis только ради экономии.

### TERRA — default balanced Work/Codex tier

`TERRA` — стандартный выбор для большинства содержательных class 2–3 agentic pass, если не доказана необходимость Sol:

- multi-source public-web research;
- buyer-demand discovery и lead qualification;
- конкурентный анализ;
- сравнение офферов / условий / фактов;
- browser research с несколькими связанными ветками;
- обычная реализация/отладка в Codex;
- funnel/operations analysis;
- synthesis, где ошибки обратимы и результат будет проверен человеком.

Типичный effort: `medium` или `high`.

Если задача не очевидно Luna и не требует Sol, начинать с Terra.

### SOL — quality-first / consequential synthesis

Выбирать `SOL`, когда цена ошибки или сложность синтеза существенно выше экономии quota:

- legal + commercial synthesis;
- security/production decisions;
- противоречащие authoritative sources;
- сложная архитектура или incident reasoning;
- финальная стратегия на основе большого неоднородного fact pack;
- class 4 read-only analysis, где неверный вывод способен привести к деньгам, данным, production или репутационному риску;
- задачи, где Terra уже дала недостаточный результат и есть новая гипотеза, а не просто повтор того же prompt.

Типичный effort: `high`. Более сильный effort требует отдельного обоснования.

Sol не является default для всей важной работы: важность задачи сама по себе не отменяет принцип минимально достаточного tier.

## 4. Effort routing

Effort выбирать отдельно от tier.

- `light/medium` — extraction, классификация, bounded routine work;
- `medium/high` — основной research, implementation, comparison, synthesis;
- `high` — сложные/последовательные решения, противоречия, consequential read-only analysis;
- `extra-high/max` — только bounded задача с `WHY_MAX`; нельзя включать «на всякий случай»;
- `ultra` — только если текущий UI/plan действительно предлагает режим, задача естественно параллелизуема, есть quota/runway и есть `WHY_ULTRA`.

Обязательные поля при `max`:

```text
WHY_MAX=<почему high недостаточно>
MAX_SCOPE_BOUND=<что именно ограничивает работу>
```

При `ultra` дополнительно:

```text
WHY_ULTRA=<почему параллельная multi-agent работа полезнее обычного pass>
ULTRA_MERGE_PLAN=<как объединяются независимые ветки>
```

Отсутствие обоснования → понизить effort до минимально достаточного.

## 5. Escalation / de-escalation

Эскалация tier допустима, если:

1. текущая strategy валидна;
2. failure связан с capability/quality, а не с blocker, CAPTCHA, отсутствием данных или плохим scope;
3. сформулирована новая гипотеза;
4. quota/runway допускает более дорогой pass;
5. записан `WHY_THIS_MODEL`.

После двух одинаковых неудач запрещено просто повышать tier/effort. Сначала менять strategy/scope.

Деэскалировать к более дешёвому tier, если этап перешёл от reasoning к массовой extraction/classification и качество можно проверить schema/tests.

## 6. Surface-specific defaults

### Work

- high-volume discovery/extraction → Luna;
- обычный multi-source research / lead qualification → Terra;
- legal-commercial / security / финальный consequential synthesis → Sol.

### Codex

- простые механические edits/tests, где diff/tests дают сильную проверку → Luna или Terra по фактической доступности;
- обычная implementation/debugging → Terra;
- сложная архитектура, security-sensitive reasoning, production incident analysis → Sol.

Для class 4 mutation модель не заменяет read-only baseline, approval, tests и rollback.

## 7. Mixed-pipeline strategy

Один gate может иметь один primary surface, но внутри одного утверждённого workflow допустима экономичная staged-модель, если продукт это поддерживает без дублирования работы:

```text
Luna: discover/extract/filter
→ Terra: qualify/compare/synthesize
→ Sol: only final consequential synthesis if required
```

Не гонять одни и те же страницы через все tiers ради «надёжности». Передавать compact evidence package между стадиями.

Если Work/Codex не позволяет менять tier внутри одного безопасного workflow без раздутого контекста, предпочесть отдельный bounded pass с compact handoff.

## 8. Cost discipline

Не использовать статическую rate card как персональный usage snapshot. Rate card показывает относительную стоимость, а фактический остаток определяется first-party Usage UI.

При одинаково достаточном качестве выбирать более дешёвый tier.

Если текущая официальная rate card существенно изменилась, обновить SOURCE_MAP и это reference до следующего release, а не переносить старые коэффициенты в постоянную логику.

## 9. Fallback

Если рекомендованный tier недоступен:

1. не выдумывать его наличие;
2. выбрать ближайший достаточный доступный tier;
3. записать `FALLBACK_MODEL` и причину;
4. если fallback меняет risk/cost существенно — статус `ПОДГОТОВКА` до подтверждения пользователя или quota snapshot.

Пример:

```text
MODEL_TIER=TERRA
EFFORT=high
WHY_THIS_MODEL=multi-source buyer-demand research; Sol not justified
FALLBACK_MODEL=SOL/high only if Terra cannot resolve conflicting authoritative evidence
```

## 10. Forbidden model behavior

Запрещено:

- выбирать Sol только потому, что задача «важная»;
- выбирать Luna только потому, что она дешёвая, если цена ошибки высока;
- включать max/ultra без bounded justification;
- повторять один и тот же failing prompt на более сильном tier без новой гипотезы;
- хардкодить конкретный generation ID как постоянную политику;
- считать API/token rate card точным burn конкретного pass;
- считать availability из документации сильнее фактического account/workspace UI.
