from __future__ import annotations

from pathlib import Path

import pytest

from portable_kb.settings import (
    SearchMode,
    Settings,
    SettingsError,
    default_cache_dir,
    default_config_path,
    default_data_dir,
    load_settings,
    save_settings,
)


def test_settings_round_trip_creates_local_directories(tmp_path: Path) -> None:
    target = tmp_path / "config" / "config.yaml"
    settings = Settings(
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        search_mode=SearchMode.SEMANTIC,
    )
    assert save_settings(settings, target) == target
    assert load_settings(target) == settings
    assert settings.data_dir.is_dir()
    assert settings.cache_dir.is_dir()
    assert target.stat().st_mode & 0o777 == 0o600
    assert "mode: semantic" in target.read_text(encoding="utf-8")


def test_settings_refuse_overwrite_and_symbolic_link(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    target = tmp_path / "config.yaml"
    save_settings(settings, target)
    with pytest.raises(SettingsError, match="already exist"):
        save_settings(settings, target)
    link = tmp_path / "linked.yaml"
    link.symlink_to(target.name)
    with pytest.raises(SettingsError, match="symbolic-link"):
        save_settings(settings, link, overwrite=True)


def test_settings_reject_unknown_or_unsafe_data(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("schema_version: 1\nunknown: true\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="fields"):
        load_settings(target)
    target.write_text("!!python/object/apply:os.system ['false']\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="safe YAML"):
        load_settings(target)


def test_xdg_defaults_are_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    assert default_config_path() == tmp_path / "config/portable-kb/config.yaml"
    assert default_data_dir() == tmp_path / "data/portable-kb"
    assert default_cache_dir() == tmp_path / "cache/portable-kb"
