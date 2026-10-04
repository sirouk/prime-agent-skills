import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDirMixin, make_checkout  # noqa: E402


class SkillSyncTests(TempDirMixin, unittest.TestCase):
    def sync(self, root: Path, *args: str):
        return subprocess.run(
            [sys.executable, str(root / "scripts" / "sync_skill_payloads.py"), *args],
            text=True, capture_output=True,
        )

    def test_check_passes_in_sync_and_fails_after_difference(self):
        root = make_checkout(self.tmp)
        result = self.sync(root, "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        copy = root / "skills" / "deep-solve" / "scripts" / "update_check.py"
        self.assertEqual(copy.read_bytes(), (root / "scripts" / "skill_update.py").read_bytes())
        copy.write_text(copy.read_text() + "# drift\n")
        result = self.sync(root, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("update_check.py", result.stderr)
        result = self.sync(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sync(root, "--check").returncode, 0)

    def test_check_fails_when_copy_missing(self):
        root = make_checkout(self.tmp)
        (root / "skills" / "deep-solve" / "scripts" / "update_check.py").unlink()
        self.assertEqual(self.sync(root, "--check").returncode, 1)

    def test_repo_copies_are_in_sync(self):
        repo = Path(__file__).resolve().parent.parent
        self.assertEqual(self.sync(repo, "--check").returncode, 0)


if __name__ == "__main__":
    unittest.main()
