# Active-work-window weekly runway

**Policy version:** v4.0
**Status:** normative project policy

```text
WORKDAY_START_LOCAL=09:00
WORKDAY_SOFT_END_LOCAL=22:00
WORKDAY_HARD_END_LOCAL=23:00
ACTIVE_DAYS=MON,TUE,WED,THU,FRI,SAT,SUN
TASK_DURATION_LIMIT=NONE
```

The user may override the schedule. It controls when quota is expected to be consumed, not a task timeout.

Compute ACTIVE_MINUTES_TO_RESET as the overlap between now..weekly-reset and configured active windows. Sleeping/off-hours do not consume planned runway.

At a fresh weekly anchor:

```text
U0=weekly used pp
A0=active minutes from anchor to reset
R0=100-U0
Z0=min(10,0.50*R0)
S0=max(0,R0-Z0)
```

The reserve releases during the last 360 active minutes.

For current remaining active minutes A:

```text
S_REMAINING(A)=S0*A/A0
Z_REMAINING(A)=Z0*clamp(A/min(360,A0),0,1)
TARGET_SPENT(A)=R0-S_REMAINING(A)-Z_REMAINING(A)
```

Keep one epoch anchor until reset/allowance architecture changes. Normal lookahead is one configured active workday; bounded advance is two.

Default 09:00-23:00:

```text
BASE_LOOKAHEAD_ACTIVE_MINUTES=840
MAX_ADVANCE_ACTIVE_MINUTES=1680
```

Weekly is the core runway. If the current snapshot reports another window, enforce it independently. If a valid weekly snapshot contains no secondary window, proceed weekly-only. Absence is not exhaustion.

Use observed compatible shared-allowance movement. Never convert API token prices or public credit rates into weekly pp. Subtract already-admitted Work/Codex commitments before allocating the same future allowance twice.

If fitting runway would require weakening required model, reasoning, sources, tests or verification: QUOTA_DECISION=DEFER_FOR_QUALITY and continue useful ChatGPT work.
