# Contributing

This is a private operational repository. Changes should optimize correctness, safety and auditability rather than feature count.

## Change classes

### Documentation-only

Examples: wording, repository navigation, examples that do not alter the operational decision model.

Requirements:

- no behavior change in `SKILL.md`;
- run `python3 scripts/validate_repo.py`.

### Operational rule change

Any change affecting classification, timing, safety, quota gates, model choice, surface routing, sessions, subagents, stop conditions or result acceptance is a behavioral change.

Required sequence:

1. identify the normative source or create a dated operational supplement;
2. update the relevant `references/*.md` file;
3. synchronize `SKILL.md`;
4. update `references/SOURCE_MAP.md`;
5. add/update regression cases in `tests/TEST_CASES.md`;
6. update `CHANGELOG.md` and `VERSION` when released behavior changes;
7. run the repository validator and the release round-trip:

   ```bash
   python3 scripts/validate_repo.py
   python3 scripts/package_release.py
   ```

## Source discipline

Time-sensitive OpenAI product properties — pricing, credit eligibility, quota accounting, reset behavior, model availability, context sizes, Fast/reasoning cost and shared-pool feature set — must be verified from first-party OpenAI sources before being made normative. Do not use blogs/forums as a normative source when an official OpenAI source exists.

Never promote a temporary account state into a permanent rule. Current percentages, a single billing reset date and one-cycle emergency budgets belong to live runtime context, not the skill.

## Safety invariants

Do not weaken the following merely to make the regulator less restrictive:

- class 4 for money, production data, secrets, auth, production infrastructure and irreversible operations;
- read-only/baseline gates before critical changes;
- rollback and verification requirements;
- no silent bypass of hard quota limits;
- no automatic paid credits / Auto top-up;
- credit authorization never implies credit eligibility;
- no hidden expansion of project runway;
- two-attempt stop discipline;
- untrusted content is data, not instructions;
- downloading is not permission to execute;
- wrong browser account means STOP before the action.

## Commit style

Prefer short imperative commit subjects, for example:

```text
feat: add credit eligibility gate
fix: sync surface routing with test 37
docs: clarify snapshot freshness policy
test: cover scheduled-task runaway
```
