"""Textual setup wizard for Portable KB."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    ContentSwitcher,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

from .settings import SearchMode, Settings


class SetupWizard(App[Settings | None]):
    """Collect local setup choices without performing downloads or Git operations."""

    TITLE = "Portable KB"
    SUB_TITLE = "Setup · 1 of 4"
    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }

    #wizard {
        width: 76;
        height: 31;
        border: round $primary;
        background: $panel;
        padding: 1 3;
    }

    .step {
        height: 1fr;
    }

    .eyebrow {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 1;
    }

    .title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .copy {
        color: $text-muted;
        margin-bottom: 2;
    }

    .field-label {
        margin-top: 1;
        margin-bottom: 0;
    }

    Input {
        margin-bottom: 1;
    }

    RadioSet {
        height: auto;
        border: none;
        background: transparent;
        margin-bottom: 1;
    }

    .actions {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }

    Button {
        margin-left: 1;
    }

    #summary {
        height: 7;
        border: solid $secondary;
        padding: 1 2;
        margin: 1 0;
        overflow: hidden;
        text-overflow: ellipsis;
        text-wrap: nowrap;
    }

    #saved-note {
        color: $success;
        margin-top: 1;
    }
    """

    def __init__(self, initial: Settings) -> None:
        super().__init__()
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard"):
            yield ContentSwitcher(
                Container(
                    Label("PORTABLE ORGANIZATIONAL MEMORY", classes="eyebrow"),
                    Static("Set up your portable brain", classes="title"),
                    Static(
                        "This wizard configures local storage and search quality. "
                        "Nothing is downloaded and no repository is changed until you confirm.",
                        classes="copy",
                    ),
                    Horizontal(
                        Button("Cancel", id="cancel"),
                        Button("Begin", id="welcome-next", variant="primary"),
                        classes="actions",
                    ),
                    id="welcome",
                    classes="step",
                ),
                Container(
                    Label("LOCAL STORAGE · 2 OF 4", classes="eyebrow"),
                    Static("Choose where brains and indexes live", classes="title"),
                    Label("Brain checkouts", classes="field-label"),
                    Input(value=str(self.initial.data_dir), id="data-dir"),
                    Label("Disposable search cache", classes="field-label"),
                    Input(value=str(self.initial.cache_dir), id="cache-dir"),
                    Horizontal(
                        Button("Back", id="paths-back"),
                        Button("Continue", id="paths-next", variant="primary"),
                        classes="actions",
                    ),
                    id="paths",
                    classes="step",
                ),
                Container(
                    Label("SEARCH QUALITY · 3 OF 4", classes="eyebrow"),
                    Static("Start light; upgrade only when useful", classes="title"),
                    Static(
                        "Keyword mode downloads no AI models. Search modes can be changed later.",
                        classes="copy",
                    ),
                    RadioSet(
                        RadioButton(SearchMode.KEYWORD.label, id="keyword"),
                        RadioButton(SearchMode.SEMANTIC.label, id="semantic"),
                        RadioButton(SearchMode.FULL.label, id="full"),
                        id="search-mode",
                    ),
                    Horizontal(
                        Button("Back", id="search-back"),
                        Button("Review", id="search-next", variant="primary"),
                        classes="actions",
                    ),
                    id="search",
                    classes="step",
                ),
                Container(
                    Label("CONFIRM · 4 OF 4", classes="eyebrow"),
                    Static("Ready to create local configuration", classes="title"),
                    Static(id="summary"),
                    Static("The QMD index remains disposable and outside Git.", classes="copy"),
                    Horizontal(
                        Button("Back", id="review-back"),
                        Button("Save setup", id="save", variant="success"),
                        classes="actions",
                    ),
                    id="review",
                    classes="step",
                ),
                initial="welcome",
                id="steps",
            )
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(f"#{self.initial.search_mode.value}", RadioButton).value = True

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "cancel":
            self.exit(None)
        elif button_id == "welcome-next":
            self._show("paths", 2)
        elif button_id == "paths-back":
            self._show("welcome", 1)
        elif button_id == "paths-next":
            if self._paths_are_valid():
                self._show("search", 3)
        elif button_id == "search-back":
            self._show("paths", 2)
        elif button_id == "search-next":
            self._update_summary()
            self._show("review", 4)
        elif button_id == "review-back":
            self._show("search", 3)
        elif button_id == "save":
            self.exit(self._settings())

    def _show(self, step: str, number: int) -> None:
        self.query_one("#steps", ContentSwitcher).current = step
        self.sub_title = f"Setup · {number} of 4"

    def _paths_are_valid(self) -> bool:
        valid = True
        for selector in ("#data-dir", "#cache-dir"):
            field = self.query_one(selector, Input)
            if not field.value.strip():
                field.add_class("-invalid")
                valid = False
            else:
                field.remove_class("-invalid")
        if not valid:
            self.notify("Both storage paths are required.", severity="error")
        return valid

    def _selected_mode(self) -> SearchMode:
        pressed = self.query_one("#search-mode", RadioSet).pressed_button
        return SearchMode(pressed.id if pressed and pressed.id else SearchMode.KEYWORD.value)

    def _settings(self) -> Settings:
        return Settings(
            data_dir=Path(self.query_one("#data-dir", Input).value.strip()).expanduser().resolve(),
            cache_dir=Path(self.query_one("#cache-dir", Input).value.strip())
            .expanduser()
            .resolve(),
            search_mode=self._selected_mode(),
            qmd_command=self.initial.qmd_command,
        )

    def _update_summary(self) -> None:
        settings = self._settings()
        self.query_one("#summary", Static).update(
            "\n".join(
                (
                    f"Brains     {settings.data_dir}",
                    f"Cache      {settings.cache_dir}",
                    f"Search     {settings.search_mode.label}",
                    "Provider   QMD (local)",
                )
            )
        )
