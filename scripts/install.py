#!/usr/bin/env python3
"""Installer for prime-agent-skills: skills, prompt templates, manifests, uninstall.

Called by install.sh with a frozen source snapshot. Python 3.9+, stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

SKILL_MANIFEST = ".prime-agent-skills-install.json"
PROMPTS_MANIFEST = ".prime-agent-skills-prompts.json"
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class Source:
    root: Path
    url: str
    ref: str
    commit: str
    dirty: bool


@dataclass(frozen=True)
class Options:
    source: Source
    skills: str
    list_only: bool
    project: bool
    uninstall: bool
    force: bool


def truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def full_sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value.lower())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_snapshot(root: Path, excluded: Optional[set] = None) -> Dict[str, str]:
    """sha256 of every regular file under root. Refuses symlinks and special files."""
    excluded = excluded or set()
    if root.is_symlink() or not root.is_dir():
        raise InstallError(f"unsafe skill directory: {root}")
    result: Dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded or "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise InstallError(f"symlinks are not allowed in managed payloads: {path}")
        if path.is_file():
            result[relative] = file_sha256(path)
        elif not path.is_dir():
            raise InstallError(f"unsupported managed payload entry: {path}")
    return result


def read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise InstallError(f"invalid install metadata: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallError(f"invalid install metadata: {path}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"invalid install metadata: {path}")
    return value


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o644) -> bool:
    """Write via a temp sibling and os.replace. Returns False when unchanged."""
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise InstallError(f"refusing to replace non-regular file: {path}")
        if path.read_bytes() == data:
            return False
        mode = path.stat().st_mode & 0o777
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def frontmatter_value(skill_md: Path, key: str) -> str:
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            return ""
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def discover_skills(root: Path) -> List[str]:
    skills_dir = root / "skills"
    slugs = []
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if entry.name.startswith(".") or not (entry / "SKILL.md").is_file():
                continue
            if not SLUG_RE.match(entry.name):
                raise InstallError(f"invalid skill slug: {entry.name}")
            if frontmatter_value(entry / "SKILL.md", "name") != entry.name:
                raise InstallError(f"SKILL.md name does not match directory: skills/{entry.name}")
            slugs.append(entry.name)
    return slugs


def discover_prompts(root: Path) -> List[str]:
    prompts_dir = root / "prompts"
    if not prompts_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in prompts_dir.iterdir()
        if entry.is_file() and entry.suffix == ".md" and not entry.name.startswith(".")
    )


def select_slugs(raw: str, available: List[str]) -> List[str]:
    raw = (raw or "all").strip()
    if raw in {"", "all"}:
        return list(available)
    wanted = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [item for item in wanted if item not in available]
    if unknown:
        raise InstallError(
            f"unknown skill(s): {', '.join(unknown)}; available: {', '.join(available) or 'none'}"
        )
    return [item for item in available if item in wanted]


def prompt_selected(name: str, selected: List[str], everything: bool, available: List[str]) -> bool:
    stem = name[:-3]
    if everything:
        return True
    if stem in selected:
        return True
    return False


def skill_manifest(source: Source, slug: str, files: Dict[str, str]) -> dict:
    return {
        "schema": 1,
        "skill": slug,
        "source": source.url,
        "ref": source.ref,
        "commit": source.commit,
        "source_dirty": source.dirty,
        "installed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files,
    }


@dataclass
class Plan:
    slug: str
    source_dir: Path
    destination: Path
    files: Dict[str, str]
    action: str  # installed | updated | unchanged | skipped
    note: str = ""


def plan_skill(source: Source, slug: str, destination: Path, force: bool) -> Plan:
    source_dir = source.root / "skills" / slug
    files = tree_snapshot(source_dir)
    if not files:
        raise InstallError(f"source skill is empty: {source_dir}")
    if not os.path.lexists(destination):
        return Plan(slug, source_dir, destination, files, "installed")
    if destination.is_symlink() or not destination.is_dir():
        raise InstallError(f"skill destination is not a safe directory: {destination}")
    current = tree_snapshot(destination, {SKILL_MANIFEST})
    metadata = read_json(destination / SKILL_MANIFEST)
    if metadata is None:
        if current == files:
            # Byte-identical to what we would install: adopting it only adds the manifest.
            return Plan(slug, source_dir, destination, files, "installed", "adopted identical unmanaged copy")
        if not force:
            return Plan(
                slug, source_dir, destination, files, "skipped",
                f"unmanaged skill already exists at {destination} (no manifest, not installed by this tool); "
                "move it away, or rerun with --force to replace it",
            )
        return Plan(slug, source_dir, destination, files, "installed", "replaced unmanaged copy (--force)")
    recorded = metadata.get("files")
    recorded_snapshot = (
        {str(key): str(value) for key, value in recorded.items()}
        if isinstance(recorded, dict)
        else None
    )
    if recorded_snapshot != current and not force:
        return Plan(
            slug, source_dir, destination, files, "skipped",
            f"locally modified at {destination}; keep it, or rerun with --force to overwrite",
        )
    if (
        recorded_snapshot == current
        and current == files
        and metadata.get("commit") == source.commit
        and metadata.get("source") == source.url
        and metadata.get("ref") == source.ref
        and metadata.get("source_dirty") == source.dirty
    ):
        return Plan(slug, source_dir, destination, files, "unchanged")
    note = "overwrote local changes (--force)" if recorded_snapshot != current else ""
    return Plan(slug, source_dir, destination, files, "updated", note)


def apply_skill(plan: Plan, source: Source) -> None:
    destination = plan.destination
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage.", dir=str(parent)))
    backup: Optional[Path] = None
    try:
        shutil.copytree(str(plan.source_dir), str(stage), dirs_exist_ok=True)
        for cache in list(stage.rglob("__pycache__")):
            shutil.rmtree(str(cache))
        updater = stage / "scripts" / "update_check.py"
        if updater.exists():
            updater.chmod(0o755)
        manifest = skill_manifest(source, plan.slug, plan.files)
        atomic_write_bytes(
            stage / SKILL_MANIFEST,
            (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
            0o600,
        )
        if tree_snapshot(stage, {SKILL_MANIFEST}) != plan.files:
            raise InstallError(f"staged skill verification failed: {destination}")
        if os.path.lexists(destination):
            backup = parent / f".{destination.name}.backup.{uuid.uuid4().hex}"
            os.replace(str(destination), str(backup))
        try:
            os.replace(str(stage), str(destination))
        except BaseException:
            if backup is not None and backup.exists() and not os.path.lexists(destination):
                os.replace(str(backup), str(destination))
            raise
        if backup is not None:
            shutil.rmtree(str(backup))
    finally:
        if stage.exists():
            shutil.rmtree(str(stage))


def load_prompts_manifest(path: Path) -> dict:
    value = read_json(path)
    if value is None:
        return {"schema": 1, "prompts": {}}
    prompts = value.get("prompts")
    if not isinstance(prompts, dict):
        raise InstallError(f"invalid install metadata: {path}")
    return value


def write_prompts_manifest(path: Path, source: Source, prompts: Dict[str, str]) -> None:
    if not prompts:
        if path.exists():
            path.unlink()
        return
    value = {
        "schema": 1,
        "source": source.url,
        "ref": source.ref,
        "commit": source.commit,
        "installed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompts": prompts,
    }
    atomic_write_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def paths(options: Options):
    if options.project:
        agent_dir = Path.cwd() / ".prime" / "agent"
    else:
        agent_dir = Path(os.environ.get("PRIME_AGENT_DIR") or (Path.home() / ".prime" / "agent"))
    dest_override = os.environ.get("PRIME_AGENT_SKILLS_DEST")
    skills_dest = Path(dest_override) if dest_override else agent_dir / "skills"
    skills_dest = skills_dest.expanduser().absolute()
    # Prompts live beside the skills dir (same agent dir by default).
    return skills_dest, skills_dest.parent / "prompts"


def run_list(source: Source) -> int:
    slugs = discover_skills(source.root)
    prompts = discover_prompts(source.root)
    print(f"Skills in snapshot (commit {source.commit[:12]}):")
    for slug in slugs:
        description = frontmatter_value(source.root / "skills" / slug / "SKILL.md", "description")
        if len(description) > 110:
            description = description[:107] + "..."
        print(f"  {slug}  {description}")
    print("Prompts:")
    for name in prompts:
        print(f"  /{name[:-3]}")
    return 0


def run_install(options: Options) -> int:
    source = options.source
    available = discover_skills(source.root)
    if not available:
        raise InstallError(f"no skills found under {source.root}/skills")
    everything = options.skills.strip() in {"", "all"}
    selected = select_slugs(options.skills, available)
    skills_dest, prompts_dir = paths(options)

    plans = [plan_skill(source, slug, skills_dest / slug, options.force) for slug in selected]
    prompt_names = [
        name for name in discover_prompts(source.root)
        if prompt_selected(name, selected, everything, available)
    ]
    for name in prompt_names:
        if (source.root / "prompts" / name).is_symlink():
            raise InstallError(f"symlinks are not allowed in managed payloads: prompts/{name}")

    print(f"Source: {source.url} ref={source.ref} commit={source.commit[:12]}"
          f"{' (dirty checkout)' if source.dirty else ''}")
    print(f"Skills dir: {skills_dest}")
    skipped = 0
    for plan in plans:
        if plan.action in {"installed", "updated"}:
            apply_skill(plan, source)
        if plan.action == "skipped":
            skipped += 1
            print(f"  skill  {plan.slug}: skipped")
            print(f"         {plan.note}")
        else:
            suffix = f" ({plan.note})" if plan.note else ""
            print(f"  skill  {plan.slug}: {plan.action}{suffix}")

    prompts_manifest_path = skills_dest / PROMPTS_MANIFEST
    recorded = load_prompts_manifest(prompts_manifest_path)
    recorded_prompts = {str(k): str(v) for k, v in recorded["prompts"].items()}
    if prompt_names:
        print(f"Prompts dir: {prompts_dir}")
    for name in prompt_names:
        data = (source.root / "prompts" / name).read_bytes()
        target = prompts_dir / name
        new_hash = hashlib.sha256(data).hexdigest()
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise InstallError(f"prompt destination is not a regular file: {target}")
        if target.is_file():
            current_hash = file_sha256(target)
            recorded_hash = recorded_prompts.get(name)
            if current_hash == new_hash:
                recorded_prompts[name] = new_hash
                print(f"  prompt /{name[:-3]}: unchanged")
                continue
            if current_hash != recorded_hash and not options.force:
                skipped += 1
                who = "locally modified" if recorded_hash else "not installed by this tool"
                print(f"  prompt /{name[:-3]}: skipped ({who} at {target}; rerun with --force to overwrite)")
                continue
        atomic_write_bytes(target, data)
        recorded_prompts[name] = new_hash
        print(f"  prompt /{name[:-3]}: installed")
    if prompt_names:
        write_prompts_manifest(prompts_manifest_path, source, recorded_prompts)

    installed_any = any(plan.action != "skipped" for plan in plans)
    if installed_any:
        print()
        print("Next steps:")
        print("  - Run /reload in open prime-agent sessions.")
        commands = [f"/{name[:-3]} <problem>" for name in prompt_names if name == "deep-solve.md"]
        if commands:
            print(f"  - Use `{commands[0]}` or just describe a hard problem.")
        print("  - Alternative: prime-agent package install "
              + re.sub(r"\.git$", "", source.url))
    return 1 if skipped else 0


def run_uninstall(options: Options) -> int:
    source = options.source
    available = discover_skills(source.root)
    skills_dest, prompts_dir = paths(options)
    everything = options.skills.strip() in {"", "all"}
    selected = select_slugs(options.skills, available)

    candidates = set(selected)
    if everything and skills_dest.is_dir():
        for entry in skills_dest.iterdir():
            if (entry / SKILL_MANIFEST).is_file() and not entry.is_symlink():
                candidates.add(entry.name)
    skipped = 0
    for slug in sorted(candidates):
        destination = skills_dest / slug
        if not os.path.lexists(destination):
            continue
        if destination.is_symlink() or not destination.is_dir():
            raise InstallError(f"refusing to remove non-directory: {destination}")
        metadata = read_json(destination / SKILL_MANIFEST)
        if metadata is not None and not options.force:
            current = tree_snapshot(destination, {SKILL_MANIFEST})
            recorded = metadata.get("files")
            if not isinstance(recorded, dict) or {str(k): str(v) for k, v in recorded.items()} != current:
                skipped += 1
                print(f"  skill  {slug}: skipped (locally modified; use --force to remove)")
                continue
        shutil.rmtree(str(destination))
        print(f"  skill  {slug}: removed")

    prompts_manifest_path = skills_dest / PROMPTS_MANIFEST
    recorded = load_prompts_manifest(prompts_manifest_path)
    recorded_prompts = {str(k): str(v) for k, v in recorded["prompts"].items()}
    # Only prompts this tool recorded are candidates; a prompt file the user wrote
    # (same name, never installed by us) is never touched.
    names = {
        name for name in recorded_prompts
        if everything or name[:-3] in selected
    }
    for name in sorted(names):
        target = prompts_dir / name
        if not target.is_file() or target.is_symlink():
            recorded_prompts.pop(name, None)
            continue
        if file_sha256(target) != recorded_prompts[name] and not options.force:
            skipped += 1
            print(f"  prompt /{name[:-3]}: skipped (locally modified; use --force to remove)")
            continue
        target.unlink()
        print(f"  prompt /{name[:-3]}: removed")
        recorded_prompts.pop(name, None)
    write_prompts_manifest(prompts_manifest_path, source, recorded_prompts)
    print("Run /reload in open prime-agent sessions.")
    return 1 if skipped else 0


def parse_args(argv: List[str]) -> Options:
    parser = argparse.ArgumentParser(prog="install.py", description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--source-dirty", default="false")
    parser.add_argument("--skills", default=None)
    parser.add_argument("--list", dest="list_only", action="store_true")
    parser.add_argument("--project", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if not full_sha(args.commit):
        parser.error("--commit must be a full 40-hex sha")
    source = Source(
        root=Path(args.source_root).resolve(),
        url=args.source_url,
        ref=args.ref,
        commit=args.commit.lower(),
        dirty=truthy(args.source_dirty),
    )
    skills = args.skills if args.skills is not None else os.environ.get("PRIME_AGENT_SKILLS_SKILLS", "all")
    return Options(
        source=source,
        skills=skills,
        list_only=args.list_only,
        project=args.project,
        uninstall=args.uninstall,
        force=args.force or truthy(os.environ.get("PRIME_AGENT_SKILLS_FORCE")),
    )


def main(argv: Optional[List[str]] = None) -> int:
    options = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        if options.list_only:
            return run_list(options.source)
        if options.uninstall:
            return run_uninstall(options)
        return run_install(options)
    except InstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
