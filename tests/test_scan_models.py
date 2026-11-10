"""Run with python3 -I chuck/tests/test_scan_models.py (no third-party dependencies)."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/scan-models.py"
spec = importlib.util.spec_from_file_location("scan_models", SCRIPT)
scan_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_models)


def catalog(models):
    return {"providers": [{"id": "opencode", "models": models}]}


FREE = {"input": 0, "output": 0, "cache": {"read": 0, "write": 0}}
PAID = {"input": 1, "output": 1, "cache": {"read": 0, "write": 0}}


class ScanModelsTests(unittest.TestCase):
    def test_only_free_active_models_become_candidates(self):
        data = catalog([
            {"id": "opencode/a-free", "name": "A", "status": "active",
             "variants": ["low", "high"], "released": 2, "cost": [FREE]},
            {"id": "opencode/b-paid", "name": "B", "status": "active",
             "variants": ["low"], "released": 3, "cost": [PAID]},
            {"id": "opencode/c-unknown", "name": "C", "status": "active",
             "variants": ["low"], "released": 4, "cost": []},
            {"id": "opencode/d-gone", "name": "D", "status": "deprecated",
             "variants": ["low"], "released": 5, "cost": [FREE]},
        ])
        self.assertEqual([c.model for c in scan_models.parse_catalog(data)],
                         ["opencode/a-free"])

    def test_candidates_sorted_by_release_then_id(self):
        data = catalog([
            {"id": "opencode/z-free", "name": "Z", "status": "active",
             "variants": [], "released": 10, "cost": [FREE]},
            {"id": "opencode/a-free", "name": "A", "status": "active",
             "variants": [], "released": 10, "cost": [FREE]},
            {"id": "opencode/new-free", "name": "N", "status": "active",
             "variants": [], "released": 20, "cost": [FREE]},
        ])
        self.assertEqual([c.model for c in scan_models.parse_catalog(data)],
                         ["opencode/new-free", "opencode/a-free", "opencode/z-free"])

    def test_role_coverage_counts(self):
        data = catalog([
            {"id": "opencode/full", "name": "Full", "status": "active",
             "variants": ["low", "medium", "high", "xhigh"], "released": 1,
             "cost": [FREE]},
            {"id": "opencode/small", "name": "Small", "status": "active",
             "variants": ["low"], "released": 2, "cost": [FREE]},
        ])
        out = scan_models.render(scan_models.parse_catalog(data))
        self.assertIn("worker       low      2", out)
        self.assertIn("design       xhigh    1", out)

    def test_update_inserts_candidates_before_tiers(self):
        text = "[opencode]\nladder = []\n\n[opencode.tiers.x]\nmodel = \"p/m\"\n"
        cands = scan_models.parse_catalog(catalog([
            {"id": "opencode/a-free", "name": "A", "status": "active",
             "variants": ["low"], "released": 1, "cost": [FREE]},
        ]))
        out = scan_models._insert_candidates(text, cands, "2026-11-09")
        self.assertIn('[opencode.free_candidates."opencode/a-free"]', out)
        self.assertLess(out.index("[opencode.free_candidates]"),
                        out.index("[opencode.tiers.x]"))
        self.assertIn('scanned = "2026-11-09"', out)

    def test_update_replaces_existing_table(self):
        text = ("[opencode]\nladder = []\n\n[opencode.free_candidates]\n"
                'scanned = "2026-01-01"\n\n[opencode.free_candidates."opencode/old-free"]\n'
                'provider = "opencode"\nname = "Old"\nvariants = []\nreleased = 0\n\n'
                "[opencode.tiers.x]\nmodel = \"p/m\"\n")
        cands = scan_models.parse_catalog(catalog([
            {"id": "opencode/new-free", "name": "New", "status": "active",
             "variants": ["low"], "released": 1, "cost": [FREE]},
        ]))
        out = scan_models._insert_candidates(text, cands, "2026-11-09")
        self.assertNotIn("opencode/old-free", out)
        self.assertIn('[opencode.free_candidates."opencode/new-free"]', out)
        self.assertIn("[opencode.tiers.x]", out)
        self.assertEqual(out.count("[opencode.free_candidates]"), 1)

    def test_check_detects_missing_and_stale(self):
        text = ("[opencode.free_candidates]\nscanned = \"2026-11-09\"\n\n"
                '[opencode.free_candidates."opencode/old-free"]\n'
                'provider = "opencode"\nname = "Old"\nvariants = []\nreleased = 0\n\n'
                "[opencode.tiers.x]\nmodel = \"p/m\"\n")
        cands = scan_models.parse_catalog(catalog([
            {"id": "opencode/new-free", "name": "New", "status": "active",
             "variants": ["low"], "released": 1, "cost": [FREE]},
        ]))
        self.assertEqual(scan_models.check(cands, text), 1)
        synced = scan_models._insert_candidates(text, cands, "2026-11-09")
        self.assertEqual(scan_models.check(cands, synced), 0)

    def test_models_toml_has_free_candidates(self):
        import tomllib
        config = tomllib.loads((ROOT / "models.toml").read_text())
        candidates = config["opencode"]["free_candidates"]
        self.assertGreaterEqual(len(candidates), 1)
        self.assertIn("opencode/flint-40b-free", candidates)

    def test_candidates_match_live_catalog(self):
        """The committed list must equal what the in-session catalog returns.

        Skips (does not fail) when the `opencode` CLI is unavailable, so the
        suite still runs outside OpenCode. Requires real cost data, which only
        the Code Mode `opencode.models` tool provides.
        """
        import shutil
        if not shutil.which("opencode"):
            self.skipTest("opencode CLI not on PATH")
        result = scan_models.scan_free_models(("opencode",))
        if hasattr(result, "__await__"):
            import asyncio
            result = asyncio.run(result)
        if result.cost_unknown:
            self.skipTest("no cost data: use the Code Mode path")
        self.assertEqual(scan_models.check(result.candidates), 0)

    def test_cli_names_list_provider_models(self):
        data = scan_models._query_cli("opencode")
        ids = [m["id"] for m in data["providers"][0]["models"]]
        self.assertTrue(any(i.endswith("-free") for i in ids))
        self.assertTrue(data["_cost_unknown"])

    def test_check_allow_unknown_compares_ids_only(self):
        text = ("[opencode.free_candidates]\nscanned = \"2026-11-09\"\n\n"
                '[opencode.free_candidates."opencode/old-free"]\n'
                'provider = "opencode"\nname = "Old"\nvariants = []\nreleased = 0\n\n'
                "[opencode.tiers.x]\nmodel = \"p/m\"\n")
        cands = scan_models.parse_catalog(catalog([
            {"id": "opencode/new-free", "name": "New", "status": "active",
             "variants": ["low"], "released": 1, "cost": [FREE]},
        ]))
        self.assertEqual(scan_models.check(cands, text, allow_unknown=True), 1)
        synced = scan_models._insert_candidates(text, cands, "2026-11-09")
        self.assertEqual(scan_models.check(cands, synced, allow_unknown=True), 0)

    def test_cli_check_without_cost_data_errors(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--check", "--providers", "opencode"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--allow-unknown", result.stderr)

    def test_cli_check_allow_unknown_runs(self):
        import subprocess
        import sys
        # The CLI cannot prove $0, but it can compare ids; exit is 1 here
        # because the live catalog differs from the committed list.
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--check",
             "--providers", "opencode", "--allow-unknown"],
            capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 1))
        self.assertNotIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
