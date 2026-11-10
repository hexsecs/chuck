---
tags: [skill-creator]
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill]
---

You are in OpenCode. Dry-run only: do not dispatch agents or read project files.
Chuck is active. My model is `opencode/minimax-m3.1-flash-free` (a $0 free model).
I have three independent synthetic classification units with exact JSON outputs,
and one security review of a diff.

Tell me your routing decision: which lane you detected, the exact model route
and effort encoding for each unit and for the review, and what you would do if
the preferred native agent were not advertised. Available agents: general,
explore. Models: openai/gpt-6-luna (low, medium, high),
openai/gpt-6.1-sol (low, medium, high, xhigh),
opencode/inkling-2-small-free (low, medium, high),
opencode/minimax-m3.1-flash-free (low, medium, high, xhigh),
opencode/flint-40b-free (low, medium, high, xhigh). subagent has model but no
effort parameter. Do not ask for confirmation just to proceed: give the default
and explain the lane boundary.
