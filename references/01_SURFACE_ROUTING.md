# Surface routing: Chat vs Work vs Codex

**Version:** 1.1  
**Verified:** 2026-08-22  
**Status:** normative

## 1. Product roles

OpenAI currently documents the experiences as:

- Chat — fast conversational help and everyday questions;
- Work — longer, multi-step research/analysis and finished deliverables, with files/apps/browser-style work and Scheduled Tasks where available;
- Codex — software development and technical work: code, tests, commands, repositories.

This regulator turns those product roles into a quota-saving routing rule.

## 2. Routing rule

Use the cheapest surface that has the capabilities the task genuinely needs.

### CHAT

Use for:

- discussing strategy;
- reviewing an agent report;
- drafting the next bounded prompt;
- deciding between alternatives;
- compact handoff;
- ordinary questions.

Do not start an agentic run merely because the task is important.

### Bounded Chat (CHAT_BOUNDED_WEB)

Ordinary Chat with its built-in web/file capabilities is cheaper than a full agentic pass. A simple task must not automatically lose to Work.

`CHAT_BOUNDED_WEB` fits when all of the following hold:

- simple lookup / short web research;
- usually no more than 3–5 public pages;
- no login;
- no persistent browser state;
- no external action;
- no autonomous monitoring;
- no schedule;
- no complex multi-step connected-app workflow;
- ordinary Chat already has the web/file capabilities needed.

Examples that must NOT automatically route to WORK:

- find one current fact;
- check 1–3 public sources;
- briefly summarize an attached file;
- analyze material the user already supplied;
- create a simple artifact from already-supplied content when no multi-step agentic work is required.

### WORK

Use for:

- live web/browser research beyond bounded Chat scope;
- connected apps/files;
- multi-source fact packs of significant volume;
- office/document deliverables;
- scheduled monitoring;
- multi-step non-code workflows;
- controlled external actions with approval.

### CODEX

Use for:

- source code;
- repository inspection/change;
- terminal commands;
- test/build/lint;
- Git diff/commit;
- technical server/config/deploy;
- debugging systems.

## 2.1. WHY_AGENTIC gate

Before any expensive agentic pass, record:

```text
WHY_AGENTIC=<why ordinary Chat is insufficient>
VALUE_OUTPUT=<which verifiable result closes the gate>
```

If `WHY_AGENTIC` does not explain why ordinary Chat is insufficient, prefer CHAT or PREPARE.

## 2.2. User surface override

```text
USER_SURFACE_OVERRIDE=YES
```

If the user explicitly insists on Work after one quota-saving CHAT recommendation, and safety/quota gates pass, respect the user's choice. The override does not cancel safety gates, paid-credit policy, capability gates or forbidden actions.

## 3. One-gate owner

```text
ONE_GATE = ONE_PRIMARY_SURFACE
```

If Work already produced a sufficient research/fact pack, Codex receives a compact handoff and does not repeat full research.

If Codex already audited a repo/config, Work does not perform a second full technical audit unless a distinct independent verification is explicitly required.

## 4. Cross-surface handoff

Minimum package:

```text
GOAL
FACTS / SOURCES
DECISIONS
EXACT SCOPE
FORBIDDEN SCOPE
OPEN QUESTIONS
EXPECTED OUTPUT
STOP CONDITION
```

Avoid copying the entire source conversation.

## 5. Official source

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
