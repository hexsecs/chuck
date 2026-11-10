"""Run and grade chuck behaviour evals.

An eval case is a directory under `evals/` with:

    case.yaml          schema_version, name, expected_outcome
    prompt.md          frontmatter (tags, max_turns, timeout_seconds, allowed_tools) + body
    graders/*.md       frontmatter (type: llm, focus, weight) + rubric body

Usage:
  python3 -I scripts/run-evals.py            # validate structure (default)
  python3 -I scripts/run-evals.py --list
  python3 -I scripts/run-evals.py --run      # execute cases, save transcripts
  python3 -I scripts/run-evals.py --grade    # grade saved transcripts
  python3 -I scripts/run-evals.py --all      # run + grade

  --model provider/model#variant   fallback model under test for cases with no `model:`
  --grade-model provider/model#variant  judging model (default: GPT, high)
  --case name                      only this case (repeatable)

Each case may set `model:` in case.yaml to pin the coordinator it assumes; that
keeps lane-specific cases running in their own lane.

Transcripts are written to `evals/<name>/.last-run.txt` and `.last-run.json`
(gitignored). Grading needs a capable model; the default is paid.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
DEFAULT_MODEL = "opencode/inkling-2-small-free#low"
DEFAULT_GRADE_MODEL = "openai/gpt-6.1-sol#high"


@dataclass
class Case:
    name: str
    directory: Path
    expected: str
    prompt: str
    graders: list[Path] = field(default_factory=list)
    model: str | None = None

    @property
    def transcript(self) -> Path:
        return self.directory / ".last-run.txt"

    @property
    def raw(self) -> Path:
        return self.directory / ".last-run.json"


def _strip_frontmatter(text: str) -> str:
    """Drop a leading `---` block (eval metadata) from a prompt."""
    if text.startswith("---\n"):
        _, sep, body = text.partition("\n---\n")
        if sep:
            return body.strip()
    return text.strip()


def _read_case(directory: Path) -> Case:
    case = _read_yaml_simple((directory / "case.yaml").read_text())
    prompt = _strip_frontmatter((directory / "prompt.md").read_text())
    graders = sorted((directory / "graders").glob("*.md"))
    return Case(
        name=case.get("name", directory.name),
        directory=directory,
        expected=case.get("expected_outcome", "").strip(),
        prompt=prompt,
        graders=graders,
        model=case.get("model") or None,
    )


def _read_yaml_simple(text: str) -> dict[str, str]:
    """Parse the flat `key: value` / `key: |` subset used by case.yaml.

    No third-party dependency: the eval cases only need scalar values and one
    block scalar. Returns strings; callers treat them as opaque.
    """
    out: dict[str, str] = {}
    key: str | None = None
    block: list[str] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw.strip())
        if match and indent == 0:
            if key is not None:
                out[key] = "\n".join(block).strip() if block else ""
            key = match.group(1)
            value = match.group(2).strip()
            block = []
            if value in ("|", ">", "|-", ">-"):
                continue  # block scalar follows
            out[key] = value.strip("\"'")
            key = None
        elif key is not None and indent > 0:
            block.append(raw.strip())
    if key is not None:
        out[key] = "\n".join(block).strip()
    return out


def discover(root: Path = EVALS) -> list[Case]:
    return [_read_case(d) for d in sorted(root.iterdir())
            if d.is_dir() and (d / "case.yaml").exists() and (d / "prompt.md").exists()]


def validate(cases: list[Case]) -> int:
    problems = 0
    for case in cases:
        if not case.expected:
            print(f"{case.name}: missing expected_outcome")
            problems += 1
        if not case.prompt:
            print(f"{case.name}: empty prompt")
            problems += 1
        if not case.graders:
            print(f"{case.name}: no graders")
            problems += 1
        for grader in case.graders:
            text = grader.read_text()
            if "type: llm" not in text:
                print(f"{case.name}: {grader.name} is not an llm grader")
                problems += 1
    print(f"{len(cases)} case(s), {problems} problem(s)")
    return 1 if problems else 0


def _run_opencode(model: str, message: str) -> tuple[str, dict]:
    """Run one prompt, return (text, usage)."""
    proc = subprocess.run(
        ["opencode", "run", "--model", model, "--archived", "--auto",
         "--format", "json", message],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"opencode run failed: {proc.stderr.strip()}")
    text_parts: list[str] = []
    usage: dict = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = event.get("part", {})
        if part.get("type") == "text" and part.get("text"):
            text_parts.append(part["text"])
        if part.get("type") == "step-finish":
            usage = {
                "cost": part.get("cost"),
                "tokens": part.get("tokens"),
                "reason": part.get("reason"),
            }
    return "".join(text_parts).strip(), usage


def run_case(case: Case, model: str) -> int:
    print(f"running {case.name} on {model} ...")
    try:
        text, usage = _run_opencode(model, case.prompt)
    except (RuntimeError, OSError) as exc:
        print(f"  ERROR: {exc}")
        return 1
    case.transcript.write_text(text + "\n")
    case.raw.write_text(json.dumps({"model": model, "usage": usage}, indent=2) + "\n")
    tokens = usage.get("tokens") or {}
    print(f"  {len(text)} chars, {tokens.get('input', '?')} in / "
          f"{tokens.get('output', '?')} out, cost {usage.get('cost')}")
    return 0


def grade_case(case: Case, model: str) -> int:
    if not case.transcript.exists():
        print(f"{case.name}: no transcript (run --run first)")
        return 1
    transcript = case.transcript.read_text()
    verdicts: list[tuple[str, str]] = []
    for grader in case.graders:
        rubric = _strip_frontmatter(grader.read_text())
        message = (
            "You are grading an agent's trace against an expected outcome.\n\n"
            f"## Expected outcome\n{case.expected}\n\n"
            f"## Grader rubric\n{rubric}\n\n"
            f"## Agent trace\n{transcript}\n\n"
            "End with exactly PASS or FAIL on its own line, then one sentence."
        )
        try:
            text, _ = _run_opencode(model, message)
        except (RuntimeError, OSError) as exc:
            print(f"  {case.name}/{grader.name}: ERROR {exc}")
            return 1
        verdict = _parse_verdict(text)
        verdicts.append((grader.name, verdict))
        print(f"  {case.name}/{grader.name}: {verdict}")
    return 0 if all(v == "PASS" for _, v in verdicts) else 1


def _parse_verdict(text: str) -> str:
    """Read a PASS/FAIL line from a grader response.

    The rubric asks for the verdict on its own line followed by one sentence,
    so the verdict is not necessarily the last line.
    """
    for line in text.splitlines():
        stripped = line.strip().strip("*`").upper()
        if stripped in ("PASS", "FAIL"):
            return stripped
    return "FAIL"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run and grade chuck evals")
    p.add_argument("--list", action="store_true", help="list cases and exit")
    p.add_argument("--run", action="store_true", help="execute cases")
    p.add_argument("--grade", action="store_true", help="grade saved transcripts")
    p.add_argument("--all", action="store_true", help="run then grade")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"fallback model under test (default: {DEFAULT_MODEL})")
    p.add_argument("--grade-model", default=DEFAULT_GRADE_MODEL,
                   help=f"judging model (default: {DEFAULT_GRADE_MODEL})")
    p.add_argument("--case", action="append", dest="only", default=[],
                   help="only this case name (repeatable)")
    args = p.parse_args(argv)

    cases = discover()
    if args.only:
        cases = [c for c in cases if c.name in args.only]
    if not cases:
        print("no eval cases found")
        return 1
    if args.list:
        for case in cases:
            first = case.expected.splitlines()[0] if case.expected else ""
            model = case.model or args.model
            print(f"{case.name} [{model}]: {first}")
        return 0

    status = validate(cases)
    if status:
        return status

    if args.all:
        args.run = args.grade = True
    if args.run:
        for case in cases:
            status |= run_case(case, case.model or args.model)
    if args.grade:
        print(f"grading with {args.grade_model} (paid by default)")
        for case in cases:
            status |= grade_case(case, args.grade_model)
    return status


if __name__ == "__main__":
    sys.exit(main())
