# Documentation

Если нужно быстро понять проект, начинайте с трёх файлов:

1. [USAGE.md](USAGE.md) - как работать со skill.
2. [ARCHITECTURE.md](ARCHITECTURE.md) - как устроены ChatGPT control plane, Work/Codex execution plane и quota path.
3. [../SKILL.md](../SKILL.md) - исполняемый контракт v4.0.

## По задаче

| Нужно | Читать |
| --- | --- |
| Установить и начать работать | [USAGE.md](USAGE.md) |
| Понять routing и handoff | [ARCHITECTURE.md](ARCHITECTURE.md), [../references/11_ORCHESTRATION_AND_HANDOFF.md](../references/11_ORCHESTRATION_AND_HANDOFF.md) |
| Разобраться с model + reasoning policy | [../references/08_MODEL_REASONING_ROUTER.md](../references/08_MODEL_REASONING_ROUTER.md) |
| Проверить weekly runway | [../references/10_WEEKLY_QUOTA_CONTROLLER.md](../references/10_WEEKLY_QUOTA_CONTROLLER.md), [../references/14_WORK_SCHEDULE_RUNWAY.md](../references/14_WORK_SCHEDULE_RUNWAY.md) |
| Посмотреть quota telemetry | [../references/12_AUTONOMOUS_QUOTA_TELEMETRY.md](../references/12_AUTONOMOUS_QUOTA_TELEMETRY.md), [../plugin/README.md](../plugin/README.md) |
| Настроить IdP / OAuth staging | [IDP_DEPLOYMENT.md](IDP_DEPLOYMENT.md) |
| Понять release process | [RELEASE_PROCESS.md](RELEASE_PROCESS.md) |
| Проверить источники | [../references/SOURCE_MAP.md](../references/SOURCE_MAP.md) |
| Посмотреть security model | [../SECURITY.md](../SECURITY.md) |

## Release v4.0

Текущий stable release: [v4.0](https://github.com/misyukdima/openai-work-codex-regulator/releases/tag/v4.0).

В нём ChatGPT остаётся primary orchestrator, Work/Codex работают как execution planes, а weekly quota распределяется по активным рабочим минутам. Secondary limits появляются в admission только тогда, когда их реально вернул текущий account snapshot.
