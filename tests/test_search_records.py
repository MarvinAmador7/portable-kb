from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from portable_kb.brains import add_brain
from portable_kb.parsing import parse_concept
from portable_kb.search import _healthy_brain
from portable_kb.search_provider import SearchError
from portable_kb.search_records import normalize_bundle, normalize_item
from portable_kb.settings import Settings


def _brain(tmp_path, brain_repo_factory):
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    source = brain_repo_factory("sections", "urn:uuid:99999999-9999-4999-8999-999999999999")
    add_brain(str(source), settings, as_of="2026-08-17")
    brain, _, bundle, _ = _healthy_brain(settings, None, as_of="2026-08-17")
    return brain, bundle


def test_sections_preserve_canonical_source_ranges_and_provenance(tmp_path, brain_repo_factory):
    brain, bundle = _brain(tmp_path, brain_repo_factory)
    records = normalize_bundle(brain, bundle)
    assert records
    assert len({record.item_id for record in records}) == 14
    assert len({record.section_id for record in records}) == len(records)
    for record in records:
        item = parse_concept(bundle / record.path, bundle).item
        lines = item.source_text.splitlines(keepends=True)
        assert record.body == "".join(lines[record.line_start - 1 : record.line_end])
        assert record.content_hash == "sha256:" + hashlib.sha256(record.body.encode()).hexdigest()
        assert record.commit == brain.commit
        assert record.brain_id == brain.id
        assert record.item_id == item.id
        assert record.status == item.status
        assert "generated:" not in record.body
        assert not record.path.endswith(("index.md", "log.md"))
    assert records == normalize_bundle(brain, bundle)


def test_fenced_headings_and_setext_ranges_are_not_confused(tmp_path, brain_repo_factory):
    brain, bundle = _brain(tmp_path, brain_repo_factory)
    path = bundle / "curated/concepts/material-change.md"
    item = parse_concept(path, bundle).item
    frontmatter = item.source_text[: len(item.source_text) - len(item.body)]
    body = "# C#\n\nIntro.\n\n## Example ###\n\n```md\n## Not a section\n~~~\n```\n\nSetext heading\n---\n\nActual prose.\n"
    changed = replace(item, source_text=frontmatter + body, body=body)
    sections = normalize_item(brain, changed)
    assert [record.heading for record in sections] == ["C#", "Example", "Setext heading"]
    assert "## Not a section\n~~~\n```" in sections[1].body
    assert sections[2].body.startswith("Setext heading\n---")
    assert (
        normalize_item(
            brain, replace(item, source_text=frontmatter + "# Title\n", body="# Title\n")
        )
        == ()
    )
    with pytest.raises(SearchError, match="identity"):
        normalize_item(brain, replace(item, metadata={}))


def test_normalization_rejects_unsafe_paths_and_bad_frontmatter(tmp_path, brain_repo_factory):
    brain, bundle = _brain(tmp_path, brain_repo_factory)
    concept = bundle / "unsafe.md"
    concept.symlink_to(bundle / "curated/concepts/material-change.md")
    with pytest.raises(SearchError, match="symbolic"):
        normalize_bundle(brain, bundle)
    concept.unlink()
    concept.write_text("Missing frontmatter")
    with pytest.raises(SearchError, match="safely"):
        normalize_bundle(brain, bundle)
