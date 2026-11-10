"""Tests for the eval runner (scripts/run-evals.py).

Run with python3 -I tests/test_run_evals.py (no third-party dependencies).
"""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-evals.py"

spec = importlib.util.spec_from_file_location("run_evals", SCRIPT)
run_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_evals)


class YamlTests(unittest.TestCase):
    def test_scalars_and_block_scalars(self):
        parsed = run_evals._read_yaml_simple(
            'name: demo\nmodel: "openai/gpt-6.1-sol#high"\n'
            "expected_outcome: |\n  first line\n  second line\n"
        )
        self.assertEqual(parsed["name"], "demo")
        self.assertEqual(parsed["model"], "openai/gpt-6.1-sol#high")
        self.assertEqual(parsed["expected_outcome"], "first line\nsecond line")

    def test_ignores_comments_and_blank_lines(self):
        parsed = run_evals._read_yaml_simple(
            "# a comment\n\nname: demo\n\nfocused: true\n"
        )
        self.assertEqual(parsed, {"name": "demo", "focused": "true"})


class VerdictTests(unittest.TestCase):
    def test_verdict_on_first_line(self):
        self.assertEqual(run_evals._parse_verdict("PASS\nIt did the thing."), "PASS")

    def test_verdict_on_last_line(self):
        self.assertEqual(run_evals._parse_verdict("Reasoning.\nFAIL"), "FAIL")

    def test_verdict_with_markdown_emphasis(self):
        self.assertEqual(run_evals._parse_verdict("**PASS**\nok"), "PASS")
        self.assertEqual(run_evals._parse_verdict("`FAIL`\nno"), "FAIL")

    def test_missing_verdict_defaults_to_fail(self):
        self.assertEqual(run_evals._parse_verdict("I am not sure."), "FAIL")


class DiscoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = run_evals.discover()

    def test_every_case_is_well_formed(self):
        self.assertEqual(run_evals.validate(self.cases), 0)

    def test_cases_are_discovered(self):
        names = {case.name for case in self.cases}
        self.assertIn("lane-mirroring", names)
        self.assertIn("free-unavailable", names)
        self.assertIn("private-free-routing", names)

    def test_each_case_pins_a_model(self):
        for case in self.cases:
            self.assertTrue(case.model, f"{case.name} has no model")
            self.assertIn("/", case.model, f"{case.name} model {case.model}")

    def test_lane_cases_pin_their_own_lane(self):
        by_name = {case.name: case for case in self.cases}
        self.assertTrue(by_name["lane-mirroring"].model.endswith("-free"))
        self.assertTrue(by_name["free-unavailable"].model.startswith("openai/"))
        self.assertTrue(by_name["private-free-routing"].model.startswith("openai/"))


if __name__ == "__main__":
    unittest.main()
