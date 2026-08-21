# Project runway, pass discipline and burn accounting

**Version:** 1.1  
**Status:** normative

## 1. Why runway exists

The shared Work/Codex pool means a project can consume its future capacity by spending too much on early repeated audits. Runway is a planning budget, not an OpenAI product limit.

## 2. Pass definition

A pass closes one named gate.

```text
PASS_ID=
SURFACE=CHATGPT_WORK|CODEX
ROLE=RESEARCH|ACTION|IMPL|VERIFY|DEPLOY|MONITOR
GATE=
STOP AFTER REPORT
```

A successful pass produces evidence and stops.

## 3. Attempts

An execution that consumes usage without closing the gate is an attempt, not a completed pass.

```text
ATTEMPT_WITHOUT_GATE_CLOSE=1
CAUSE=
COMPENSATION=
```

Readiness runway does not decrement.

## 4. Runway ledger

```text
PROJECT=
CHECKPOINT=
REMAINING_PASSES=Pmin..Pmax
THIS_PASS=
ROLE=
GATE=
ATTEMPTS_SINCE_LAST_GATE=
```

Do not silently add gates.

## 5. Percentage-window budget

If first-party UI exposes percentages:

```text
W_REM = 100 - W_USED
F_REM = 100 - F_USED
W_RESERVE = 10 percentage points
F_RESERVE = 10 percentage points
W_USABLE = max(0, W_REM - W_RESERVE)
F_USABLE = max(0, F_REM - F_RESERVE)
TARGET_AVG_WEEKLY_BURN_PER_PASS = W_USABLE / max(1, Pmax)
```

The 10-point reserve is an internal operating policy, not an OpenAI limit.

## 6. Burn measurement

Same reset-window only:

```text
DELTA_WEEKLY = after - before
DELTA_5H = after - before
```

If reset occurs between snapshots, delta is invalid.

If thread/task credit usage is shown, record it directly:

```text
PASS_CREDITS=<value>
```

Do not invent a tokens→quota-percent coefficient.

## 7. Comparable history

Estimate with conservative maximum of up to 3 accepted comparable passes of same surface/role/class.

```text
EST_BURN=max(last comparable burns)
```

No data → unknown.

## 8. Attribution: CLEAN / MIXED / UNKNOWN

Contamination is not limited to Work ↔ Codex. Any other OpenAI agentic feature from the shared pool — confirmed by current official sources / account UI (as of the verification date: Workspace Agent, ChatGPT for Excel/PowerPoint, Voice-started tasks) — between before/after snapshots makes the measurement unclean.

```text
OTHER_SHARED_POOL_ACTIVITY=YES|NO|UNKNOWN
ATTRIBUTION=CLEAN|MIXED|UNKNOWN
```

- `CLEAN` is allowed only if no other meaningful OpenAI shared-pool consumer ran between snapshots;
- `MIXED` — such a consumer ran; the delta must not be treated as the exact burn of the current pass;
- `UNKNOWN` — other-consumer activity is unknown.

The consumer list is not hardcoded forever: count only features confirmed by current official sources / account UI.

Kimi, Skyvern and other external tools are not OpenAI shared-pool activity and do not by themselves make attribution `MIXED`.

Do not attribute a combined delta to one task.

## 9. Reset-aware rules

- 5h reset ≤15 minutes + class 3–4 non-incident → defer.
- weekly reset ≤2 hours + heavy non-urgent pass → prefer defer.
- weekly reset ≤24 hours → current pass must fit, but whole project need not fit before reset.

## 10. Anti-inflation

Do not automatically create:

```text
research → independent research → audit → implementation → second audit → polish
```

If a gate already provides sufficient evidence, move to the next value-producing stage.
