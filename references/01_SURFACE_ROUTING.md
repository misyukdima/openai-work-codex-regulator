# Surface routing: Chat vs Work vs Codex

**Version:** 2.2  
**Verified:** 2026-09-06  
**Status:** normative

## 1. Product roles

Current OpenAI guidance distinguishes:

- Chat — conversational/bounded assistance;
- Work — longer multi-step research/apps/deliverables/actions;
- Codex — software development and technical work.

## 2. Routing rule

Use the least expensive surface that can close the gate at the required quality.

### CHAT

Use for orchestration, planning, review, prompt/handoff, supplied-material analysis and bounded web/file work.

`CHAT_BOUNDED_WEB` fits simple read-only work, usually within 1–5 public sources, with no login, persistent browser state, external action, schedule or complex connected-app workflow.

### WORK

Use for substantial multi-step browser/research/apps/files/deliverables/scheduled monitoring/controlled external actions.

### CODEX

Use for repository/code/terminal/tests/build/Git/server/config/deploy/debugging.

## 3. Agentic gate

Before Work/Codex:

```text
WHY_AGENTIC=<why Chat is insufficient>
VALUE_OUTPUT=<verifiable gate-closing result>
```

Do not spend shared agentic quota merely because the task is important.

## 4. User surface override

If the regulator recommends Chat to save quota but the user explicitly insists on Work after one concise warning, record:

```text
USER_SURFACE_OVERRIDE=YES
```

Respect the chosen surface only if safety, quota/pace, permissions, paid-spend and action gates still pass. Override never creates missing capability or permission.

## 5. One gate / one primary executor

```text
ONE_GATE = ONE_PRIMARY_SURFACE
```

Do not duplicate full research in Codex after Work/Chat already produced an accepted fact pack. Do not repeat a technical audit in Work after Codex already established the technical state unless a distinct independent verification is required.

## 6. Control plane vs executor

When regulator is running in Chat and routes to Work/Codex:

```text
CONTROL_PLANE_OWNER=CHAT
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

The downstream executor must not be required to have this regulator installed. Chat resolves quota/model/admission and forwards only the bounded execution contract.

If user directly invokes an installed regulator inside Work/Codex, that surface may locally own its control plane for the current pass.

## 7. Cross-surface handoff

Executor packet should contain:

```text
GOAL
FACT PACK
DECISIONS
EXACT READ/WRITE/ACTION SCOPE
FORBIDDEN SCOPE
TESTS / EVIDENCE
ROLLBACK
STOP CONDITION
```

Do not copy full conversation or internal quota-controller state unless it is itself task data.

## 8. Progress under quota pressure

If an agentic pass should not launch now, routing does not end with automatic waiting. First check whether Chat can make meaningful progress through planning, review, compact handoff, supplied-file analysis or other non-agentic work.

```text
MEANINGFUL_PROGRESS_WITHOUT_AGENTIC=<YES|NO|UNKNOWN>
```

## 9. Official source

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
