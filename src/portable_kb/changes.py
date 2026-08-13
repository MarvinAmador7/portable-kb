"""Reviewable, optimistic file change sets for lifecycle operations."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .models import ValidationReport


class ConcurrentChangeError(RuntimeError):
    """The bundle changed after a change set was planned."""


@dataclass(frozen=True, slots=True)
class FileChange:
    relative_path: str
    before: str | None
    after: str | None

    @property
    def kind(self) -> str:
        if self.before is None:
            return "create"
        if self.after is None:
            return "delete"
        return "update"


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """A validated plan that is applied only through an explicit call."""

    bundle: Path
    changes: tuple[FileChange, ...]
    validation: ValidationReport
    operation: str

    def apply(self) -> None:
        """Apply with optimistic preflight and best-effort rollback."""

        for change in self.changes:
            path = self.bundle / change.relative_path
            actual = path.read_text(encoding="utf-8") if path.exists() else None
            if actual != change.before:
                raise ConcurrentChangeError(
                    f"Bundle changed after planning: {change.relative_path}"
                )
        applied: list[FileChange] = []
        try:
            # Write replacements before removing move sources so a crash cannot
            # erase the only copy of an identity.
            for change in self.changes:
                if change.after is not None:
                    _atomic_write(self.bundle / change.relative_path, change.after)
                    applied.append(change)
            for change in self.changes:
                if change.after is None:
                    path = self.bundle / change.relative_path
                    path.unlink()
                    applied.append(change)
        except Exception:
            for change in reversed(applied):
                path = self.bundle / change.relative_path
                if change.before is None:
                    if path.exists():
                        path.unlink()
                else:
                    _atomic_write(path, change.before)
            raise


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        with suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def diff_trees(base: Path, proposed: Path, report: ValidationReport, operation: str) -> ChangeSet:
    """Create a deterministic text-file change set between two bundle trees."""

    paths = sorted(_text_paths(base) | _text_paths(proposed))
    changes: list[FileChange] = []
    for relative in paths:
        old_path = base / relative
        new_path = proposed / relative
        before = old_path.read_text(encoding="utf-8") if old_path.exists() else None
        after = new_path.read_text(encoding="utf-8") if new_path.exists() else None
        if before != after:
            changes.append(FileChange(relative, before, after))
    return ChangeSet(base.resolve(), tuple(changes), report, operation)


def _text_paths(root: Path) -> set[str]:
    suffixes = {".md", ".yaml", ".yml"}
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix in suffixes
    }
