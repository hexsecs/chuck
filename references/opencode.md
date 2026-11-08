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

## Discover models, don't guess

Use `opencode.models` (through Code Mode discovery/execute when applicable)
before the first dispatch, and refresh on model/variant unavailability. Query
the `openai` provider first, then free/local providers if relevant. Model
catalog entries do not prove authentication, reachability, quality or quota.
Run a small bounded task before depending on a new model.

Prefer the user's existing **OpenAI/ChatGPT account** route (`openai/...`) for GPT
work. Do not silently substitute `openrouter/openai/...`, another metered API,
or require an API key. A ChatGPT subscription is not unlimited: optimize quota,
latency, context size and retries per completed task, not hypothetical API spend.
Empty `cost` metadata means unknown, not zero. Catalog prices on another
provider do not describe the user's subscription. Do not promise remaining
quota or dollar savings without measurement.

### Initial GPT-first routing profile

These exact IDs and variants were present on 2026-11-06. Revalidate at runtime.
The profile is a starting policy, not a measured ranking or Claude equivalence.

| Work | Preferred agent (fallback) | Model | Effort |
|---|---|---|---|
| Mechanical extraction, scoped lookup, classification | `chuck-worker` (`explore` for reads, `general` for edits) | `openai/gpt-6-luna` | low |
| Clear implementation, scripts, docs, subsystem explanation | `chuck-artisan` (`general`, or `explore` for explanation) | `openai/gpt-6.1-sol` | medium |
| Tricky invariants, security, concurrency, crypto | `chuck-artisan` (`general`) | `openai/gpt-6.1-sol` | high |
| Independent review | `chuck-reviewer` (`general`, explicitly read-only) | `openai/gpt-6.1-sol` | high |
| Ambiguous debugging, design, failed high-effort work | `general` | `openai/gpt-6.1-sol` | xhigh |
| Optional checkable, non-sensitive read-only units | `chuck-free` (`explore`) | `opencode/inkling-2-small-free` | low |

For example, dispatch a normal implementation with
`model:"openai/gpt-6.1-sol#medium"`; a free unit uses
`model:"opencode/inkling-2-small-free#low"`. If a model has no variants, omit
the `#...` suffix and record effort as unsupported. Do not infer that newer,
more expensive or differently named models are stronger. Other GPTs (including
Terra and Astra) remain available for explicit user choice or measured profile
updates; do not automatically route hard work to an untested model.

The reviewer is a different child session from the author, at the same or a
better-validated capability level; using the same GPT at higher effort is fine.
Free-worker output is always checked by GPT or a deterministic test.

## Optional free lane

Use a free worker only if the user has opted in. Opting in to free workers is not
consent to disclose private workspace context. Use one only after the context preflight below, for small bounded units with
an exactly checkable output, not implementation, final review, security
analysis or architectural judgment. Keep briefs short and request JSON or
precise file/line references. A free model with a long prompt and a GPT redo
can cost more quota and time than a direct GPT call.

- Confirm zero input/output prices on the exact selected route. Availability,
  rate limits and free offers can change. Never silently fall back to paid.
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
  for services. Report the fallback.

## Escalation

1. Verify the failure first. Distinguish model quality from tool/config errors.
2. For reasoning failures, retry once at the next supported higher variant.
   Never repeat the same model/variant/brief unchanged.
3. If a free model has no higher supported variant, or the retry fails, move to
   Luna; move Luna failures to Sol at medium/high. For security start on Sol.
4. Sol failures move through supported higher variants up to xhigh. After an
   xhigh failure, ask whether to try a different validated model, use max, or
   change approach. There is no automatic Fable/API-spend escalation.
5. Fix schema/config errors directly; increasing effort won't repair them.

## Installation and maintenance

OpenCode already discovers `~/.claude/skills/chuck`; no duplicate skill install
is needed. Native optional profiles live in this skill's `opencode/agents/`.
Link them into `~/.config/opencode/agents/` (or the XDG config equivalent),
preserving any existing files. The separate Claude profiles in `agents/` are
unchanged. OpenCode watches configuration changes; use `/reload` if the new
profiles are not advertised yet, not a service restart. Until then use built-ins.

Official references: https://opencode.ai/docs/agents and
https://opencode.ai/docs/skills. Re-check these before changing native formats.
