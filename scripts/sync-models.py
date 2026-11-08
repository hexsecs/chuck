"""Copy model/effort defaults from models.toml into the bundled agent profiles.

Usage: python3 -I scripts/sync-models.py [--check]
--check exits 1 (changing nothing) if any profile is out of date.
"""
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def wanted(config, role_path):
    runtime, role_name = role_path.split(".")
    role = config[runtime]["roles"][role_name]
    model = config[runtime]["tiers"][role["tier"]]["model"]
    if runtime == "opencode":  # effort is encoded as a #variant
        return {"model": f"{model}#{role['effort']}"}
    return {"model": model, "effort": role["effort"]}


def sync(text, fields):
    head, sep, body = text.partition("\n---\n")
    if not text.startswith("---\n") or not sep:
        raise ValueError("no frontmatter")
    for key, value in fields.items():
        line = f"{key}: {value}"
        head, n = re.subn(rf"(?m)^{key}:.*$", line, head)
        if not n:
            head += "\n" + line
    return head + sep + body


def main(argv):
    check = "--check" in argv
    config = tomllib.loads((ROOT / "models.toml").read_text())
    stale = []
    for rel, role_path in config["profiles"].items():
        path = ROOT / rel
        old = path.read_text()
        new = sync(old, wanted(config, role_path))
        if new != old:
            stale.append(rel)
            if not check:
                path.write_text(new)
    verb = "out of date" if check else "updated"
    for rel in stale:
        print(f"{verb}: {rel}")
    return 1 if check and stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
