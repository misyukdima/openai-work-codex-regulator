# Adaptive model + reasoning router

**Policy version:** v4.0
**Verified:** 2026-09-24
**Status:** normative project policy

ChatGPT is the regulator. Work and Codex are execution planes.

```text
QUALITY_FLOOR=NON_NEGOTIABLE
TASK_FIT_FIRST=YES
CAPABILITY_FAILURE_NE_REASONING_FAILURE=YES
```

## Canonical state

```text
MODEL_FAMILY=<GPT6|LEGACY|OTHER|UNKNOWN>
MODEL_ID=<canonical id|UNKNOWN>
MODEL_ALIAS=<ASTRA|SOL|LUNA|OTHER|UNKNOWN>
REASONING_EFFORT=<NONE|LOW|MEDIUM|HIGH|XHIGH|MAX|UNKNOWN>
EXECUTION_PRESET=<STANDARD|ULTRA|UNKNOWN>
SPEED_MODE=<STANDARD|FAST|UNKNOWN>
```

MAX is a reasoning effort. Ultra, when available, is not silently treated as that enum or as guaranteed multi-agent execution.

## Starting policy

| Class | Starting target |
|---|---|
| MECHANICAL | Luna Low |
| ROUTINE | Luna Medium |
| PROFESSIONAL | Sol Medium |
| COMPLEX | Sol High |
| CRITICAL | Astra High |

Astra Low/Medium can be preferable to Sol xhigh/max when capability breadth rather than deliberation is the bottleneck. Sol Low fits focused writing/editing, fact checking, simple code and straightforward app work. Sol xhigh fits deep verification when Sol remains the right capability level. Max is reserved for reasoning-depth bottlenecks and only when exposed now.

## Candidate selection

Classify the gate, set minimum capability and reasoning, read currently available options, reject unavailable and below-quality combinations, then prefer the best compatible observed burn/runway posture. With no history, use the lightest sufficient policy starting point and calibrate conservatively.

Reasoning-depth failure -> same model, higher effort.

Capability failure -> Luna to Sol or Sol to Astra, initially at equal/lower effort when sufficient.

Permission/account/network/CAPTCHA/source/safety/authorization blockers -> no model escalation.

Quota pressure may select a lighter candidate only after it independently passes the quality floor.

```text
BURN_PROFILE_KEY=SURFACE:MODEL_ID:REASONING_EFFORT:EXECUTION_PRESET:TASK_CLASS:CONTEXT_BAND
```

No fixed Astra:Sol:Luna conversion ratio is normative.
