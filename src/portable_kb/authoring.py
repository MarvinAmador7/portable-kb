"""Governed authoring adapters over the deterministic lifecycle planners."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from .brains import (
    BrainManifest,
    InstalledBrain,
    authoring_repository,
    clean_repository_head,
    commit_authoring_changes,
    refresh_brain_from_authoring,
)
from .changes import ChangeSet
from .models import KnowledgeItem
from .operations import OperationError, plan_create, plan_update
from .parsing import RESERVED_NAMES, discover_concepts, parse_concept
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
    base_commit: str
    change_set: ChangeSet

    def as_dict(self, *, applied: bool) -> dict[str, Any]:
        return {
            "brain": self.brain.slug,
            "repository": str(self.repository),
            "path": self.relative_path,
            "operation": self.change_set.operation,
            "applied": applied,
            "saved_version": None,
            "active_brain_updated": False,
            "changes": [
                {"path": change.relative_path, "kind": change.kind}
                for change in self.change_set.changes
            ],
            "validation_warnings": [
                finding.as_dict() for finding in self.change_set.validation.warnings
            ],
        }


@dataclass(frozen=True, slots=True)
class KnowledgeCreateResult:
    """A locally saved draft that is immediately available to consumers."""

    plan: KnowledgeCreatePlan
    commit: str
    refresh: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a stable machine-readable save result."""

        payload = self.plan.as_dict(applied=True)
        payload["saved_version"] = self.commit
        payload["active_brain_updated"] = True
        payload["previous_version"] = self.refresh["previous_commit"]
        return payload


@dataclass(frozen=True, slots=True)
class KnowledgeUpdatePlan:
    """A validated material update plan against a local authoring repository."""

    brain: InstalledBrain
    repository: Path
    manifest: BrainManifest
    item: KnowledgeItem
    base_commit: str
    change_set: ChangeSet

    def as_dict(self, *, applied: bool) -> dict[str, Any]:
        """Return a stable machine-readable update plan."""

        resulting_status = self.item.status
        if self.item.status == "stable" and self.item.type in {
            "decision",
            "procedure",
            "policy",
        }:
            resulting_status = "draft"
        return {
            "brain": self.brain.slug,
            "repository": str(self.repository),
            "item_id": self.item.id,
            "path": self.item.relative_path,
            "title": self.item.metadata.get("title"),
            "operation": self.change_set.operation,
            "previous_status": self.item.status,
            "resulting_status": resulting_status,
            "verification_invalidated": "verified" in self.item.metadata,
            "applied": applied,
            "saved_version": None,
            "active_brain_updated": False,
            "changes": [
                {"path": change.relative_path, "kind": change.kind}
                for change in self.change_set.changes
            ],
            "validation_warnings": [
                finding.as_dict() for finding in self.change_set.validation.warnings
            ],
        }


@dataclass(frozen=True, slots=True)
class KnowledgeUpdateResult:
    """A locally saved material update available to brain consumers."""

    plan: KnowledgeUpdatePlan
    commit: str
    refresh: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a stable machine-readable save result."""

        payload = self.plan.as_dict(applied=True)
        payload["saved_version"] = self.commit
        payload["active_brain_updated"] = True
        payload["previous_version"] = self.refresh["previous_commit"]
        return payload


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
    base_commit = clean_repository_head(repository)
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
        base_commit=base_commit,
        change_set=change_set,
    )


def save_knowledge_create(
    settings: Settings,
    plan: KnowledgeCreatePlan,
    *,
    as_of: str | None = None,
) -> KnowledgeCreateResult:
    """Apply, locally version, and activate a validated draft in one action."""

    current = clean_repository_head(plan.repository)
    if current != plan.base_commit:
        raise ValueError("The brain changed while this knowledge was being prepared.")
    plan.change_set.apply()
    repository_paths = tuple(
        f"{plan.manifest.bundle}/{change.relative_path}"
        for change in plan.change_set.changes
    )
    title = " ".join(plan.relative_path.rsplit("/", 1)[-1].removesuffix(".md").split("-"))
    commit = commit_authoring_changes(
        plan.repository,
        repository_paths,
        expected_head=plan.base_commit,
        message=f"Add {title} draft",
    )
    refresh = refresh_brain_from_authoring(
        settings,
        plan.brain.slug,
        commit,
        as_of=as_of,
    )
    return KnowledgeCreateResult(plan=plan, commit=commit, refresh=refresh)


def plan_knowledge_update(
    settings: Settings,
    reference: str,
    *,
    actor: str,
    method: GenerationMethod,
    body: str | None = None,
    metadata_updates: Mapping[str, Any] | None = None,
    approve_sensitivity_lowering: bool = False,
    timestamp: str | None = None,
    slug: str | None = None,
    as_of: str | None = None,
) -> KnowledgeUpdatePlan:
    """Plan a material update by immutable ID or bundle-relative path."""

    if body is None and not metadata_updates:
        raise ValueError("Knowledge update requires a body or at least one metadata field.")
    lifecycle_fields = {
        "archived",
        "created_at",
        "generated",
        "id",
        "status",
        "superseded_by",
        "supersedes",
        "type",
        "updated_at",
        "verified",
    }
    blocked = sorted(lifecycle_fields.intersection(metadata_updates or {}))
    if blocked:
        raise ValueError(
            "Knowledge update cannot change lifecycle-controlled fields: " + ", ".join(blocked)
        )
    brain, repository, manifest = authoring_repository(settings, slug)
    base_commit = clean_repository_head(repository)
    bundle = repository / manifest.bundle
    item = _resolve_authoring_item(bundle, reference)
    change_set = plan_update(
        bundle,
        item.relative_path,
        actor=actor.strip(),
        method=method.value,
        timestamp=timestamp or utc_timestamp(),
        body=body,
        metadata_updates=metadata_updates,
        approve_sensitivity_lowering=approve_sensitivity_lowering,
        as_of=as_of,
    )
    return KnowledgeUpdatePlan(
        brain=brain,
        repository=repository,
        manifest=manifest,
        item=item,
        base_commit=base_commit,
        change_set=change_set,
    )


def save_knowledge_update(
    settings: Settings,
    plan: KnowledgeUpdatePlan,
    *,
    as_of: str | None = None,
) -> KnowledgeUpdateResult:
    """Apply, locally version, and activate a validated material update."""

    current = clean_repository_head(plan.repository)
    if current != plan.base_commit:
        raise ValueError("The brain changed while this update was being prepared.")
    plan.change_set.apply()
    repository_paths = tuple(
        f"{plan.manifest.bundle}/{change.relative_path}"
        for change in plan.change_set.changes
    )
    title = str(plan.item.metadata.get("title") or PurePosixPath(plan.item.relative_path).stem)
    commit = commit_authoring_changes(
        plan.repository,
        repository_paths,
        expected_head=plan.base_commit,
        message=f"Update {title}",
    )
    refresh = refresh_brain_from_authoring(
        settings,
        plan.brain.slug,
        commit,
        as_of=as_of,
    )
    return KnowledgeUpdateResult(plan=plan, commit=commit, refresh=refresh)


def _resolve_authoring_item(bundle: Path, reference: str) -> KnowledgeItem:
    """Resolve one editable item by immutable ID or safe bundle path."""

    normalized = reference.strip()
    if not normalized or "\x00" in reference:
        raise OperationError("Knowledge item reference must be a non-empty ID or bundle path.")
    concepts = discover_concepts(bundle)
    if normalized.startswith("urn:uuid:"):
        for path in concepts:
            parsed = parse_concept(path, bundle)
            if parsed.item is not None and parsed.item.id == normalized:
                return parsed.item
        raise OperationError(f"Knowledge item ID was not found in the selected brain: {normalized}")

    relative_text = normalized.removeprefix("knowledge/")
    relative = PurePosixPath(relative_text)
    if (
        not relative_text
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix != ".md"
        or relative.name in RESERVED_NAMES
    ):
        raise OperationError("Knowledge item path is unsafe, reserved, or not a Markdown concept.")
    path = bundle.joinpath(*relative.parts)
    if path not in concepts or path.is_symlink() or not path.is_file():
        raise OperationError(
            f"Knowledge item path was not found in the selected brain: {relative_text}"
        )
    parsed = parse_concept(path, bundle)
    if parsed.item is None:
        raise OperationError("Knowledge item could not be mapped to an editable concept.")
    return parsed.item


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
