from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from portable_kb.authoring import (
    ConfidenceLevel,
    GenerationMethod,
    KnowledgeType,
    Sensitivity,
    body_template,
    plan_knowledge_create,
    plan_knowledge_update,
    save_knowledge_create,
    save_knowledge_update,
    slugify,
)
from portable_kb.brains import (
    BrainError,
    clean_repository_head,
    commit_authoring_changes,
    init_brain,
    load_catalog,
    save_catalog,
    sync_brain,
)
from portable_kb.operations import OperationError
from portable_kb.parsing import parse_concept
from portable_kb.settings import Settings
from portable_kb.validation import validate_bundle


def test_plan_knowledge_create_is_reviewable_then_applies_to_authoring_repo(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "business"
    init_brain(
        str(repository),
        "Business Knowledge",
        "business",
        settings,
        as_of="2026-08-13",
    )
    body = body_template(KnowledgeType.CONCEPT, "Customer activation").replace(
        "<!-- Replace with bounded, sourced content. -->",
        "Activation is the point at which a customer first realizes the product's core value.",
        1,
    )

    plan = plan_knowledge_create(
        settings,
        item_type=KnowledgeType.CONCEPT,
        title="Customer activation",
        description="Defines the first customer experience of the product's core value.",
        actor="human:marvin",
        method=GenerationMethod.HUMAN_AUTHORED,
        body=body,
        tags=["customer-success"],
        sensitivity=Sensitivity.INTERNAL,
        timestamp="2026-08-13T15:00:00Z",
        as_of="2026-08-13",
    )

    target = repository / "knowledge/inbox/customer-activation.md"
    assert not target.exists()
    assert plan.change_set.validation.profile_passes
    assert {change.relative_path for change in plan.change_set.changes} >= {
        "inbox/customer-activation.md",
        "inbox/index.md",
        "index.md",
        "log.md",
    }
    result = save_knowledge_create(settings, plan, as_of="2026-08-13")

    item = parse_concept(target, repository / "knowledge").item
    assert item is not None
    assert item.status == "draft"
    assert item.metadata["generated"] == {
        "by": "human:marvin",
        "at": "2026-08-13T15:00:00Z",
        "method": "human-authored",
    }
    assert validate_bundle(repository / "knowledge", as_of="2026-08-13").profile_passes
    assert result.commit == load_catalog(settings).get("business").commit
    assert (
        settings.data_dir / "brains/business/knowledge/inbox/customer-activation.md"
    ).is_file()


def test_plan_agent_generated_draft_requires_and_preserves_provenance(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "agent-brain"
    init_brain(
        str(repository),
        "Agent Brain",
        "agent-brain",
        settings,
        as_of="2026-08-13",
    )
    body = """# Onboarding evidence

## Summary

The source describes a bounded onboarding practice.[^guide]

## Key claims

The source recommends an explicit activation checkpoint.[^guide]

## Limitations

Only the cited guide was reviewed.

## Relevance

The practice may inform a future internal procedure.

[^guide]: Onboarding guide.
"""
    plan = plan_knowledge_create(
        settings,
        item_type=KnowledgeType.SOURCE_SUMMARY,
        title="Onboarding evidence",
        description="Summarizes one external guide about customer onboarding checkpoints.",
        actor="anthropic/claude-code",
        method=GenerationMethod.AGENT_GENERATED,
        body=body,
        sources=[
            {
                "id": "guide",
                "resource": "https://example.com/onboarding",
                "title": "Onboarding guide",
            }
        ],
        confidence_level=ConfidenceLevel.MEDIUM,
        confidence_basis="The cited guide was available, but no independent source was compared.",
        timestamp="2026-08-13T15:00:00Z",
        as_of="2026-08-13",
    )
    plan.change_set.apply()

    item = parse_concept(
        repository / "knowledge/inbox/onboarding-evidence.md",
        repository / "knowledge",
    ).item
    assert item is not None
    assert item.metadata["sources"][0]["id"] == "guide"
    assert item.metadata["confidence"]["level"] == "medium"


def test_plan_and_save_update_preserves_identity_and_refreshes_active_brain(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "update-brain"
    init_brain(
        str(repository),
        "Update Brain",
        "update-brain",
        settings,
        as_of="2026-08-13",
    )
    created = plan_knowledge_create(
        settings,
        item_type=KnowledgeType.CONCEPT,
        title="Customer activation",
        description="Defines the first customer realization of the product's core value.",
        actor="human:marvin",
        method=GenerationMethod.HUMAN_AUTHORED,
        body="# Customer activation\n\n## Definition\n\nThe first realization of value.\n",
        timestamp="2026-08-13T15:00:00Z",
        as_of="2026-08-13",
    )
    save_knowledge_create(settings, created, as_of="2026-08-13")
    original_path = repository / "knowledge/inbox/customer-activation.md"
    original = parse_concept(original_path, repository / "knowledge").item
    assert original is not None

    update = plan_knowledge_update(
        settings,
        original.id or "",
        actor="openai/codex",
        method=GenerationMethod.AGENT_GENERATED,
        body=(
            "# Customer activation\n\n## Definition\n\n"
            "The first verified customer realization of product value.[^evidence]\n\n"
            "[^evidence]: Customer interview summary.\n"
        ),
        metadata_updates={
            "description": "Defines the first evidenced customer realization of product value.",
            "sources": [
                {
                    "id": "evidence",
                    "resource": "https://example.com/customer-interviews",
                    "title": "Customer interview summary",
                }
            ],
            "confidence": {
                "level": "medium",
                "basis": "The source supports the definition, but the sample is still limited.",
            },
            "x-owner-note": "preserve-on-future-updates",
        },
        timestamp="2026-08-13T16:00:00Z",
        as_of="2026-08-13",
    )

    assert update.item.id == original.id
    assert update.as_dict(applied=False)["applied"] is False
    assert "verified" not in update.item.metadata
    stable_item = replace(
        update.item,
        metadata={
            **update.item.metadata,
            "type": "policy",
            "status": "stable",
            "verified": [{"by": "human:marvin", "at": "2026-08-13T15:30:00Z"}],
        },
    )
    stable_payload = replace(update, item=stable_item).as_dict(applied=False)
    assert stable_payload["resulting_status"] == "draft"
    assert stable_payload["verification_invalidated"] is True
    result = save_knowledge_update(settings, update, as_of="2026-08-13")

    revised = parse_concept(original_path, repository / "knowledge").item
    assert revised is not None
    assert revised.id == original.id
    assert revised.metadata["created_at"] == original.metadata["created_at"]
    assert revised.metadata["generated"]["by"] == "openai/codex"
    assert revised.metadata["x-owner-note"] == "preserve-on-future-updates"
    assert result.commit == load_catalog(settings).get("update-brain").commit
    installed = (
        settings.data_dir / "brains/update-brain/knowledge/inbox/customer-activation.md"
    )
    assert "first verified customer realization" in installed.read_text(encoding="utf-8")


def test_plan_update_rejects_missing_change_and_unsafe_reference(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    init_brain(
        str(tmp_path / "brain"),
        "Guarded Update",
        "guarded-update",
        settings,
        as_of="2026-08-13",
    )
    with pytest.raises(ValueError, match="requires a body"):
        plan_knowledge_update(
            settings,
            "inbox/missing.md",
            actor="openai/codex",
            method=GenerationMethod.AGENT_GENERATED,
            timestamp="2026-08-13T16:00:00Z",
            as_of="2026-08-13",
        )
    with pytest.raises(ValueError, match="lifecycle-controlled fields: status"):
        plan_knowledge_update(
            settings,
            "inbox/missing.md",
            actor="openai/codex",
            method=GenerationMethod.AGENT_GENERATED,
            metadata_updates={"status": "stable"},
            timestamp="2026-08-13T16:00:00Z",
            as_of="2026-08-13",
        )
    with pytest.raises(OperationError, match="unsafe"):
        plan_knowledge_update(
            settings,
            "../escape.md",
            actor="human:marvin",
            method=GenerationMethod.HUMAN_AUTHORED,
            body="# Escape\n\nShould not resolve.\n",
            timestamp="2026-08-13T16:00:00Z",
            as_of="2026-08-13",
        )
    for reference, message in (
        ("", "non-empty ID"),
        ("inbox/missing.md", "path was not found"),
        ("urn:uuid:00000000-0000-4000-8000-000000000000", "ID was not found"),
    ):
        with pytest.raises(OperationError, match=message):
            plan_knowledge_update(
                settings,
                reference,
                actor="human:marvin",
                method=GenerationMethod.HUMAN_AUTHORED,
                body="# Missing\n\nShould not resolve.\n",
                timestamp="2026-08-13T16:00:00Z",
                as_of="2026-08-13",
            )


def test_authoring_helpers_generate_safe_defaults() -> None:
    assert slugify("  Customer Success / Activation! ") == "customer-success-activation"
    body = body_template(KnowledgeType.PROCEDURE, "Review knowledge")
    assert body.startswith("# Review knowledge\n")
    assert "## Preconditions" in body
    assert "## Rollback" in body


def test_plan_knowledge_create_explains_unfinished_local_changes(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "business"
    init_brain(
        str(repository),
        "Business Knowledge",
        "business",
        settings,
        as_of="2026-08-13",
    )
    (repository / "unfinished.txt").write_text("unfinished\n", encoding="utf-8")

    with pytest.raises(BrainError, match="another unfinished local change"):
        plan_knowledge_create(
            settings,
            item_type=KnowledgeType.CONCEPT,
            title="Blocked draft",
            description="Explains why new drafts wait for unfinished local work.",
            actor="human:marvin",
            method=GenerationMethod.HUMAN_AUTHORED,
            body="# Blocked draft\n\n## Definition\n\nThis should not be created.\n",
            timestamp="2026-08-13T15:00:00Z",
            as_of="2026-08-13",
        )


def test_save_knowledge_updates_published_brain_without_implicitly_sharing(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "business"
    initialized, catalog, _report = init_brain(
        str(repository),
        "Business Knowledge",
        "business",
        settings,
        as_of="2026-08-13",
    )
    remote = tmp_path / "organization.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(remote))
    _git(repository, "remote", "add", "origin", str(remote))
    _git(repository, "push", "--quiet", "--set-upstream", "origin", "main")
    checkout = initialized.brain.checkout_path(settings)
    _git(checkout, "remote", "set-url", "origin", str(remote))
    published = replace(initialized.brain, source=str(remote))
    save_catalog(catalog.updating(published), settings)

    plan = plan_knowledge_create(
        settings,
        item_type=KnowledgeType.CONCEPT,
        title="Local customer signal",
        description="Defines a local draft that is not implicitly shared upstream.",
        actor="human:marvin",
        method=GenerationMethod.HUMAN_AUTHORED,
        body="# Local customer signal\n\n## Definition\n\nA bounded local signal.\n",
        timestamp="2026-08-13T15:00:00Z",
        as_of="2026-08-13",
    )
    result = save_knowledge_create(settings, plan, as_of="2026-08-13")

    assert result.commit != initialized.brain.commit
    assert _git_output(remote, "rev-parse", "refs/heads/main").strip() == initialized.brain.commit
    assert _git_output(checkout, "rev-parse", "HEAD").strip() == result.commit
    synced = sync_brain(settings, "business", as_of="2026-08-13")
    assert synced["changed"] is False
    assert synced["source_behind"] is True


def test_save_rejects_a_plan_when_the_brain_changes_before_confirmation(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "business"
    init_brain(
        str(repository),
        "Business Knowledge",
        "business",
        settings,
        as_of="2026-08-13",
    )
    plan = plan_knowledge_create(
        settings,
        item_type=KnowledgeType.CONCEPT,
        title="Concurrent draft",
        description="Exercises the optimistic save guard for concurrent local versions.",
        actor="human:marvin",
        method=GenerationMethod.HUMAN_AUTHORED,
        body="# Concurrent draft\n\n## Definition\n\nA guarded draft.\n",
        timestamp="2026-08-13T15:00:00Z",
        as_of="2026-08-13",
    )
    _git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "Concurrent version",
    )

    with pytest.raises(ValueError, match="changed while this knowledge was being prepared"):
        save_knowledge_create(settings, plan, as_of="2026-08-13")

    saved_plan = plan_knowledge_create(
        settings,
        item_type=KnowledgeType.CONCEPT,
        title="Update concurrency",
        description="Provides a target for the material update concurrency guard.",
        actor="human:marvin",
        method=GenerationMethod.HUMAN_AUTHORED,
        body="# Update concurrency\n\n## Definition\n\nA guarded update target.\n",
        timestamp="2026-08-13T15:30:00Z",
        as_of="2026-08-13",
    )
    saved = save_knowledge_create(settings, saved_plan, as_of="2026-08-13")
    update_plan = plan_knowledge_update(
        settings,
        "inbox/update-concurrency.md",
        actor="human:marvin",
        method=GenerationMethod.HUMAN_AUTHORED,
        body="# Update concurrency\n\n## Definition\n\nA revised guarded target.\n",
        timestamp="2026-08-13T16:00:00Z",
        as_of="2026-08-13",
    )
    assert update_plan.base_commit == saved.commit
    _git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "Concurrent update version",
    )
    with pytest.raises(ValueError, match="changed while this update was being prepared"):
        save_knowledge_update(settings, update_plan, as_of="2026-08-13")

    current = clean_repository_head(repository)
    with pytest.raises(BrainError, match="contains no files"):
        commit_authoring_changes(
            repository,
            (),
            expected_head=current,
            message="Empty change",
        )


def _git(repository: Path, *arguments: str) -> None:
    _git_output(repository, *arguments)


def _git_output(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
