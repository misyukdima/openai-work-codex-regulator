# Architecture — v4.0

## Control plane

```text
ChatGPT
  ├─ task / quality classification
  ├─ current quota snapshot
  ├─ active-work-window runway
  ├─ observed burn compatibility
  ├─ surface selection
  └─ model + reasoning admission
          │
     ┌────┴────┐
     ▼         ▼
    Work      Codex
     └────┬────┘
          ▼
      evidence
          ▼
       ChatGPT
```

ChatGPT is the primary orchestrator. Work and Codex are execution planes. Handoffs are self-contained.

## Quota acquisition

```text
ChatGPT
 -> connected read-only Regulator Plugin/App
 -> authenticated server-side backend
 -> official Codex app-server
 -> account/rateLimits/read
 -> normalized quota facts
```

The backend has no admission authority. Missing fields remain unknown/absent.

## Weekly runway

v4 replaces raw wall-clock pacing with active working minutes. Default planning window is 09:00–23:00 local, with 22:00 as normal soft end; users can override schedule/days.

One quota epoch is anchored to weekly used pp and active minutes remaining to weekly reset. Off-hours do not consume planned runway.

Project-policy reserve, one-workday normal lookahead and two-workday bounded advance are described in references/14_WORK_SCHEDULE_RUNWAY.md.

## Secondary quota windows

No plan-wide five-hour assumption is hardcoded. A secondary window is enforced only when the current normalized account snapshot reports it. Different denominators remain separate.

## Model router

The router is quality-first:

```text
required quality
 -> minimum sufficient capability
 -> minimum sufficient reasoning
 -> available candidates
 -> compatible observed burn/runway
 -> launch
```

Capability failure and reasoning-depth failure are distinct. Product facts live in references/MODEL_CAPABILITY_SNAPSHOT.json; project routing policy lives in references/08_MODEL_REASONING_ROUTER.md.

## Security inheritance

v4 inherits v3 development hardening: subject-isolated auth, sealed credential lifecycle, production-safe provider boundaries, OIDC/JWKS verification, exact read-only MCP tool surface, and hardened host crypto-helper socket semantics.

The static host credential key is not model-visible and repository code does not implement equivalent Python cryptography.

## Packaging and CI

The root and packaged SKILL.md must remain byte-identical. v4 CI runs repository, routing, plugin, release-contract, auth, transport and production-provider checks. scripts/package_release.py validates source and clean unpacked ZIP before publication.
