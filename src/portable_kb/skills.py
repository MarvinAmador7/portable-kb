"""Installation of the bundled Portable KB skill for supported coding agents."""

from __future__ import annotations

import os
import shutil
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any


class SkillError(RuntimeError):
    """Raised when the bundled agent skill cannot be installed safely."""


class SkillTarget(StrEnum):
    """Supported user-level agent skill locations."""

    CODEX = "codex"
    CLAUDE = "claude"
    BOTH = "both"


def bundled_skill_path() -> Path:
    """Locate the canonical skill in a checkout or installed wheel."""

    repository = Path(__file__).resolve().parents[2] / ".agents" / "skills" / "portable-kb"
    packaged = Path(__file__).resolve().parent / "skills" / "portable-kb"
    source = repository if repository.is_dir() else packaged
    if source.is_symlink() or not source.is_dir() or not (source / "SKILL.md").is_file():
        raise SkillError("The bundled Portable KB skill is unavailable or unsafe.")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise SkillError("The bundled Portable KB skill must not contain symbolic links.")
    return source


def install_agent_skill(
    target: SkillTarget | str = SkillTarget.BOTH,
    *,
    force: bool = False,
    user_home: Path | None = None,
) -> dict[str, Any]:
    """Atomically install the same skill for Codex, Claude Code, or both."""

    try:
        selected = SkillTarget(target)
    except ValueError as exc:
        raise SkillError("Skill target must be codex, claude, or both.") from exc
    home = (user_home or Path.home()).expanduser().absolute()
    targets = _target_paths(home, selected)
    source = bundled_skill_path()
    unchanged: list[str] = []
    for destination in targets.values():
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            raise SkillError(f"Agent skill target is unsafe: {destination}")
        if destination.exists() and not force and _trees_match(source, destination):
            unchanged.append(next(agent for agent, path in targets.items() if path == destination))
            continue
        if destination.exists() and not force:
            raise SkillError(f"Agent skill already exists; use --force to replace it: {destination}")
        if destination.parent.is_symlink():
            raise SkillError(f"Agent skill parent must not be a symbolic link: {destination.parent}")

    stages: dict[str, Path] = {}
    backups: dict[str, Path | None] = {}
    published: list[str] = []
    try:
        for agent, destination in targets.items():
            if agent in unchanged:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(
                tempfile.mkdtemp(prefix=".portable-kb-skill-", dir=destination.parent)
            )
            shutil.rmtree(stage)
            shutil.copytree(source, stage)
            stages[agent] = stage

        for agent, destination in targets.items():
            if agent in unchanged:
                continue
            backup: Path | None = None
            if destination.exists():
                backup = Path(
                    tempfile.mkdtemp(prefix=".portable-kb-previous-", dir=destination.parent)
                )
                backup.rmdir()
                os.replace(destination, backup)
            backups[agent] = backup
            try:
                os.replace(stages[agent], destination)
            except Exception:
                if backup is not None:
                    os.replace(backup, destination)
                    backups[agent] = None
                raise
            published.append(agent)
    except Exception as exc:
        for agent in reversed(published):
            destination = targets[agent]
            shutil.rmtree(destination, ignore_errors=True)
            backup = backups.get(agent)
            if backup is not None and backup.exists():
                os.replace(backup, destination)
                backups[agent] = None
        if isinstance(exc, SkillError):
            raise
        raise SkillError("Agent skill installation failed; prior installations were restored.") from exc
    finally:
        for stage in stages.values():
            shutil.rmtree(stage, ignore_errors=True)

    for backup in backups.values():
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    return {
        "skill": "portable-kb",
        "targets": {agent: str(path) for agent, path in targets.items()},
        "unchanged": unchanged,
        "ok": True,
    }


def _target_paths(home: Path, target: SkillTarget) -> dict[str, Path]:
    paths = {
        "codex": home / ".agents" / "skills" / "portable-kb",
        "claude": home / ".claude" / "skills" / "portable-kb",
    }
    if target is SkillTarget.BOTH:
        return paths
    return {target.value: paths[target.value]}


def _trees_match(source: Path, destination: Path) -> bool:
    if any(path.is_symlink() for path in destination.rglob("*")):
        return False
    source_files = {
        path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()
    }
    destination_files = {
        path.relative_to(destination): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    return source_files == destination_files
