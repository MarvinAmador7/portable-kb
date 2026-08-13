"""Round-trip-aware frontmatter editing utilities."""

from __future__ import annotations

from collections.abc import MutableMapping
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .parsing import parse_concept


def roundtrip_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.allow_duplicate_keys = False
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 1000
    return yaml


def load_editable(path: Path, bundle: Path) -> tuple[MutableMapping[str, Any], str]:
    result = parse_concept(path, bundle)
    if result.item is None or result.findings:
        messages = "; ".join(f"{finding.code}: {finding.message}" for finding in result.findings)
        raise ValueError(f"Cannot edit invalid concept {path}: {messages}")
    metadata = result.item.metadata
    if not isinstance(metadata, MutableMapping):
        raise ValueError(f"Frontmatter is not mutable: {path}")
    return metadata, result.item.body


def quoted(value: str) -> DoubleQuotedScalarString:
    return DoubleQuotedScalarString(value)


def render_concept(metadata: MutableMapping[str, Any], body: str) -> str:
    stream = StringIO()
    roundtrip_yaml().dump(metadata, stream)
    normalized_body = body.lstrip("\n").rstrip() + "\n"
    return f"---\n{stream.getvalue()}---\n\n{normalized_body}"
