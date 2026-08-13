"""Inline, scrollback-preserving prompts for local-first brain creation."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .brains import GitHubVisibility
from .setup_prompt import PromptBackend, PromptChoice, QuestionaryBackend


@dataclass(frozen=True, slots=True)
class BrainInitInputs:
    """Confirmed inputs for the local initialization step."""

    repository: Path
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class BrainPublishChoice:
    """Confirmed optional GitHub publication target."""

    repository: str
    visibility: GitHubVisibility


def run_brain_init_prompts(
    *,
    repository: str | None = None,
    name: str | None = None,
    slug: str | None = None,
    backend: PromptBackend | None = None,
    write: Callable[[str], None] = print,
) -> BrainInitInputs | None:
    """Collect and confirm the inputs needed to create the local repository."""

    prompts = backend or QuestionaryBackend()
    write("┌  portable-kb")
    write("│")
    write("◇  New local brain")
    write("│  Create and validate locally first · publishing stays optional")
    try:
        selected_name = name or prompts.text("Brain name", default="")
        if selected_name is None:
            return _cancel(write)
        selected_name = selected_name.strip()

        default_slug = slug or _slugify(selected_name)
        selected_slug = slug or prompts.text("Brain slug", default=default_slug)
        if selected_slug is None:
            return _cancel(write)
        selected_slug = selected_slug.strip()

        default_repository = repository or str(Path.cwd() / selected_slug)
        selected_repository = repository or prompts.text(
            "Local repository",
            default=default_repository,
        )
        if selected_repository is None:
            return _cancel(write)
        path = Path(selected_repository.strip()).expanduser().absolute()

        write("│")
        write("◇  Review local creation")
        write(f"│  Name       {selected_name}")
        write(f"│  Slug       {selected_slug}")
        write(f"│  Repository {path}")
        write("│")
        if prompts.confirm("Create this local brain?", default=True) is not True:
            return _cancel(write)
    except (EOFError, KeyboardInterrupt):
        return _cancel(write)
    return BrainInitInputs(repository=path, name=selected_name, slug=selected_slug)


def run_brain_publish_prompt(
    slug: str,
    *,
    backend: PromptBackend | None = None,
    write: Callable[[str], None] = print,
) -> BrainPublishChoice | None:
    """Ask whether a successfully created local brain should be published."""

    prompts = backend or QuestionaryBackend()
    write("│")
    write("◇  Local brain ready")
    write("│  The local repository and installed brain are safe even if publishing fails.")
    try:
        if prompts.confirm("Publish this brain to GitHub now?", default=False) is not True:
            write("│")
            write("└  Brain ready locally")
            return None
        target = prompts.text("GitHub repository (org/repo)", default=f"your-org/{slug}")
        if target is None:
            write("│")
            write("└  Publishing skipped · brain remains local")
            return None
        visibility = prompts.select(
            "Repository visibility",
            choices=(
                PromptChoice("Private  · recommended", GitHubVisibility.PRIVATE.value),
                PromptChoice("Internal · organization members", GitHubVisibility.INTERNAL.value),
                PromptChoice("Public", GitHubVisibility.PUBLIC.value),
            ),
            default=GitHubVisibility.PRIVATE.value,
        )
        if visibility is None:
            write("│")
            write("└  Publishing skipped · brain remains local")
            return None
    except (EOFError, KeyboardInterrupt):
        write("│")
        write("└  Publishing skipped · brain remains local")
        return None
    return BrainPublishChoice(
        repository=target.strip(),
        visibility=GitHubVisibility(visibility),
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _cancel(write: Callable[[str], None]) -> None:
    write("│")
    write("└  Brain creation cancelled")
    return None
