from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from pathlib import Path

from portable_kb.brain_prompt import (
    BrainInitInputs,
    BrainPublishChoice,
    run_brain_init_prompts,
    run_brain_publish_prompt,
)
from portable_kb.brains import GitHubVisibility
from portable_kb.setup_prompt import PromptChoice


class FakeBackend:
    def __init__(
        self,
        *,
        texts: Sequence[str | None] = (),
        selections: Sequence[str | None] = (),
        confirmations: Sequence[bool | None] = (),
    ) -> None:
        self.texts = deque(texts)
        self.selections = deque(selections)
        self.confirmations = deque(confirmations)
        self.calls: list[tuple[str, str]] = []

    def text(self, message: str, *, default: str) -> str | None:
        self.calls.append((message, default))
        return self.texts.popleft()

    def select(
        self,
        message: str,
        *,
        choices: Sequence[PromptChoice],
        default: str,
    ) -> str | None:
        self.calls.append((message, default))
        assert choices
        return self.selections.popleft()

    def confirm(self, message: str, *, default: bool) -> bool | None:
        self.calls.append((message, str(default)))
        return self.confirmations.popleft()


def test_brain_init_prompts_collect_local_inputs_and_slug_default(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    backend = FakeBackend(
        texts=["Customer Success", "customer-success", str(tmp_path / "customer-success")],
        confirmations=[True],
    )
    output: list[str] = []

    result = run_brain_init_prompts(backend=backend, write=output.append)

    assert result == BrainInitInputs(
        repository=tmp_path / "customer-success",
        name="Customer Success",
        slug="customer-success",
    )
    assert backend.calls[1] == ("Brain slug", "customer-success")
    assert "◇  Review local creation" in output


def test_brain_init_prompts_can_cancel_before_writing(tmp_path: Path) -> None:
    backend = FakeBackend(
        texts=["Local Brain", "local-brain", str(tmp_path / "local-brain")],
        confirmations=[False],
    )
    output: list[str] = []

    assert run_brain_init_prompts(backend=backend, write=output.append) is None
    assert output[-1] == "└  Brain creation cancelled"
    assert not (tmp_path / "local-brain").exists()

    for backend in (
        FakeBackend(texts=[None]),
        FakeBackend(texts=["Local Brain", None]),
        FakeBackend(texts=["Local Brain", "local-brain", None]),
    ):
        assert run_brain_init_prompts(backend=backend, write=lambda _: None) is None


def test_brain_init_prompts_handle_terminal_interrupt() -> None:
    class InterruptedBackend(FakeBackend):
        def text(self, message: str, *, default: str) -> str | None:
            raise EOFError

    output: list[str] = []
    assert run_brain_init_prompts(
        backend=InterruptedBackend(),
        write=output.append,
    ) is None
    assert output[-1] == "└  Brain creation cancelled"


def test_brain_publish_prompt_defaults_to_local_only_and_private() -> None:
    skipped_output: list[str] = []
    skipped = run_brain_publish_prompt(
        "sales",
        backend=FakeBackend(confirmations=[False]),
        write=skipped_output.append,
    )
    assert skipped is None
    assert skipped_output[-1] == "└  Brain ready locally"

    backend = FakeBackend(
        texts=["acme/sales"],
        selections=["private"],
        confirmations=[True],
    )
    published = run_brain_publish_prompt("sales", backend=backend, write=lambda _: None)
    assert published == BrainPublishChoice(
        repository="acme/sales",
        visibility=GitHubVisibility.PRIVATE,
    )
    assert backend.calls[1] == ("GitHub repository (org/repo)", "your-org/sales")


def test_brain_publish_prompt_handles_cancellation_after_publish_choice() -> None:
    target_cancelled_output: list[str] = []
    target_cancelled = run_brain_publish_prompt(
        "sales",
        backend=FakeBackend(texts=[None], confirmations=[True]),
        write=target_cancelled_output.append,
    )
    assert target_cancelled is None
    assert target_cancelled_output[-1] == "└  Publishing skipped · brain remains local"

    visibility_cancelled = run_brain_publish_prompt(
        "sales",
        backend=FakeBackend(
            texts=["acme/sales"],
            selections=[None],
            confirmations=[True],
        ),
        write=lambda _: None,
    )
    assert visibility_cancelled is None

    class InterruptedBackend(FakeBackend):
        def confirm(self, message: str, *, default: bool) -> bool | None:
            raise KeyboardInterrupt

    assert run_brain_publish_prompt(
        "sales",
        backend=InterruptedBackend(),
        write=lambda _: None,
    ) is None
