"""Command-line interface for Portable KB consumers."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer

from .brains import BrainError, add_brain, brain_status, load_catalog, sync_brain, use_brain
from .search import SearchError, index_keyword_brain, search_keyword
from .settings import (
    SearchMode,
    Settings,
    SettingsError,
    default_config_path,
    default_settings,
    load_settings,
    save_settings,
)
from .setup_tui import SetupWizard

app = typer.Typer(
    name="pkb",
    help="Portable, governed knowledge for humans and agents.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
brain_app = typer.Typer(help="Install, sync, select, and inspect portable brains.")
app.add_typer(brain_app, name="brain")
search_app = typer.Typer(help="Build and query disposable local search indexes.")
app.add_typer(search_app, name="search")


@app.command()
def setup(
    non_interactive: Annotated[
        bool,
        typer.Option("--non-interactive", help="Write configuration without opening the TUI."),
    ] = False,
    search_mode: Annotated[
        SearchMode,
        typer.Option("--search-mode", help="QMD capability tier."),
    ] = SearchMode.KEYWORD,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Directory for local brain checkouts."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Directory for disposable indexes and models."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace existing configuration in non-interactive mode."),
    ] = False,
) -> None:
    """Configure local storage and QMD search quality."""

    target = (config_path or default_config_path()).expanduser().absolute()
    initial = _initial_settings(target)
    initial = Settings(
        data_dir=(data_dir or initial.data_dir).expanduser().resolve(),
        cache_dir=(cache_dir or initial.cache_dir).expanduser().resolve(),
        search_mode=search_mode if non_interactive else initial.search_mode,
        qmd_command=initial.qmd_command,
    )
    if non_interactive:
        _persist(initial, target, overwrite=force)
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo("Interactive setup requires a terminal. Use --non-interactive.", err=True)
        raise typer.Exit(2)
    result = SetupWizard(initial).run()
    if result is None:
        typer.echo("Setup cancelled.")
        return
    _persist(result, target, overwrite=True)


@app.command()
def doctor(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable status."),
    ] = False,
) -> None:
    """Check local configuration and QMD availability without changing anything."""

    target = (config_path or default_config_path()).expanduser().absolute()
    try:
        settings = load_settings(target)
    except SettingsError as exc:
        _doctor_output(
            {"ok": False, "config": str(target), "config_valid": False, "error": str(exc)},
            json_output,
        )
        raise typer.Exit(1) from None
    qmd_path = shutil.which(settings.qmd_command)
    result = {
        "ok": qmd_path is not None,
        "config": str(target),
        "config_valid": True,
        "data_dir": str(settings.data_dir),
        "cache_dir": str(settings.cache_dir),
        "search_mode": settings.search_mode.value,
        "qmd_command": settings.qmd_command,
        "qmd_path": qmd_path,
    }
    _doctor_output(result, json_output)
    if not result["ok"]:
        raise typer.Exit(1)


@brain_app.command("add")
def brain_add(
    source: Annotated[str, typer.Argument(help="Local path or Git repository URL.")],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Explicit ISO date for bundle validation."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable installation details."),
    ] = False,
) -> None:
    """Clone and validate a brain before adding it to the local catalog."""

    settings = _load_cli_settings(config_path)
    try:
        brain, catalog, report = add_brain(source, settings, as_of=as_of)
    except (BrainError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    payload = {
        **brain.as_dict(active=brain.slug == catalog.active),
        "validation_warnings": [finding.as_dict() for finding in report.warnings],
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Added brain: {brain.name} ({brain.slug})")
    typer.echo(f"Commit: {brain.commit}")
    if brain.slug == catalog.active:
        typer.echo("Active brain: yes")
    if report.warnings:
        typer.echo(f"Validation warnings: {len(report.warnings)}")


@brain_app.command("list")
def brain_list(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the machine-readable catalog."),
    ] = False,
) -> None:
    """List locally installed brains without accessing their remotes."""

    settings = _load_cli_settings(config_path)
    try:
        catalog = load_catalog(settings)
    except BrainError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(json.dumps(catalog.as_dict(), indent=2, sort_keys=True))
        return
    if not catalog.brains:
        typer.echo("No brains installed.")
        return
    typer.echo("ACTIVE  SLUG                 COMMIT        NAME")
    for brain in catalog.brains:
        marker = "*" if brain.slug == catalog.active else " "
        typer.echo(f"{marker:<7} {brain.slug:<20} {brain.commit[:12]}  {brain.name}")


@brain_app.command("use")
def brain_use(
    slug: Annotated[str, typer.Argument(help="Installed brain slug.")],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
) -> None:
    """Select the active worldview for unscoped commands."""

    settings = _load_cli_settings(config_path)
    try:
        brain = use_brain(slug, settings)
    except BrainError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Active brain: {brain.slug} ({brain.name})")


@brain_app.command("status")
def show_brain_status(
    slug: Annotated[
        str | None,
        typer.Argument(help="Installed brain slug; defaults to the active brain."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Explicit ISO date for bundle validation."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable health."),
    ] = False,
) -> None:
    """Inspect local Git and bundle health without fetching or changing files."""

    settings = _load_cli_settings(config_path)
    try:
        result = brain_status(settings, slug, as_of=as_of)
    except (BrainError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        typer.echo(f"Brain: {result['name']} ({result['slug']})")
        typer.echo(f"Commit: {result['current_commit'] or 'unavailable'}")
        typer.echo(f"Catalog pin: {'match' if result['commit_matches'] else 'mismatch'}")
        typer.echo(f"Working tree: {'dirty' if result['dirty'] else 'clean'}")
        typer.echo(f"Bundle: {'valid' if result['bundle_valid'] else 'invalid'}")
    if not result["ok"]:
        raise typer.Exit(1)


@brain_app.command("sync")
def brain_sync(
    slug: Annotated[
        str | None,
        typer.Argument(help="Installed brain slug; defaults to the active brain."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Explicit ISO date for candidate validation."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable synchronization details."),
    ] = False,
) -> None:
    """Fetch and activate a validated fast-forward update."""

    settings = _load_cli_settings(config_path)
    try:
        result = sync_brain(settings, slug, as_of=as_of)
    except (BrainError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return
    if result["changed"]:
        typer.echo(f"Synchronized brain: {result['slug']}")
        typer.echo(f"Previous commit: {result['previous_commit']}")
        typer.echo(f"Current commit:  {result['current_commit']}")
    else:
        typer.echo(f"Brain is already current: {result['slug']}")
        typer.echo(f"Commit: {result['current_commit']}")
    if result["validation_warnings"]:
        typer.echo(f"Validation warnings: {len(result['validation_warnings'])}")


@search_app.command("index")
def search_index(
    slug: Annotated[
        str | None,
        typer.Argument(help="Installed brain slug; defaults to the active brain."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Explicit ISO date for bundle validation."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable index details."),
    ] = False,
) -> None:
    """Build a disposable, model-free QMD keyword index."""

    settings = _load_cli_settings(config_path)
    try:
        result = index_keyword_brain(settings, slug, as_of=as_of)
    except (BrainError, SearchError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return
    typer.echo(f"Indexed brain: {result['brain_slug']}")
    typer.echo(f"Commit: {result['commit']}")
    typer.echo(f"Concepts: {result['concept_count']}")
    typer.echo("Search mode: keyword (no models downloaded)")


@search_app.command("query")
def search_query(
    query: Annotated[str, typer.Argument(help="BM25 keyword query.")],
    slug: Annotated[
        str | None,
        typer.Option("--brain", help="Installed brain slug; defaults to the active brain."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", min=1, max=100, help="Maximum number of results."),
    ] = 10,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Explicit ISO date for bundle validation."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit cited machine-readable results."),
    ] = False,
) -> None:
    """Search the current pinned brain with model-free BM25 retrieval."""

    settings = _load_cli_settings(config_path)
    try:
        result = search_keyword(settings, query, slug, limit=limit, as_of=as_of)
    except (BrainError, SearchError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return
    if not result["results"]:
        typer.echo("No matching knowledge items.")
        return
    for item in result["results"]:
        typer.echo(f"{item['rank']:>2}. {item['score']:.2f}  {item['title']}")
        typer.echo(
            f"    {item['path']} · {item['item_id']} · "
            f"{result['brain']['commit'][:12]}"
        )
        if item.get("snippet"):
            typer.echo(f"    {item['snippet']}")


def _initial_settings(path: Path) -> Settings:
    if not path.exists():
        return default_settings()
    try:
        return load_settings(path)
    except SettingsError as exc:
        typer.echo(f"Cannot load existing configuration: {exc}", err=True)
        raise typer.Exit(2) from None


def _load_cli_settings(path: Path | None) -> Settings:
    target = (path or default_config_path()).expanduser().absolute()
    try:
        return load_settings(target)
    except SettingsError as exc:
        typer.echo(f"Portable KB is not configured: {exc}", err=True)
        typer.echo("Run `pkb setup` first.", err=True)
        raise typer.Exit(2) from None


def _persist(settings: Settings, target: Path, *, overwrite: bool) -> None:
    try:
        saved = save_settings(settings, target, overwrite=overwrite)
    except SettingsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from None
    typer.echo(f"Portable KB configured: {saved}")
    typer.echo(f"Search mode: {settings.search_mode.value}")
    if shutil.which(settings.qmd_command) is None:
        typer.echo("QMD is not installed yet; setup was saved without downloading anything.")


def _doctor_output(result: dict[str, object], json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return
    mark = "✓" if result.get("config_valid") else "✗"
    typer.echo(f"{mark} Configuration: {result['config']}")
    if result.get("config_valid"):
        qmd = result.get("qmd_path") or "not found"
        typer.echo(f"{'✓' if result.get('qmd_path') else '✗'} QMD: {qmd}")
        typer.echo(f"  Search mode: {result['search_mode']}")
    elif result.get("error"):
        typer.echo(f"  {result['error']}")


if __name__ == "__main__":
    app()
