# Project runway, pass discipline and burn accounting

**Version:** 2.2  
**Status:** normative

## 1. Two runways

1. **Project runway** — meaningful gates/passes remaining.
2. **Quota runway** — shared Work/Codex capacity remaining before reset.

A failed attempt may leave project runway unchanged while still consuming real quota.

Weekly quota/pace mathematics is normative in `references/10_WEEKLY_QUOTA_CONTROLLER.md`.

## 2. Pass definition

```text
PASS_ID=
SURFACE=CHATGPT_WORK|CODEX
ROLE=RESEARCH|ACTION|IMPL|VERIFY|DEPLOY|MONITOR
GATE=
STOP AFTER REPORT
```

One substantive pass closes one named gate and produces evidence.

## 3. Attempts

```text
ATTEMPT_WITHOUT_GATE_CLOSE=1
CAUSE=
COMPENSATION=
```

Failed attempts still count in the aggregate weekly meter.

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

Do not silently add gates. If a mandatory gate appears, show the runway delta or explicitly merge/replace another gate.

## 5. Quota linkage in v2.2

Project passes link to the controller anchor, not to a private daily budget:

```text
QUOTA_EPOCH_ID=
TRAJECTORY_ANCHOR_WEEKLY_USED_PP=
TRAJECTORY_ANCHOR_HOURS_TO_RESET=
BASE_ACTION_HEADROOM_PP=
MAX_ADVANCE_HEADROOM_PP=
BURN_ESTIMATE_WEEKLY_PP=
PACE_RISK_IF_DEFER=
QUOTA_RISK_IF_LAUNCH=
QUALITY_FLOOR=NON_NEGOTIABLE
```

A 24h look-ahead is a normal target, not a mandatory wait boundary.

## 6. Observed burn

Same-epoch aggregate delta:

```text
DELTA_WEEKLY_PP = WEEKLY_USED_AFTER - WEEKLY_USED_BEFORE
```

Separate 5h delta:

```text
DELTA_5H_PP = FIVE_HOUR_USED_AFTER - FIVE_HOUR_USED_BEFORE
```

A reset invalidates the corresponding delta. Weekly and 5h pp are different denominators.

Task/chat credits may be supporting evidence but must not be converted into weekly pp with a guessed coefficient.

## 7. Attribution

```text
OTHER_SHARED_POOL_ACTIVITY=YES|NO|UNKNOWN
ATTRIBUTION=CLEAN|MIXED|UNKNOWN
```

- CLEAN — current pass was the only meaningful confirmed shared-pool consumer.
- MIXED — another shared-pool consumer ran.
- UNKNOWN — attribution cannot be established.

`MIXED` cannot be called exact pass burn, but its aggregate meter movement still reduces total quota runway.

## 8. Comparable history

Use max five recent observations comparable in allowance configuration, surface, role/class, model/profile, reasoning/speed, task shape and context scale.

```text
BURN_HISTORY_COMPATIBLE=YES|NO|UNKNOWN
```

Cross-reset observations may remain useful if economics remain compatible.

## 9. Priority under quota pressure

Do not process backlog FIFO merely to appear fair. Prefer work that closes critical gates and reduces future rework.

Typical value ordering:

```text
critical-path implementation
→ verification that unblocks next gate
→ consequential research
→ optional polish/audit
```

This priority never waives safety/approval.

## 10. Equal quota/pace priority

After safety/quality gates, quota continuity and workflow pace are equal objectives:

```text
BALANCED_PRIORITY=QUOTA_50_PACE_50
```

A pass slightly above the 24h target may use bounded future advance when its normalized quota risk is no greater than the normalized pace risk of waiting.

Therefore this is no longer valid as a universal rule:

```text
quality pass does not fit 24h target -> wait 24h
```

Instead apply the v2.2 balanced controller and progress-preserving fallback ladder.

## 11. Anti-inflation

Remove duplicate research, unchanged repeated audits, redundant agents and unnecessary context before reducing useful work.

Never remove mandatory source quality, tests, security baseline, rollback or minimum sufficient model capability.

## 12. Reset handling

A confirmed reset changes quota state, not project truth.

After reset:

- preserve accepted evidence/decisions/diffs/closed gates;
- create new `QUOTA_EPOCH_ID` + trajectory anchor;
- revalidate burn-history compatibility;
- do not rerun completed gates merely because capacity returned.

## 13. Scheduled commitments

```text
SCHEDULED_WEEKLY_COMMITMENT_PP=<estimate|unknown>
EXPECTED_SHARED_BURN_DURING_LOOKAHEAD_PP=<estimate|unknown>
```

Subtract commitments before both base and future-advance headroom. Never double-allocate the same allowance.

## 14. Acceptance update

After accepted class 2–4 pass:

1. verify gate/evidence;
2. update project runway;
3. obtain aggregate usage when available;
4. update actual spend against the same trajectory anchor;
5. add burn sample only with correct attribution/compatibility;
6. preserve quality floor;
7. re-run balanced admission for the next gate rather than automatically waiting for a daily boundary.
