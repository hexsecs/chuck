"""Run with python3 -I chuck/tests/test_sync_models.py (no third-party dependencies)."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/sync-models.py"
spec = importlib.util.spec_from_file_location("sync_models", SCRIPT)
sync_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_models)


class SyncModelsTests(unittest.TestCase):
    def test_profiles_match_config(self):
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--check"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rewrites_only_frontmatter(self):
        text = "---\nname: x\nmodel: old\n---\n\nmodel: body stays\n"
        out = sync_models.sync(text, {"model": "new", "effort": "high"})
        self.assertEqual(out, "---\nname: x\nmodel: new\neffort: high\n---\n\nmodel: body stays\n")

    def test_opencode_encodes_effort_as_variant(self):
        config = {"opencode": {"roles": {"r": {"tier": "t", "effort": "low"}},
                               "tiers": {"t": {"model": "p/m"}}}}
        self.assertEqual(sync_models.wanted(config, "opencode.r"), {"model": "p/m#low"})


if __name__ == "__main__":
    unittest.main()
