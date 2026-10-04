"""check_brief.py: the mechanical half of the deep-solve-prep readiness gate."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECK = REPO / "skills" / "deep-solve-prep" / "scripts" / "check_brief.py"
READY = REPO / "skills" / "deep-solve-prep" / "references" / "brief-example-ready.md"

BAD = """# DS-X

/deep-solve Make the kernel durable and intelligent

Context: This brief is DS-X of 1.

Question: how do we redesign the kernel to be sustainable and self-aware, and then deploy it and put capital to use?

Success criteria:
1. It is robust.
2. Bless the world with results.

Inputs:
- the data on the old machine, I will bring it over

Constraints: none

Budget: until done.

Human gates: none. Ask me questions when I say go.
"""


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECK), *args], text=True, capture_output=True)


class CheckBriefTests(unittest.TestCase):
    def test_ready_example_passes(self):
        result = run(str(READY))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DS-1: OK", result.stdout)

    def test_bad_brief_fails_on_every_class_of_defect(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BRIEFS.md"
            path.write_text(BAD)
            result = run(str(path))
        self.assertEqual(result.returncode, 1)
        out = result.stdout
        for expected in (
            "title has",
            "missing section 'Out of scope'",
            "joins two actions with 'and'",
            "'sustainable' in Question with no number",
            "'robust' in Success criteria with no number",
            "no known-bad rejection",
            "no known-good acceptance",
            "purpose word 'bless'",
            "'kernel' collides",
            "'put capital' appears outside Human gates",
            "conversation gate",
            "no '(proved by:",
            "not on this machine",
            "Budget has no number",
            "cap behavior",
        ):
            self.assertIn(expected, out, f"missing defect: {expected}\n{out}")

    def test_id_selection_and_json(self):
        result = run(str(READY), "--id", "DS-1", "--json")
        self.assertEqual(result.returncode, 0)
        self.assertIn('"DS-1": []', result.stdout)
        result = run(str(READY), "--id", "nope")
        self.assertEqual(result.returncode, 2)

    def test_file_without_briefs_is_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BRIEFS.md"
            path.write_text("# nothing here\n")
            result = run(str(path))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
