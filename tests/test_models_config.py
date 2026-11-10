"""Validate models.toml internal consistency.

Run with python3 -I chuck/tests/test_models_config.py (no third-party dependencies).

These are the invariants the dispatcher relies on. A typo in a tier name or a
profile path fails silently at dispatch time, so catch it here.
"""
from pathlib import Path
import importlib.util
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "models.toml"


def load():
    return tomllib.loads(CONFIG.read_text())


class ModelsConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load()

    def test_every_role_tier_resolves(self):
        for runtime in ("claude", "opencode"):
            tiers = self.config[runtime]["tiers"]
            for name, role in self.config[runtime]["roles"].items():
                for key in ("tier", "free_tier"):
                    if key in role:
                        self.assertIn(role[key], tiers,
                                      f"{runtime}.{name}.{key}={role[key]}")

    def test_every_ladder_entry_resolves(self):
        for runtime in ("claude", "opencode"):
            tiers = self.config[runtime]["tiers"]
            for key in ("ladder", "free_ladder"):
                for tier in self.config[runtime].get(key, []):
                    self.assertIn(tier, tiers, f"{runtime}.{key}={tier}")

    def test_role_tier_is_in_ladder_unless_optional(self):
        for runtime in ("claude", "opencode"):
            roles = self.config[runtime]["roles"]
            tiers = self.config[runtime]["tiers"]
            ladder = self.config[runtime].get("ladder", [])
            for name, role in roles.items():
                tier = role.get("tier")
                if tier is None or tier in ladder:
                    continue
                self.assertTrue(
                    tiers.get(tier, {}).get("optional"),
                    f"{runtime}.{name} uses off-ladder tier {tier} without optional=true",
                )

    def test_profiles_exist_and_reference_roles(self):
        for rel, role_path in self.config["profiles"].items():
            self.assertTrue((ROOT / rel).exists(), f"missing profile file {rel}")
            runtime, role_name = role_path.split(".", 1)
            self.assertIn(role_name, self.config[runtime]["roles"],
                          f"{rel} -> {role_path}")

    def test_free_candidates_are_well_formed(self):
        candidates = self.config["opencode"].get("free_candidates", {})
        candidates.pop("scanned", None)
        self.assertTrue(candidates, "no free candidates recorded")
        for model, entry in candidates.items():
            self.assertEqual(entry.get("provider"), "opencode",
                             f"{model} provider")
            self.assertIsInstance(entry.get("variants"), list,
                                  f"{model} variants")
            self.assertTrue(entry.get("name"), f"{model} missing name")

    def test_free_ladder_models_are_candidates(self):
        candidates = self.config["opencode"].get("free_candidates", {})
        candidates.pop("scanned", None)
        for tier in self.config["opencode"]["free_ladder"]:
            model = self.config["opencode"]["tiers"][tier]["model"]
            self.assertIn(model, candidates,
                          f"free_ladder tier {tier} model {model} not a candidate")

    def test_security_work_never_routes_to_no_security_free_tier(self):
        """A role whose work mentions security must not have a no_security free_tier."""
        opencode = self.config["opencode"]
        for name, role in opencode["roles"].items():
            work = role.get("work", "").lower()
            free_tier = role.get("free_tier")
            if not free_tier:
                continue
            if "security" in work or "crypto" in work or "concurrency" in work:
                self.assertFalse(
                    opencode["tiers"][free_tier].get("no_security"),
                    f"{name} does security work but free_tier {free_tier} is no_security",
                )

    def test_checkable_free_tier_has_a_stronger_reviewer(self):
        """A checkable free_tier needs a strictly higher tier in free_ladder."""
        opencode = self.config["opencode"]
        ladder = opencode["free_ladder"]
        for name, role in opencode["roles"].items():
            free_tier = role.get("free_tier")
            if not free_tier:
                continue
            if not opencode["tiers"][free_tier].get("checkable"):
                continue
            idx = ladder.index(free_tier)
            self.assertLess(
                idx, len(ladder) - 1,
                f"{name} free_tier {free_tier} is checkable but is the top of free_ladder",
            )

    def test_free_lane_is_for_checkable_non_security_units(self):
        """hard/review/design are GPT-lane-only; the Free lane stays checkable."""
        opencode = self.config["opencode"]
        for name in ("hard", "review", "design"):
            self.assertNotIn("free_tier", opencode["roles"][name],
                             f"{name} must be GPT-lane-only")

    def test_opencode_roles_have_effort(self):
        for name, role in self.config["opencode"]["roles"].items():
            self.assertIn("effort", role, f"opencode.{name} missing effort")


if __name__ == "__main__":
    unittest.main()
