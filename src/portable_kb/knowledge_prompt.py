"""Inline prompts for planning governed draft knowledge."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .authoring import (
    ConfidenceLevel,
    GenerationMethod,
    KnowledgeType,
    Sensitivity,
    body_template,
    slugify,
)
from .setup_prompt import PromptBackend, PromptChoice, QuestionaryBackend


@dataclass(frozen=True, slots=True)
class KnowledgeCreateInputs:
    """Interactive inputs for one governed draft creation plan."""

    item_type: KnowledgeType
    title: str
    description: str
    actor: str
    method: GenerationMethod
    body: str
    relative_path: str
    sources: tuple[Mapping[str, Any], ...]
    confidence_level: ConfidenceLevel | None
    confidence_basis: str | None
    sensitivity: Sensitivity


def run_knowledge_create_prompts(
    *,
    backend: PromptBackend | None = None,
    write: Callable[[str], None] = print,
) -> KnowledgeCreateInputs | None:
    """Collect a complete draft candidate without applying filesystem changes."""

    prompts = backend or QuestionaryBackend()
    write("┌  portable-kb")
    write("│")
    write("◇  New knowledge draft")
    write("│  Draft only · validated before write · no automatic commit or push")
    try:
        raw_type = prompts.select(
            "Knowledge type",
            choices=tuple(
                PromptChoice(item_type.value.replace("-", " ").title(), item_type.value)
                for item_type in KnowledgeType
            ),
            default=KnowledgeType.CONCEPT.value,
        )
        if raw_type is None:
            return _cancel(write)
        item_type = KnowledgeType(raw_type)
        title = prompts.text("Title", default="")
        if title is None:
            return _cancel(write)
        title = title.strip()
        description = prompts.text("One-sentence description", default="")
        if description is None:
            return _cancel(write)
        description = description.strip()

        raw_method = prompts.select(
            "How was the substantive content produced?",
            choices=(
                PromptChoice("Human authored", GenerationMethod.HUMAN_AUTHORED.value),
                PromptChoice("Agent generated", GenerationMethod.AGENT_GENERATED.value),
                PromptChoice("Transformed from sources", GenerationMethod.TRANSFORMED.value),
                PromptChoice("Imported", GenerationMethod.IMPORTED.value),
                PromptChoice("Calculated", GenerationMethod.CALCULATED.value),
            ),
            default=GenerationMethod.HUMAN_AUTHORED.value,
        )
        if raw_method is None:
            return _cancel(write)
        method = GenerationMethod(raw_method)
        actor_default = "human:author" if method is GenerationMethod.HUMAN_AUTHORED else "agent/model"
        actor = prompts.text("Producer identity", default=actor_default)
        if actor is None:
            return _cancel(write)

        sources: list[Mapping[str, Any]] = []
        source_required = (
            method is not GenerationMethod.HUMAN_AUTHORED
            or item_type is KnowledgeType.SOURCE_SUMMARY
        )
        add_source = source_required or prompts.confirm("Add a source?", default=False) is True
        while add_source:
            source_id = prompts.text("Source ID", default=f"source-{len(sources) + 1}")
            if source_id is None:
                return _cancel(write)
            resource = prompts.text("Source resource or URL", default="")
            if resource is None:
                return _cancel(write)
            source_title = prompts.text("Source title", default="")
            if source_title is None:
                return _cancel(write)
            sources.append(
                {
                    "id": source_id.strip(),
                    "resource": resource.strip(),
                    "title": source_title.strip(),
                }
            )
            add_source = prompts.confirm("Add another source?", default=False) is True

        confidence_level = None
        confidence_basis = None
        if method is GenerationMethod.AGENT_GENERATED:
            raw_confidence = prompts.select(
                "Producer confidence",
                choices=tuple(
                    PromptChoice(level.value.title(), level.value) for level in ConfidenceLevel
                ),
                default=ConfidenceLevel.MEDIUM.value,
            )
            if raw_confidence is None:
                return _cancel(write)
            confidence_level = ConfidenceLevel(raw_confidence)
            confidence_basis = prompts.text("Plain-language confidence basis", default="")
            if confidence_basis is None:
                return _cancel(write)
            confidence_basis = confidence_basis.strip()

        raw_sensitivity = prompts.select(
            "Sensitivity",
            choices=tuple(
                PromptChoice(value.value.title(), value.value) for value in Sensitivity
            ),
            default=Sensitivity.INTERNAL.value,
        )
        if raw_sensitivity is None:
            return _cancel(write)
        sensitivity = Sensitivity(raw_sensitivity)
        template = body_template(item_type, title)
        body = prompts.editor("Edit Markdown body", default=template)
        if body is None:
            return _cancel(write)
        if body.strip() == template.strip():
            write("│")
            write("└  Draft not created · replace at least one template placeholder")
            return None
        relative_path = prompts.text("Knowledge path", default=f"inbox/{slugify(title)}.md")
        if relative_path is None:
            return _cancel(write)
    except (EOFError, KeyboardInterrupt):
        return _cancel(write)

    return KnowledgeCreateInputs(
        item_type=item_type,
        title=title,
        description=description,
        actor=actor.strip(),
        method=method,
        body=body,
        relative_path=relative_path.strip(),
        sources=tuple(sources),
        confidence_level=confidence_level,
        confidence_basis=confidence_basis,
        sensitivity=sensitivity,
    )


def confirm_knowledge_apply(
    *,
    backend: PromptBackend | None = None,
    write: Callable[[str], None] = print,
) -> bool:
    """Request explicit confirmation after a validated change preview."""

    prompts = backend or QuestionaryBackend()
    try:
        confirmed = prompts.confirm("Apply this validated draft?", default=True)
    except (EOFError, KeyboardInterrupt):
        confirmed = False
    if confirmed is not True:
        write("└  Draft plan not applied")
        return False
    return True


def _cancel(write: Callable[[str], None]) -> None:
    write("│")
    write("└  Knowledge creation cancelled")
    return None
