from __future__ import annotations

from pathlib import Path

from portable_kb.authoring import (
    ConfidenceLevel,
    GenerationMethod,
    KnowledgeType,
    Sensitivity,
    body_template,
    plan_knowledge_create,
    slugify,
)
from portable_kb.brains import init_brain
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
    plan.change_set.apply()

    item = parse_concept(target, repository / "knowledge").item
    assert item is not None
    assert item.status == "draft"
    assert item.metadata["generated"] == {
        "by": "human:marvin",
        "at": "2026-08-13T15:00:00Z",
        "method": "human-authored",
    }
    assert validate_bundle(repository / "knowledge", as_of="2026-08-13").profile_passes


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


def test_authoring_helpers_generate_safe_defaults() -> None:
    assert slugify("  Customer Success / Activation! ") == "customer-success-activation"
    body = body_template(KnowledgeType.PROCEDURE, "Review knowledge")
    assert body.startswith("# Review knowledge\n")
    assert "## Preconditions" in body
    assert "## Rollback" in body
