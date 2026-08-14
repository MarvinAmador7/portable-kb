from __future__ import annotations

from pathlib import Path

import pytest
from conftest import authorize

from portable_kb import (
    OperationError,
    OperationValidationError,
    plan_archive,
    plan_create,
    plan_move,
    plan_promote,
    plan_reverify,
    plan_supersede,
    plan_update,
    validate_bundle,
)
from portable_kb.changes import ConcurrentChangeError
from portable_kb.parsing import parse_concept

TIMESTAMP = "2026-08-13T03:00:00Z"
REVIEWER = "human:reviewer-42"


def test_create_is_reviewable_and_applies_explicitly(bundle: Path) -> None:
    change_set = plan_create(
        bundle,
        "inbox/new-question.md",
        item_type="question",
        title="Does planned creation preserve safety",
        description="A test candidate confirms that creation is validated before files are explicitly applied.",
        actor="openai-codex/gpt-5",
        method="agent-generated",
        timestamp=TIMESTAMP,
        body=(
            "# Does planned creation preserve safety\n\n"
            "## Question\n\nDoes the plan validate?[^operation]\n\n"
            "## Why it matters\n\nUnsafe writes would weaken review.\n\n"
            "## Known facts\n\nThe operation plans in a temporary tree.\n\n"
            "## Resolution criteria\n\nThe applied bundle validates.\n\n"
            "## Outcome\n\nPending.\n\n"
            "[^operation]: The lifecycle operation contract.\n"
        ),
        sources=[{"id": "operation", "resource": "urn:core-kb:test:operation"}],
        confidence={"level": "high", "basis": "The behavior is directly exercised by this test."},
        tags=["test-candidate"],
        sensitivity="internal",
        as_of="2026-08-12",
    )
    assert not (bundle / "inbox/new-question.md").exists()
    assert change_set.validation.profile_passes
    assert change_set.operation == "create"
    change_set.apply()
    result = validate_bundle(bundle, as_of="2026-08-12")
    assert result.profile_passes
    parsed = parse_concept(bundle / "inbox/new-question.md", bundle).item
    assert parsed is not None and parsed.id is not None


def test_create_preserves_authored_indexes_and_labels_new_decision_index(
    bundle: Path,
) -> None:
    original_root = (bundle / "index.md").read_text(encoding="utf-8")
    original_concepts = (bundle / "curated/concepts/index.md").read_text(encoding="utf-8")

    change_set = plan_create(
        bundle,
        "inbox/discount-approval.md",
        item_type="decision",
        title="Discount approval",
        description="Records the draft approval threshold for customer discounts.",
        actor="anthropic/claude-code",
        method="agent-generated",
        timestamp=TIMESTAMP,
        body=(
            "# Discount approval\n\n"
            "## Decision\n\nDiscounts above the threshold require approval.[^report]\n\n"
            "## Context\n\nA participant reported the meeting outcome.\n\n"
            "[^report]: Participant report captured in the authorized conversation.\n"
        ),
        sources=[{"id": "report", "resource": "urn:pkb:conversation:test-report"}],
        confidence={
            "level": "medium",
            "basis": "A participant reported the decision, but no meeting record was reviewed.",
        },
        sensitivity="internal",
        as_of="2026-08-13",
    )

    changed = {change.relative_path: change.after for change in change_set.changes}
    assert set(changed) == {
        "inbox/discount-approval.md",
        "inbox/index.md",
        "index.md",
        "log.md",
    }
    assert "This bundle is the governed, portable knowledge layer" in changed["index.md"]
    assert original_root.split("## Knowledge", 1)[0] in changed["index.md"]
    assert changed["inbox/index.md"] is not None
    assert "## Decisions" in changed["inbox/index.md"]
    assert "## Concepts" not in changed["inbox/index.md"]
    assert (bundle / "curated/concepts/index.md").read_text(encoding="utf-8") == original_concepts


def test_change_set_detects_concurrent_edit(bundle: Path) -> None:
    change_set = plan_move(
        bundle,
        "curated/concepts/material-change.md",
        "curated/concepts/material-updates.md",
        timestamp=TIMESTAMP,
        as_of="2026-08-12",
    )
    log = bundle / "log.md"
    log.write_text(log.read_text(encoding="utf-8") + "\nConcurrent edit.\n", encoding="utf-8")
    with pytest.raises(ConcurrentChangeError):
        change_set.apply()


def test_move_preserves_id_and_repairs_links(bundle: Path) -> None:
    source = bundle / "curated/concepts/immutable-knowledge-identity.md"
    original = parse_concept(source, bundle).item
    assert original is not None
    change_set = plan_move(
        bundle,
        "curated/concepts/immutable-knowledge-identity.md",
        "curated/concepts/stable-knowledge-identity.md",
        timestamp=TIMESTAMP,
        as_of="2026-08-12",
    )
    change_set.apply()
    destination = bundle / "curated/concepts/stable-knowledge-identity.md"
    moved = parse_concept(destination, bundle).item
    assert moved is not None and moved.id == original.id
    assert not source.exists()
    procedure = (bundle / "procedures/move-knowledge-item.md").read_text(encoding="utf-8")
    assert "stable-knowledge-identity.md" in procedure
    assert validate_bundle(bundle, as_of="2026-08-12").profile_passes


def test_material_update_preserves_unknown_fields_and_clears_verification(
    valid_examples: Path,
) -> None:
    path = valid_examples / "procedure-review-stale-knowledge.md"
    text = path.read_text(encoding="utf-8").replace("tags:\n", "x-owner-note: preserve-me\ntags:\n")
    path.write_text(text, encoding="utf-8")
    original = parse_concept(path, valid_examples).item
    assert original is not None
    change_set = plan_update(
        valid_examples,
        path.name,
        actor="openai-codex/gpt-5",
        method="agent-generated",
        timestamp=TIMESTAMP,
        metadata_updates={
            "confidence": {
                "level": "high",
                "basis": "The revised procedure remains grounded in its existing sources.",
            },
            "sources": [{"id": "design", "resource": "urn:core-kb:test:update"}],
        },
        body=original.body
        + "\nThe material revision is explicit.[^design]\n\n[^design]: Update design.\n",
        as_of="2026-08-12",
    )
    change_set.apply()
    updated = parse_concept(path, valid_examples).item
    assert updated is not None
    assert updated.id == original.id
    assert updated.status == "draft"
    assert "verified" not in updated.metadata
    assert updated.metadata["x-owner-note"] == "preserve-me"


def test_promotion_requires_configured_reviewer(bundle: Path) -> None:
    with pytest.raises(OperationError, match="not authorized"):
        plan_promote(
            bundle,
            "decisions/pin-okf-v02.md",
            reviewer=REVIEWER,
            timestamp=TIMESTAMP,
            verification_scope="Reviewed the final decision against its pinned source.",
            as_of="2026-08-13",
        )
    authorize(bundle, "decision", REVIEWER)
    change_set = plan_promote(
        bundle,
        "decisions/pin-okf-v02.md",
        reviewer=REVIEWER,
        timestamp=TIMESTAMP,
        verification_scope="Reviewed the final decision against its pinned source.",
        valid_from="2026-08-13",
        as_of="2026-08-13",
    )
    change_set.apply()
    promoted = parse_concept(bundle / "decisions/pin-okf-v02.md", bundle).item
    assert promoted is not None and promoted.status == "stable"
    assert promoted.metadata["verified"][0]["by"] == REVIEWER
    assert f"<!-- core-kb-verification: {REVIEWER} at {TIMESTAMP} -->" in promoted.body
    assert "Reviewed the final decision against its pinned source." in promoted.body


def test_reverify_replaces_snapshot_verification(bundle: Path) -> None:
    authorize(bundle, "procedure", REVIEWER)
    promote = plan_promote(
        bundle,
        "procedures/review-stale-knowledge.md",
        reviewer=REVIEWER,
        timestamp=TIMESTAMP,
        verification_scope="Reviewed the procedure steps against the lifecycle design.",
        as_of="2026-08-13",
    )
    promote.apply()
    reverify = plan_reverify(
        bundle,
        "procedures/review-stale-knowledge.md",
        reviewer=REVIEWER,
        timestamp="2026-09-01T03:00:00Z",
        verification_scope="Rechecked all procedure steps and freshness requirements.",
        stale_after="2027-01-01",
        as_of="2026-09-01",
    )
    reverify.apply()
    item = parse_concept(bundle / "procedures/review-stale-knowledge.md", bundle).item
    assert item is not None
    assert item.metadata["verified"] == [{"by": REVIEWER, "at": "2026-09-01T03:00:00Z"}]


def test_supersession_updates_both_sides_atomically(bundle: Path) -> None:
    authorize(bundle, "decision", REVIEWER)
    first = plan_promote(
        bundle,
        "decisions/pin-okf-v02.md",
        reviewer=REVIEWER,
        timestamp=TIMESTAMP,
        verification_scope="Reviewed the decision against the pinned upstream specification.",
        as_of="2026-08-13",
    )
    first.apply()
    replacement = plan_create(
        bundle,
        "decisions/pin-okf-v02-revision.md",
        item_type="decision",
        title="Pin the reviewed OKF v0.2 revision",
        description="A replacement test decision pins the reviewed upstream revision through reciprocal supersession.",
        actor="openai-codex/gpt-5",
        method="agent-generated",
        timestamp="2026-08-14T03:00:00Z",
        body=(
            "# Pin the reviewed OKF v0.2 revision\n\n"
            "## Decision\n\nUse the reviewed revision.[^spec]\n\n"
            "## Context\n\nThe prior test decision is replaced.\n\n"
            "## Options considered\n\nKeep or replace.\n\n"
            "## Rationale\n\nThis exercises supersession.\n\n"
            "## Consequences\n\nBoth identities remain.\n\n"
            "## Review triggers\n\nA new upstream release.\n\n"
            "[^spec]: Synthetic specification source.\n"
        ),
        sources=[{"id": "spec", "resource": "urn:core-kb:test:spec"}],
        confidence={
            "level": "high",
            "basis": "The synthetic source exists only to exercise lifecycle behavior.",
        },
        as_of="2026-08-14",
    )
    replacement.apply()
    supersede = plan_supersede(
        bundle,
        "decisions/pin-okf-v02-revision.md",
        ["decisions/pin-okf-v02.md"],
        reviewer=REVIEWER,
        operator=REVIEWER,
        timestamp="2026-08-15T03:00:00Z",
        reason="The test replacement has the narrower reviewed scope.",
        verification_scope="Reviewed the replacement and predecessor mapping together.",
        as_of="2026-08-15",
    )
    supersede.apply()
    old = parse_concept(bundle / "decisions/pin-okf-v02.md", bundle).item
    new = parse_concept(bundle / "decisions/pin-okf-v02-revision.md", bundle).item
    assert old is not None and new is not None
    assert old.status == "deprecated" and new.status == "stable"
    assert old.id in new.metadata["supersedes"]
    assert new.id in old.metadata["superseded_by"]
    assert validate_bundle(bundle, as_of="2026-08-15").profile_passes


def test_archive_abandoned_draft_question(bundle: Path) -> None:
    change_set = plan_archive(
        bundle,
        "questions/publish-project-source-identifiers.md",
        operator="openai-codex/gpt-5",
        timestamp=TIMESTAMP,
        reason="The synthetic test abandons this draft question after preserving its history.",
        as_of="2026-08-13",
    )
    change_set.apply()
    archived = bundle / "archive/questions/publish-project-source-identifiers.md"
    item = parse_concept(archived, bundle).item
    assert item is not None and item.status == "draft"
    assert item.metadata["archived"]["reason"].startswith("The synthetic test")
    assert validate_bundle(bundle, as_of="2026-08-13").profile_passes


def test_operation_preconditions_reject_unsafe_inputs(bundle: Path) -> None:
    with pytest.raises(OperationError, match="Unsafe or reserved"):
        plan_move(bundle, "index.md", "elsewhere.md", timestamp=TIMESTAMP)
    with pytest.raises(OperationError, match="strict UTC"):
        plan_move(
            bundle,
            "curated/concepts/material-change.md",
            "curated/concepts/material-updates.md",
            timestamp="2026-08-13T03:00:00-06:00",
        )
    with pytest.raises(OperationError, match="verification_scope"):
        plan_promote(
            bundle,
            "decisions/pin-okf-v02.md",
            reviewer=REVIEWER,
            timestamp=TIMESTAMP,
            verification_scope="vague",
            as_of="2026-08-13",
        )
    with pytest.raises(OperationError, match="Only a draft"):
        authorize(bundle, "decision", REVIEWER)
        promoted = plan_promote(
            bundle,
            "decisions/pin-okf-v02.md",
            reviewer=REVIEWER,
            timestamp=TIMESTAMP,
            verification_scope="Reviewed the final decision against its pinned source.",
            as_of="2026-08-13",
        )
        promoted.apply()
        plan_promote(
            bundle,
            "decisions/pin-okf-v02.md",
            reviewer=REVIEWER,
            timestamp="2026-08-14T03:00:00Z",
            verification_scope="Reviewed the final decision against its pinned source.",
            as_of="2026-08-14",
        )


def test_sensitivity_lowering_needs_explicit_human_approval(bundle: Path) -> None:
    with pytest.raises(OperationError, match="Lowering sensitivity"):
        plan_update(
            bundle,
            "curated/concepts/material-change.md",
            actor="openai-codex/gpt-5",
            method="agent-generated",
            timestamp=TIMESTAMP,
            metadata_updates={"sensitivity": "public"},
            as_of="2026-08-13",
        )
    with pytest.raises(OperationError, match="Lowering sensitivity"):
        plan_update(
            bundle,
            "curated/concepts/material-change.md",
            actor="human:reviewer-42",
            method="human-authored",
            timestamp=TIMESTAMP,
            metadata_updates={"sensitivity": "public"},
            as_of="2026-08-13",
        )
    approved = plan_update(
        bundle,
        "curated/concepts/material-change.md",
        actor="human:reviewer-42",
        method="human-authored",
        timestamp=TIMESTAMP,
        metadata_updates={"sensitivity": "public"},
        approve_sensitivity_lowering=True,
        as_of="2026-08-13",
    )
    assert approved.validation.profile_passes


def test_move_last_item_regenerates_empty_source_index(bundle: Path) -> None:
    change_set = plan_move(
        bundle,
        "sources/okf-v02.md",
        "curated/concepts/okf-v02-summary.md",
        timestamp=TIMESTAMP,
        as_of="2026-08-13",
    )
    source_index = next(
        change.after for change in change_set.changes if change.relative_path == "sources/index.md"
    )
    assert source_index is not None
    assert "No current knowledge is indexed in this scope." in source_index
    assert "okf-v02.md" not in source_index
    change_set.apply()
    assert validate_bundle(bundle, as_of="2026-08-13").profile_passes


def test_operations_refuse_an_invalid_base_bundle(bundle: Path) -> None:
    external = bundle.parent / "external.md"
    external.write_text("outside\n", encoding="utf-8")
    link = bundle / "inbox/external.md"
    link.parent.mkdir()
    link.symlink_to(external)
    with pytest.raises(OperationValidationError) as failure:
        plan_move(
            bundle,
            "curated/concepts/material-change.md",
            "curated/concepts/material-updates.md",
            timestamp=TIMESTAMP,
            as_of="2026-08-13",
        )
    assert "KB-E007" in {finding.code for finding in failure.value.report.findings}
