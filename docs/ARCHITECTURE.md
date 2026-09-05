# Architecture v2.0

## Decision pipeline

```text
User goal
  ↓
Does it need an agentic run?
  ├─ no → CHAT / class 0 / CHAT_BOUNDED_WEB
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
       ↓
PASS_ID / ROLE / GATE
       ↓
Project runway
       ↓
Allowance domain
  WORK_CODEX ≠ CHAT_PRO ≠ API
       ↓
Shared usage / credits / reset
       ↓
Capability & permission state
       ↓
Model router
  ├─ TIERED → Luna / Terra / Sol
  └─ ASTRA  → exceptional admission contract
       ↓
If ASTRA:
  ASTRA_JUSTIFIED
  ASTRA_SCOPE_BOUND
  client readiness
  steering policy
  safety-pause policy
  cyber authorization when applicable
       ↓
Scope & safety
  read / write / action / approval / rollback
       ↓
Run
       ↓
Evidence / steering events / safety state / post-pass usage
       ↓
Accept gate or record attempt
```

## Major v2 change: two-axis model architecture

v1.2 treated model selection primarily as a Luna/Terra/Sol tier choice. v2.0 preserves that efficient tiered path but separates Astra into an exceptional profile.

```text
MODEL_PROFILE=TIERED
MODEL_TIER=LUNA|TERRA|SOL
```

or:

```text
MODEL_PROFILE=ASTRA
MODEL_TIER=N/A
ASTRA_JUSTIFIED=YES
```

This prevents two opposite errors:

1. making Astra the universal default because it is strongest;
2. pretending Astra is merely a more expensive Sol tier when its product role is end-to-end multi-step work.

## Allowance-domain architecture

The regulator does not maintain one fictional universal quota number.

```text
WORK_CODEX
  shared agentic usage/credits for Work and Codex where current plan says so

CHAT_PRO
  separate Chat model allowance semantics

API
  API token/tool billing and limits
```

Burn comparison is valid only inside the same allowance domain and reset window.

## Astra admission boundary

Astra may own multiple internal stages inside one gate, but may not silently cross into the next gate.

```text
ONE_GATE = ONE_PRIMARY_SURFACE
```

Astra end-to-end execution is therefore deeper inside a gate, not broader across permissions/business goals.

## Steering transaction

Mid-turn changes are classified:

```text
SAME_GATE
EXPANDS_GATE
CHANGES_ACTION
CHANGES_CLASS
UNKNOWN
```

Only `SAME_GATE` can continue without a fresh admission, and only if quota, safety, permissions and scope remain unchanged.

## Safety-state architecture

```text
NORMAL
PAUSED_FOR_REVIEW
BLOCKED
UNKNOWN
```

A platform/model safety pause is a control-plane event. It is not converted into an ordinary model failure and is not bypassed by switching surfaces or replaying the same prompt.

## Normative layers

- `SKILL.md` — executable synthesis.
- `references/01` — surface routing.
- `references/02` — allowance domains / shared Work-Codex pool / credits.
- `references/03` — class 0–4.
- `references/04` — runway / burn.
- `references/05` — Work/browser/actions/schedules.
- `references/06` — Codex technical discipline.
- `references/07` — failure recovery.
- `references/08` — model profile/tier router.
- `references/09` — Astra execution contract.
- `references/SOURCE_MAP.md` — first-party provenance.

## Attribution states

```text
CLEAN
  One meaningful shared-pool consumer inside the same allowance domain.

MIXED
  Multiple confirmed shared-pool consumers ran between snapshots.

UNKNOWN
  Snapshot/reset/domain/activity state is insufficient.
```

Only CLEAN comparable data is strong burn-history evidence.

Astra history should be compared to similar Astra work, not estimated from a guessed Sol/Terra multiplier.
