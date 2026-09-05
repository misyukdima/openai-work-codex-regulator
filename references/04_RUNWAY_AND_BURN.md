# Project runway, pass discipline and burn accounting

**Version:** 2.1  
**Status:** normative

## 1. Two different runways

v2.1 explicitly separates:

1. **project runway** — how many meaningful gates/passes remain in the project;
2. **quota runway** — how much Work/Codex allowance can safely be used before the current weekly reset.

They are related but not interchangeable.

A failed attempt can leave project runway unchanged while still consuming real weekly quota.

Weekly continuity mathematics is normative in `references/10_WEEKLY_QUOTA_CONTROLLER.md`.

## 2. Pass definition

A substantive agentic pass closes one named gate.

```text
PASS_ID=
SURFACE=CHATGPT_WORK|CODEX
ROLE=RESEARCH|ACTION|IMPL|VERIFY|DEPLOY|MONITOR
GATE=
STOP AFTER REPORT
```

A successful pass produces evidence and stops.

## 3. Attempts

An execution that consumes usage without closing the gate is an attempt, not a completed project pass.

```text
ATTEMPT_WITHOUT_GATE_CLOSE=1
CAUSE=
COMPENSATION=
```

Project runway does not decrement automatically after a failed attempt.

Quota state **does** move according to the actual first-party shared weekly meter.

## 4. Project ledger

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

If a new mandatory gate appears, show the runway delta or merge/replace an existing gate explicitly.

## 5. Quota linkage

For class 2–4 Work/Codex passes, link the project pass to the current quota-controller state:

```text
QUOTA_EPOCH_ID=
CONTROL_SLICE_ID=
CONTROL_SLICE_BUDGET_PP=
SLICE_SPENT_PP=
EFFECTIVE_SLICE_HEADROOM_PP=
BURN_ESTIMATE_WEEKLY_PP=
BURN_ESTIMATE_CONFIDENCE=
QUALITY_FLOOR=NON_NEGOTIABLE
CONTINUITY_FEASIBLE=YES|NO|UNKNOWN
```

A pass does not receive its own independent daily budget. It spends from the currently anchored shared control slice.

## 6. Observed burn

A same-epoch before/after weekly meter gives total shared-pool change:

```text
DELTA_WEEKLY_PP =
  WEEKLY_USED_AFTER
  - WEEKLY_USED_BEFORE
```

For a separate 5-hour meter:

```text
DELTA_5H_PP =
  FIVE_HOUR_USED_AFTER
  - FIVE_HOUR_USED_BEFORE
```

If a reset occurs between snapshots, the corresponding delta is invalid.

Do not compare weekly pp and 5h pp as though they were the same unit.

If thread/task credits are shown, record them as supporting task-level evidence:

```text
PASS_CREDITS=<value>
```

Do not convert them into weekly percentage points with a guessed coefficient.

## 7. Attribution

```text
OTHER_SHARED_POOL_ACTIVITY=YES|NO|UNKNOWN
ATTRIBUTION=CLEAN|MIXED|UNKNOWN
```

- `CLEAN`: current pass was the only meaningful confirmed shared-pool consumer between snapshots;
- `MIXED`: another shared-pool consumer ran;
- `UNKNOWN`: contamination state cannot be established.

For **pass attribution**, `MIXED` cannot be called exact burn of one pass.

For **quota continuity**, the aggregate mixed meter increase still correctly reduces total remaining allowance and current slice headroom.

This distinction prevents the regulator from losing track of weekly capacity merely because attribution is imperfect.

## 8. Comparable history

The v2.1 burn estimator may use at most five recent materially comparable observations.

Comparable means similar:

```text
allowance configuration
surface
role/class
model profile/tier
reasoning/speed posture
task shape/context scale
```

Record:

```text
BURN_HISTORY_COMPATIBLE=YES|NO|UNKNOWN
```

Cross-reset observations may remain useful if economics stay compatible. Material model/product/plan/task-shape changes invalidate or split the history.

## 9. Project priority under quota pressure

When the current weekly slice is constrained, do not consume it in FIFO order merely because tasks arrived first.

Prefer work that closes meaningful project gates and reduces future rework.

Good quota-aware ordering can include:

```text
blocking implementation
→ verification needed to unblock next gate
→ consequential research
→ lower-value polish/optional audit
```

Priority does not waive safety or approval requirements.

## 10. Quality-preserving anti-inflation

The following pattern is normally wasteful unless each stage closes a distinct required gate:

```text
research
→ duplicate research
→ independent audit without new hypothesis
→ implementation
→ second unchanged audit
→ polish
```

Under quota pressure, first remove duplicate work, repeated context and unnecessary surfaces.

Do not reduce:

- mandatory source quality;
- required tests;
- security baseline;
- rollback evidence;
- minimum sufficient model capability.

If a quality-sufficient pass does not fit the current slice:

```text
QUOTA_DECISION=DEFER_FOR_QUALITY
```

## 11. Reset handling

A quota reset changes quota state, not project truth.

After a confirmed reset:

- preserve accepted evidence, decisions, diffs and closed gates;
- discard old `QUOTA_EPOCH_ID` / `CONTROL_SLICE_*` state;
- create a fresh weekly controller anchor from current first-party UI;
- revalidate burn-history compatibility;
- do not rerun completed gates just because capacity returned.

## 12. Scheduled commitments

Scheduled Tasks consume future quota runway and therefore must be visible in project planning.

```text
SCHEDULED_WEEKLY_COMMITMENT_PP=<estimate|unknown>
EXPECTED_SCHEDULED_BURN_BEFORE_SLICE_END_PP=<estimate|unknown>
```

Do not reserve the same percentage points simultaneously for a scheduled task and an interactive project pass.

## 13. Acceptance update

After an accepted class 2–4 pass:

1. verify the gate and evidence;
2. update project runway;
3. obtain post-pass aggregate usage when available;
4. update current slice spent/headroom;
5. add a burn-history sample only with the correct attribution/compatibility label;
6. keep quality floor unchanged for the next pass.
