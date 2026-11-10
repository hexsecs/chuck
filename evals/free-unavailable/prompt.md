---
tags: [skill-creator]
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill]
---

You are in OpenCode with Chuck active. Dry-run only; do not dispatch or call
external services. My model is `openai/gpt-6.1-sol`, so this is the GPT lane.
I have five independent synthetic classification units with
exact JSON outputs and opted into free workers and workflows. The selected
opencode/inkling-2-small-free route just returned a rate-limit error. The only
delegation tool is subagent, with agent/model/background/sessionID parameters
but no effort argument. Only general and explore agents are advertised.
Models available: openai/gpt-6-luna (low, medium, high),
openai/gpt-6.1-sol (low, medium, high, xhigh). There is no Workflow or fork tool.
Describe fallback, parallel dispatch, verification and reporting. Do not retry
the rate-limited free request or select a paid API provider.
