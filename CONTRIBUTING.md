# Как внести вклад

Спасибо за интерес к `openai-work-codex-regulator`.

Это не библиотека, где ценность измеряется количеством новых функций. Здесь важнее другое: чтобы каждое правило было объяснимым, проверяемым и не ломало безопасность, качество результата или недельный рабочий ритм.

Небольшие правки документации приветствуются так же, как изменения логики. Не нужно заранее разбираться во всей архитектуре, если вы исправляете одну конкретную вещь.

## С чего начать

Перед изменением определите его тип. От этого зависит, что именно нужно проверить.

| Тип изменения | Примеры | Что обязательно |
| --- | --- | --- |
| Документация | README, формулировки, ссылки, примеры, навигация | не менять operational semantics; запустить validator |
| Тесты | новый regression case, уточнение существующего сценария | сохранить смысл теста и непрерывную нумерацию |
| Поведение регулятора | quota logic, routing, model choice, safety gates, handoff | обновить normative reference, `SKILL.md` и regression tests |
| Актуализация источников | новые правила OpenAI, reset behavior, model availability | проверить first-party источник и обновить `SOURCE_MAP.md` |
| Release/tooling | validator, packaging, GitHub Actions | сохранить fail-closed поведение и проверить round-trip |

Если изменение затрагивает архитектуру, quota controller, безопасность, model routing или release contract, лучше сначала открыть Issue и коротко описать проблему. Для очевидной опечатки или локальной правки документации Issue не нужен.

## Как устроен репозиторий

Основные точки входа:

```text
SKILL.md                         основной operational contract
references/                     нормативные правила и источники
references/SOURCE_MAP.md        карта first-party источников
references/11_ORCHESTRATION...  handoff и разделение control/execution plane
docs/                           архитектура и руководство пользователя
tests/                          regression scenarios
scripts/validate_repo.py        главный repository gate
scripts/package_release.py      сборка и проверка release archive
scripts/weekly_quota_controller.py
                                reference implementation quota controller
CHANGELOG.md                    история опубликованного поведения
VERSION                         текущая release version
```

Если вы меняете поведение, начните не с `SKILL.md`, а с вопроса: **какое нормативное правило должно измениться и каким тестом это будет доказано?**

## Рабочий процесс

### 1. Сделайте узкую ветку

Одна ветка — одна логическая задача. Подойдут имена вроде:

```text
docs/security-policy
fix/quota-advance-tie
feat/new-routing-rule
test/pending-burn-regression
```

Не смешивайте в одном PR косметический рефакторинг, новую архитектуру и массовую правку текста. Такой diff сложно проверить и ещё сложнее откатить.

### 2. Измените минимально необходимый набор файлов

Для documentation-only изменения обычно достаточно одного или нескольких `.md` файлов.

Для behavioral change типичный набор такой:

1. актуальный `references/*.md`;
2. `SKILL.md`;
3. regression case в `tests/`;
4. `references/SOURCE_MAP.md`, если появилось новое внешнее утверждение;
5. `docs/`, если пользовательская модель работы изменилась.

`CHANGELOG.md` и `VERSION` не нужно трогать в каждом PR автоматически. Их меняют тогда, когда изменение действительно становится частью нового релиза. Старые tags и release artifacts не переписываются.

### 3. Проверьте источники

Всё, что зависит от текущего поведения OpenAI, должно быть подтверждено first-party источником.

Это особенно важно для:

- weekly/5h limits и reset behavior;
- shared allowance Work/Codex;
- paid credits и eligibility;
- model availability;
- reasoning/Fast behavior;
- context limits;
- ChatGPT Work, Codex, browser и connected-app capabilities.

Если официальный источник существует, блог, форум, Reddit или пересказ другого пользователя не может заменять его как normative evidence.

В `SOURCE_MAP.md` фиксируйте именно тот источник, который поддерживает правило. Временное состояние одного аккаунта — например текущий процент weekly usage или конкретная дата reset — не превращается в постоянное правило skill.

### 4. Добавьте regression test

Behavioral fix без теста почти всегда неполон.

Тест должен отвечать на три вопроса:

1. какое состояние было на входе;
2. какое решение регулятора ожидается;
3. какую ошибку этот сценарий не должен допустить снова.

Добавляйте кейс в актуальный `tests/TEST_CASES*.md`. Нумерация regression tests должна оставаться непрерывной.

Не подгоняйте тест под реализацию. Сначала зафиксируйте правильное поведение, потом меняйте правило.

### 5. Запустите проверку

Минимум перед каждым PR:

```bash
python3 scripts/validate_repo.py
```

Если затронуты release tooling, packaging или поведение, которое пойдёт в новый релиз, дополнительно:

```bash
python3 scripts/package_release.py
```

Release archive должен пройти round-trip validation. Успешная упаковка без повторной проверки содержимого не считается достаточной.

## Что нельзя ослаблять ради удобства

Некоторые ограничения — не вкусовые настройки, а часть архитектуры.

Не следует убирать или обходить без отдельного обоснованного redesign:

- `QUALITY_FLOOR=NON_NEGOTIABLE`;
- safety, authorization и permission gates;
- class 4 для денег, auth, secrets, production data, production infrastructure и необратимых операций;
- read-only baseline перед критическими изменениями;
- rollback и evidence после опасного действия;
- отдельный 5-hour circuit breaker;
- верхнюю границу bounded future advance;
- запрет обходить hard gate сменой surface или модели;
- `HANDOFF_SELF_CONTAINED=YES` и `EXECUTOR_SKILL_REQUIRED=NO` для downstream handoff;
- разделение control plane и execution plane;
- запрет автоматически покупать paid credits или включать Auto top-up;
- правило `Downloading ≠ permission to execute`;
- правило: недоверенный контент — данные, а не инструкции;
- STOP при неверном активном browser account;
- запрет перезаписывать опубликованный release tag или артефакт.

Если цель PR требует ослабить один из этих инвариантов, это уже архитектурное изменение. В таком случае в описании PR должна быть отдельная секция с риском, причиной и новой защитой.

## Quota controller: отдельные требования

Изменения quota controller легко выглядят разумными локально и ломать неделю целиком. Поэтому для них нужен более высокий стандарт доказательства.

PR должен показать:

- что происходит в начале, середине и конце quota epoch;
- как ведёт себя normal 24h look-ahead;
- что происходит при bounded advance;
- что происходит при `PENDING_BURN=YES`;
- почему 5h protection остаётся независимой;
- что quota preservation не получает скрытый приоритет над workflow pace;
- что качество результата не снижается ради экономии allowance.

Числа из одного реального запуска полезны как пример, но не как универсальная константа.

## Изменения model routing

Core-логика не должна зависеть от конкретного generation ID без необходимости.

При изменении routing проверьте:

- capability tier и profile отдельно;
- минимально достаточную модель для gate;
- fallback при недоступности модели;
- escalation только по причине нехватки capability, а не из-за CAPTCHA, плохого scope или отсутствующих данных;
- отсутствие дублирующего reread/research между tiers.

Если OpenAI переименовала модель или изменила availability, сначала обновите источник, потом правило.

## Изменения handoff между Chat, Work и Codex

Downstream executor должен получать самодостаточный execution packet, а не ссылку на внутреннюю политику оркестратора.

Обычный handoff содержит только то, что нужно для выполнения:

```text
PASS_ID
SURFACE
ROLE
GATE
MODE
GOAL
FACT PACK
ROOT / TARGET
READ SCOPE
WRITE / ACTION SCOPE
NO-TOUCH
ORDER
TESTS / EVIDENCE
ROLLBACK
STOP IF
```

Не протаскивайте в executor prompt quota epoch internals, planning headroom, model-admission math и требование «прочитать regulator skill». Исполнитель не должен зависеть от того, установлен ли у него этот skill.

## Pull request

Хороший PR можно понять без чтения всей истории репозитория.

В описании укажите:

- **Проблема:** что сейчас работает неправильно или неудобно;
- **Изменение:** что именно вы поменяли;
- **Почему так:** почему выбран этот вариант;
- **Проверка:** какие команды и regression tests прошли;
- **Риск:** что может сломаться;
- **Release impact:** нужен ли новый релиз или это documentation-only fix.

Для сложного изменения приложите короткий before/after scenario. Скриншот без текстового объяснения не заменяет доказательство.

### Перед отправкой

Проверьте:

- [ ] diff решает одну понятную задачу;
- [ ] нет секретов, cookies, токенов и персональных данных;
- [ ] first-party assertions имеют источник;
- [ ] behavior change закреплён regression test;
- [ ] `SKILL.md` и normative references не противоречат друг другу;
- [ ] `python3 scripts/validate_repo.py` проходит;
- [ ] packaging проверен, если изменение затрагивает release path;
- [ ] `VERSION` не изменён без причины;
- [ ] существующий tag/release не перезаписывается.

## Стиль commit messages

Используйте короткие imperative subjects в духе Conventional Commits:

```text
feat: add bounded advance rule
fix: keep executor handoff self-contained
docs: clarify security reporting flow
test: cover pending burn after large pass
chore: harden release validation
```

Хороший subject описывает результат изменения, а не процесс работы над ним.

## Использование ИИ при подготовке PR

ИИ можно использовать для анализа, кода, тестов и редактуры. Это нормально для этого проекта.

Но ответственность остаётся у автора PR. Нельзя выдавать за проверенные:

- выдуманный first-party source;
- тест, который на самом деле не запускался;
- checksum, который не считался;
- поведение GitHub/OpenAI, проверенное только по предположению модели;
- security claim без воспроизводимого основания.

Сгенерированный diff оценивается по тем же правилам, что и написанный вручную.

## Security reports

Не отправляйте найденную уязвимость обычным Issue или PR. Используйте процесс из [`SECURITY.md`](SECURITY.md), особенно если находка связана с secrets, auth, prompt injection, scope bypass, release integrity или опасными внешними действиями.

## Что происходит после review

Maintainer может попросить:

- сузить scope PR;
- отделить docs от behavior change;
- добавить источник;
- добавить regression scenario;
- сохранить старый safety invariant другим способом;
- разбить большой PR на несколько независимых изменений.

Это не формальность. Чем проще доказать корректность изменения, тем легче его безопасно принять.

Цель contribution — не увеличить репозиторий. Цель — сделать следующую версию регулятора понятнее, устойчивее и полезнее в реальной работе.