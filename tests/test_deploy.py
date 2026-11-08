"""Run with python3 -I chuck/tests/test_deploy.py (no third-party dependencies)."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = ("claude", "opencode")


class DeployTests(unittest.TestCase):
    def deploy(self, *args, env=None):
        return subprocess.run(["sh", str(ROOT / "deploy.sh"), *map(str, args)],
                              capture_output=True, text=True, env=env)

    def test_install_and_repeat(self):
        for runtime in RUNTIMES:
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "agents with spaces"
                for _ in range(2):
                    result = self.deploy(runtime, dest)
                    self.assertEqual(result.returncode, 0, result.stderr)
                sources = sorted((ROOT / "agents" / runtime).glob("*.md"))
                self.assertTrue(sources)
                self.assertEqual(sorted(p.name for p in dest.iterdir()), [s.name for s in sources])
                for source in sources:
                    self.assertTrue((dest / source.name).is_symlink())
                    self.assertEqual((dest / source.name).resolve(), source)

    def test_conflict_preserves_files_and_installs_nothing(self):
        for broken_link in (False, True):
            with self.subTest(broken_link=broken_link), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp)
                conflict = dest / "chuck-worker.md"
                if broken_link:
                    conflict.symlink_to(dest / "missing")
                else:
                    conflict.write_text("user work\n")
                result = self.deploy("opencode", dest)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list(dest.iterdir()), [conflict])
                if broken_link:
                    self.assertEqual(os.readlink(conflict), str(dest / "missing"))
                else:
                    self.assertEqual(conflict.read_text(), "user work\n")

    def test_default_destinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(Path(tmp) / "xdg"))
            for runtime in RUNTIMES:
                self.assertEqual(self.deploy(runtime, env=env).returncode, 0)
            self.assertTrue((Path(tmp) / ".claude/agents/worker-bee.md").is_symlink())
            self.assertTrue((Path(tmp) / "xdg/opencode/agents/chuck-free.md").is_symlink())

    def test_requires_runtime(self):
        for args in ((), ("codex",)):
            with self.subTest(args=args):
                self.assertEqual(self.deploy(*args).returncode, 2)


if __name__ == "__main__":
    unittest.main()
