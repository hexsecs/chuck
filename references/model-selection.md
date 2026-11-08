# Model selection for subagents: evidence

Supporting notes for `SKILL.md`. Read when you need the numbers behind a
routing choice, not on every invocation.

These are Claude API notes, not GPT benchmarks or estimates for a ChatGPT
subscription. OpenCode uses `opencode.md` and live model discovery instead.
The historical measurements below have incomplete source provenance; treat
them as hypotheses for routing, not verified cross-provider capability rankings.

## Prices (Claude API, USD per million tokens, checked 2026-11-06)

| Model             | ID                  | Input  | Output | Notes                                    |
|-------------------|---------------------|--------|--------|------------------------------------------|
| Claude Haiku 5.5  | `claude-haiku-5-5`  | $0.10  | $0.50  | $0.50 / $2.50 for prompts over 100K; refusals have no server-side fallback; effort default `medium` |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2.00  | $10.00 | effort default `high`                    |
| Claude Opus 5.5   | `claude-opus-5-5`   | $4.00  | $20.00 | effort default `medium`                  |
| Claude Fable 5.1  | `claude-fable-5-1`  | $10.00 | $50.00 |                                          |

Source: the Claude API reference bundled with Claude Code (`claude-api` skill,
model table cached 2026-10-06). Re-check when models change.

## Measured cost per solved task (SWE-bench Pro)

Carried over from earlier working notes; the original sources were not
recorded (as of 2026-11-06). Add them here if found.

| Setup                                           | Solved | Cost per solved task |
|-------------------------------------------------|--------|----------------------|
| Opus, low effort                                | 87%    | ~$0.12 (matched Sonnet at high) |
| Opus, medium effort                             | 93%    | ~$0.22               |
| Fable, high effort                              | 92%    | ~$1.19               |
| Opus, everything at high                        | 95%    | ~$0.29               |
| Opus low, re-run only failures at high          | ~97%   | ~$0.17               |

Accuracy gap noted for Haiku: ~85% vs ~91% GPQA (source not recorded).

## Delegation

A subagent starts with a fresh context and no shared prompt cache. Workers
saved money only on routine, many-unit work or work too big for one context;
otherwise the orchestrator doing it itself at lower effort won.
