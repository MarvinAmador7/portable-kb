"""Governed authoring adapters over the deterministic lifecycle planners."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .brains import BrainManifest, InstalledBrain, authoring_repository
from .changes import ChangeSet
from .operations import plan_create
from .settings import Settings


class KnowledgeType(StrEnum):
    """Knowledge types supported by the core profile."""

    CONCEPT = "concept"
    DECISION = "decision"
    PROCEDURE = "procedure"
    POLICY = "policy"
    SYSTEM = "system"
    SOURCE_SUMMARY = "source-summary"
    QUESTION = "question"


class GenerationMethod(StrEnum):
    """Honest production-method labels supported by the profile."""

    HUMAN_AUTHORED = "human-authored"
    IMPORTED = "imported"
    TRANSFORMED = "transformed"
    AGENT_GENERATED = "agent-generated"
    CALCULATED = "calculated"


class Sensitivity(StrEnum):
    """Knowledge handling classifications."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ConfidenceLevel(StrEnum):
    """Producer confidence labels; never authority labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class KnowledgeCreatePlan:
    """A validated draft creation plan against a local authoring repository."""

    brain: InstalledBrain
    repository: Path
    manifest: BrainManifest
    relative_path: str
    change_set: ChangeSet

    def as_dict(self, *, applied: bool) -> dict[str, Any]:
        return {
            "brain": self.brain.slug,
            "repository": str(self.repository),
            "path": self.relative_path,
            "operation": self.change_set.operation,
            "applied": applied,
            "changes": [
                {"path": change.relative_path, "kind": change.kind}
                for change in self.change_set.changes
            ],
            "validation_warnings": [
                finding.as_dict() for finding in self.change_set.validation.warnings
            ],
        }


def plan_knowledge_create(
    settings: Settings,
    *,
    item_type: KnowledgeType,
    title: str,
    description: str,
    actor: str,
    method: GenerationMethod,
    body: str,
    relative_path: str | None = None,
    sources: Sequence[Mapping[str, Any]] | None = None,
    confidence_level: ConfidenceLevel | None = None,
    confidence_basis: str | None = None,
    tags: Sequence[str] | None = None,
    sensitivity: Sensitivity | None = None,
    timestamp: str | None = None,
    slug: str | None = None,
    as_of: str | None = None,
) -> KnowledgeCreatePlan:
    """Plan a new draft in a verified local authoring repository."""

    brain, repository, manifest = authoring_repository(settings, slug)
    path = relative_path or f"inbox/{slugify(title)}.md"
    confidence = None
    if confidence_level is not None or confidence_basis is not None:
        confidence = {
            "level": (confidence_level or ConfidenceLevel.MEDIUM).value,
            "basis": (confidence_basis or "").strip(),
        }
    change_set = plan_create(
        repository / manifest.bundle,
        path,
        item_type=item_type.value,
        title=title.strip(),
        description=description.strip(),
        actor=actor.strip(),
        method=method.value,
        timestamp=timestamp or utc_timestamp(),
        body=body,
        sources=sources,
        confidence=confidence,
        tags=tags,
        sensitivity=sensitivity.value if sensitivity is not None else None,
        as_of=as_of,
    )
    return KnowledgeCreatePlan(
        brain=brain,
        repository=repository,
        manifest=manifest,
        relative_path=path,
        change_set=change_set,
    )


def slugify(value: str) -> str:
    """Convert a title into a readable lowercase kebab-case filename stem."""

    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def utc_timestamp() -> str:
    """Return the current UTC time in the profile's strict second-resolution form."""

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def body_template(item_type: KnowledgeType, title: str) -> str:
    """Return an editable Markdown body skeleton for one knowledge type."""

    sections = {
        KnowledgeType.CONCEPT: ("Definition", "Context", "Examples", "Boundaries"),
        KnowledgeType.DECISION: (
            "Decision",
            "Context",
            "Options considered",
            "Rationale",
            "Consequences",
            "Review triggers",
        ),
        KnowledgeType.PROCEDURE: (
            "Purpose",
            "Preconditions",
            "Steps",
            "Verification",
            "Rollback",
            "Escalation",
            "Safety",
        ),
        KnowledgeType.POLICY: (
            "Policy",
            "Scope",
            "Requirements",
            "Exceptions",
            "Rationale",
            "Enforcement",
            "Review",
        ),
        KnowledgeType.SYSTEM: (
            "Purpose",
            "Boundaries",
            "Architecture",
            "Dependencies",
            "Interfaces",
            "Operations",
            "Risks",
        ),
        KnowledgeType.SOURCE_SUMMARY: (
            "Summary",
            "Key claims",
            "Limitations",
            "Relevance",
            "Follow-up",
        ),
        KnowledgeType.QUESTION: (
            "Question",
            "Why it matters",
            "Known facts",
            "Competing hypotheses",
            "Resolution criteria",
            "Outcome",
        ),
    }[item_type]
    lines = [f"# {title.strip()}", ""]
    for section in sections:
        lines.extend((f"## {section}", "", "<!-- Replace with bounded, sourced content. -->", ""))
    return "\n".join(lines).rstrip() + "\n"
