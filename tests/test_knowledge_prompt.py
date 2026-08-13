from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from portable_kb.authoring import (
    ConfidenceLevel,
    GenerationMethod,
    KnowledgeType,
    Sensitivity,
    body_template,
)
from portable_kb.knowledge_prompt import (
    KnowledgeCreateInputs,
    confirm_knowledge_apply,
    run_knowledge_create_prompts,
)
from portable_kb.setup_prompt import PromptChoice


class FakeBackend:
    def __init__(
        self,
        *,
        texts: Sequence[str | None] = (),
        selections: Sequence[str | None] = (),
        confirmations: Sequence[bool | None] = (),
        edits: Sequence[str | None] = (),
    ) -> None:
        self.texts = deque(texts)
        self.selections = deque(selections)
        self.confirmations = deque(confirmations)
        self.edits = deque(edits)

    def text(self, message: str, *, default: str) -> str | None:
        return self.texts.popleft()

    def select(
        self,
        message: str,
        *,
        choices: Sequence[PromptChoice],
        default: str,
    ) -> str | None:
        assert choices
        return self.selections.popleft()

    def confirm(self, message: str, *, default: bool) -> bool | None:
        return self.confirmations.popleft()

    def editor(self, message: str, *, default: str) -> str | None:
        return self.edits.popleft()


def test_human_authored_prompt_collects_local_draft() -> None:
    body = body_template(KnowledgeType.CONCEPT, "Customer activation").replace(
        "<!-- Replace with bounded, sourced content. -->",
        "Activation is the first realization of product value.",
        1,
    )
    backend = FakeBackend(
        texts=[
            "Customer activation",
            "Defines when a customer first realizes meaningful product value.",
            "human:marvin",
            "inbox/customer-activation.md",
        ],
        selections=["concept", "human-authored", "internal"],
        confirmations=[False],
        edits=[body],
    )

    result = run_knowledge_create_prompts(backend=backend, write=lambda _: None)

    assert result == KnowledgeCreateInputs(
        item_type=KnowledgeType.CONCEPT,
        title="Customer activation",
        description="Defines when a customer first realizes meaningful product value.",
        actor="human:marvin",
        method=GenerationMethod.HUMAN_AUTHORED,
        body=body,
        relative_path="inbox/customer-activation.md",
        sources=(),
        confidence_level=None,
        confidence_basis=None,
        sensitivity=Sensitivity.INTERNAL,
    )


def test_agent_prompt_requires_source_and_confidence() -> None:
    body = body_template(KnowledgeType.SOURCE_SUMMARY, "Market evidence").replace(
        "<!-- Replace with bounded, sourced content. -->",
        "The source describes the market constraint.[^report]",
        1,
    )
    backend = FakeBackend(
        texts=[
            "Market evidence",
            "Summarizes a bounded report about one relevant market constraint.",
            "openai/codex",
            "report",
            "https://example.com/report",
            "Market report",
            "Only one primary report was available for this initial summary.",
            "inbox/market-evidence.md",
        ],
        selections=["source-summary", "agent-generated", "medium", "confidential"],
        confirmations=[False],
        edits=[body],
    )

    result = run_knowledge_create_prompts(backend=backend, write=lambda _: None)

    assert result is not None
    assert result.sources == (
        {
            "id": "report",
            "resource": "https://example.com/report",
            "title": "Market report",
        },
    )
    assert result.confidence_level is ConfidenceLevel.MEDIUM
    assert result.sensitivity is Sensitivity.CONFIDENTIAL


def test_unchanged_template_and_apply_decline_do_not_write() -> None:
    title = "Unedited concept"
    output: list[str] = []
    backend = FakeBackend(
        texts=[
            title,
            "Describes why an unchanged authoring template must never become knowledge.",
            "human:author",
        ],
        selections=["concept", "human-authored", "internal"],
        confirmations=[False],
        edits=[body_template(KnowledgeType.CONCEPT, title)],
    )
    assert run_knowledge_create_prompts(backend=backend, write=output.append) is None
    assert output[-1].startswith("└  Draft not created")

    assert confirm_knowledge_apply(
        backend=FakeBackend(confirmations=[False]),
        write=output.append,
    ) is False
    assert output[-1] == "└  Draft not saved"
    assert confirm_knowledge_apply(
        backend=FakeBackend(confirmations=[True]),
        write=lambda _: None,
    ) is True


def test_prompt_cancellation_at_each_primary_stage_is_safe() -> None:
    edited = "# Draft\n\n## Definition\n\nSubstantive content.\n"
    backends = (
        FakeBackend(selections=[None]),
        FakeBackend(selections=["concept"], texts=[None]),
        FakeBackend(selections=["concept"], texts=["Draft title", None]),
        FakeBackend(selections=["concept", None], texts=["Draft title", "A useful description."]),
        FakeBackend(
            selections=["concept", "human-authored"],
            texts=["Draft title", "A useful description.", None],
        ),
        FakeBackend(
            selections=["concept", "human-authored", None],
            texts=["Draft title", "A useful description.", "human:author"],
            confirmations=[False],
        ),
        FakeBackend(
            selections=["concept", "human-authored", "internal"],
            texts=["Draft title", "A useful description.", "human:author"],
            confirmations=[False],
            edits=[None],
        ),
        FakeBackend(
            selections=["concept", "human-authored", "internal"],
            texts=["Draft title", "A useful description.", "human:author", None],
            confirmations=[False],
            edits=[edited],
        ),
    )
    for backend in backends:
        output: list[str] = []
        assert run_knowledge_create_prompts(backend=backend, write=output.append) is None
        assert output[-1] == "└  Knowledge creation cancelled"


def test_required_source_and_confidence_cancellation_is_safe() -> None:
    source_cancelled = FakeBackend(
        selections=["source-summary", "transformed"],
        texts=["Draft title", "A useful source summary description.", "agent/model", None],
    )
    assert run_knowledge_create_prompts(
        backend=source_cancelled,
        write=lambda _: None,
    ) is None

    confidence_cancelled = FakeBackend(
        selections=["source-summary", "agent-generated", None],
        texts=[
            "Draft title",
            "A useful source summary description.",
            "agent/model",
            "source-1",
            "urn:test:source",
            "Test source",
        ],
        confirmations=[False],
    )
    assert run_knowledge_create_prompts(
        backend=confidence_cancelled,
        write=lambda _: None,
    ) is None


def test_prompt_and_apply_interrupts_are_treated_as_cancellation() -> None:
    class InterruptedBackend(FakeBackend):
        def select(
            self,
            message: str,
            *,
            choices: Sequence[PromptChoice],
            default: str,
        ) -> str | None:
            raise EOFError

        def confirm(self, message: str, *, default: bool) -> bool | None:
            raise KeyboardInterrupt

    assert run_knowledge_create_prompts(
        backend=InterruptedBackend(),
        write=lambda _: None,
    ) is None
    assert confirm_knowledge_apply(
        backend=InterruptedBackend(),
        write=lambda _: None,
    ) is False
