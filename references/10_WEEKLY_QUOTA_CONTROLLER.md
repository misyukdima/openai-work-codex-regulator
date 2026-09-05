# Adaptive weekly Work/Codex quota controller

**Policy version:** v2.1  
**Verified:** 2026-09-05  
**Status:** normative

This reference defines the mathematical controller used to preserve useful Work/Codex capacity across an entire weekly reset window without lowering the minimum sufficient quality of work.

## 1. Required normalized state

The controller operates on first-party Work/Codex allowance telemetry only.

```text
ALLOWANCE_DOMAIN=WORK_CODEX
WEEKLY_METER_SEMANTICS=<USED|REMAINING>
WEEKLY_USED_PP=<0..100>
WEEKLY_RESET_AT=<timestamp>
SNAPSHOT_AT=<timestamp>
HOURS_TO_WEEKLY_RESET=<positive hours>
WEEKLY_METER_GRANULARITY_PP=<pp|unknown>
QUOTA_EPOCH_ID=<id>
```

If the account UI reports remaining rather than used:

```text
WEEKLY_USED_PP = 100 - WEEKLY_REMAINING_PP
```

Never infer meter semantics from an unlabeled number.

If the account does not expose a percentage meter, this percentage-point controller is unavailable. If the account exposes another exact first-party unit, an analogous controller may be built in that unit. Never convert token counts, API prices or rate-card credits into weekly percentage points.

## 2. Quota epoch

A quota epoch is one coherent Work/Codex weekly allowance window.

```text
QUOTA_EPOCH_EVENT=<NONE|RESET|PLAN_CHANGE|ALLOWANCE_CHANGE|UNKNOWN>
```

Start a new epoch when any of the following is confirmed:

- normal weekly reset;
- paid instant weekly reset;
- banked/promotional reset applied by the account;
- material reset-time change indicating a new cycle;
- plan/workspace allowance architecture changed.

On a new epoch:

1. discard old `CONTROL_SLICE_*` state;
2. obtain a fresh first-party meter/reset snapshot;
3. revalidate compatibility of burn history;
4. preserve completed project gates and evidence — quota reset does not erase project state.

Default reset-spend posture:

```text
PAID_WEEKLY_RESET_ALLOWED=NO
```

A paid reset is a separate class-4 money action. Current first-party documentation says an eligible completed instant reset changes the weekly schedule; therefore it must never be modeled as a silent extension of the old epoch.

## 3. Why `remaining / days` is insufficient

A naive daily budget such as:

```text
(100 - WEEKLY_USED) / days_remaining
```

has four problems:

1. actual Work/Codex burn is variable rather than fixed per pass;
2. repeatedly recomputing a full daily budget after each pass can front-load the week;
3. it leaves no error reserve for measurement granularity, unexpected task complexity or shared-pool activity;
4. a permanently held reserve can strand usable allowance at the end of the week.

v2.1 therefore uses a **stateful fixed 24h control slice**, observed feedback and a reserve that is released near reset.

## 4. Core weekly mathematics

At a slice anchor:

```text
U = WEEKLY_USED_PP
R = max(0, 100 - U)
H = HOURS_TO_WEEKLY_RESET
```

Internal controller constants:

```text
BASE_WEEKLY_RESERVE_PP = 10
RESERVE_FRACTION_CAP = 0.50
RESERVE_RELEASE_HOURS = 72
CONTROL_SLICE_HOURS = 24
```

These are regulator policies, not OpenAI product limits.

### 4.1. Dynamic risk reserve

First cap the reserve so it cannot consume most of a nearly exhausted allowance:

```text
RESERVE_CAP =
  min(
    BASE_WEEKLY_RESERVE_PP,
    RESERVE_FRACTION_CAP * R
  )
```

Release it linearly through the final 72 hours:

```text
release_factor(H) =
  clamp(H / RESERVE_RELEASE_HOURS, 0, 1)

Z(H) =
  RESERVE_CAP * release_factor(H)
```

Interpretation:

- with more than 72h left, full risk reserve remains held;
- during the last 72h the reserve is progressively released;
- at reset time held reserve reaches zero.

### 4.2. Fixed rolling 24h slice

```text
h = min(CONTROL_SLICE_HOURS, H)
Z0 = Z(H)
Z1 = Z(H - h)
S = max(0, R - Z0)

CONTROL_SLICE_BUDGET_PP =
    S * (h / H)
  + max(0, Z0 - Z1)
```

The first term spreads currently schedulable allowance over remaining time. The second term gives the current slice its share of reserve being released before the next anchor.

Fresh normalized seven-day example:

```text
U = 0
R = 100
H = 168h
Z0 = 10
S = 90

CONTROL_SLICE_BUDGET_PP =
  90 * 24 / 168
  = 12.857142857 pp
```

If each future slice spends exactly its planned envelope, the controller releases the reserve and reaches the full normalized allowance at reset rather than permanently stranding 10 percentage points.

### 4.3. Slice ledger is stateful

At creation:

```text
CONTROL_SLICE_ID=<id>
CONTROL_SLICE_START_AT=<time>
CONTROL_SLICE_END_AT=<time>
CONTROL_SLICE_START_WEEKLY_USED_PP=<U0>
CONTROL_SLICE_BUDGET_PP=<fixed budget>
```

During the slice:

```text
SLICE_SPENT_PP =
  max(
    0,
    WEEKLY_USED_NOW
    - CONTROL_SLICE_START_WEEKLY_USED_PP
  )

SLICE_HEADROOM_PP =
  max(
    0,
    CONTROL_SLICE_BUDGET_PP
    - SLICE_SPENT_PP
  )
```

Let `g` be the known first-party meter granularity in percentage points. If unknown, v2.1 uses a conservative internal 1pp observation buffer.

```text
EFFECTIVE_SLICE_HEADROOM_PP =
  max(0, SLICE_HEADROOM_PP - g)
```

**Critical anti-front-loading rule:** do not recalculate a new full 24h slice after every pass. The current fixed slice remains authoritative until it expires or the quota epoch changes.

## 5. Feedback behavior

The controller automatically corrects future pace:

- **under-spend:** more allowance remains over fewer future hours → next slice grows;
- **on-plan:** future trajectory remains approximately stable;
- **over-spend:** less allowance remains over future hours → next slice shrinks;
- **reset:** old trajectory is invalid → create a new quota epoch and re-anchor.

This feedback property is why no universal fixed model-to-quota coefficient is needed.

## 6. Conservative pass burn estimator

A pass can be admitted only if its quality-sufficient conservative burn fits the current effective headroom.

A comparable history sample should match materially on:

```text
allowance configuration
+ surface
+ role/class
+ model profile/tier
+ reasoning/speed posture
+ task shape
```

Use at most the five most recent compatible samples.

```text
BURN_HISTORY_COMPATIBLE=<YES|NO|UNKNOWN>
BURN_SAMPLE_i=<weekly pp delta>
```

A `CLEAN` sample can represent pass burn directly. A `MIXED` interval may be retained only as a conservative `UPPER_MIXED` bound; never attribute the whole mixed delta to one pass as exact fact.

Let `g` be meter granularity or the conservative observation buffer.

### 6.1. One sample

```text
B_SAFE =
  x + max(g, 0.50*x)

BURN_ESTIMATE_CONFIDENCE=LOW
```

### 6.2. Two samples

```text
m = max(x1, x2)

B_SAFE =
  m + max(g, 0.25*m)

BURN_ESTIMATE_CONFIDENCE=LOW
```

### 6.3. Three to five samples

```text
M = median(samples)
MAD = median(abs(sample - M))
ROBUST_SIGMA = 1.4826 * MAD
P80 = empirical 80th percentile

B_SAFE =
  max(
    P80,
    M + 1.645 * ROBUST_SIGMA
  ) + g
```

Confidence labels:

```text
3–4 samples -> MEDIUM
5 samples   -> HIGH
```

The median/MAD/P80 construction is a conservative planning heuristic. `1.645` is used as a one-sided normal-equivalent planning margin; **it is not a claim of a probabilistic guarantee**, because Work/Codex burn is not assumed to be normally distributed or stationary.

Record:

```text
BURN_ESTIMATE_WEEKLY_PP=<value|unknown>
BURN_ESTIMATE_CONFIDENCE=<LOW|MEDIUM|HIGH|UNKNOWN>
BURN_ESTIMATE_METHOD=<method>
```

## 7. Admission rule

Quality is non-negotiable:

```text
QUALITY_FLOOR=NON_NEGOTIABLE
```

A quality-sufficient pass fits the weekly controller when:

```text
B_SAFE <= EFFECTIVE_SLICE_HEADROOM_PP
```

If Scheduled Tasks have reserved burn, compare against interactive headroom after that reservation instead.

The 5-hour meter is a separate local circuit breaker. If the UI exposes it, construct a separate estimator in **5-hour percentage points** and require that it also fits. Weekly percentage points and 5-hour percentage points are different denominators and must not be compared directly.

If `B_SAFE=unknown`:

- use the smallest useful quality-sufficient bounded calibration gate when headroom is ample;
- obtain a fresh post-pass aggregate snapshot;
- do not claim deterministic continuity before observation;
- class 3–4/Astra with constrained headroom should `ПОДГОТОВКА`/`ПЕРЕНОС` rather than gamble.

## 8. Quality-preserving optimization order

When a desired pass does not fit the current slice, reduce **waste**, not quality:

1. reuse an accepted compact handoff/evidence package;
2. remove duplicate research, repeated audits and redundant agents;
3. batch naturally dependent internal steps inside the same gate;
4. remove non-decision-critical context or verbosity;
5. choose a cheaper tier/effort only if it is independently sufficient for the gate;
6. split the gate only if the split preserves verification and does not create more rework;
7. defer lower-value work to the next slice/reset.

Forbidden quota-saving shortcuts:

- model below minimum sufficient capability;
- removal of mandatory sources;
- skipping required tests/verification;
- replacing fresh evidence with stale evidence;
- accepting an incomplete gate merely to produce activity today.

If the quality-sufficient form still does not fit:

```text
QUOTA_DECISION=DEFER_FOR_QUALITY
```

## 9. Continuity feasibility

The regulator should explicitly distinguish a feasible daily-continuity plan from an impossible one.

```text
CONTINUITY_FEASIBLE =
  minimum useful quality-sufficient B_SAFE
  <= available current slice headroom
```

If false, it is mathematically dishonest to promise a useful Work/Codex pass every day without at least one of:

- reducing workload while preserving quality;
- changing schedule/priorities;
- waiting for reset;
- explicitly authorized paid capacity/reset where eligible.

The controller optimizes for continuous **useful** work, not for artificial daily activity.

## 10. Pace modes and observability

Normalize:

```text
WEEKLY_QUOTA_MODE=<ADAPTIVE|RECOVERY|FINAL_RELEASE|UNAVAILABLE>
```

- `ADAPTIVE` — normal stateful slice control.
- `RECOVERY` — current slice overspent or telemetry uncertainty requires conservative re-plan.
- `FINAL_RELEASE` — reserve is being released inside the last 72h; still subject to B_SAFE and quality.
- `UNAVAILABLE` — required first-party weekly meter/reset cannot be normalized.

Recommended ledger:

```text
QUOTA_EPOCH_ID=
WEEKLY_USED_PP=
WEEKLY_RESET_AT=
HOURS_TO_WEEKLY_RESET=
CONTROL_SLICE_ID=
CONTROL_SLICE_START_WEEKLY_USED_PP=
CONTROL_SLICE_BUDGET_PP=
SLICE_SPENT_PP=
EFFECTIVE_SLICE_HEADROOM_PP=
BURN_ESTIMATE_WEEKLY_PP=
BURN_ESTIMATE_CONFIDENCE=
QUALITY_FLOOR=NON_NEGOTIABLE
CONTINUITY_FEASIBLE=<YES|NO|UNKNOWN>
```

## 11. Meter lag and pending burn

After meaningful class 2–4 work:

```text
POST_PASS_METER_STATE=<UPDATED|PENDING|UNKNOWN>
PENDING_BURN=<YES|NO>
```

If the aggregate first-party meter has not plausibly reflected the prior run, do not stack another large run on top of unobserved burn.

A per-chat/task total can support diagnosis, but total weekly continuity is controlled from the aggregate allowance meter. Current first-party documentation notes that reporting can lag and that chat-level totals may not include all usage in some environments.

## 12. 5-hour local circuit breaker

The weekly controller does not replace shorter reset windows.

If a 5-hour percentage meter is available:

```text
FIVE_HOUR_USED_PP=
FIVE_HOUR_RESET_AT=
FIVE_HOUR_B_SAFE=<separate estimate>
```

Admission requires both the weekly and 5h constraints to fit.

Existing reset-aware policy remains:

- class 3–4 non-incident with 5h reset ≤15 minutes → prefer defer;
- do not consume a large 5h burst simply because the weekly slice still has capacity.

## 13. Scheduled work reservation

Recurring/triggered agentic work competes with interactive work for the same weekly objective.

Record:

```text
SCHEDULED_WEEKLY_COMMITMENT_PP=<estimate|unknown>
EXPECTED_SCHEDULED_BURN_BEFORE_SLICE_END_PP=<estimate|unknown>
```

Interactive headroom becomes:

```text
AVAILABLE_FOR_INTERACTIVE_WORK_PP =
  max(
    0,
    EFFECTIVE_SLICE_HEADROOM_PP
    - EXPECTED_SCHEDULED_BURN_BEFORE_SLICE_END_PP
  )
```

Never double-allocate the same percentage points to scheduled and interactive work.

## 14. Cross-cycle burn history

Burn history may cross weekly resets only if task economics remain materially compatible.

```text
BURN_HISTORY_COMPATIBLE=<YES|NO|UNKNOWN>
```

Invalidate or separate history after material changes in:

- plan/workspace allowance behavior;
- model profile/tier economics;
- Fast/reasoning posture;
- surface/role/class;
- task shape/context scale;
- product changes that alter usage accounting.

A quota reset alone does not make otherwise compatible burn observations useless; it only invalidates the current slice/epoch ledger.

## 15. Reference implementation

The repository ships:

```text
scripts/weekly_quota_controller.py
```

It implements the reserve schedule, fixed control-slice planner, stateful slice status, robust burn estimator and deterministic self-tests.

Reference check:

```bash
python3 scripts/weekly_quota_controller.py \
  --weekly-used 0 \
  --hours-to-reset 168 \
  --self-test
```

The script is a reproducible reference calculation, not a replacement for fresh first-party account telemetry.

## 16. Official sources

- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/20001507-paid-weekly-work-and-codex-rate-limit-resets
- https://help.openai.com/en/articles/20001478-reviewing-work-and-codex-usage-and-using-personal-analytics-in-chatgpt-desktop
- https://help.openai.com/en/articles/12642688
