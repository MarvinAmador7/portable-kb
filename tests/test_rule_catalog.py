from __future__ import annotations

import shutil
from pathlib import Path

from ruamel.yaml import YAML

from portable_kb import validate_bundle, validate_transition


def codes(bundle: Path, as_of: str = "2026-08-12") -> set[str]:
    return {finding.code for finding in validate_bundle(bundle, as_of=as_of).findings}


def test_vocabulary_extension_actor_and_tag_rules(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "sensitivity: internal",
        "author: human:legacy\nx-experiment: value\nmystery: value\nsensitivity: internal",
    )
    text = text.replace("by: openai-codex/gpt-5", "by: human:x")
    text = text.replace("  - lifecycle\n  - verification", "  - Bad Tag\n  - Bad Tag")
    path.write_text(text, encoding="utf-8")
    assert {"KB-E103", "KB-W104", "KB-E105", "KB-E106", "KB-E208"} <= codes(bundle)


def test_source_resource_citation_usage_and_primary_rules(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "resource: urn:core-kb:design:lifecycle:material-change",
        "resource: ../../sources/okf-v02.md\n    usage_count: 3",
    )
    text = text.replace("id: lifecycle-design", "id: unused-source")
    path.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-E204", "KB-W205", "KB-E206", "KB-W207"} <= result


def test_missing_and_duplicate_source_fields(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "  - id: lifecycle-design\n    resource: urn:core-kb:design:lifecycle:material-change",
        "  - id: lifecycle-design\n  - id: lifecycle-design\n    resource: urn:core-kb:design:duplicate",
    )
    path.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-E202", "KB-E203"} <= result


def test_lifecycle_archive_inbox_and_tag_health(bundle: Path) -> None:
    source = bundle / "questions/assign-authorized-reviewers.md"
    inbox = bundle / "inbox/old-question.md"
    inbox.parent.mkdir()
    text = source.read_text(encoding="utf-8")
    text = text.replace("2026-08-13T01:34:46Z", "2026-01-01T00:00:00Z")
    text = text.replace("status: draft", "status: deprecated")
    text = text.replace(
        "sensitivity: internal",
        'archived:\n  at: "2026-08-12T00:00:00Z"\n  reason: This is intentionally in the wrong directory.\nsensitivity: internal',
    )
    inbox.write_text(text, encoding="utf-8")
    result = codes(bundle, as_of="2026-08-12")
    assert {"KB-W312", "KB-E313"} <= result

    # Restore draft status while retaining the old timestamp to exercise inbox cadence.
    inbox.write_text(
        text.replace("status: deprecated", "status: draft").replace(
            'archived:\n  at: "2026-08-12T00:00:00Z"\n  reason: This is intentionally in the wrong directory.\n',
            "",
        ),
        encoding="utf-8",
    )
    assert "KB-I603" in codes(bundle, as_of="2026-08-12")


def test_system_review_and_stable_tag_health(valid_examples: Path) -> None:
    path = valid_examples / "stale-system.md"
    text = path.read_text(encoding="utf-8")
    verified = 'verified:\n  - by: human:fixture-reviewer\n    at: "2026-05-01T11:00:00Z"\n'
    tags = "tags:\n  - fixture\n  - stale\n"
    path.write_text(text.replace(verified, "").replace(tags, ""), encoding="utf-8")
    result = codes(valid_examples, as_of="2026-08-06")
    assert {"KB-W307", "KB-W308", "KB-I604"} <= result


def test_effective_and_freshness_date_rules(valid_examples: Path) -> None:
    path = valid_examples / "decision-adopt-stable-identifiers.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'valid_from: "2026-08-06"', 'valid_from: "2027-01-02"\nstale_after: "2027-01-01"'
    )
    path.write_text(text, encoding="utf-8")
    result = codes(valid_examples, as_of="2026-08-06")
    assert {"KB-I309", "KB-E310"} <= result


def test_source_change_after_verification_is_reported(valid_examples: Path) -> None:
    path = valid_examples / "decision-adopt-stable-identifiers.md"
    text = path.read_text(encoding="utf-8").replace(
        "title: Open Knowledge Format v0.2 specification",
        'title: Open Knowledge Format v0.2 specification\n    last_modified: "2026-08-07"',
    )
    path.write_text(text, encoding="utf-8")
    assert "KB-W309" in codes(valid_examples, as_of="2026-08-08")


def test_body_safety_consistency_and_relationship_prose(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("# Material change", "# Different heading", 1)
    text = text.replace(
        "[verification is snapshot evidence](verification-is-evidence.md)", "verification evidence"
    )
    text += "\n[[wiki-link]]\n\n![tracker](https://example.invalid/pixel.gif)\n"
    path.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-W602", "KB-W406", "KB-W407", "KB-E506"} <= result


def test_stable_placeholder_and_sections(valid_examples: Path) -> None:
    path = valid_examples / "procedure-review-stale-knowledge.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("## Rollback", "## Recovery") + "\nTODO\n"
    path.write_text(text, encoding="utf-8")
    result = codes(valid_examples, as_of="2026-08-06")
    assert {"KB-W505", "KB-W507"} <= result


def test_index_membership_description_and_entry_shape(bundle: Path) -> None:
    index = bundle / "curated/concepts/index.md"
    text = index.read_text(encoding="utf-8")
    text = text.replace(
        "* [Material change](material-change.md) - A material change alters what a reader may believe or do and therefore invalidates prior verification.\n",
        "",
    )
    text += "* malformed entry\n"
    text = text.replace("A knowledge item's UUID remains constant", "A mismatched description")
    index.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-W503", "KB-W504", "KB-E500"} <= result


def test_duplicate_title_resource_and_conflict_candidates(valid_examples: Path) -> None:
    source = valid_examples / "source-summary-okf-v02.md"
    duplicate = valid_examples / "source-summary-okf-v02-copy.md"
    text = source.read_text(encoding="utf-8").replace(
        "urn:uuid:12614e98-57c7-4aa3-aaea-7b3dd2dd8c1e",
        "urn:uuid:92c63fc2-78b0-4d6a-8307-0961230106a0",
    )
    duplicate.write_text(text, encoding="utf-8")
    result = codes(valid_examples, as_of="2026-08-06")
    assert {"KB-W600", "KB-W601", "KB-W605"} <= result


def test_relation_target_and_status_vocabulary(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("status: draft", "status: current")
    text = text.replace(
        "urn:uuid:3052cfa1-4270-45e1-8399-90ba1a02fe86",
        "urn:uuid:92c63fc2-78b0-4d6a-8307-0961230106a0",
    )
    path.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-E300", "KB-E400"} <= result


def test_file_required_type_identity_and_timestamp_rules(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    renamed = path.with_name("Bad Filename.md")
    path.rename(renamed)
    text = renamed.read_text(encoding="utf-8")
    text = text.replace("type: concept\n", "")
    text = text.replace("title: Material change\n", "")
    text = text.replace(
        "urn:uuid:7d657931-1613-4ff9-945b-5048617d7659",
        "not-a-uuid",
    )
    text = text.replace(
        '  at: "2026-08-13T01:52:16Z"',
        '  at: "2026-08-13T01:52:17Z"',
        1,
    )
    renamed.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-E005", "KB-E100", "KB-E101", "KB-E120", "KB-E125"} <= result


def test_unknown_type_and_old_verification_rules(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("type: concept", "type: unknown-domain-type")
    text = text.replace(
        "confidence:\n",
        'verified:\n  - by: human:reviewer\n    at: "2026-01-01T00:00:00Z"\nconfidence:\n',
    )
    path.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-E102", "KB-E127", "KB-E703"} <= result


def test_generation_source_and_confidence_conditionals(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    start = text.index("sources:\n")
    end = text.index("confidence:\n")
    text = text[:start] + text[end:]
    text = text.replace(
        "confidence:\n  level: high\n  basis: The lifecycle model enumerates material fields and the transition validator checks their effects.\n",
        "",
    )
    path.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-E200", "KB-E209"} <= result


def test_each_authoritative_promotion_gate(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    original = path.read_text(encoding="utf-8")
    expected = {
        "decision": "KB-E302",
        "procedure": "KB-E303",
        "policy": "KB-E304",
        "system": "KB-E305",
    }
    for item_type, rule in expected.items():
        text = original.replace("type: concept", f"type: {item_type}").replace(
            "status: draft", "status: stable"
        )
        path.write_text(text, encoding="utf-8")
        assert rule in codes(bundle), item_type
    # Stable generated content independently needs a human event.
    path.write_text(original.replace("status: draft", "status: stable"), encoding="utf-8")
    assert "KB-E306" in codes(bundle)


def test_disallowed_deprecated_to_stable_transition(bundle: Path, tmp_path: Path) -> None:
    base = tmp_path / "base"
    proposed = tmp_path / "proposed"
    shutil.copytree(bundle, base)
    target = base / "curated/concepts/material-change.md"
    target.write_text(
        target.read_text(encoding="utf-8").replace("status: draft", "status: deprecated"),
        encoding="utf-8",
    )
    shutil.copytree(base, proposed)
    proposed_target = proposed / "curated/concepts/material-change.md"
    text = proposed_target.read_text(encoding="utf-8").replace(
        "status: deprecated", "status: stable"
    )
    text = text.replace(
        "confidence:\n",
        'verified:\n  - by: human:reviewer\n    at: "2026-08-13T01:52:16Z"\nconfidence:\n',
    )
    proposed_target.write_text(text, encoding="utf-8")
    report = validate_transition(base, proposed, as_of="2026-08-13")
    assert "KB-E301" in {finding.code for finding in report.findings}


def test_broken_index_target_rule(bundle: Path) -> None:
    index = bundle / "questions/index.md"
    index.write_text(
        index.read_text(encoding="utf-8").replace("assign-authorized-reviewers.md", "missing.md"),
        encoding="utf-8",
    )
    assert "KB-E502" in codes(bundle)


def test_labeled_heuristic_evaluation_set() -> None:
    root = Path(__file__).resolve().parents[1]
    labels = YAML(typ="safe").load((root / "examples/heuristics/labels.yaml").read_text())
    assert {pair["expected_rule"] for pair in labels["pairs"]} == {"KB-W601", "KB-W605"}
    duplicate_report = validate_bundle(root / "examples/heuristics", as_of="2026-08-12")
    conflict_report = validate_bundle(root / "examples/valid", as_of="2026-08-06")
    assert "KB-W601" in {finding.code for finding in duplicate_report.findings}
    assert "KB-W605" in {finding.code for finding in conflict_report.findings}


def test_unicode_content_remains_portable(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("title: Material change", "title: Café material change ☕")
    text = text.replace("# Material change", "# Café material change ☕", 1)
    path.write_text(text, encoding="utf-8")
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert report.okf_passes
    assert report.profile_passes


def test_bundle_paths_cannot_escape_or_hide_broken_directories(bundle: Path) -> None:
    item = bundle / "curated/concepts/material-change.md"
    text = item.read_text(encoding="utf-8")
    text = text.replace(
        "resource: urn:core-kb:design:lifecycle:material-change",
        "resource: ../../../../README.md",
    )
    text += "\n[Outside](../../../README.md)\n\n[Missing directory](missing/)\n"
    item.write_text(text, encoding="utf-8")
    result = codes(bundle)
    assert {"KB-E202", "KB-W405"} <= result

    index = bundle / "questions/index.md"
    index.write_text(
        index.read_text(encoding="utf-8").replace(
            "assign-authorized-reviewers.md", "../../README.md"
        ),
        encoding="utf-8",
    )
    assert "KB-E502" in codes(bundle)


def test_footnote_definition_alone_is_not_a_live_citation(bundle: Path) -> None:
    item = bundle / "curated/concepts/material-change.md"
    text = item.read_text(encoding="utf-8")
    text = text.replace("relationships.[^lifecycle-design]", "relationships.")
    item.write_text(text, encoding="utf-8")
    assert "KB-W205" in codes(bundle)


def test_archive_path_requires_archive_metadata(bundle: Path) -> None:
    source = bundle / "questions/assign-authorized-reviewers.md"
    destination = bundle / "archive/questions/assign-authorized-reviewers.md"
    destination.parent.mkdir(parents=True)
    source.rename(destination)
    assert "KB-E313" in codes(bundle)


def test_title_collisions_are_scoped_to_a_directory(bundle: Path) -> None:
    source = bundle / "curated/concepts/material-change.md"
    destination = bundle / "questions/material-change.md"
    text = source.read_text(encoding="utf-8").replace(
        "urn:uuid:7d657931-1613-4ff9-945b-5048617d7659",
        "urn:uuid:92c63fc2-78b0-4d6a-8307-0961230106a0",
    )
    destination.write_text(text, encoding="utf-8")
    assert "KB-W600" not in codes(bundle)
