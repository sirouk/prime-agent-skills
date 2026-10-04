"""Shared test helpers: a throwaway git checkout of this repo."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GIT_IDENTITY = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]
COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".deep-solve")


def git(checkout: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *GIT_IDENTITY, "-C", str(checkout), *args],
        text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def make_checkout(parent: Path, name: str = "checkout") -> Path:
    """Copy the repo working tree into parent/name and commit it in a fresh git repo."""
    checkout = parent / name
    shutil.copytree(REPO, checkout, ignore=COPY_IGNORE)
    subprocess.run(["git", "init", "-q", "-b", "main", str(checkout)], check=True)
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "initial")
    return checkout


def run_install(checkout: Path, agent_dir: Path, *args: str, env: dict | None = None,
                cwd: Path | None = None) -> subprocess.CompletedProcess:
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PRIME_AGENT")}
    environment["PRIME_AGENT_DIR"] = str(agent_dir)
    environment["PRIME_AGENT_SKILLS_SOURCE"] = str(checkout)  # never touch the network
    environment.update(env or {})
    return subprocess.run(
        ["sh", str(checkout / "install.sh"), *args],
        text=True, capture_output=True, env=environment, cwd=str(cwd or checkout.parent),
    )


class TempDirMixin:
    def setUp(self) -> None:  # noqa: N802 (unittest naming)
        self._tmp = tempfile.TemporaryDirectory(prefix="pas-test.")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
