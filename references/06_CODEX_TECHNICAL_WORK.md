# Codex technical work discipline

**Version:** 2.2  
**Status:** normative

## 1. Codex role

Codex owns technical implementation: repository, code, commands, tests, Git and technical systems.

## 2. Executor independence

A Codex handoff must be self-contained:

```text
HANDOFF_SELF_CONTAINED=YES
EXECUTOR_SKILL_REQUIRED=NO
```

If Chat used the regulator to route/admit the pass, Codex does **not** need the regulator installed and must not be asked to locate/load/apply it as a prerequisite.

Chat/control plane resolves quota/model/admission before launch. Codex receives only the execution contract.

Reading `SKILL.md` remains allowed when it is itself part of the repository/task read/write scope.

## 3. Read-only first

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

## 4. Exact scope

Executor packet must contain:

- allowed read scope;
- allowed write scope;
- no-touch list;
- tests/evidence;
- rollback;
- stop conditions.

No opportunistic refactor.

## 5. Class 4

First entry:

```text
STRICT READ-ONLY BASELINE.
NO MUTATION.
STOP AFTER REPORT.
```

After approved plan:

```text
BOUNDED MUTATION ONLY.
STOP ON DRIFT OR SCOPE EXPANSION.
```

## 6. Git

- inspect `git status`;
- exact-file staging;
- never `git add .`;
- no force push;
- no secrets/customer data/backups/db files outside explicit necessary scope;
- push/deploy only when explicitly inside the gate.

## 7. Evidence

Completion needs relevant changed files, diff summary, test/build/lint/runtime evidence and final Git state.

## 8. Handoff efficiency

If Chat/Work already researched facts, Codex receives a compact accepted fact pack and should not repeat the same public research unless implementation requires a specific verification.

Do not forward control-plane-only fields such as quota epoch, trajectory headroom, quota/pace risk or paid-reset state unless Codex's explicit task is to inspect those values.

Optional executor instruction:

```text
EFFICIENCY_POSTURE=MINIMIZE_WASTE_WITHOUT_QUALITY_LOSS
```

## 9. Official sources

- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
