"""Scan OpenCode's model catalog for free ($0) models and update the Free lane.

This is a *scan*, not a rerank. It only adds or removes candidates from
`[opencode.free_candidates]` in models.toml; it never rewrites `free_ladder`
or any role by itself. A human (or a measured decision) picks the ladder.
Capability order is not derivable from the catalog: only cost, status and
variants are.

Usage (Code Mode is the default and preferred path):
  import this file as a module and call `scan_free_models`, then `update`,
  with an async `query` callable, e.g.:

      import importlib.util
      spec = importlib.util.spec_from_file_location(
          "scan_models", "scripts/scan-models.py")
      mod = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(mod)

      result = await mod.scan_free_models(query=models_tool)  # query: async
      print(mod.render(result.candidates))
      mod.update(result.candidates)                            # writes models.toml

  `query(provider)` returns the `opencode.models` result for one provider:
  `{"providers": [{"id": ..., "models": [{"id", "name", "variants",
  "status", "released", "cost"}]}]}`. This is the only path with real cost
  data, so it is the only one that can prove a model is $0.

Usage (CLI, when `opencode` is on PATH; this build lists ids only):
  python3 -I scripts/scan-models.py --names --providers opencode
  python3 -I scripts/scan-models.py --scan --providers opencode
  python3 -I scripts/scan-models.py --update --providers opencode
  python3 -I scripts/scan-models.py --check --providers opencode

The CLI prints ids with no cost/variant data; `--scan` on it returns zero
candidates rather than guessing. Use `--names` to spot new free models, then
verify them with the Code Mode path. Only $0 input+output+cache models on
the requested provider are candidates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "models.toml"
DEFAULT_PROVIDERS = ("opencode", "openrouter")

# Roles -> effort they need a variant for; keep in sync with [opencode.roles].
ROLE_EFFORTS: dict[str, str] = {
    "worker": "low",
    "implement": "medium",
    "hard": "high",
    "review": "high",
    "design": "xhigh",
}


@dataclass(frozen=True)
class ScanResult:
    """A catalog scan: candidates plus whether cost metadata was available."""

    candidates: list[Candidate]
    cost_unknown: bool = False

    def __iter__(self):
        # Backwards-compatible: `for c in scan` yields candidates.
        return iter(self.candidates)

    def __len__(self) -> int:
        return len(self.candidates)


@dataclass(frozen=True)
class Candidate:
    """One free model candidate, as the catalog reported it."""

    provider: str
    model: str
    name: str
    variants: tuple[str, ...]
    released: int

    def supports_role(self, role: str) -> bool:
        effort = ROLE_EFFORTS.get(role)
        return effort is None or effort in self.variants

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "name": self.name,
            "variants": list(self.variants),
            "released": self.released,
        }


def _is_free(cost: Any) -> bool:
    """True when every cost entry has $0 input/output/cache."""
    if not cost:
        return False  # empty metadata means unknown, not zero
    for tier in cost:
        if tier.get("input") not in (0, 0.0):
            return False
        if tier.get("output") not in (0, 0.0):
            return False
        cache = tier.get("cache") or {}
        if cache.get("read") not in (0, 0.0) or cache.get("write") not in (0, 0.0):
            return False
    return True


def parse_catalog(data: Any) -> list[Candidate]:
    """Turn opencode.models output into free candidates.

    Catalog order is not a capability ranking; sort by recency then id.
    When the source reports unknown cost (`_cost_unknown`), every active
    model is returned as a candidate — the caller must not treat that as
    proof of $0, only as a name list to verify.
    """
    cost_unknown = bool(data.get("_cost_unknown"))
    out: list[Candidate] = []
    for provider in data.get("providers", []):
        pid = provider.get("id", "")
        for model in provider.get("models", []):
            if model.get("status") != "active":
                continue
            if not cost_unknown and not _is_free(model.get("cost")):
                continue
            out.append(
                Candidate(
                    provider=pid,
                    model=model.get("id", ""),
                    name=model.get("name", ""),
                    variants=tuple(model.get("variants", [])),
                    released=model.get("released", 0),
                )
            )
    out.sort(key=lambda c: (-c.released, c.model))
    return out


def _query_cli(provider: str) -> Any:
    """`opencode models` (ids only; no --json/--provider in this CLI version).

    Returns a catalog-shaped dict whose cost metadata is unknown, so the CLI
    path can only *list* candidates, not prove they are $0. Prefer the
    in-session `opencode.models` tool, which returns real cost data.
    """
    proc = subprocess.run(["opencode", "models"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"`opencode models` failed: {proc.stderr.strip()}")
    ids = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    models = [
        {
            "id": mid,
            "name": mid.rsplit("/", 1)[-1],
            "status": "active",
            "variants": [],
            "released": 0,
            # Unknown cost: the CLI gives no price data. Mark unknown so the
            # caller knows the $0 filter could not run.
            "cost": [],
        }
        for mid in ids
        if mid.startswith(f"{provider}/")
    ]
    return {"providers": [{"id": provider, "models": models}], "_cost_unknown": True}


async def scan_free_models(
    providers: Iterable[str] = DEFAULT_PROVIDERS,
    query: Callable[[str], Awaitable[Any]] | Callable[[str], Any] | None = None,
) -> ScanResult:
    """Query the catalog for each provider. `query` is the opencode.models tool."""
    out: list[Candidate] = []
    cost_unknown = False
    for pid in providers:
        data = (query or _query_cli)(pid)
        if hasattr(data, "__await__"):
            data = await data
        cost_unknown = cost_unknown or bool(data.get("_cost_unknown"))
        out.extend(parse_catalog(data))
    return ScanResult(candidates=out, cost_unknown=cost_unknown)


def _format(c: Candidate) -> str:
    variants = ",".join(c.variants) if c.variants else "(no variants)"
    return f"{c.provider:12} {c.model:40} {c.name:30} {variants}"


def render(candidates: Iterable[Candidate], cost_unknown: bool = False) -> str:
    """Human-readable catalog scan, grouped by role coverage."""
    cands = list(candidates)
    warning = ("  (cost unknown: source gave no price data; verify $0 before use)\n"
               if cost_unknown else "")
    lines = [
        f"Free ($0) models: {len(cands)}",
        warning,
        *(f"  {_format(c)}" for c in cands),
        "",
        "Role coverage (effort needed -> models with that variant):",
    ]
    for role, effort in ROLE_EFFORTS.items():
        ok = [c.model for c in cands if effort in c.variants]
        lines.append(f"  {role:12} {effort:7} {len(ok):2}  " + ", ".join(ok))
    return "\n".join(lines)


_TABLE_START = "[opencode.free_candidates]"
_TABLE_END = "[opencode.tiers."


def _insert_candidates(text: str, candidates: list[Candidate], scanned: str) -> str:
    """Replace the [opencode.free_candidates] table, keeping the rest of the file."""
    if _TABLE_END not in text:
        raise ValueError("models.toml has no [opencode.tiers.*] section")

    lines = [
        _TABLE_START,
        "# Free-lane candidates from the last `scripts/scan-models.py --update`.",
        "# Picking `free_ladder` from this list is a human/measured decision:",
        "# cost is $0 for all of them; capability order is not in the catalog.",
        f'scanned = "{scanned}"',
        "",
    ]
    for c in candidates:
        lines.append(f'[opencode.free_candidates."{c.model}"]')
        lines.append(f'provider = "{c.provider}"')
        lines.append(f'name = "{c.name}"')
        lines.append(f"variants = {json.dumps(list(c.variants))}")
        lines.append(f"released = {c.released}")
        lines.append("")
    table = "\n".join(lines)

    if _TABLE_START in text:
        head = text.split(_TABLE_START, 1)[0]
        tail = text.split(_TABLE_END, 1)[1]
        return head + table + "\n" + _TABLE_END + tail
    anchor = text.index(_TABLE_END)
    return text[:anchor] + table + "\n" + text[anchor:]


def update(candidates: list[Candidate], scanned: str | None = None) -> str:
    """Write [opencode.free_candidates] into models.toml. Returns the new text."""
    text = CONFIG.read_text()
    new = _insert_candidates(text, candidates, scanned or date.today().isoformat())
    if new != text:
        CONFIG.write_text(new)
    return new


def check(candidates: list[Candidate], config_text: str | None = None) -> int:
    """Exit 1 when the catalog scan disagrees with models.toml."""
    current = set(
        tomllib.loads(config_text if config_text is not None else CONFIG.read_text())
        .get("opencode", {})
        .get("free_candidates", {})
    )
    latest = {c.model for c in candidates}
    # `scanned` is metadata, not a candidate.
    current.discard("scanned")
    missing = latest - current
    stale = current - latest
    for m in sorted(missing):
        print(f"missing from models.toml: {m}")
    for m in sorted(stale):
        print(f"stale in models.toml: {m}")
    return 1 if (missing or stale) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scan OpenCode free models into models.toml")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true", help="query and print candidates")
    g.add_argument("--names", action="store_true",
                   help="list provider model ids (no cost data; cannot prove $0)")
    g.add_argument("--update", action="store_true", help="write candidates to models.toml")
    g.add_argument("--check", action="store_true", help="fail if models.toml is stale")
    p.add_argument("--provider", action="append", dest="providers",
                   help="provider id (repeatable); default: opencode openrouter")
    p.add_argument("--providers", default=None,
                   help="comma-separated provider ids (overrides --provider)")
    p.add_argument("--min-variants", default="low",
                   help="comma-separated variants a candidate must support (default: low)")
    args = p.parse_args(argv)

    providers = tuple(args.providers) if args.providers else DEFAULT_PROVIDERS
    if args.providers:
        providers = tuple(p for p in args.providers.split(",") if p)
    needed = {v for v in args.min_variants.split(",") if v}
    try:
        result = scan_free_models(providers)  # sync path: opencode CLI
        if hasattr(result, "__await__"):
            import asyncio
            result = asyncio.run(result)
    except (RuntimeError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.names:
        # Cost metadata is unavailable here; this is a name list, not a $0 proof.
        for c in sorted(result.candidates, key=lambda c: c.model):
            print(c.model)
        return 0

    candidates = [c for c in result.candidates if needed <= set(c.variants)]
    if args.update:
        if result.cost_unknown:
            print("error: --update needs real cost data; use the Code Mode path",
                  file=sys.stderr)
            return 2
        update(candidates)
        print(f"updated {CONFIG} with {len(candidates)} free candidates")
        return 0
    if args.check:
        # The CLI source has no cost data, so it cannot confirm candidates.
        print("error: --check needs real cost data; use the Code Mode path",
              file=sys.stderr)
        return 2
    print(render(candidates, result.cost_unknown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
