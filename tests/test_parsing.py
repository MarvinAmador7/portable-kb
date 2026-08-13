from __future__ import annotations

from pathlib import Path

from portable_kb.parsing import discover_concepts, parse_concept


def test_discovery_excludes_reserved_and_hidden(bundle: Path) -> None:
    paths = discover_concepts(bundle)
    relative = {path.relative_to(bundle).as_posix() for path in paths}
    assert "index.md" not in relative
    assert "log.md" not in relative
    assert all(not part.startswith(".") for path in relative for part in Path(path).parts)
    assert len(paths) == 14


def test_parse_preserves_body_and_field_lines(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    result = parse_concept(path, bundle)
    assert result.findings == ()
    assert result.item is not None
    assert result.item.id == "urn:uuid:7d657931-1613-4ff9-945b-5048617d7659"
    assert "# Material change" in result.item.body
    assert result.item.field_lines["id"] == 3


def test_missing_frontmatter_is_okf_error(bundle: Path) -> None:
    path = bundle / "inbox/bad.md"
    path.parent.mkdir()
    path.write_text("# No frontmatter\n", encoding="utf-8")
    result = parse_concept(path, bundle)
    assert result.item is None
    assert [(finding.code, finding.profile) for finding in result.findings] == [
        ("KB-E002", "OKF v0.2")
    ]


def test_bom_and_crlf_are_reported(bundle: Path) -> None:
    source = (bundle / "curated/concepts/material-change.md").read_text(encoding="utf-8")
    path = bundle / "inbox/bom.md"
    path.parent.mkdir()
    path.write_bytes(b"\xef\xbb\xbf" + source.replace("\n", "\r\n").encode())
    result = parse_concept(path, bundle)
    assert result.item is not None
    assert {finding.code for finding in result.findings} == {"KB-E001", "KB-W006"}


def test_duplicate_yaml_key_is_rejected(bundle: Path) -> None:
    path = bundle / "inbox/duplicate.md"
    path.parent.mkdir()
    path.write_text("---\ntype: concept\ntype: question\n---\n# Duplicate\n", encoding="utf-8")
    result = parse_concept(path, bundle)
    assert result.item is None
    assert [finding.code for finding in result.findings] == ["KB-E003"]


def test_yaml_alias_is_rejected(bundle: Path) -> None:
    path = bundle / "inbox/alias.md"
    path.parent.mkdir()
    path.write_text("---\ntype: &kind concept\ntitle: *kind\n---\n# Alias\n", encoding="utf-8")
    result = parse_concept(path, bundle)
    assert result.item is not None
    assert "KB-E003" in {finding.code for finding in result.findings}


def test_invalid_utf8_and_missing_delimiter_are_rejected(bundle: Path) -> None:
    inbox = bundle / "inbox"
    inbox.mkdir()
    binary = inbox / "binary.md"
    binary.write_bytes(b"---\ntype: concept\n---\n\xff")
    invalid = parse_concept(binary, bundle)
    assert invalid.item is None
    assert [finding.code for finding in invalid.findings] == ["KB-E001"]

    unterminated = inbox / "unterminated.md"
    unterminated.write_text("---\ntype: concept\n", encoding="utf-8")
    missing = parse_concept(unterminated, bundle)
    assert missing.item is None
    assert [finding.code for finding in missing.findings] == ["KB-E004"]


def test_frontmatter_root_must_be_mapping(bundle: Path) -> None:
    path = bundle / "inbox/list-root.md"
    path.parent.mkdir()
    path.write_text("---\n- concept\n- question\n---\n# List\n", encoding="utf-8")
    result = parse_concept(path, bundle)
    assert result.item is None
    assert [finding.code for finding in result.findings] == ["KB-E003"]


def test_symbolic_link_concepts_are_rejected(bundle: Path) -> None:
    link = bundle / "inbox/external-concept.md"
    link.parent.mkdir()
    link.symlink_to(bundle.parent.parent / "README.md")
    from portable_kb import validate_bundle

    report = validate_bundle(bundle, as_of="2026-08-12")
    assert "KB-E007" in {finding.code for finding in report.findings}
