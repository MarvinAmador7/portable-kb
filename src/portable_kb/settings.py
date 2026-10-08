"""Local application settings for Portable KB consumers."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


class SettingsError(ValueError):
    """Raised when local settings cannot be loaded safely."""


class SearchProvider(StrEnum):
    QMD = "qmd"
    BUILTIN = "builtin"


class SearchMode(StrEnum):
    """QMD capability tiers exposed by Portable KB."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    FULL = "full"

    @property
    def label(self) -> str:
        return {
            self.KEYWORD: "Keyword · no model download",
            self.SEMANTIC: "Semantic · about 300 MB",
            self.FULL: "Full hybrid · about 2 GB",
        }[self]


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated local configuration shared by CLI and future UI consumers."""

    data_dir: Path
    cache_dir: Path
    search_mode: SearchMode = SearchMode.KEYWORD
    qmd_command: str = "qmd"
    schema_version: int = 1
    search_provider: SearchProvider = SearchProvider.QMD
    native_command: str = "pkb-search"

    def __post_init__(self) -> None:
        if self.search_provider is SearchProvider.BUILTIN and self.search_mode is not SearchMode.KEYWORD:
            raise SettingsError("The builtin provider supports keyword mode only.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "data_dir": str(self.data_dir),
            "cache_dir": str(self.cache_dir),
            "search": {
                "provider": self.search_provider.value,
                "mode": self.search_mode.value,
                "command": self.qmd_command if self.search_provider is SearchProvider.QMD else self.native_command,
            },
        }


def default_config_path() -> Path:
    """Return the XDG-aware user configuration path."""

    root = _environment_path("XDG_CONFIG_HOME", Path.home() / ".config")
    return root / "portable-kb" / "config.yaml"


def default_data_dir() -> Path:
    """Return the XDG-aware directory for local brain checkouts."""

    root = _environment_path("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return root / "portable-kb"


def default_cache_dir() -> Path:
    """Return the XDG-aware directory for disposable indexes and models."""

    root = _environment_path("XDG_CACHE_HOME", Path.home() / ".cache")
    return root / "portable-kb"


def default_settings() -> Settings:
    return Settings(data_dir=default_data_dir(), cache_dir=default_cache_dir(), search_provider=SearchProvider.BUILTIN)


def load_settings(path: str | Path | None = None) -> Settings:
    """Load and validate local settings without creating files or directories."""

    source = _absolute(path or default_config_path())
    if not source.is_file() or source.is_symlink():
        raise SettingsError(f"Settings file does not exist or is not a regular file: {source}")
    yaml = YAML(typ="safe")
    try:
        payload = yaml.load(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SettingsError(f"Settings file is not valid safe YAML: {source}") from exc
    if not isinstance(payload, dict):
        raise SettingsError("Settings root must be a mapping.")
    expected = {"schema_version", "data_dir", "cache_dir", "search"}
    if set(payload) != expected:
        raise SettingsError("Settings fields do not match schema version 1.")
    if payload.get("schema_version") != 1:
        raise SettingsError("Unsupported settings schema version.")
    search = payload.get("search")
    if not isinstance(search, dict) or set(search) != {"provider", "mode", "command"}:
        raise SettingsError("Search settings are incomplete.")
    try:
        provider = SearchProvider(search.get("provider"))
    except ValueError as exc:
        raise SettingsError("Search provider must be qmd or builtin.") from exc
    data_dir = payload.get("data_dir")
    cache_dir = payload.get("cache_dir")
    command = search.get("command")
    if not all(isinstance(value, str) and value.strip() for value in (data_dir, cache_dir, command)):
        raise SettingsError("Settings paths and search command must be non-empty strings.")
    try:
        mode = SearchMode(search.get("mode"))
    except ValueError as exc:
        raise SettingsError("Search mode must be keyword, semantic, or full.") from exc
    return Settings(
        data_dir=_absolute(data_dir),
        cache_dir=_absolute(cache_dir),
        search_mode=mode,
        qmd_command=command.strip() if provider is SearchProvider.QMD else "qmd",
        native_command=command.strip() if provider is SearchProvider.BUILTIN else "pkb-search",
        search_provider=provider,
    )


def save_settings(
    settings: Settings,
    path: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically persist settings and create their local storage directories."""

    target = _absolute(path or default_config_path())
    if target.exists() and not overwrite:
        raise SettingsError(f"Settings already exist: {target}")
    if target.is_symlink():
        raise SettingsError(f"Refusing to replace symbolic-link settings: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            yaml.dump(settings.as_dict(), stream)
        temporary.chmod(0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _environment_path(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    return _absolute(value) if value else fallback.resolve()


def _absolute(value: str | Path) -> Path:
    return Path(value).expanduser().absolute()
