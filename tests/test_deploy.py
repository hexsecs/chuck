"""Run with python3 -I chuck/tests/test_deploy.py (no third-party dependencies)."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeployTests(unittest.TestCase):
    def deploy(self, dest=None, env=None):
        args = ["sh", str(ROOT / "deploy-opencode.sh")]
        if dest is not None:
            args.append(str(dest))
        return subprocess.run(args, capture_output=True, text=True, env=env)

    def test_install_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "agents with spaces"
            for _ in range(2):
                result = self.deploy(dest)
                self.assertEqual(result.returncode, 0, result.stderr)
                for source in (ROOT / "opencode/agents").glob("*.md"):
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
                result = self.deploy(dest)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list(dest.iterdir()), [conflict])
                if broken_link:
                    self.assertEqual(os.readlink(conflict), str(dest / "missing"))
                else:
                    self.assertEqual(conflict.read_text(), "user work\n")

    def test_xdg_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_CONFIG_HOME=tmp)
            result = self.deploy(env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(tmp) / "opencode/agents/chuck-free.md").is_symlink())


if __name__ == "__main__":
    unittest.main()
