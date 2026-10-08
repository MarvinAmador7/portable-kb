from __future__ import annotations

import sys
from collections import deque
from collections.abc import Sequence
from pathlib import Path

import pytest

from portable_kb.settings import SearchMode, Settings
from portable_kb.setup_prompt import (
    PromptChoice,
    QuestionaryBackend,
    SetupPromptError,
    SetupResult,
    run_setup_prompts,
)
from portable_kb.skills import SkillTarget


class FakeBackend:
    def __init__(
        self,
        *,
        texts: Sequence[str | None],
        selections: Sequence[str | None],
        confirmation: bool | None,
    ) -> None:
        self.texts = deque(texts)
        self.selections = deque(selections)
        self.confirmation = confirmation
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
        return self.confirmation


def test_inline_setup_collects_confirmed_settings(tmp_path: Path) -> None:
    initial = Settings(data_dir=tmp_path / "old-data", cache_dir=tmp_path / "old-cache")
    backend = FakeBackend(
        texts=[str(tmp_path / "brains"), str(tmp_path / "cache")],
        selections=["qmd", "semantic", "both"],
        confirmation=True,
    )
    output: list[str] = []

    result = run_setup_prompts(initial, backend=backend, write=output.append)

    assert isinstance(result, SetupResult)
    assert result.settings.data_dir == (tmp_path / "brains").resolve()
    assert result.settings.cache_dir == (tmp_path / "cache").resolve()
    assert result.settings.search_mode is SearchMode.SEMANTIC
    assert result.skill_target is SkillTarget.BOTH
    assert backend.calls[0] == ("Brain checkout root", str(initial.data_dir))
    assert output[0] == "┌  portable-kb"
    assert "◇  Review" in output
    assert output[-1] == "└  Setup ready"


def test_inline_setup_can_skip_skill_and_decline_write(tmp_path: Path) -> None:
    backend = FakeBackend(
        texts=[str(tmp_path / "data"), str(tmp_path / "cache")],
        selections=["qmd", "keyword", "none"],
        confirmation=False,
    )
    output: list[str] = []

    result = run_setup_prompts(
        Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache"),
        backend=backend,
        write=output.append,
    )

    assert result is None
    assert "│  Agents   Skip" in output
    assert output[-1] == "└  Setup cancelled"


def test_inline_setup_handles_prompt_cancellation(tmp_path: Path) -> None:
    backend = FakeBackend(texts=[None], selections=[], confirmation=None)
    output: list[str] = []

    result = run_setup_prompts(
        Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache"),
        backend=backend,
        write=output.append,
    )

    assert result is None
    assert output[-1] == "└  Setup cancelled"


def test_inline_setup_handles_selector_cancellation(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    retrieval_cancelled = FakeBackend(
        texts=[str(settings.data_dir), str(settings.cache_dir)],
        selections=[None],
        confirmation=None,
    )
    agent_cancelled = FakeBackend(
        texts=[str(settings.data_dir), str(settings.cache_dir)],
        selections=["qmd", "keyword", None],
        confirmation=None,
    )

    assert run_setup_prompts(settings, backend=retrieval_cancelled, write=lambda _: None) is None
    assert run_setup_prompts(settings, backend=agent_cancelled, write=lambda _: None) is None


def test_inline_setup_reports_missing_prompt_dependency(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "questionary", None)

    with pytest.raises(SetupPromptError, match="Reinstall Portable KB"):
        QuestionaryBackend()
