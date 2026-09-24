# Source map

**Verified:** 2026-09-24
**Skill release:** 4.0

This file separates volatile OpenAI product facts from project policy.

## Current first-party OpenAI product facts

### ChatGPT Work and Codex
https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

Used for Chat/Work/Codex roles, shared Work/Codex usage structure, GPT-6 Sol/Luna in Work/Codex, Plus Astra availability, and plan/workspace-dependent model picker behavior. Volatility: HIGH.

### Using Codex with your ChatGPT plan
https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan

Used for the account usage dashboard as source of truth and the fact that usage depends on model, task complexity, context, reasoning, speed and tools. Volatility: HIGH.

### Managing usage with GPT-6 Astra in Work and Codex
https://help.openai.com/en/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex

Used for general allowance behavior only. The regulator does not hardcode a five-hour limit by plan; it uses windows returned by the current account snapshot. Volatility: HIGH.

### Model selection
https://developers.openai.com/api/docs/guides/model-selection

Used for Astra/Sol/Luna task-fit guidance and model-vs-reasoning selection. Volatility: MEDIUM.

### GPT-6 model pages
https://developers.openai.com/api/docs/models/gpt-6-astra
https://developers.openai.com/api/docs/models/gpt-6-sol
https://developers.openai.com/api/docs/models/gpt-6-luna

Used for canonical ids, supported reasoning efforts, context and output limits. Volatility: MEDIUM.

### Reasoning and migration
https://developers.openai.com/api/docs/guides/reasoning
https://developers.openai.com/api/docs/guides/latest-model

Used for reasoning-effort semantics and GPT-6 compatibility constraints. Volatility: MEDIUM.

### Skills guidance
https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra

Used for progressive disclosure and avoiding bloated root skill instructions. Volatility: MEDIUM.

## Plugin / MCP / auth sources retained from v3

https://developers.openai.com/plugins/build/mcp-server
https://developers.openai.com/plugins/build/auth
https://developers.openai.com/plugins/build/plugins
https://github.com/modelcontextprotocol/python-sdk
https://github.com/openai/openai-apps-sdk-examples
https://github.com/openai/codex

## Project policy — not OpenAI limits

- 10 percentage-point weekly reserve.
- 50% reserve cap.
- final 360 active-minute reserve release.
- one-workday normal lookahead.
- two-workday bounded advance.
- task classes and model starting matrix.
- burn-history compatibility key.
- quality-first quota-pressure behavior.
- default 09:00–23:00 working window.

Current account/workspace state overrides stale availability assumptions.
