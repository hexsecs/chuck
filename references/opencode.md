# OpenCode adapter

Read this before dispatching in OpenCode. This adapter takes precedence over
Claude Code routing, tool names, effort and pricing in `SKILL.md`.

## Tools and agents

- Delegate with `subagent({agent, description, prompt, model, ...})`, using the
  tool's actual schema. Set `model` explicitly to `provider/model#variant`.
  There is no separate `effort` argument in the current schema. Record effort
  in the manifest and brief, but a prompt asking for effort does not configure it.
- Built-in child agents are `general` (implementation, planning, review) and
  `explore` (read-only exploration). `plan` is primary-only, not a child agent.
  Prefer advertised `chuck-*` agents when installed; otherwise use these built-ins.
  A review on `general` needs an explicit read-only brief; it is not permission-enforced.
- Ask with `question({questions:[{header, question, options, multiple:true}]})`.
  `multiple`, not `multiSelect`, enables the next-steps multi-picker.
- Run independent calls together. Use `background:true` only when there is
  independent work to do; completion notifications arrive automatically. Do
  not poll, sleep or repeat the job. Use `sessionID` for follow-ups, not `fork`.
- Workflow is optional and absent in many OpenCode sessions. User opt-in alone
  does not make a missing tool available. Fall back to parallel subagent calls.
- The coordinator owns dispatch: OpenCode's built-in general child cannot
  launch more children. Do not ask it to orchestrate nested delegation.
- Tool schemas and higher-priority permission rules always win over this skill.
- `scripts/scan-models.py` scans the live catalog for $0 models and updates
  `[opencode.free_candidates]`; it never picks `free_ladder` for you.

## Main-model lane and discovery pass

Subagents mirror the coordinator's lane. Identify the coordinator model before
the first dispatch, then discover and validate the lane's models.

### 1. Identify the coordinator model

Read the `Your Model` block (provider ID + model ID) from the runtime context
or your self-knowledge (e.g. `openai/gpt-6.1-sol`, `opencode/minimax-m3.1-flash-free`).
Re-detect each session; the user changing the session model mid-session
changes the lane.

| Coordinator model | Lane | Ladder / role key |
|---|---|---|
| Provider `openai`, `openai/*` | **GPT** | `ladder` / `tier` |
| Model ID contains `-free` (e.g. `opencode/*-free`) or otherwise $0 cost | **Free** | `free_ladder` / `free_tier` |
| Other / local (`lmstudio/...`, etc.) or unknown | **Same provider as coordinator** | discover that provider's models; do not invent a lane, and do not switch providers without approval |

Never route subagents to a different provider than the coordinator, except the
opt-in `free` role in the GPT lane (see below). Escalation stays in the lane.

### Free lane scope: checkable, non-security units only

Every Free-lane tier is `no_security` + `checkable`. That makes the lane safe
for bounded, verifiable work and wrong for anything needing judgment or
security. In `models.toml` the `hard`, `review` and `design` roles therefore
have **no `free_tier`** — they are GPT-lane-only.

- In the Free lane, those roles **stop and ask**; do not substitute a free tier.
- `checkable` output needs a stronger tier to read it next. `free_hard` is the
  top of `free_ladder`, so nothing may start there: `worker` starts at
  `free_small`, `implement` at `free`, and both escalate upward.
- `tests/test_models_config.py` enforces both rules; a config that breaks them
  fails `make test`.

### 2. Discovery pass (`opencode.models`)

Run once per session before the first dispatch, and refresh on
model/variant unavailability. Through Code Mode `execute` when applicable.
Searching free models is just a query — e.g. `opencode.models({query:"free"})`
lists all `$0` models with their providers, variants and costs.

**Use `scripts/scan-models.py` for this.** It calls `opencode.models` for the
lane provider, filters to active $0 models, prints a role-coverage table, and
updates the generated `[opencode.free_candidates]` list in `models.toml`:

```python
# Code Mode
spec = importlib.util.spec_from_file_location(
    "scan_models", "scripts/scan-models.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
cands = await mod.scan_free_models(query=models_tool, providers=("opencode",))
print(mod.render(cands))
mod.update(cands)          # writes [opencode.free_candidates] into models.toml
mod.check(cands)           # 1 if models.toml disagrees with the catalog
```

CLI fallback: `python3 -I scripts/scan-models.py --scan|--update|--check`.
The `opencode` CLI in this session has no `--json` flag, so the CLI path
raises; use the Code Mode path above.

1. **GPT lane:** query `provider:"openai"`. Confirm each `ladder` tier exists,
   is `active`, and supports the role `effort` variant (e.g. `luna` at `low`,
   `sol` at `medium`/`high`/`xhigh`). The GPT lane has no generated candidate
   list; `[opencode].ladder` is maintained by hand from discovery.
2. **Free lane:** run the scanner (`providers=("opencode",)` for the default
   lane). It writes `[opencode.free_candidates]` — the current $0 catalog —
   from which `free_ladder` is picked. Choosing the ladder is a
   human/measured decision: the list records cost, variants and release date,
   not quality. In this session (2026-11-09) `opencode` had 11 `$0` models
   (see `free_candidates`); `openrouter/*:free` models are a *different
   provider* — candidates only after the user approves switching providers.
3. **Other provider:** query that provider (`provider:"<id>"`) and use its
   models only; scan with `--provider <id>` / `providers=("<id>",)`.
4. If a configured tier is missing, inactive, or its variants stop supporting
   the role effort, say so in the manifest and use the nearest available
   model in the *same lane/provider* — do not guess a new ID, and do not
   jump lanes. If no model in the lane is available, ask the user.
5. Model catalog entries do not prove authentication, reachability, quality
   or quota. Run a small bounded task before depending on a new model.

Preferences inside a lane: prefer the user's existing route (`openai/...`
for GPT; the coordinator's `opencode/*-free` provider for Free). Do not
silently substitute `openrouter/openai/...`, another metered API, or require
an API key. A ChatGPT subscription is not unlimited: optimize quota,
latency, context size and retries per completed task, not hypothetical API
spend. Empty `cost` metadata means unknown, not zero. Catalog prices on
another provider do not describe the user's subscription. Do not promise
remaining quota or dollar savings without measurement.

### Routing profile: `[opencode]` in `models.toml`

Roles, tiers and ladders live in the skill's `models.toml`. Use `explore`
for read-only fallbacks and `general` for edits. The profile is a starting
policy, not a measured ranking or Claude equivalence. Revalidate its IDs
against the discovery pass at runtime.

Dispatch as `model:"<tier model>#<role effort>"`, where `<tier model>` comes
from the lane's key: e.g. `implement` is `openai/gpt-6.1-sol#medium` in the
GPT lane (`tier:"sol"`) and `opencode/minimax-m3.1-flash-free#medium` in
the Free lane (`free_tier:"free"`). If a model has no variants, omit the
`#...` suffix and record effort as unsupported. Do not infer that newer,
more expensive or differently named models are stronger. Other GPTs
(including Terra and Astra) and other free models remain available for
explicit user choice or measured profile updates; do not automatically
route hard work to an untested model.

The reviewer is a different child session from the author, at the same or
a better-validated capability level in the same lane; using the same model
at higher effort is fine. Free-lane output is checked by a higher free tier
or a deterministic test; GPT-lane output by GPT or a deterministic test.

Hard rules: `no_security` tiers never get security content (vulnerabilities,
exploits, attacks); `checkable` output must be JSON/tests or a stronger
lane tier's input and is never passed on unreviewed; never pick an
`ask_first` tier unprompted. In the Free lane every tier is
`no_security`+`checkable`, so a security task has no eligible free tier —
stop and ask before using a paid tier. That is also why `hard`, `review` and
`design` carry no `free_tier`: they are GPT-lane-only.

## Optional cross-provider free worker (GPT lane only)

This applies only in the GPT lane, where a free worker would be a *different
provider* than the coordinator. In the Free lane, free tiers are the default
(same provider as the coordinator), so no extra opt-in or preflight is needed
beyond normal dispatch; skip this section.

In the GPT lane, use a free worker only if the user has opted in. Opting in
to free workers is not consent to disclose private workspace context. Use one
only after the context preflight below, for small bounded units with an
exactly checkable output, not implementation, final review, security
analysis or architectural judgment. Keep briefs short and request JSON or
precise file/line references. A free model with a long prompt and a GPT redo
can cost more quota and time than a direct GPT call.

- Confirm zero input/output prices on the exact selected route via discovery.
  Availability, rate limits and free offers can change. Never silently fall
  back to paid.
- **Context preflight:** a new external provider is a new data destination.
  Child sessions can receive project instructions, skills and references even
  with tools denied. A public/synthetic brief is not proof of an isolated
  request. In a private workspace, disable external free dispatch unless the
  user explicitly approves that provider and the full outgoing-context scope.
  Otherwise require a separate sanitized public/synthetic environment with
  verified instruction sources and no inherited private context. If the
  available tools cannot establish that isolation, stay on the existing GPT
  route. Never expose credentials. Do not claim tool denial prevents disclosure.
- The bundled `chuck-free` profile is **tool-free**. Pass its approved data in
  the brief, but remember that this does not strip injected instructions.
  Public-data lookups can use `explore` only after the same full-context
  preflight and with a narrow public-source brief; never let it roam a private
  workspace. Installing a profile is not approval to send private context.
- Configured local models (`lmstudio/...`) are another possible zero-token-price
  route; confirm the endpoint is actually local/reachable and benchmark before
  adopting one. Zero catalog price does not mean zero hardware/time cost.
- An auth, rate-limit or availability error is not a reasoning failure. Skip
  the blocked free route and use the existing GPT route; do not loop or sign up
  for services. Report the fallback. In the Free lane, skip the blocked free
  model and use the next tier on `free_ladder` instead — never jump to GPT.

## Escalation (lane-confined)

1. Verify the failure first. Distinguish model quality from tool/config errors.
2. For reasoning failures, retry once at the next supported higher variant.
   Never repeat the same model/variant/brief unchanged.
3. If a tier has no higher supported variant, or the retry fails, move to the
   next tier on the lane's ladder — `[opencode].ladder` (GPT) or
   `free_ladder` (Free) — at medium/high. Never start security work on a
   `no_security` tier. All Free-lane tiers carry `no_security`, so a
   security task in the Free lane stops and asks before using a paid tier.
4. The lane's top tier moves through supported higher variants up to
   `max_effort`. After that fails, ask whether to try a different validated
   model *in the same lane/provider*, use max, or change approach. There is
   no automatic cross-provider or Fable/API-spend escalation, and no jump
   from Free to GPT (or GPT to Free) to fix a failure.
5. Fix schema/config errors directly; increasing effort won't repair them.

## Installation and maintenance

OpenCode already discovers `~/.claude/skills/chuck`; no duplicate skill install
is needed. Native optional profiles live in this skill's `agents/opencode/`
(next to the Claude Code ones in `agents/claude/`). `sh deploy.sh opencode`
links them into `~/.config/opencode/agents/` (or the XDG config equivalent),
preserving any existing files. OpenCode watches configuration changes; use `/reload` if the new
profiles are not advertised yet, not a service restart. Until then use built-ins.

Official references: https://opencode.ai/docs/agents and
https://opencode.ai/docs/skills. Re-check these before changing native formats.
