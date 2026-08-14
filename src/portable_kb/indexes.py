"""Deterministic OKF progressive index generation."""

from __future__ import annotations

import re
from pathlib import Path

from .parsing import discover_concepts, parse_concept

INDEX_START = "<!-- portable-kb:index:start -->"
INDEX_END = "<!-- portable-kb:index:end -->"
LINK = re.compile(r"^\* \[[^\]]+\]\(([^)]+)\) - .+$")
TYPE_LABELS = {
    "concept": "Concepts",
    "decision": "Decisions",
    "policy": "Policies",
    "procedure": "Procedures",
    "question": "Questions",
    "source-summary": "Source summaries",
    "system": "Systems",
}


def generate_indexes(bundle: str | Path) -> tuple[Path, ...]:
    """Regenerate indexes for directories containing current knowledge."""

    root = Path(bundle).resolve()
    items_by_dir: dict[Path, list[tuple[str, str, str, str]]] = {}
    for path in discover_concepts(root):
        parsed = parse_concept(path, root)
        if (
            parsed.item is None
            or parsed.item.status == "deprecated"
            or parsed.item.metadata.get("archived") is not None
        ):
            continue
        title = parsed.item.metadata.get("title")
        description = parsed.item.metadata.get("description")
        if isinstance(title, str) and isinstance(description, str):
            items_by_dir.setdefault(path.parent, []).append(
                (title, path.name, description, parsed.item.type or "concept")
            )

    directories = {
        root,
        *items_by_dir,
        *(path.parent for path in root.rglob("index.md")),
    }
    for directory in tuple(directories):
        current = directory
        while current != root:
            directories.add(current)
            current = current.parent

    changed: list[Path] = []
    for directory in sorted(directories, key=lambda value: value.relative_to(root).as_posix()):
        path = directory / "index.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        content = _render_index(root, directory, items_by_dir, existing)
        if existing != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            changed.append(path)
    return tuple(changed)


def _render_index(
    root: Path,
    directory: Path,
    items_by_dir: dict[Path, list[tuple[str, str, str, str]]],
    existing: str | None,
) -> str:
    child_dirs = sorted(
        {
            candidate.relative_to(directory).parts[0]
            for candidate in items_by_dir
            if candidate != directory and directory in candidate.parents
        },
        key=str.casefold,
    )
    items = sorted(items_by_dir.get(directory, []), key=lambda item: (item[0].casefold(), item[1]))
    prefix, managed, suffix = _index_regions(root, directory, existing)
    generated = _render_managed(child_dirs, items, managed)
    return f"{prefix}{INDEX_START}\n{generated}{INDEX_END}{suffix}"


def _index_regions(
    root: Path,
    directory: Path,
    existing: str | None,
) -> tuple[str, str | None, str]:
    """Split an index around its generated navigation without touching authored prose."""

    if existing is None:
        label = "Portable KB core" if directory == root else _humanize(directory.name)
        header = ""
        if directory == root:
            header = '---\nokf_version: "0.2"\n---\n\n'
        return f"{header}# {label}\n\n", None, "\n"

    starts = existing.count(INDEX_START)
    ends = existing.count(INDEX_END)
    if starts == 0 and ends == 0:
        return existing.rstrip() + "\n\n", None, "\n"
    if starts != 1 or ends != 1 or existing.index(INDEX_START) > existing.index(INDEX_END):
        raise ValueError("Index contains incomplete or duplicate Portable KB managed markers.")
    prefix, remainder = existing.split(INDEX_START, 1)
    managed, suffix = remainder.split(INDEX_END, 1)
    return prefix, managed.strip("\n"), suffix


def _render_managed(
    child_dirs: list[str],
    items: list[tuple[str, str, str, str]],
    existing: str | None,
) -> str:
    """Render navigation while retaining existing labels and descriptions by target."""

    existing_lines: dict[str, str] = {}
    target_headings: dict[str, str | None] = {}
    heading: str | None = None
    for line in (existing or "").splitlines():
        if line.startswith("## "):
            heading = line
            continue
        match = LINK.fullmatch(line)
        if match is not None:
            target = match.group(1)
            existing_lines[target] = line
            target_headings[target] = heading

    lines: list[str] = []
    group_targets = [f"{child}/" for child in child_dirs]
    if group_targets:
        group_targets = _preserve_existing_order(group_targets, existing_lines)
        group_heading = next(
            (target_headings[target] for target in group_targets if target_headings.get(target)),
            "## Groups",
        )
        lines.extend([group_heading, ""])
        for target in group_targets:
            child = target.removesuffix("/")
            lines.append(
                existing_lines.get(
                    target,
                    f"* [{_humanize(child)}]({target}) - Browse {_humanize(child).casefold()} knowledge.",
                )
            )
        lines.append("")

    if items:
        items_by_target = {item[1]: item for item in items}
        item_targets = _preserve_existing_order(list(items_by_target), existing_lines)
        items = [items_by_target[target] for target in item_targets]
        existing_heading = next(
            (target_headings[target] for target in item_targets if target_headings.get(target)),
            None,
        )
        item_types = {item_type for _title, _filename, _description, item_type in items}
        expected_heading = (
            f"## {TYPE_LABELS[next(iter(item_types))]}"
            if len(item_types) == 1
            else "## Knowledge"
        )
        known_type_headings = {f"## {label}" for label in TYPE_LABELS.values()}
        if existing_heading in known_type_headings and existing_heading != expected_heading:
            existing_heading = expected_heading
        item_heading = existing_heading or (expected_heading if existing is None or child_dirs else None)
        if item_heading is not None:
            lines.extend([item_heading, ""])
        for title, filename, description, _item_type in items:
            lines.append(f"* [{title}]({filename}) - {description}")
        lines.append("")

    if not child_dirs and not items:
        lines.extend(["No current knowledge is indexed in this scope.", ""])
    return "\n".join(lines)


def _preserve_existing_order(
    desired: list[str],
    existing_lines: dict[str, str],
) -> list[str]:
    """Keep authored navigation order and append new targets deterministically."""

    desired_set = set(desired)
    retained = [target for target in existing_lines if target in desired_set]
    retained_set = set(retained)
    return [*retained, *(target for target in desired if target not in retained_set)]


def _humanize(value: str) -> str:
    return value.replace("-", " ").capitalize()
