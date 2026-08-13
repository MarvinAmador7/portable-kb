from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import ContentSwitcher, Static

from portable_kb.settings import SearchMode, Settings
from portable_kb.setup_tui import SetupWizard


def test_setup_wizard_collects_confirmed_settings(tmp_path: Path) -> None:
    initial = Settings(data_dir=tmp_path / "brains", cache_dir=tmp_path / "cache")
    app = SetupWizard(initial)

    async def drive_wizard() -> Settings | None:
        async with app.run_test() as pilot:
            assert app.query_one("#steps", ContentSwitcher).current == "welcome"
            await pilot.click("#welcome-next")
            assert app.query_one("#steps", ContentSwitcher).current == "paths"
            await pilot.click("#paths-next")
            assert app.query_one("#steps", ContentSwitcher).current == "search"
            await pilot.click("#semantic")
            await pilot.click("#search-next")
            assert app.query_one("#steps", ContentSwitcher).current == "review"
            assert "Semantic" in str(app.query_one("#summary", Static).render())
            await pilot.click("#save")
            await pilot.pause()
        return app.return_value

    result = asyncio.run(drive_wizard())
    assert result is not None
    assert result.data_dir == initial.data_dir
    assert result.cache_dir == initial.cache_dir
    assert result.search_mode is SearchMode.SEMANTIC


def test_setup_wizard_can_cancel(tmp_path: Path) -> None:
    app = SetupWizard(Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache"))

    async def cancel() -> Settings | None:
        async with app.run_test() as pilot:
            await pilot.click("#cancel")
            await pilot.pause()
        return app.return_value

    assert asyncio.run(cancel()) is None
