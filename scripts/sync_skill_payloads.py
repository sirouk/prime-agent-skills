#!/usr/bin/env python3
"""Keep skills/*/scripts/update_check.py identical to scripts/skill_update.py.

  python3 scripts/sync_skill_payloads.py          copy the canonical updater into every skill
  python3 scripts/sync_skill_payloads.py --check  exit 1 if any copy differs or is missing
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def sync(root: Path, check: bool) -> int:
    canonical = root / "scripts" / "skill_update.py"
    if not canonical.is_file():
        print(f"ERROR: missing canonical updater: {canonical}", file=sys.stderr)
        return 2
    expected = canonical.read_bytes()
    stale = []
    skills = root / "skills"
    for skill in sorted(skills.iterdir()) if skills.is_dir() else []:
        if not (skill / "SKILL.md").is_file():
            continue
        target = skill / "scripts" / "update_check.py"
        current = target.read_bytes() if target.is_file() else None
        if current == expected and target.stat().st_mode & 0o111:
            continue
        stale.append(target)
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical, target)
            target.chmod(0o755)
            print(f"synced {target.relative_to(root)}")
    if check and stale:
        for target in stale:
            print(f"out of sync: {target.relative_to(root)}", file=sys.stderr)
        print("run: python3 scripts/sync_skill_payloads.py", file=sys.stderr)
        return 1
    if not stale:
        print("update_check.py copies are in sync")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    return sync(args.root.resolve(), args.check)


if __name__ == "__main__":
    raise SystemExit(main())
