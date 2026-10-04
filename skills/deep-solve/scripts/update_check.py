#!/usr/bin/env python3
"""Check or safely apply an update to one installed prime-agent-skills skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


MANIFEST = ".prime-agent-skills-install.json"
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Network guard: an offline machine must fail fast, not hang.
NETWORK_TIMEOUT = 10


class UpdateError(RuntimeError):
    pass


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise UpdateError("unsafe_payload")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST or "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise UpdateError("unsafe_payload")
        if path.is_file():
            result[relative] = file_hash(path)
        elif not path.is_dir():
            raise UpdateError("unsafe_payload")
    return result


def load_manifest(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise UpdateError("unmanaged_install")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("invalid_metadata") from exc
    required = {
        "schema",
        "skill",
        "source",
        "ref",
        "commit",
        "source_dirty",
        "files",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        raise UpdateError("invalid_metadata")
    if (
        value["schema"] != 1
        or not isinstance(value["skill"], str)
        or not SLUG_RE.match(value["skill"])
    ):
        raise UpdateError("invalid_metadata")
    if (
        not isinstance(value["source"], str)
        or not value["source"]
        or not isinstance(value["ref"], str)
        or not value["ref"]
        or not isinstance(value["commit"], str)
        or not is_sha(value["commit"])
        or not isinstance(value["source_dirty"], bool)
        or not isinstance(value["files"], dict)
    ):
        raise UpdateError("invalid_metadata")
    for relative, digest in value["files"].items():
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise UpdateError("invalid_metadata")
    return value


def is_sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value.lower())


def git_commit(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    value = result.stdout.strip().lower()
    if result.returncode != 0 or not is_sha(value):
        raise UpdateError("checkout_commit_unavailable")
    return value


def remote_commit(source: str, ref: str) -> str:
    if is_sha(ref):
        return ref.lower()
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            ["git", "ls-remote", source, ref],
            text=True,
            capture_output=True,
            check=False,
            timeout=NETWORK_TIMEOUT,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        value = result.stdout.split()[0].lower()
        if is_sha(value):
            return value
    repo = github_repo(source)
    if not repo:
        raise UpdateError("latest_commit_unavailable")
    try:
        with urllib.request.urlopen(
            f"https://api.github.com/repos/{repo}/commits/{ref}", timeout=NETWORK_TIMEOUT
        ) as response:
            value = json.loads(response.read().decode("utf-8")).get("sha", "").lower()
    except (OSError, UnicodeError, ValueError, urllib.error.URLError) as exc:
        raise UpdateError("latest_commit_unavailable") from exc
    if not is_sha(value):
        raise UpdateError("latest_commit_unavailable")
    return value


def github_repo(source: str) -> str:
    prefixes = ("https://github.com/", "git@github.com:")
    for prefix in prefixes:
        if source.startswith(prefix):
            value = source[len(prefix) :]
            return value[:-4] if value.endswith(".git") else value
    return ""


def remote_installer(source: str, commit: str, destination: Path) -> None:
    repo = github_repo(source)
    if not repo:
        raise UpdateError("installer_url_unavailable")
    try:
        with urllib.request.urlopen(
            f"https://raw.githubusercontent.com/{repo}/{commit}/install.sh", timeout=NETWORK_TIMEOUT
        ) as response:
            data = response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError("installer_download_failed") from exc
    if not data.startswith(b"#!/"):
        raise UpdateError("installer_download_invalid")
    destination.write_bytes(data)
    destination.chmod(0o755)


def run_installer(
    installer: Path,
    skill_dir: Path,
    manifest: dict[str, object],
    latest: str,
    force: bool,
) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "PRIME_AGENT_SKILLS_SOURCE": str(manifest["source"]),
            "PRIME_AGENT_SKILLS_REF": str(manifest["ref"]),
            "PRIME_AGENT_SKILLS_COMMIT": latest,
            "PRIME_AGENT_SKILLS_SOURCE_DIRTY": "false",
            "PRIME_AGENT_SKILLS_SKILLS": str(manifest["skill"]),
            "PRIME_AGENT_SKILLS_DEST": str(skill_dir.parent),
            "PRIME_AGENT_SKILLS_NONINTERACTIVE": "1",
        }
    )
    environment.pop("PRIME_AGENT_SKILLS_SOURCE_DIR", None)
    if force:
        environment["PRIME_AGENT_SKILLS_FORCE"] = "1"
    else:
        environment.pop("PRIME_AGENT_SKILLS_FORCE", None)
    result = subprocess.run(
        ["/bin/sh", str(installer)],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise UpdateError(f"apply_failed_{detail[-1] if detail else 'unknown'}")


def verify_updated_install(skill_dir: Path, latest: str) -> None:
    manifest = load_manifest(skill_dir / MANIFEST)
    if str(manifest["commit"]).lower() != latest:
        raise UpdateError("updated_commit_mismatch")
    recorded = {str(key): str(value) for key, value in manifest["files"].items()}
    if snapshot(skill_dir) != recorded:
        raise UpdateError("updated_payload_mismatch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--from-checkout", type=Path)
    return parser.parse_args()


def main() -> int:
    options = parse_args()
    skill_dir = Path(__file__).resolve().parent.parent
    lock = skill_dir.parent / f".{skill_dir.name}.update.lock"
    try:
        manifest = load_manifest(skill_dir / MANIFEST)
        recorded = {str(key): str(value) for key, value in manifest["files"].items()}
        current = snapshot(skill_dir)
        payload_dirty = current != recorded
        source_dirty = bool(manifest["source_dirty"])
        installed = str(manifest["commit"]).lower()
        if (payload_dirty or source_dirty) and not options.force:
            print(
                f"LOCAL_DIRTY skill={manifest['skill']} installed={installed} latest=unchecked "
                f"payload_dirty={str(payload_dirty).lower()} "
                f"source_dirty={str(source_dirty).lower()}"
            )
            return 0
        checkout = options.from_checkout.resolve() if options.from_checkout else None
        latest = (
            git_commit(checkout)
            if checkout
            else remote_commit(str(manifest["source"]), str(manifest["ref"]))
        )

        if payload_dirty or source_dirty:
            status = (
                f"LOCAL_DIRTY skill={manifest['skill']} installed={installed} latest={latest} "
                f"payload_dirty={str(payload_dirty).lower()} "
                f"source_dirty={str(source_dirty).lower()}"
            )
        elif installed == latest:
            print(f"UP_TO_DATE skill={manifest['skill']} commit={installed}")
            return 0
        else:
            status = (
                f"UPDATE_AVAILABLE skill={manifest['skill']} "
                f"installed={installed} latest={latest}"
            )

        print(status)
        if not options.apply:
            return 0
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise UpdateError("update_locked") from exc
        try:
            if checkout:
                installer = checkout / "install.sh"
                if not installer.is_file():
                    raise UpdateError("checkout_installer_missing")
                run_installer(installer, skill_dir, manifest, latest, options.force)
            else:
                with tempfile.TemporaryDirectory(prefix="prime-agent-skills-update.") as temporary:
                    installer = Path(temporary) / "install.sh"
                    remote_installer(str(manifest["source"]), latest, installer)
                    run_installer(installer, skill_dir, manifest, latest, options.force)
            verify_updated_install(skill_dir, latest)
        finally:
            lock.rmdir()
        print(f"UPDATED skill={manifest['skill']} commit={latest}")
        return 0
    except UpdateError as exc:
        reason = str(exc).replace(" ", "_")
        if reason == "unmanaged_install":
            print(f"UNMANAGED skill={skill_dir.name} update_check=skipped")
            return 0
        print(f"ERROR skill={skill_dir.name} reason={reason}")
        return 2
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR skill={skill_dir.name} reason={type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
