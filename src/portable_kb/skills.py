"""Installation of the bundled Portable KB skill for supported coding agents."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any

RECEIPT_NAME = ".portable-kb-skill.json"


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
    source_hash = _tree_hash(source)
    unchanged: list[str] = []
    for agent, destination in targets.items():
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            raise SkillError(f"Agent skill target is unsafe: {destination}")
        if destination.exists() and not force:
            if _trees_match(source, destination):
                receipt = _read_receipt(destination)
                if receipt is not None and receipt.get("content_sha256") == source_hash:
                    unchanged.append(agent)
                continue
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
            _write_receipt(stage, source_hash)
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


def skill_status(
    target: SkillTarget | str = SkillTarget.BOTH,
    *,
    user_home: Path | None = None,
) -> dict[str, Any]:
    """Compare installed agent workflows with the bundled canonical skill."""

    try:
        selected = SkillTarget(target)
    except ValueError as exc:
        raise SkillError("Skill target must be codex, claude, or both.") from exc
    home = (user_home or Path.home()).expanduser().absolute()
    source = bundled_skill_path()
    bundled_hash = _tree_hash(source)
    targets: dict[str, dict[str, Any]] = {}
    for agent, destination in _target_paths(home, selected).items():
        result: dict[str, Any] = {
            "path": str(destination),
            "state": "missing",
            "managed": False,
            "bundled_hash": bundled_hash,
            "installed_hash": None,
        }
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            result.update(state="unsafe", error="Skill target is not a regular directory.")
        elif destination.exists():
            if any(path.is_symlink() for path in destination.rglob("*")):
                result.update(state="unsafe", error="Skill target contains symbolic links.")
            else:
                installed_hash = _tree_hash(destination)
                receipt = _read_receipt(destination)
                result["installed_hash"] = installed_hash
                result["managed"] = receipt is not None
                if installed_hash == bundled_hash:
                    result["state"] = "current"
                elif receipt is None:
                    result["state"] = "unmanaged"
                elif receipt.get("content_sha256") == installed_hash:
                    result["state"] = "outdated"
                else:
                    result["state"] = "modified"
                if receipt is not None:
                    result["installed_version"] = receipt.get("portable_kb_version")
        targets[agent] = result
    return {
        "skill": "portable-kb",
        "ok": all(result["state"] == "current" for result in targets.values()),
        "bundled_hash": bundled_hash,
        "targets": targets,
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
    source_files = _tree_files(source)
    destination_files = _tree_files(destination)
    return source_files == destination_files


def _tree_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name != RECEIPT_NAME
    }


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative, content in sorted(_tree_files(root).items(), key=lambda item: item[0].as_posix()):
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _write_receipt(destination: Path, content_hash: str) -> None:
    receipt = destination / RECEIPT_NAME
    if receipt.is_symlink():
        raise SkillError(f"Agent skill receipt is unsafe: {receipt}")
    try:
        version = importlib.metadata.version("portable-kb-core")
    except importlib.metadata.PackageNotFoundError:
        version = "source"
    payload = {
        "schema_version": 1,
        "skill": "portable-kb",
        "portable_kb_version": version,
        "content_sha256": content_hash,
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{RECEIPT_NAME}.", suffix=".tmp", dir=destination
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        temporary.chmod(0o600)
        os.replace(temporary, receipt)
    finally:
        temporary.unlink(missing_ok=True)


def _read_receipt(destination: Path) -> dict[str, Any] | None:
    receipt = destination / RECEIPT_NAME
    if receipt.is_symlink() or not receipt.is_file():
        return None
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return None
    content_hash = payload.get("content_sha256")
    if not isinstance(content_hash, str) or not content_hash.startswith("sha256:"):
        return None
    return payload
