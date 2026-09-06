# Orchestration and self-contained handoff contract

**Policy version:** v2.2  
**Status:** normative

This reference separates regulator control-plane logic from downstream Work/Codex execution.

## 1. Principle

The regulator belongs to the surface where it is actually loaded/invoked.

```text
CONTROL_PLANE_OWNER=<CHAT|WORK|CODEX>
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

A downstream executor must not be assumed to have the regulator installed.

## 2. Default Chat orchestration

When Chat invokes the regulator and decides to use Work or Codex:

1. Chat resolves surface, quota, model/profile/effort, risk class and admission;
2. Chat prepares one bounded execution packet;
3. Work/Codex executes that packet;
4. executor reports evidence;
5. Chat updates quota/project state and decides the next gate.

The execution packet must remain valid even if the executor has never seen this repository or skill.

## 3. Forbidden dependency pattern

A handoff must not make success conditional on instructions such as:

```text
use/load/follow the regulator skill
read the regulator before starting
apply the regulator rules yourself
```

as a prerequisite for ordinary execution.

If the current task is to modify this regulator repository itself, reading `SKILL.md` or references as target project files is naturally allowed; that is not an executor dependency.

## 4. Control-plane-only state

The following normally stays upstream:

```text
QUOTA_EPOCH_ID
TRAJECTORY_ANCHOR_*
BASE_ACTION_HEADROOM_PP
MAX_ADVANCE_HEADROOM_PP
BORROWABLE_EXTRA_PP
PACE_RISK_IF_DEFER
QUOTA_RISK_IF_LAUNCH
BALANCED_PRIORITY
BURN_ESTIMATE_* planning state
paid-reset decision state
```

Do not forward these merely because they were used to authorize the pass.

Exception: an executor whose explicit gate is to inspect usage telemetry/controller code may receive the relevant fields as task data.

## 5. Executor-relevant state

Forward only what changes execution:

```text
PASS_ID
SURFACE
ROLE
GATE
MODE
GOAL
compact FACT PACK
ROOT / TARGET
READ SCOPE
WRITE / ACTION SCOPE
NO-TOUCH
ORDER
TESTS / EVIDENCE
ROLLBACK
STOP IF
```

Optional efficiency posture:

```text
EFFICIENCY_POSTURE=MINIMIZE_WASTE_WITHOUT_QUALITY_LOSS
```

This means reuse accepted facts, avoid duplicate research and stop at the gate. It does not require the executor to know quota math.

## 6. Model selection

Model/profile/effort admission is control-plane work. If the product requires the user/orchestrator to choose a model before launch, do that before sending the packet.

The executor must not independently re-open model admission merely because it lacks the regulator skill.

## 7. Direct invocation inside Codex/Work

If the user directly invokes an installed regulator inside Codex or Work, that surface may become its own `CONTROL_PLANE_OWNER` for that local pass.

This does not change the cross-surface rule: any subsequent downstream handoff is still self-contained and cannot depend on another installation.

## 8. Work packet

```text
PASS_ID: <id>
SURFACE: CHATGPT_WORK
ROLE: <role>
GATE: <one gate>
STOP AFTER REPORT.

GOAL:
<exact goal>

CONTEXT / FACT PACK:
<accepted facts only>

ALLOWED ACTIONS:
<exact>

FORBIDDEN:
<exact>

OUTPUT / EVIDENCE:
<schema>

STOP IF:
<drift/scope expansion/safety issue>
```

## 9. Codex packet

```text
PASS_ID: <id>
SURFACE: CODEX
ROLE: IMPL|VERIFY|DEPLOY
GATE: <one gate>
MODE: READ_ONLY|BOUNDED_MUTATION
STOP AFTER REPORT.

GOAL:
<exact goal>

ROOT / REPO / ENVIRONMENT:
<known state>

CONTEXT / FACT PACK:
<accepted facts only>

READ SCOPE:
<paths>

WRITE SCOPE:
<exact paths/actions>

NO-TOUCH:
<paths/services/secrets>

ORDER:
1. baseline
2. minimal sufficient change
3. tests
4. diff
5. report

TESTS:
<commands>

ROLLBACK:
<point>

STOP IF:
<drift/scope expansion/safety pause/failing invariant>
```

## 10. Why this saves quota

A self-contained handoff prevents:

- duplicate policy reading;
- executor re-research of already accepted facts;
- failure caused by missing skill installation;
- extra turns spent asking where the skill is;
- control-plane state being copied into every technical prompt.

It also keeps orchestration stable when Chat has the regulator but Codex does not.
