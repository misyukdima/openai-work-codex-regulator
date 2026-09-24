# OpenAI Work + Codex Regulator

**v4.0 — quota-aware orchestration skill for ChatGPT.**

ChatGPT remains the control plane. It understands the project gate, chooses ChatGPT/Work/Codex, protects a non-negotiable quality floor, selects the lightest sufficient Work/Codex model + reasoning level, and paces the shared allowance so useful work can continue through the user's working day and until weekly reset.

## Default operating window

```text
09:00 start
22:00 normal end
23:00 hard end
daily by default
```

The user can override this schedule. Tasks themselves have no duration cap.

## What v4 changes

- GPT-6 adaptive routing for Astra / Sol / Luna.
- Capability failure and reasoning-depth failure are separate.
- Quota saving happens only among quality-sufficient candidates.
- Weekly runway is paced by remaining active working minutes, not sleeping hours.
- The current quota snapshot is authoritative. A missing five-hour or secondary window is not invented and does not block a valid weekly-only account state.
- Burn estimates come from observed shared-allowance movement, not API prices.
- ChatGPT keeps planning/review/handoff work moving when an agentic pass should wait.
- Root SKILL.md uses progressive disclosure.

```text
CHATGPT_PRIMARY_ORCHESTRATOR=YES
CONTROL_PLANE_OWNER=CHAT
WORK_CODEX_ROLE=EXECUTION_PLANE
QUALITY_FLOOR=NON_NEGOTIABLE
TASK_DURATION_LIMIT=NONE
```

Work is for long browser/app/file workflows and finished deliverables. Codex is for code/repository/terminal/build/deploy work.

## Quota telemetry

get_quota_snapshot() is a read-only zero-argument tool. When connected, ChatGPT uses it at quota-sensitive decisions. If automatic telemetry is unavailable, a manual first-party usage snapshot is fallback only.

The skill does not hardcode that every Plus account has or lacks a five-hour window. It uses the quota windows the current account actually reports.

## Model routing

Project-policy starting points:

- Luna Low — mechanical extraction/dedupe/fixed-schema work.
- Luna Medium — routine clear-brief coordinated work.
- Sol Medium — normal professional coding/research/writing/debugging.
- Sol High — complex work when reasoning depth is the bottleneck.
- Astra Low/Medium — capability/breadth escalation.
- Astra High — high-error-cost security/production/critical gates.

Current account/workspace availability always wins over static docs.

## Installation

Use the release ZIP and keep openai-work-codex-regulator/SKILL.md as the entrypoint.

Detailed policy:
- references/08_MODEL_REASONING_ROUTER.md
- references/14_WORK_SCHEDULE_RUNWAY.md
- references/MODEL_CAPABILITY_SNAPSHOT.json

## Release lineage

v2.2 was the last previously published stable line. v3.x was a development line that produced automatic telemetry and the hardened backend baseline. v3.1 was not released. v4.0 carries that security work forward and adds the adaptive GPT-6 routing/runway controller.
