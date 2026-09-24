# ChatGPT orchestration and self-contained handoff

**Policy version:** v4.0
**Status:** normative

```text
CONTROL_PLANE_OWNER=CHAT
CHATGPT_PRIMARY_ORCHESTRATOR=YES
WORK_CODEX_ROLE=EXECUTION_PLANE
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

ChatGPT owns task understanding, complexity/quality classification, quota runway, surface choice and model/reasoning admission.

Work and Codex receive one self-contained execution packet. They do not need this skill installed and they do not independently reopen quota/model admission.

Control-plane-only state such as quota epochs, burn estimates, model candidate comparisons and runway headroom normally stays in ChatGPT.

Forward only execution-relevant state:

```text
PASS_ID
SURFACE
ROLE
GATE
MODE
GOAL
FACT_PACK
ROOT_OR_TARGET
READ_SCOPE
WRITE_OR_ACTION_SCOPE
NO_TOUCH
ORDER
TESTS_OR_EVIDENCE
ROLLBACK
STOP_IF
STOP_AFTER_REPORT
```

This saves quota by avoiding duplicate policy reading, duplicate research and executor re-planning.

A direct user action in Work/Codex is outside this skill's normal orchestration contract; the release is designed first for ChatGPT as control plane.
