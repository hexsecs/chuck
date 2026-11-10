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
| `SKILL.md` | The skill: delegation rules, lane detection, escalation, reporting |
| `models.toml` | All model routing: roles, tiers, prices, escalation ladders for both runtimes |
| `scripts/sync-models.py` | Copies `models.toml` defaults into the agent profiles' frontmatter |
| `scripts/scan-models.py` | Scans the OpenCode catalog for free ($0) models and updates `[opencode.free_candidates]` |
| `Makefile` | `make sync`, `make check`, `make test`, `make scan`, `make deploy-claude`, `make deploy-opencode` |
| `agents/claude/` | Claude Code subagents chuck routes to: `worker-bee` (Haiku), `artisan` (Sonnet), `reviewer` (Sonnet, read-only) |
| `agents/opencode/` | Optional OpenCode profiles: `chuck-worker`, `chuck-artisan`, `chuck-reviewer`, `chuck-free` |
| `references/model-selection.md` | Prices and measurements behind the routing choices |
| `references/opencode.md` | OpenCode adapter: tool names, main-model lane detection, discovery pass, optional free-worker lane |
| `deploy.sh` | `deploy.sh claude\|opencode [dir]` links one runtime's profiles into its config without overwriting existing files |
| `evals/`, `tests/` | Behaviour evals and deploy/scanner tests |

## Install

Clone the repo, then symlink it so edits take effect immediately:

```sh
git clone https://github.com/hexsecs/chuck.git
ln -s "$PWD/chuck" ~/.claude/skills/chuck

make -C chuck deploy-claude           # links agents/claude/*.md into ~/.claude/agents
```

OpenCode also finds the skill in `~/.claude/skills`. The native profiles are
optional:

```sh
make -C chuck deploy-opencode         # default: ${XDG_CONFIG_HOME:-~/.config}/opencode/agents
make -C chuck deploy-opencode AGENTS_DIR=/some/other/dir
```

Run `/reload` in OpenCode if the profiles don't show up.

## Choosing models

Every model choice lives in `models.toml`:

- **tiers** are the models, with price, strengths, weak spots and flags
  (`no_security`, `checkable`, `ask_first`).
- **roles** map a kind of work to an agent type, a tier and an effort.
- **ladder** sets the order chuck escalates through when a task fails.

In OpenCode, subagents mirror the coordinator's lane: `openai/*` uses the GPT
ladder (`ladder` / `tier`), a `$0` `-free` model uses the Free ladder
(`free_ladder` / `free_tier`). Escalation never crosses providers. The
`[opencode.free_candidates]` table is generated from the catalog; picking the
ladder from it is a measured decision, not a capability ranking.

Chuck reads the file at dispatch time. The agent profiles can't read it, so
after editing run:

```sh
make -C chuck sync     # rewrite the model/effort defaults in agents/claude/ and agents/opencode/
make -C chuck check    # fail if they are out of date
```

To refresh the free-model candidate list from the OpenCode catalog:

```sh
make -C chuck scan     # lists free model ids (no cost data)
```

The scanner's real cost data comes from the in-session `opencode.models` tool;
see `references/opencode.md` for the Code Mode invocation that writes
`[opencode.free_candidates]`.

## Test

```sh
make -C chuck test
```

## Notes

- Prices and model IDs in `models.toml` were current on 2026-11-09. Check them
  again when models change.
- The OpenCode Free lane mirrors a `$0` coordinator model. The cross-provider
  free-worker lane is opt-in: read the privacy preflight in
  `references/opencode.md` before you send any private workspace context to a
  third-party provider.

## License

MIT, see [LICENSE](LICENSE).
