import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import REPO, TempDirMixin, git, make_checkout, run_install  # noqa: E402

MANIFEST = ".prime-agent-skills-install.json"
SLUGS = sorted(p.name for p in (REPO / "skills").iterdir() if (p / "SKILL.md").is_file())


def own_reference(slug: str) -> Path:
    """A reference file that belongs to this skill, relative to the skill directory."""
    files = sorted(p for p in (REPO / "skills" / slug / "references").iterdir() if p.suffix == ".md")
    return files[0].relative_to(REPO / "skills" / slug)


class SkillUpdateCases(TempDirMixin):
    """Update flow for one skill; SLUG is set by the per-skill subclasses below."""

    SLUG = ""

    def setUp(self) -> None:
        super().setUp()
        self.checkout = make_checkout(self.tmp)
        self.agent = self.tmp / "agent"
        self.skill = self.agent / "skills" / self.SLUG
        self.reference = own_reference(self.SLUG)
        result = run_install(self.checkout, self.agent)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.updater = self.skill / "scripts" / "update_check.py"

    def check(self, *args: str):
        environment = {k: v for k, v in os.environ.items() if not k.startswith("PRIME_AGENT")}
        return subprocess.run(
            [sys.executable, str(self.updater), *args],
            text=True, capture_output=True, env=environment,
        )

    def new_commit(self):
        path = self.checkout / "skills" / self.SLUG / self.reference
        path.write_text(path.read_text() + "\nupdated line\n")
        git(self.checkout, "add", "-A")
        git(self.checkout, "commit", "-q", "-m", "update")
        return git(self.checkout, "rev-parse", "HEAD")

    def test_up_to_date(self):
        head = git(self.checkout, "rev-parse", "HEAD")
        result = self.check("--from-checkout", str(self.checkout))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"UP_TO_DATE skill={self.SLUG} commit={head}")

    def test_update_available_then_applied(self):
        old = git(self.checkout, "rev-parse", "HEAD")
        new = self.new_commit()
        result = self.check("--from-checkout", str(self.checkout))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(), f"UPDATE_AVAILABLE skill={self.SLUG} installed={old} latest={new}"
        )
        self.assertNotIn("updated line", (self.skill / self.reference).read_text())

        result = self.check("--apply", "--from-checkout", str(self.checkout))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(lines[-1], f"UPDATED skill={self.SLUG} commit={new}")
        installed = (self.skill / self.reference).read_bytes()
        source = (self.checkout / "skills" / self.SLUG / self.reference).read_bytes()
        self.assertEqual(installed, source)
        self.assertTrue(os.access(self.updater, os.X_OK))
        self.assertFalse((self.agent / "skills" / f".{self.SLUG}.update.lock").exists())
        again = self.check("--from-checkout", str(self.checkout))
        self.assertEqual(again.stdout.strip(), f"UP_TO_DATE skill={self.SLUG} commit={new}")

    def test_local_dirty_is_preserved(self):
        edited = self.skill / "SKILL.md"
        edited.write_text(edited.read_text() + "\nlocal edit\n")
        self.new_commit()
        before = edited.read_bytes()
        result = self.check("--apply", "--from-checkout", str(self.checkout))
        self.assertEqual(result.returncode, 0, result.stderr)
        old = git(self.checkout, "rev-parse", "HEAD~1")
        self.assertEqual(
            result.stdout.strip(),
            f"LOCAL_DIRTY skill={self.SLUG} installed={old} latest=unchecked "
            "payload_dirty=true source_dirty=false",
        )
        self.assertEqual(edited.read_bytes(), before)

    def test_force_overwrites_local_edit(self):
        edited = self.skill / "SKILL.md"
        edited.write_text(edited.read_text() + "\nlocal edit\n")
        new = self.new_commit()
        result = self.check("--apply", "--force", "--from-checkout", str(self.checkout))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip().splitlines()[-1].startswith(f"UPDATED skill={self.SLUG} commit={new}"))
        self.assertNotIn("local edit", edited.read_text())

    def test_unmanaged(self):
        (self.skill / MANIFEST).unlink()
        result = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), f"UNMANAGED skill={self.SLUG} update_check=skipped")

    def test_error_fast_when_source_unreachable(self):
        import json
        manifest_path = self.skill / MANIFEST
        manifest = json.loads(manifest_path.read_text())
        manifest["source"] = str(self.tmp / "does-not-exist")
        manifest_path.write_text(json.dumps(manifest))
        started = time.monotonic()
        result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            result.stdout.strip(), f"ERROR skill={self.SLUG} reason=latest_commit_unavailable"
        )
        self.assertLess(time.monotonic() - started, 10)


for _slug in SLUGS:
    _name = "SkillUpdateTests_" + _slug.replace("-", "_")
    globals()[_name] = type(_name, (SkillUpdateCases, unittest.TestCase), {"SLUG": _slug})
del _slug, _name


if __name__ == "__main__":
    unittest.main()
