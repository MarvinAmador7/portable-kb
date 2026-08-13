"""Deterministic OKF progressive index generation."""

from __future__ import annotations

from pathlib import Path

from .parsing import discover_concepts, parse_concept


def generate_indexes(bundle: str | Path) -> tuple[Path, ...]:
    """Regenerate indexes for directories containing current knowledge."""

    root = Path(bundle).resolve()
    items_by_dir: dict[Path, list[tuple[str, str, str]]] = {}
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
            items_by_dir.setdefault(path.parent, []).append((title, path.name, description))

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
        content = _render_index(root, directory, items_by_dir)
        path = directory / "index.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            changed.append(path)
    return tuple(changed)


def _render_index(
    root: Path,
    directory: Path,
    items_by_dir: dict[Path, list[tuple[str, str, str]]],
) -> str:
    label = "Portable KB core" if directory == root else _humanize(directory.name)
    lines: list[str] = []
    if directory == root:
        lines.extend(["---", 'okf_version: "0.2"', "---", ""])
    lines.extend([f"# {label}", ""])

    child_dirs = sorted(
        {
            candidate.relative_to(directory).parts[0]
            for candidate in items_by_dir
            if candidate != directory and directory in candidate.parents
        },
        key=str.casefold,
    )
    if child_dirs:
        lines.extend(["## Groups", ""])
        for child in child_dirs:
            lines.append(
                f"* [{_humanize(child)}]({child}/) - Browse {_humanize(child).casefold()} knowledge."
            )
        lines.append("")

    items = sorted(items_by_dir.get(directory, []), key=lambda item: (item[0].casefold(), item[1]))
    if items:
        lines.extend(["## Concepts", ""])
        for title, filename, description in items:
            lines.append(f"* [{title}]({filename}) - {description}")
        lines.append("")
    if not child_dirs and not items:
        lines.extend(["No current concepts are indexed in this scope.", ""])
    return "\n".join(lines)


def _humanize(value: str) -> str:
    return value.replace("-", " ").capitalize()
