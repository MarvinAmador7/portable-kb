from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from portable_kb import validate_bundle, validate_transition


def codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


def test_real_bundle_passes_without_findings(bundle: Path) -> None:
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert report.concept_count == 14
    assert report.okf_passes
    assert report.profile_passes
    assert report.findings == ()
    assert report.as_dict()["core_kb_0_1"] == "pass"


def test_validation_is_deterministic(bundle: Path) -> None:
    first = validate_bundle(bundle, as_of="2026-08-12").as_dict()
    second = validate_bundle(bundle, as_of="2026-08-12").as_dict()
    assert first == second


def test_golden_machine_reports(bundle: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    expected_valid = json.loads(
        (repository / "examples/golden/knowledge-report.json").read_text(encoding="utf-8")
    )
    expected_invalid = json.loads(
        (repository / "examples/golden/invalid-report.json").read_text(encoding="utf-8")
    )
    assert validate_bundle(bundle, as_of="2026-08-12").as_dict() == expected_valid
    assert (
        validate_bundle(repository / "examples/invalid", as_of="2026-08-06").as_dict()
        == expected_invalid
    )


def test_existing_positive_and_negative_corpora(valid_examples: Path) -> None:
    positive = validate_bundle(valid_examples, as_of="2026-08-06")
    negative = validate_bundle(
        Path(__file__).resolve().parents[1] / "examples" / "invalid",
        as_of="2026-08-06",
    )
    assert positive.profile_passes
    assert {finding.code for finding in positive.warnings} == {
        "KB-W308",
        "KB-W503",
        "KB-W605",
    }
    assert {
        "KB-E123",
        "KB-E124",
        "KB-E201",
        "KB-E400",
        "KB-E401",
        "KB-E402",
        "KB-E403",
    } <= codes(negative)
    assert "KB-I408" in codes(positive)
    assert not negative.profile_passes
    assert negative.okf_passes


def test_missing_bundle_config_is_an_error(bundle: Path) -> None:
    (bundle / ".core-kb.yaml").unlink()
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert "KB-E700" in codes(report)


def test_missing_bundle_and_invalid_config_are_reported(bundle: Path, tmp_path: Path) -> None:
    missing = validate_bundle(tmp_path / "does-not-exist", as_of="2026-08-12")
    assert codes(missing) == {"KB-E000"}
    config = bundle / ".core-kb.yaml"
    config.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    invalid = validate_bundle(bundle, as_of="2026-08-12")
    assert "KB-E700" in codes(invalid)


def test_bundle_config_cannot_silently_change_upstream_pin(bundle: Path) -> None:
    config = bundle / ".core-kb.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "374e0bc4c644310ff56cdf9c0fe81eccdec862b0",
            "930b65fc3f5619d5d0591f88c72ebae8b848d60d",
        ),
        encoding="utf-8",
    )
    assert "KB-E700" in codes(validate_bundle(bundle, as_of="2026-08-12"))


def test_bundle_config_and_reserved_files_cannot_be_symlinks(bundle: Path) -> None:
    real_config = bundle / "config-real.yaml"
    config = bundle / ".core-kb.yaml"
    config.rename(real_config)
    config.symlink_to(real_config.name)
    real_index = bundle / "index-real.md"
    index = bundle / "index.md"
    index.rename(real_index)
    index.symlink_to(real_index.name)
    result = codes(validate_bundle(bundle, as_of="2026-08-12"))
    assert {"KB-E007", "KB-E700"} <= result


def test_reserved_index_and_log_structure(bundle: Path) -> None:
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n# Wrong\n', encoding="utf-8")
    (bundle / "log.md").write_text("# Log\n\n## not-a-date\n\n* Entry\n", encoding="utf-8")
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert {"KB-E500", "KB-E501"} <= codes(report)


def test_log_date_groups_must_be_unique(bundle: Path) -> None:
    log = bundle / "log.md"
    text = log.read_text(encoding="utf-8")
    log.write_text(text + "\n## 2026-08-12\n\n* Duplicate date group.\n", encoding="utf-8")
    assert "KB-E501" in codes(validate_bundle(bundle, as_of="2026-08-12"))


def test_missing_indexes_are_profile_warnings(bundle: Path) -> None:
    (bundle / "index.md").unlink()
    (bundle / "log.md").unlink()
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert [finding.code for finding in report.warnings].count("KB-W503") >= 2


def test_duplicate_id_is_a_corpus_error(bundle: Path) -> None:
    source = bundle / "curated/concepts/material-change.md"
    target = bundle / "inbox/duplicate-identity.md"
    target.parent.mkdir()
    shutil.copyfile(source, target)
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert [finding.code for finding in report.errors].count("KB-E121") == 2


def test_unquoted_date_is_an_error(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8").replace(
        'created_at: "2026-08-13T01:34:46Z"',
        "created_at: 2026-08-13T01:34:46Z",
    )
    path.write_text(text, encoding="utf-8")
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert "KB-E124A" in codes(report)


def test_broken_link_severity_depends_on_state(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8") + "\n[Missing](missing.md)\n"
    path.write_text(text, encoding="utf-8")
    draft = validate_bundle(bundle, as_of="2026-08-12")
    assert "KB-W405" in codes(draft)
    path.write_text(text.replace("status: draft", "status: stable"), encoding="utf-8")
    stable = validate_bundle(bundle, as_of="2026-08-12")
    assert "KB-E404" in codes(stable)


def test_footnote_must_join_source_id(bundle: Path) -> None:
    path = bundle / "curated/concepts/material-change.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nUnsupported.[^missing]\n", encoding="utf-8"
    )
    report = validate_bundle(bundle, as_of="2026-08-12")
    assert "KB-E204" in codes(report)


def test_inactive_stable_type_and_unauthorized_reviewer(valid_examples: Path) -> None:
    config = valid_examples / ".core-kb.yaml"
    text = config.read_text(encoding="utf-8")
    text = text.replace("  - policy\n", "").replace("    - human:fixture-reviewer-a\n", "")
    config.write_text(text, encoding="utf-8")
    report = validate_bundle(valid_examples, as_of="2026-08-06")
    assert {"KB-E701", "KB-E702"} <= codes(report)


def test_transition_rejects_identity_change_and_deletion(bundle: Path, tmp_path: Path) -> None:
    proposed = tmp_path / "proposed"
    shutil.copytree(bundle, proposed)
    identity = proposed / "curated/concepts/material-change.md"
    identity.write_text(
        identity.read_text(encoding="utf-8").replace(
            "urn:uuid:7d657931-1613-4ff9-945b-5048617d7659",
            "urn:uuid:92c63fc2-78b0-4d6a-8307-0961230106a0",
        ),
        encoding="utf-8",
    )
    (proposed / "questions/publish-project-source-identifiers.md").unlink()
    report = validate_transition(bundle, proposed, as_of="2026-08-12")
    assert {"KB-E122", "KB-E314"} <= codes(report)


def test_transition_rejects_retained_verification(valid_examples: Path, tmp_path: Path) -> None:
    proposed = tmp_path / "proposed"
    shutil.copytree(valid_examples, proposed)
    path = proposed / "decision-adopt-stable-identifiers.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("Assign every", "Require every"), encoding="utf-8"
    )
    report = validate_transition(valid_examples, proposed, as_of="2026-08-06")
    assert {"KB-W126", "KB-E311"} <= codes(report)


def test_checked_in_transition_fixture() -> None:
    repository = Path(__file__).resolve().parents[1]
    fixture = repository / "examples/transitions/retained-verification"
    report = validate_transition(fixture / "base", fixture / "proposed", as_of="2026-08-12")
    assert {"KB-E127", "KB-E311"} <= codes(report)


def test_indexed_stable_item_is_not_an_orphan() -> None:
    repository = Path(__file__).resolve().parents[1]
    fixture = repository / "examples/transitions/retained-verification/base"
    report = validate_bundle(fixture, as_of="2026-08-12")
    assert "KB-I408" not in codes(report)


@pytest.mark.parametrize(
    ("old_status", "new_status", "allowed"),
    [
        ("draft", "draft", True),
        ("draft", "stable", True),
        ("draft", "deprecated", True),
        ("stable", "draft", True),
        ("stable", "stable", True),
        ("stable", "deprecated", True),
        ("deprecated", "deprecated", True),
        ("deprecated", "draft", False),
        ("deprecated", "stable", False),
    ],
)
def test_complete_status_transition_matrix(
    bundle: Path,
    tmp_path: Path,
    old_status: str,
    new_status: str,
    allowed: bool,
) -> None:
    base = tmp_path / f"base-{old_status}-{new_status}"
    proposed = tmp_path / f"proposed-{old_status}-{new_status}"
    shutil.copytree(bundle, base)
    path = base / "curated/concepts/material-change.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("status: draft", f"status: {old_status}")
    text = text.replace("by: openai-codex/gpt-5", "by: human:transition-author")
    text = text.replace("method: agent-generated", "method: human-authored")
    path.write_text(text, encoding="utf-8")
    shutil.copytree(base, proposed)
    proposed_path = proposed / "curated/concepts/material-change.md"
    proposed_path.write_text(
        proposed_path.read_text(encoding="utf-8").replace(
            f"status: {old_status}", f"status: {new_status}"
        ),
        encoding="utf-8",
    )
    report = validate_transition(base, proposed, as_of="2026-08-13")
    transition_errors = [finding for finding in report.errors if finding.code == "KB-E301"]
    assert bool(transition_errors) is not allowed


def test_validation_never_mutates_bundle(bundle: Path) -> None:
    before = {
        path.relative_to(bundle).as_posix(): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    validate_bundle(bundle, as_of="2026-08-12")
    after = {
        path.relative_to(bundle).as_posix(): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    assert after == before
