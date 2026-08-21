# Codex technical work discipline

**Version:** 1.1  
**Status:** normative

## 1. Codex role

Codex owns technical implementation: repository, code, commands, tests, Git and technical systems.

## 2. Read-only first

Before mutation establish:

```text
identity/environment
repo/root
branch/HEAD/status
runtime/service state if relevant
exact target files
existing drift
```

Stop on unexplained drift.

## 3. Exact scope

Prompt must contain:

- allowed read scope;
- allowed write scope;
- no-touch list;
- tests;
- rollback point;
- stop conditions.

No opportunistic refactor.

## 4. Class 4

First entry:

```text
STRICT READ-ONLY BASELINE.
NO MUTATION.
STOP AFTER REPORT.
```

After an approved plan:

```text
BOUNDED MUTATION ONLY.
If baseline drift or scope expansion is required: STOP.
```

## 5. Git

- inspect `git status` before change;
- exact-file staging;
- never `git add .`;
- no force push;
- no secrets/customer data/backups/db files;
- push/deploy only when explicitly part of the pass.

## 6. Evidence

A Codex completion claim needs relevant evidence:

- changed files;
- diff summary;
- test commands/results;
- build/lint if applicable;
- runtime verification if applicable;
- Git state.

## 7. Work handoff

If Work already researched external facts, pass a compact fact pack to Codex. Codex should not spend shared usage re-browsing the same public sources unless the implementation requires a specific verification.

## 8. Official sources

- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
