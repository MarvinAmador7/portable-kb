"""Command-line interface for Portable KB consumers."""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer

from .authoring import (
    ConfidenceLevel,
    GenerationMethod,
    KnowledgeType,
    Sensitivity,
    plan_knowledge_create,
)
from .brain_prompt import run_brain_init_prompts, run_brain_publish_prompt
from .brains import (
    BrainError,
    GitHubVisibility,
    add_brain,
    brain_status,
    init_brain,
    load_catalog,
    publish_brain_to_github,
    sync_brain,
    use_brain,
)
from .changes import ConcurrentChangeError
from .knowledge_prompt import confirm_knowledge_apply, run_knowledge_create_prompts
from .operations import OperationError
from .search import SearchError, get_knowledge_item, index_keyword_brain, search_keyword
from .settings import (
    SearchMode,
    Settings,
    SettingsError,
    default_config_path,
    default_settings,
    load_settings,
    save_settings,
)
from .setup_prompt import SetupPromptError, SetupSkillChoice, run_setup_prompts
from .skills import SkillError, SkillTarget, install_agent_skill

app = typer.Typer(
    name="pkb",
    help="Portable, governed knowledge for humans and agents.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
brain_app = typer.Typer(help="Create, publish, install, sync, select, and inspect brains.")
app.add_typer(brain_app, name="brain")
search_app = typer.Typer(help="Build and query disposable local search indexes.")
app.add_typer(search_app, name="search")
skill_app = typer.Typer(help="Install the Portable KB workflow for coding agents.")
app.add_typer(skill_app, name="skill")
knowledge_app = typer.Typer(help="Plan and apply governed knowledge lifecycle changes.")
app.add_typer(knowledge_app, name="knowledge")


@app.command()
def setup(
    non_interactive: Annotated[
        bool,
        typer.Option("--non-interactive", help="Write configuration without inline prompts."),
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
    agent_skill: Annotated[
        SetupSkillChoice,
        typer.Option(
            "--agent-skill",
            help="Install the agent workflow during non-interactive setup.",
        ),
    ] = SetupSkillChoice.NONE,
    force_skill: Annotated[
        bool,
        typer.Option("--force-skill", help="Replace a conflicting agent skill installation."),
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
        _install_setup_skill(agent_skill.target, force=force_skill)
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo("Interactive setup requires a terminal. Use --non-interactive.", err=True)
        raise typer.Exit(2)
    try:
        setup_result = run_setup_prompts(initial, write=typer.echo)
    except SetupPromptError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from None
    if setup_result is None:
        return
    _persist(setup_result.settings, target, overwrite=True)
    _install_setup_skill(setup_result.skill_target, force=force_skill)


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


@app.command("get")
def get_item(
    reference: Annotated[
        str,
        typer.Argument(help="Immutable item ID or knowledge-bundle-relative Markdown path."),
    ],
    slug: Annotated[
        str | None,
        typer.Option("--brain", help="Installed brain slug; defaults to the active brain."),
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
        typer.Option("--json", help="Emit the complete cited item as JSON."),
    ] = False,
) -> None:
    """Retrieve a complete knowledge item from the current pinned brain."""

    settings = _load_cli_settings(config_path)
    try:
        result = get_knowledge_item(settings, reference, slug, as_of=as_of)
    except (BrainError, SearchError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return
    citation = result["citation"]
    typer.echo(
        f"Citation: {citation['brain_slug']}@{citation['commit'][:12]}:"
        f"{citation['path']} ({citation['item_id']})"
    )
    typer.echo()
    typer.echo(result["item"]["content"], nl=False)


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


@brain_app.command("init")
def brain_init(
    source: Annotated[
        str | None,
        typer.Argument(help="Empty local directory or empty local Git repository."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Human-readable brain name."),
    ] = None,
    slug: Annotated[
        str | None,
        typer.Option("--slug", help="Lowercase kebab-case command name."),
    ] = None,
    publish_to: Annotated[
        str | None,
        typer.Option(
            "--publish-to",
            help="Create and publish to a GitHub org/repo after local initialization.",
        ),
    ] = None,
    visibility: Annotated[
        GitHubVisibility,
        typer.Option("--visibility", help="Visibility for a newly published GitHub repository."),
    ] = GitHubVisibility.PRIVATE,
    no_publish: Annotated[
        bool,
        typer.Option("--no-publish", help="Do not ask whether to publish after local creation."),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Explicit ISO date for bundle validation and log entry."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable initialization details."),
    ] = False,
) -> None:
    """Create, commit, install, and activate a local brain, then optionally publish it."""

    settings = _load_cli_settings(config_path)
    interactive = _interactive_terminal() and not json_output
    if publish_to is not None and no_publish:
        typer.echo("--publish-to and --no-publish cannot be used together.", err=True)
        raise typer.Exit(2)
    if source is None or name is None or slug is None:
        if not interactive:
            typer.echo(
                "Brain init requires SOURCE, --name, and --slug outside an interactive terminal.",
                err=True,
            )
            raise typer.Exit(2)
        try:
            inputs = run_brain_init_prompts(
                repository=source,
                name=name,
                slug=slug,
                write=typer.echo,
            )
        except SetupPromptError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(2) from None
        if inputs is None:
            return
        source = str(inputs.repository)
        name = inputs.name
        slug = inputs.slug
    try:
        result, _catalog, report = init_brain(
            source,
            name,
            slug,
            settings,
            as_of=as_of,
        )
    except (BrainError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if not json_output:
        typer.echo(f"Initialized locally: {result.brain.name} ({result.brain.slug})")
        typer.echo(f"Repository: {result.repository}")
        typer.echo(f"Commit: {result.brain.commit}")
        typer.echo("Installed and active: yes")
        if report.warnings:
            typer.echo(f"Validation warnings: {len(report.warnings)}")

    publish_choice = None
    if publish_to is not None:
        publish_choice = (publish_to, visibility)
    elif interactive and not no_publish:
        try:
            choice = run_brain_publish_prompt(result.brain.slug, write=typer.echo)
        except SetupPromptError as exc:
            typer.echo(f"Local brain is ready, but publishing could not start: {exc}", err=True)
            raise typer.Exit(1) from None
        if choice is not None:
            publish_choice = (choice.repository, choice.visibility)

    if publish_choice is None:
        if json_output:
            typer.echo(json.dumps(result.as_dict(report), indent=2, sort_keys=True))
        return
    try:
        publication, published_catalog = publish_brain_to_github(
            settings,
            publish_choice[0],
            result.brain.slug,
            visibility=publish_choice[1],
        )
    except BrainError as exc:
        typer.echo(f"Local brain is ready, but GitHub publication failed: {exc}", err=True)
        typer.echo("Retry later with `pkb brain publish --to org/repo`.", err=True)
        raise typer.Exit(1) from None
    if json_output:
        payload = publication.as_dict(
            active=publication.brain.slug == published_catalog.active
        )
        payload["validation_warnings"] = [finding.as_dict() for finding in report.warnings]
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Published to GitHub: {publication.github_repository}")
    typer.echo(f"Visibility: {publication.visibility.value}")


@brain_app.command("publish")
def brain_publish(
    github_repository: Annotated[
        str,
        typer.Option("--to", help="GitHub repository in org/repo format."),
    ],
    slug: Annotated[
        str | None,
        typer.Argument(help="Installed local brain slug; defaults to the active brain."),
    ] = None,
    visibility: Annotated[
        GitHubVisibility,
        typer.Option("--visibility", help="Visibility for the new GitHub repository."),
    ] = GitHubVisibility.PRIVATE,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable publication details."),
    ] = False,
) -> None:
    """Publish an initialized local brain to a new GitHub repository."""

    settings = _load_cli_settings(config_path)
    try:
        result, catalog = publish_brain_to_github(
            settings,
            github_repository,
            slug,
            visibility=visibility,
        )
    except BrainError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(
            json.dumps(
                result.as_dict(active=result.brain.slug == catalog.active),
                indent=2,
                sort_keys=True,
            )
        )
        return
    typer.echo(f"Published brain: {result.brain.name} ({result.brain.slug})")
    typer.echo(f"Repository: {result.repository}")
    typer.echo(f"GitHub: {result.github_repository}")
    typer.echo(f"Visibility: {result.visibility.value}")


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


@knowledge_app.command("create")
def knowledge_create(
    item_type: Annotated[
        KnowledgeType | None,
        typer.Option("--type", help="Draft knowledge type."),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option("--title", help="Knowledge title."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="One-sentence scope or summary."),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--actor", help="Producer identity: human:id, process:id, or producer/version."),
    ] = None,
    method: Annotated[
        GenerationMethod,
        typer.Option("--method", help="How substantive content was produced."),
    ] = GenerationMethod.HUMAN_AUTHORED,
    body_file: Annotated[
        Path | None,
        typer.Option("--body-file", help="UTF-8 Markdown body without YAML frontmatter."),
    ] = None,
    relative_path: Annotated[
        str | None,
        typer.Option("--path", help="Bundle-relative Markdown path; defaults under inbox/."),
    ] = None,
    sources_file: Annotated[
        Path | None,
        typer.Option("--sources-file", help="JSON array of OKF source mappings."),
    ] = None,
    confidence_level: Annotated[
        ConfidenceLevel | None,
        typer.Option("--confidence", help="Producer confidence for agent-generated content."),
    ] = None,
    confidence_basis: Annotated[
        str | None,
        typer.Option("--confidence-basis", help="Plain-language confidence basis."),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Repeatable lowercase kebab-case tag."),
    ] = None,
    sensitivity: Annotated[
        Sensitivity | None,
        typer.Option("--sensitivity", help="Handling classification; bundle default if omitted."),
    ] = None,
    timestamp: Annotated[
        str | None,
        typer.Option("--timestamp", help="Strict UTC RFC 3339 production time."),
    ] = None,
    slug: Annotated[
        str | None,
        typer.Option("--brain", help="Installed brain slug; defaults to the active brain."),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Apply the validated change plan."),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Override the user configuration path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Explicit ISO date for deterministic validation."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the plan or applied result as JSON."),
    ] = False,
) -> None:
    """Plan a new governed draft and apply it only after explicit approval."""

    settings = _load_cli_settings(config_path)
    interactive = _interactive_terminal() and not json_output
    core_inputs = (item_type, title, description, actor, body_file)
    if not any(value is not None for value in core_inputs):
        if not interactive:
            typer.echo(
                "Knowledge create requires --type, --title, --description, --actor, and "
                "--body-file outside an interactive terminal.",
                err=True,
            )
            raise typer.Exit(2)
        try:
            inputs = run_knowledge_create_prompts(write=typer.echo)
        except SetupPromptError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(2) from None
        if inputs is None:
            return
        item_type = inputs.item_type
        title = inputs.title
        description = inputs.description
        actor = inputs.actor
        method = inputs.method
        body = inputs.body
        relative_path = inputs.relative_path
        sources = inputs.sources
        confidence_level = inputs.confidence_level
        confidence_basis = inputs.confidence_basis
        sensitivity = inputs.sensitivity
    elif not all(value is not None for value in core_inputs):
        typer.echo(
            "Provide all of --type, --title, --description, --actor, and --body-file, "
            "or omit all five to use interactive authoring.",
            err=True,
        )
        raise typer.Exit(2)
    else:
        try:
            body = _read_text_input(body_file, label="Body file")
            sources = _read_sources_input(sources_file)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(2) from None

    try:
        plan = plan_knowledge_create(
            settings,
            item_type=item_type,
            title=title,
            description=description,
            actor=actor,
            method=method,
            body=body,
            relative_path=relative_path,
            sources=sources,
            confidence_level=confidence_level,
            confidence_basis=confidence_basis,
            tags=tags,
            sensitivity=sensitivity,
            timestamp=timestamp,
            slug=slug,
            as_of=as_of,
        )
    except (BrainError, OperationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None

    if not json_output:
        typer.echo(f"Validated draft plan: {plan.relative_path}")
        for change in plan.change_set.changes:
            typer.echo(f"  {change.kind:<6} {change.relative_path}")
        if plan.change_set.validation.warnings:
            typer.echo(f"Validation warnings: {len(plan.change_set.validation.warnings)}")

    should_apply = apply
    if interactive and not apply:
        try:
            should_apply = confirm_knowledge_apply(write=typer.echo)
        except SetupPromptError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(2) from None
    if should_apply:
        try:
            plan.change_set.apply()
        except (ConcurrentChangeError, OSError) as exc:
            typer.echo(f"Draft plan could not be applied: {exc}", err=True)
            raise typer.Exit(1) from None
    payload = plan.as_dict(applied=should_apply)
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    elif should_apply:
        typer.echo("Draft applied locally; review and commit the authoring repository when ready.")
    else:
        typer.echo("Plan only; no files changed. Re-run with --apply to write it.")


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


@skill_app.command("install")
def skill_install(
    target: Annotated[
        SkillTarget,
        typer.Option("--target", help="Agent skill location to install."),
    ] = SkillTarget.BOTH,
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace existing Portable KB skill installations."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable installation details."),
    ] = False,
) -> None:
    """Install the same governed retrieval skill for Codex and Claude Code."""

    try:
        result = install_agent_skill(target, force=force)
    except SkillError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        return
    _report_skill_install(result)


def _initial_settings(path: Path) -> Settings:
    if not path.exists():
        return default_settings()
    try:
        return load_settings(path)
    except SettingsError as exc:
        typer.echo(f"Cannot load existing configuration: {exc}", err=True)
        raise typer.Exit(2) from None


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _read_text_input(path: Path | None, *, label: str) -> str:
    if path is None:
        raise ValueError(f"{label} is required.")
    source = path.expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"{label} must be a regular file: {source}")
    if source.stat().st_size > 1_048_576:
        raise ValueError(f"{label} exceeds the 1 MiB authoring limit: {source}")
    try:
        content = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must use UTF-8: {source}") from exc
    if not content.strip():
        raise ValueError(f"{label} must not be empty: {source}")
    if content.startswith("---\n"):
        raise ValueError(f"{label} must contain Markdown body only, without YAML frontmatter.")
    return content


def _read_sources_input(path: Path | None) -> tuple[Mapping[str, object], ...]:
    if path is None:
        return ()
    content = _read_text_input(path, label="Sources file")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Sources file is not valid JSON: {path.expanduser().absolute()}") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("Sources file must contain a JSON array of source objects.")
    return tuple(payload)


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


def _install_setup_skill(target: SkillTarget | None, *, force: bool) -> None:
    if target is None:
        return
    try:
        result = install_agent_skill(target, force=force)
    except SkillError as exc:
        typer.echo(f"Configuration saved, but the agent skill was not installed: {exc}", err=True)
        typer.echo("Resolve the conflict, then run `pkb skill install`.", err=True)
        raise typer.Exit(1) from None
    _report_skill_install(result)


def _report_skill_install(result: dict[str, object]) -> None:
    typer.echo("Installed Portable KB agent skill:")
    targets = result["targets"]
    assert isinstance(targets, dict)
    unchanged = set(result.get("unchanged", []))
    for agent, path in targets.items():
        note = " (already current)" if agent in unchanged else ""
        typer.echo(f"  {agent}: {path}{note}")


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
