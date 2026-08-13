"""Inline, scrollback-preserving setup prompts for Portable KB."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .settings import SearchMode, Settings
from .skills import SkillTarget


class SetupPromptError(RuntimeError):
    """Raised when interactive setup cannot start safely."""


class SetupSkillChoice(StrEnum):
    """Agent-skill choices exposed by setup."""

    NONE = "none"
    CODEX = "codex"
    CLAUDE = "claude"
    BOTH = "both"

    @property
    def target(self) -> SkillTarget | None:
        return None if self is SetupSkillChoice.NONE else SkillTarget(self.value)


@dataclass(frozen=True, slots=True)
class SetupResult:
    """Confirmed settings and optional agent-skill installation target."""

    settings: Settings
    skill_target: SkillTarget | None


@dataclass(frozen=True, slots=True)
class PromptChoice:
    """One inline selector choice."""

    label: str
    value: str


class PromptBackend(Protocol):
    """Small prompt seam used by the real terminal and deterministic tests."""

    def text(self, message: str, *, default: str) -> str | None: ...

    def select(
        self,
        message: str,
        *,
        choices: Sequence[PromptChoice],
        default: str,
    ) -> str | None: ...

    def confirm(self, message: str, *, default: bool) -> bool | None: ...


class QuestionaryBackend:
    """Arrow-key terminal prompts that leave completed answers in scrollback."""

    def __init__(self) -> None:
        try:
            import questionary
        except ModuleNotFoundError as exc:
            raise SetupPromptError(
                "Interactive setup dependency is missing. Reinstall Portable KB, then retry."
            ) from exc

        self._questionary = questionary
        self._style = questionary.Style(
            [
                ("qmark", "fg:#7aa2f7 bold"),
                ("question", "bold"),
                ("answer", "fg:#7dcfff bold"),
                ("pointer", "fg:#7dcfff bold"),
                ("highlighted", "fg:#7dcfff bold"),
                ("selected", "fg:#9ece6a"),
                ("instruction", "fg:#565f89"),
                ("text", "fg:#c0caf5"),
                ("disabled", "fg:#565f89 italic"),
            ]
        )

    def text(self, message: str, *, default: str) -> str | None:
        return self._questionary.text(
            message,
            default=default,
            qmark="◆",
            style=self._style,
            validate=lambda value: bool(value.strip()) or "A value is required.",
        ).ask()

    def select(
        self,
        message: str,
        *,
        choices: Sequence[PromptChoice],
        default: str,
    ) -> str | None:
        options = [
            self._questionary.Choice(title=choice.label, value=choice.value)
            for choice in choices
        ]
        return self._questionary.select(
            message,
            choices=options,
            default=default,
            qmark="◆",
            pointer="›",
            instruction="(↑/↓ move · enter select)",
            style=self._style,
        ).ask()

    def confirm(self, message: str, *, default: bool) -> bool | None:
        return self._questionary.confirm(
            message,
            default=default,
            qmark="◆",
            style=self._style,
        ).ask()


def run_setup_prompts(
    initial: Settings,
    *,
    backend: PromptBackend | None = None,
    write: Callable[[str], None] = print,
) -> SetupResult | None:
    """Collect setup choices through inline prompts without taking over the screen."""

    prompts = backend or QuestionaryBackend()
    write("┌  portable-kb")
    write("│")
    write("◇  Local setup")
    write("│  Git-backed knowledge · local QMD search · explicit agent access")
    try:
        write("│")
        write("◇  Storage")
        data_dir = prompts.text("Brain checkout root", default=str(initial.data_dir))
        if data_dir is None:
            return _cancel(write)
        cache_dir = prompts.text("Disposable search cache", default=str(initial.cache_dir))
        if cache_dir is None:
            return _cancel(write)

        write("│")
        write("◇  Retrieval")
        selected_mode = prompts.select(
            "Select local search mode",
            choices=tuple(
                PromptChoice(mode.label, mode.value)
                for mode in (SearchMode.KEYWORD, SearchMode.SEMANTIC, SearchMode.FULL)
            ),
            default=initial.search_mode.value,
        )
        if selected_mode is None:
            return _cancel(write)

        write("│")
        write("◇  Agent workflow")
        selected_skill = prompts.select(
            "Install Portable KB access for",
            choices=(
                PromptChoice("Codex + Claude Code  · recommended", "both"),
                PromptChoice("Codex only", "codex"),
                PromptChoice("Claude Code only", "claude"),
                PromptChoice("Skip for now", "none"),
            ),
            default="both",
        )
        if selected_skill is None:
            return _cancel(write)

        settings = Settings(
            data_dir=Path(data_dir.strip()).expanduser().resolve(),
            cache_dir=Path(cache_dir.strip()).expanduser().resolve(),
            search_mode=SearchMode(selected_mode),
            qmd_command=initial.qmd_command,
        )
        skill_choice = SetupSkillChoice(selected_skill)
        write("│")
        write("◇  Review")
        write(f"│  Brains   {settings.data_dir}")
        write(f"│  Cache    {settings.cache_dir}")
        write(f"│  Search   {settings.search_mode.label}")
        write(f"│  Agents   {_skill_label(skill_choice)}")
        write("│")
        confirmed = prompts.confirm("Write this local configuration?", default=True)
        if confirmed is not True:
            return _cancel(write)
    except (EOFError, KeyboardInterrupt):
        return _cancel(write)

    write("│")
    write("└  Setup ready")
    return SetupResult(settings=settings, skill_target=skill_choice.target)


def _skill_label(choice: SetupSkillChoice) -> str:
    return {
        SetupSkillChoice.BOTH: "Codex + Claude Code",
        SetupSkillChoice.CODEX: "Codex",
        SetupSkillChoice.CLAUDE: "Claude Code",
        SetupSkillChoice.NONE: "Skip",
    }[choice]


def _cancel(write: Callable[[str], None]) -> None:
    write("│")
    write("└  Setup cancelled")
    return None
