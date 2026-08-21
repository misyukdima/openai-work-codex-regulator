# Architecture

## Decision pipeline

```text
User goal
  ↓
Does it need an agentic run?
  ├─ no → CHAT / class 0
  └─ yes
       ↓
Task class 1–4
       ↓
Primary surface
  ├─ WORK
  ├─ CODEX
  └─ OTHER
       ↓
WHY_AGENTIC / VALUE_OUTPUT
  (why ordinary Chat is insufficient)
       ↓
Pass identity
  PASS_ID / ROLE / GATE
       ↓
Project runway
       ↓
Shared usage snapshot
  5h / weekly / credits / reset / paid-credit policy
  freshness requirement depends on class
       ↓
Capability / permission state
  Work Cloud/Local · Codex Local · browser · network
       ↓
Credit eligibility
  authorization ≠ feature eligibility
       ↓
Model & execution policy
  minimal sufficient / no unnecessary Fast/Ultra
       ↓
Scope & safety
  read / write / external action / approval / rollback
       ↓
Run
       ↓
Evidence & post-pass usage
       ↓
Accept gate or record attempt
```

## Shared-pool architecture

The central design assumption is not that Work and Codex have separate independent budgets. They are treated as competing consumers of one agentic resource pool when the account exposes them under the same allowance.

This produces three operational consequences:

1. surface routing is a quota decision, not only a capability decision;
2. duplicate Work/Codex passes are expensive and normally prohibited;
3. before/after burn measurements need clean attribution.

## Normative layers

- `SKILL.md` — executable synthesis.
- `references/01` — routing.
- `references/02` — shared pool / credits.
- `references/03` — class 0–4.
- `references/04` — runway / burn.
- `references/05` — Work/browser/actions/schedules.
- `references/06` — Codex technical discipline.
- `references/07` — failure recovery.
- `references/SOURCE_MAP.md` — official provenance.

A normative rule that exists only in a reference but not in `SKILL.md` should be treated as a release-integrity defect.

## Attribution states

```text
CLEAN
  One agentic pass was the only meaningful shared-pool consumer between snapshots.

MIXED
  Multiple supported agentic features (Work, Codex, or another confirmed
  shared-pool consumer) ran between snapshots.

UNKNOWN
  Snapshot is missing, reset crossed, accounting source changed,
  or other-consumer activity is unknown.
```

Only CLEAN comparable data is strong burn-history evidence.

The set of OpenAI shared-pool consumers is not hardcoded: only features confirmed by current official sources / account UI count. External tools (Kimi, Skyvern, etc.) are not OpenAI shared-pool consumers and do not by themselves make attribution MIXED.
