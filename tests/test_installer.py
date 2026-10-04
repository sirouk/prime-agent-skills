import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import REPO, TempDirMixin, git, make_checkout, run_install  # noqa: E402

MANIFEST = ".prime-agent-skills-install.json"
PROMPTS_MANIFEST = ".prime-agent-skills-prompts.json"


def snapshot(root: Path, exclude=()) -> dict:
    import hashlib
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and rel not in exclude and "__pycache__" not in path.parts:
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


class InstallerTests(TempDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.checkout = make_checkout(self.tmp)
        self.agent = self.tmp / "agent"
        self.skill = self.agent / "skills" / "deep-solve"

    def install(self, *args, **kwargs):
        return run_install(self.checkout, self.agent, *args, **kwargs)

    def test_shell_syntax(self):
        for shell in ("sh", "bash"):
            result = subprocess.run([shell, "-n", str(REPO / "install.sh")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_fresh_install(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("skill  deep-solve: installed", result.stdout)
        self.assertIn("prompt /deep-solve: installed", result.stdout)
        self.assertIn("/reload", result.stdout)
        self.assertTrue((self.skill / "SKILL.md").is_file())
        self.assertTrue((self.agent / "prompts" / "deep-solve.md").is_file())
        manifest = json.loads((self.skill / MANIFEST).read_text())
        self.assertEqual(manifest["commit"], git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(manifest["skill"], "deep-solve")
        self.assertEqual(manifest["schema"], 1)
        self.assertFalse(manifest["source_dirty"])
        self.assertEqual(manifest["files"], snapshot(self.skill, {MANIFEST}))
        self.assertEqual(manifest["files"], snapshot(self.checkout / "skills" / "deep-solve"))
        self.assertTrue(os.access(self.skill / "scripts" / "update_check.py", os.X_OK))
        prompts = json.loads((self.agent / "skills" / PROMPTS_MANIFEST).read_text())
        self.assertIn("deep-solve.md", prompts["prompts"])

    def test_second_run_is_unchanged(self):
        self.install()
        before = (self.skill / MANIFEST).read_text()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skill  deep-solve: unchanged", result.stdout)
        self.assertIn("prompt /deep-solve: unchanged", result.stdout)
        self.assertEqual((self.skill / MANIFEST).read_text(), before)

    def test_local_edit_needs_force(self):
        self.install()
        edited = self.skill / "SKILL.md"
        edited.write_text(edited.read_text() + "\nlocal edit\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skill  deep-solve: skipped", result.stdout)
        self.assertIn("locally modified at", result.stdout)
        self.assertIn("local edit", edited.read_text())
        result = self.install("--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skill  deep-solve: updated", result.stdout)
        self.assertNotIn("local edit", edited.read_text())
        edited.write_text(edited.read_text() + "\nlocal edit\n")
        result = self.install(env={"PRIME_AGENT_SKILLS_FORCE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("local edit", edited.read_text())

    def test_unmanaged_different_skill_is_never_replaced_without_force(self):
        # A user's own skill that happens to share our slug (no manifest) is data, not ours.
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: deep-solve\ndescription: the user's own skill\n---\n")
        (self.skill / "notes.txt").write_text("precious")
        before = snapshot(self.skill)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skill  deep-solve: skipped", result.stdout)
        self.assertIn("not installed by this tool", result.stdout)
        self.assertEqual(snapshot(self.skill), before)
        self.assertFalse((self.skill / MANIFEST).exists())
        result = self.install("--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("replaced unmanaged copy (--force)", result.stdout)
        self.assertFalse((self.skill / "notes.txt").exists())
        self.assertEqual(
            snapshot(self.skill, {MANIFEST}), snapshot(self.checkout / "skills" / "deep-solve")
        )

    def test_identical_unmanaged_copy_is_adopted(self):
        # The package-install / pre-manifest case: same bytes, so adopting only adds the manifest.
        shutil.copytree(self.checkout / "skills" / "deep-solve", self.skill)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("adopted identical unmanaged copy", result.stdout)
        self.assertTrue((self.skill / MANIFEST).is_file())
        self.assertEqual(
            snapshot(self.skill, {MANIFEST}), snapshot(self.checkout / "skills" / "deep-solve")
        )

    def test_users_own_prompt_is_never_overwritten_or_removed_without_force(self):
        prompts = self.agent / "prompts"
        prompts.mkdir(parents=True)
        own = prompts / "deep-solve.md"
        own.write_text("the user's own prompt\n")
        result = self.install()
        self.assertIn("prompt /deep-solve: skipped (not installed by this tool", result.stdout)
        self.assertEqual(own.read_text(), "the user's own prompt\n")
        result = self.install("--uninstall")
        self.assertEqual(own.read_text(), "the user's own prompt\n")
        self.assertNotIn("prompt /deep-solve: removed", result.stdout)
        result = self.install("--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prompt /deep-solve: installed", result.stdout)
        self.assertEqual(own.read_bytes(), (self.checkout / "prompts" / "deep-solve.md").read_bytes())

    def test_edited_installed_prompt_is_kept_without_force(self):
        self.install()
        installed = self.agent / "prompts" / "deep-solve.md"
        installed.write_text(installed.read_text() + "\nmy tweak\n")
        result = self.install()
        self.assertIn("prompt /deep-solve: skipped (locally modified", result.stdout)
        self.assertIn("my tweak", installed.read_text())
        result = self.install("--uninstall")
        self.assertIn("prompt /deep-solve: skipped (locally modified", result.stdout)
        self.assertTrue(installed.exists())
        result = self.install("--uninstall", "--force")
        self.assertIn("prompt /deep-solve: removed", result.stdout)
        self.assertFalse(installed.exists())

    def test_project_scope(self):
        project = self.tmp / "project"
        project.mkdir()
        result = self.install("--project", cwd=project)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((project / ".prime" / "agent" / "skills" / "deep-solve" / "SKILL.md").is_file())
        self.assertTrue((project / ".prime" / "agent" / "prompts" / "deep-solve.md").is_file())
        self.assertFalse(self.skill.exists())

    def test_dest_override(self):
        dest = self.tmp / "custom" / "skills"
        result = self.install(env={"PRIME_AGENT_SKILLS_DEST": str(dest)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((dest / "deep-solve" / MANIFEST).is_file())
        self.assertTrue((dest.parent / "prompts" / "deep-solve.md").is_file())

    def test_uninstall_leaves_unrelated_skill(self):
        self.install()
        other = self.agent / "skills" / "other-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("---\nname: other-skill\ndescription: x\n---\n")
        unrelated_prompt = self.agent / "prompts" / "mine.md"
        unrelated_prompt.write_text("mine")
        result = self.install("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.skill.exists())
        self.assertFalse((self.agent / "prompts" / "deep-solve.md").exists())
        self.assertTrue((other / "SKILL.md").is_file())
        self.assertTrue(unrelated_prompt.is_file())
        self.assertFalse((self.agent / "skills" / PROMPTS_MANIFEST).exists())

    def test_uninstall_unmanaged_slug_in_snapshot(self):
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: deep-solve\ndescription: old\n---\n")
        result = self.install("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.skill.exists())

    def test_list(self):
        result = self.install("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deep-solve", result.stdout)
        self.assertIn("/deep-solve", result.stdout)
        self.assertFalse(self.agent.exists())

    def test_skills_selection(self):
        extra = self.checkout / "skills" / "second-skill"
        extra.mkdir()
        (extra / "SKILL.md").write_text("---\nname: second-skill\ndescription: second\n---\nbody\n")
        git(self.checkout, "add", "-A")
        git(self.checkout, "commit", "-q", "-m", "second")
        result = self.install("--skills", "second-skill")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.agent / "skills" / "second-skill" / "SKILL.md").is_file())
        self.assertFalse(self.skill.exists())
        self.assertFalse((self.agent / "prompts" / "deep-solve.md").exists())
        bad = self.install("--skills", "nope")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("unknown skill", bad.stderr)

    def test_dirty_checkout_is_recorded(self):
        (self.checkout / "README.md").write_text("changed\n")
        self.install()
        manifest = json.loads((self.skill / MANIFEST).read_text())
        self.assertTrue(manifest["source_dirty"])

    def test_symlink_in_skill_is_refused(self):
        os.symlink("/etc/hostname", self.checkout / "skills" / "deep-solve" / "link")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlinks are not allowed", result.stderr)
        self.assertFalse(self.skill.exists())


if __name__ == "__main__":
    unittest.main()
