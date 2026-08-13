"""Strict, non-mutating discovery and parsing for OKF Markdown documents."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from .models import Finding, KnowledgeItem, Severity

RESERVED_NAMES = frozenset({"index.md", "log.md"})


@dataclass(frozen=True, slots=True)
class ParseResult:
    item: KnowledgeItem | None
    findings: tuple[Finding, ...]


def discover_concepts(bundle: Path) -> tuple[Path, ...]:
    """Discover concept files in stable bundle-relative order."""

    return tuple(
        sorted(
            (
                path
                for path in bundle.rglob("*.md")
                if path.name not in RESERVED_NAMES
                and not any(part.startswith(".") for part in path.relative_to(bundle).parts)
            ),
            key=lambda path: path.relative_to(bundle).as_posix(),
        )
    )


def discover_reserved(bundle: Path) -> tuple[Path, ...]:
    """Discover OKF reserved Markdown documents."""

    return tuple(
        sorted(
            (path for path in bundle.rglob("*.md") if path.name in RESERVED_NAMES),
            key=lambda path: path.relative_to(bundle).as_posix(),
        )
    )


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.allow_duplicate_keys = False
    yaml.preserve_quotes = True
    return yaml


def _field_lines(mapping: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(mapping, CommentedMap):
        return {}
    result: dict[str, int] = {}
    for key in mapping:
        try:
            line, _column = mapping.lc.key(key)
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        # The YAML payload begins after the opening delimiter.
        result[str(key)] = line + 2
    return result


def parse_concept(path: Path, bundle: Path) -> ParseResult:
    """Parse one concept without altering its source representation."""

    relative = path.relative_to(bundle).as_posix()
    findings: list[Finding] = []
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        findings.append(
            Finding(
                "KB-E001",
                Severity.ERROR,
                relative,
                "Concept begins with a UTF-8 byte-order mark.",
                line=1,
                remediation="Remove the byte-order mark and retain UTF-8 encoding.",
            )
        )
        raw = raw[3:]
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        findings.append(
            Finding(
                "KB-E001",
                Severity.ERROR,
                relative,
                f"Concept is not valid UTF-8: {exc}.",
                line=1,
                remediation="Decode the source correctly and save it as UTF-8.",
            )
        )
        return ParseResult(None, tuple(findings))

    if "\r\n" in source:
        findings.append(
            Finding(
                "KB-W006",
                Severity.WARNING,
                relative,
                "Concept uses CRLF line endings instead of canonical LF.",
                remediation="Normalize line endings only in an explicit formatting change.",
            )
        )
    if any(line.rstrip("\r\n").endswith((" ", "\t")) for line in source.splitlines(keepends=True)):
        findings.append(
            Finding(
                "KB-W006",
                Severity.WARNING,
                relative,
                "Concept contains trailing whitespace.",
                remediation="Remove trailing whitespace in an explicit formatting change.",
            )
        )
    normalized = source.replace("\r\n", "\n")
    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        findings.append(
            Finding(
                "KB-E002",
                Severity.ERROR,
                relative,
                "Concept does not begin with YAML frontmatter at byte zero.",
                line=1,
                profile="OKF v0.2",
                remediation="Add a frontmatter block beginning with --- at byte zero.",
            )
        )
        return ParseResult(None, tuple(findings))

    closing_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\n") == "---":
            closing_index = index
            break
    if closing_index is None:
        findings.append(
            Finding(
                "KB-E004",
                Severity.ERROR,
                relative,
                "Frontmatter has no unambiguous closing delimiter.",
                line=1,
                profile="OKF v0.2",
                remediation="Add a closing --- delimiter on its own line.",
            )
        )
        return ParseResult(None, tuple(findings))

    frontmatter = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :])
    try:
        metadata = _yaml().load(frontmatter)
    except (YAMLError, ValueError, TypeError) as exc:
        mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
        line = mark.line + 2 if mark is not None else 2
        findings.append(
            Finding(
                "KB-E003",
                Severity.ERROR,
                relative,
                f"Frontmatter is not safe, unambiguous YAML: {exc.__class__.__name__}.",
                line=line,
                profile="OKF v0.2",
                remediation="Remove duplicate keys, aliases, custom tags, or invalid YAML syntax.",
            )
        )
        return ParseResult(None, tuple(findings))
    if not isinstance(metadata, Mapping):
        findings.append(
            Finding(
                "KB-E003",
                Severity.ERROR,
                relative,
                "Frontmatter must parse to a mapping.",
                line=2,
                profile="OKF v0.2",
                remediation="Replace the frontmatter root with key-value mappings.",
            )
        )
        return ParseResult(None, tuple(findings))

    # Round-trip parsing permits aliases, so reject YAML graph features before
    # any consumer can accidentally assign them operational meaning.
    if _contains_yaml_graph_syntax(frontmatter):
        findings.append(
            Finding(
                "KB-E003",
                Severity.ERROR,
                relative,
                "Frontmatter uses an anchor, alias, merge key, or custom YAML tag.",
                line=2,
                remediation="Expand values explicitly and use only YAML 1.2 core scalar types.",
            )
        )

    item = KnowledgeItem(
        path=path,
        relative_path=relative,
        metadata=metadata,
        body=body,
        frontmatter_text=frontmatter,
        source_text=normalized,
        field_lines=_field_lines(metadata),
    )
    return ParseResult(item, tuple(findings))


def _contains_yaml_graph_syntax(text: str) -> bool:
    """Conservatively detect disallowed YAML graph and tag syntax."""

    for raw_line in text.splitlines():
        content = raw_line.split("#", 1)[0]
        stripped = content.lstrip()
        if stripped.startswith("<<:") or stripped.startswith("!"):
            return True
        tokens = content.replace("[", " ").replace("]", " ").replace(",", " ").split()
        if any(
            token.startswith("&") or token.startswith("*") or token.startswith("!")
            for token in tokens
        ):
            return True
    return False


def iter_mapping_paths(value: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Yield dotted/list-index paths for every value in a parsed mapping."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, child
            yield from iter_mapping_paths(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            yield path, child
            yield from iter_mapping_paths(child, path)
