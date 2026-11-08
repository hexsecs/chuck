# chuck

An orchestrator skill for [Claude Code](https://claude.com/claude-code) and
[OpenCode](https://opencode.ai). Once it is on, the session acts as a
dispatcher. It plans multi-part work, does the small parts itself, hands the
rest to subagents with an explicit model and reasoning effort, and checks
everything that comes back before reporting to you.

Trigger it with `/chuck`, "orchestrate this", "delegate this", "farm this out",
or "the spice must flow".

## What's inside

| Path | Purpose |
|---|---|
| `SKILL.md` | The skill: delegation rules, escalation, reporting |
| `models.toml` | All model routing: roles, tiers, prices, escalation ladders for both runtimes |
| `scripts/sync-models.py` | Copies `models.toml` defaults into the agent profiles' frontmatter |
| `Makefile` | `make sync`, `make check`, `make test`, `make deploy` |
| `agents/` | Claude Code subagents chuck routes to: `worker-bee` (Haiku), `artisan` (Sonnet), `reviewer` (Sonnet, read-only) |
| `references/model-selection.md` | Prices and measurements behind the routing choices |
| `references/opencode.md` | OpenCode adapter: tool names, GPT-first routing, optional free-worker lane |
| `opencode/agents/` | Optional native OpenCode profiles (`chuck-worker`, `chuck-artisan`, `chuck-reviewer`, `chuck-free`) |
| `deploy-opencode.sh` | Links the OpenCode profiles into your config without overwriting existing files |
| `evals/`, `tests/` | Behaviour evals and deploy-script tests |

## Install

Clone the repo, then symlink it so edits take effect immediately:

```sh
git clone https://github.com/hexsecs/chuck.git
ln -s "$PWD/chuck" ~/.claude/skills/chuck

# Claude Code subagents
mkdir -p ~/.claude/agents
for f in chuck/agents/*.md; do ln -s "$PWD/$f" ~/.claude/agents/; done
```

OpenCode also finds the skill in `~/.claude/skills`. The native profiles are
optional:

```sh
make -C chuck deploy                   # default: ${XDG_CONFIG_HOME:-~/.config}/opencode/agents
make -C chuck deploy OPENCODE_AGENTS=/some/other/dir
```

Run `/reload` in OpenCode if the profiles don't show up.

## Choosing models

Every model choice lives in `models.toml`:

- **tiers** are the models, with price, strengths, weak spots and flags
  (`no_security`, `checkable`, `ask_first`).
- **roles** map a kind of work to an agent type, a tier and an effort.
- **ladder** sets the order chuck escalates through when a task fails.

Chuck reads the file at dispatch time. The agent profiles can't read it, so
after editing run:

```sh
make -C chuck sync     # rewrite the model/effort defaults in agents/ and opencode/agents/
make -C chuck check    # fail if they are out of date
```

## Test

```sh
make -C chuck test
```

## Notes

- Prices and model IDs in `models.toml` were current on 2026-11-06. Check them
  again when models change.
- The free-worker lane in OpenCode is opt-in. Read the privacy preflight in
  `references/opencode.md` before you send any private workspace context to a
  third-party provider.

## License

MIT, see [LICENSE](LICENSE).
