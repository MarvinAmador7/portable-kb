from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from portable_kb.brain_prompt import BrainInitInputs, BrainPublishChoice
from portable_kb.brains import BrainError, BrainPublishResult, GitHubVisibility, load_catalog
from portable_kb.cli import app
from portable_kb.parsing import discover_concepts
from portable_kb.settings import SearchMode, Settings, load_settings, save_settings
from portable_kb.skills import SkillError

runner = CliRunner()


def test_non_interactive_setup_and_doctor(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "config.yaml"
    data = tmp_path / "brains"
    cache = tmp_path / "cache"
    result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--config",
            str(config),
            "--data-dir",
            str(data),
            "--cache-dir",
            str(cache),
            "--search-mode",
            "semantic",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Portable KB configured" in result.output
    assert load_settings(config).search_mode is SearchMode.SEMANTIC

    monkeypatch.setattr("portable_kb.cli.shutil.which", lambda command: "/opt/bin/qmd")
    doctor = runner.invoke(app, ["doctor", "--config", str(config), "--json"])
    assert doctor.exit_code == 0, doctor.output
    payload = json.loads(doctor.output)
    assert payload["ok"] is True
    assert payload["search_mode"] == "semantic"


def test_non_interactive_setup_requires_force_to_replace(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    arguments = ["setup", "--non-interactive", "--config", str(config)]
    assert runner.invoke(app, arguments).exit_code == 0
    replacement = runner.invoke(app, arguments)
    assert replacement.exit_code == 2
    assert "already exist" in replacement.output
    assert runner.invoke(app, [*arguments, "--force"]).exit_code == 0


def test_non_interactive_setup_can_install_agent_skill(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def installed(target, *, force=False):
        calls.append((target, force))
        return {
            "skill": "portable-kb",
            "targets": {"codex": "/tmp/codex/portable-kb"},
            "unchanged": [],
            "ok": True,
        }

    monkeypatch.setattr("portable_kb.cli.install_agent_skill", installed)
    result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--config",
            str(tmp_path / "config.yaml"),
            "--agent-skill",
            "codex",
            "--force-skill",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [("codex", True)]
    assert "Installed Portable KB agent skill" in result.output


def test_interactive_setup_requires_a_terminal(tmp_path: Path) -> None:
    result = runner.invoke(app, ["setup", "--config", str(tmp_path / "config.yaml")])
    assert result.exit_code == 2
    assert "requires a terminal" in result.output


def test_doctor_reports_missing_configuration(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["doctor", "--config", str(tmp_path / "missing.yaml"), "--json"],
    )
    assert result.exit_code == 1
    assert json.loads(result.output)["config_valid"] is False


def test_brain_cli_add_list_use_and_status(tmp_path: Path, brain_repo_factory) -> None:
    config = tmp_path / "config.yaml"
    setup_result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--config",
            str(config),
            "--data-dir",
            str(tmp_path / "data"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
    )
    assert setup_result.exit_code == 0
    source = brain_repo_factory("cli-brain", "urn:uuid:44444444-4444-4444-8444-444444444444")
    added = runner.invoke(
        app,
        ["brain", "add", str(source), "--config", str(config), "--as-of", "2026-08-12"],
    )
    assert added.exit_code == 0, added.output
    assert "Added brain: Cli Brain" in added.output

    listed = runner.invoke(app, ["brain", "list", "--config", str(config), "--json"])
    assert listed.exit_code == 0
    catalog = json.loads(listed.output)
    assert catalog["active"] == "cli-brain"
    assert catalog["brains"][0]["slug"] == "cli-brain"

    selected = runner.invoke(app, ["brain", "use", "cli-brain", "--config", str(config)])
    assert selected.exit_code == 0
    status = runner.invoke(
        app,
        ["brain", "status", "--config", str(config), "--as-of", "2026-08-12", "--json"],
    )
    assert status.exit_code == 0, status.output
    assert json.loads(status.output)["ok"] is True

    manifest = source / "brain.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("name: Cli Brain", "name: New Cli Brain"),
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(source), "add", "brain.yaml"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "commit", "--quiet", "-m", "Update CLI brain"],
        check=True,
        capture_output=True,
        text=True,
    )
    synced = runner.invoke(
        app,
        ["brain", "sync", "--config", str(config), "--as-of", "2026-08-12", "--json"],
    )
    assert synced.exit_code == 0, synced.output
    assert json.loads(synced.output)["changed"] is True


def test_brain_init_cli_creates_first_brain_from_empty_directory(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    save_settings(settings, config)
    repository = tmp_path / "business-a"

    initialized = runner.invoke(
        app,
        [
            "brain",
            "init",
            str(repository),
            "--name",
            "Business A",
            "--slug",
            "business-a",
            "--config",
            str(config),
            "--as-of",
            "2026-08-13",
            "--json",
        ],
    )

    assert initialized.exit_code == 0, initialized.output
    payload = json.loads(initialized.output)
    assert payload["slug"] == "business-a"
    assert payload["name"] == "Business A"
    assert payload["active"] is True
    assert payload["published"] is False
    assert payload["repository"] == str(repository)
    assert (repository / "brain.yaml").is_file()

    listed = runner.invoke(app, ["brain", "list", "--config", str(config), "--json"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["active"] == "business-a"

    human = runner.invoke(
        app,
        [
            "brain",
            "init",
            str(tmp_path / "business-b"),
            "--name",
            "Business B",
            "--slug",
            "business-b",
            "--config",
            str(config),
            "--as-of",
            "2026-08-13",
        ],
    )
    assert human.exit_code == 0, human.output
    assert "Initialized locally: Business B (business-b)" in human.output
    assert "Installed and active: yes" in human.output


def test_brain_init_cli_requires_local_source_and_complete_noninteractive_inputs(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.yaml"
    save_settings(Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache"), config)

    result = runner.invoke(
        app,
        [
            "brain",
            "init",
            "https://github.com/example/empty.git",
            "--name",
            "Remote Brain",
            "--slug",
            "remote-brain",
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 1
    assert "starts with a local repository" in result.output

    incomplete = runner.invoke(
        app,
        ["brain", "init", str(tmp_path / "incomplete"), "--config", str(config)],
    )
    assert incomplete.exit_code == 2
    assert "requires SOURCE, --name, and --slug" in incomplete.output


def test_brain_publish_cli_uses_explicit_org_repo(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "config.yaml"
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    save_settings(settings, config)
    repository = tmp_path / "publishable"
    initialized = runner.invoke(
        app,
        [
            "brain",
            "init",
            str(repository),
            "--name",
            "Publishable",
            "--slug",
            "publishable",
            "--config",
            str(config),
            "--as-of",
            "2026-08-13",
            "--json",
        ],
    )
    assert initialized.exit_code == 0, initialized.output
    brain = load_catalog(settings).get("publishable")
    calls = []

    def published(settings_arg, target, slug=None, *, visibility):
        calls.append((settings_arg, target, slug, visibility))
        return (
            BrainPublishResult(
                brain=brain,
                repository=str(repository),
                github_repository=target,
                visibility=visibility,
            ),
            load_catalog(settings),
        )

    monkeypatch.setattr("portable_kb.cli.publish_brain_to_github", published)
    result = runner.invoke(
        app,
        [
            "brain",
            "publish",
            "publishable",
            "--to",
            "acme/publishable",
            "--visibility",
            "internal",
            "--config",
            str(config),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(settings, "acme/publishable", "publishable", GitHubVisibility.INTERNAL)]
    assert json.loads(result.output)["github_repository"] == "acme/publishable"


def test_brain_init_interactive_flow_creates_locally_then_publishes(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "config.yaml"
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    save_settings(settings, config)
    repository = tmp_path / "interactive"
    monkeypatch.setattr("portable_kb.cli._interactive_terminal", lambda: True)
    monkeypatch.setattr(
        "portable_kb.cli.run_brain_init_prompts",
        lambda **_kwargs: BrainInitInputs(repository, "Interactive Brain", "interactive-brain"),
    )
    monkeypatch.setattr(
        "portable_kb.cli.run_brain_publish_prompt",
        lambda *_args, **_kwargs: BrainPublishChoice(
            "acme/interactive-brain",
            GitHubVisibility.PRIVATE,
        ),
    )

    def published(settings_arg, target, slug=None, *, visibility):
        catalog = load_catalog(settings_arg)
        brain = catalog.get(slug or "")
        return (
            BrainPublishResult(brain, str(repository), target, visibility),
            catalog,
        )

    monkeypatch.setattr("portable_kb.cli.publish_brain_to_github", published)
    result = runner.invoke(
        app,
        ["brain", "init", "--config", str(config), "--as-of", "2026-08-13"],
    )

    assert result.exit_code == 0, result.output
    assert "Initialized locally: Interactive Brain (interactive-brain)" in result.output
    assert "Published to GitHub: acme/interactive-brain" in result.output
    assert (repository / "brain.yaml").is_file()


def test_brain_init_keeps_local_result_when_explicit_publication_fails(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "config.yaml"
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    save_settings(settings, config)
    repository = tmp_path / "publication-fails"

    def failed(*_args, **_kwargs):
        raise BrainError("simulated GitHub failure")

    monkeypatch.setattr("portable_kb.cli.publish_brain_to_github", failed)
    result = runner.invoke(
        app,
        [
            "brain",
            "init",
            str(repository),
            "--name",
            "Publication Fails",
            "--slug",
            "publication-fails",
            "--publish-to",
            "acme/publication-fails",
            "--config",
            str(config),
            "--as-of",
            "2026-08-13",
        ],
    )

    assert result.exit_code == 1
    assert "Local brain is ready" in result.output
    assert "Retry later" in result.output
    assert (repository / "brain.yaml").is_file()
    assert load_catalog(settings).get("publication-fails").source == str(repository)

    conflicting = runner.invoke(
        app,
        [
            "brain",
            "init",
            str(tmp_path / "conflict"),
            "--name",
            "Conflict",
            "--slug",
            "conflict",
            "--publish-to",
            "acme/conflict",
            "--no-publish",
            "--config",
            str(config),
        ],
    )
    assert conflicting.exit_code == 2
    assert "cannot be used together" in conflicting.output


def test_search_cli_indexes_and_returns_json_citations(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd: tuple[Path, Path, Path],
) -> None:
    executable, _log, results_file = fake_qmd
    config = tmp_path / "config.yaml"
    settings = Settings(
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        qmd_command=str(executable),
    )
    save_settings(settings, config)
    source = brain_repo_factory(
        "cli-search",
        "urn:uuid:66666666-6666-4666-8666-666666666666",
    )
    added = runner.invoke(
        app,
        ["brain", "add", str(source), "--config", str(config), "--as-of", "2026-08-12"],
    )
    assert added.exit_code == 0, added.output

    indexed = runner.invoke(
        app,
        ["search", "index", "--config", str(config), "--as-of", "2026-08-12", "--json"],
    )
    assert indexed.exit_code == 0, indexed.output
    index_payload = json.loads(indexed.output)
    concept = discover_concepts(settings.data_dir / "brains/cli-search/knowledge")[0]
    relative = concept.relative_to(settings.data_dir / "brains/cli-search/knowledge").as_posix()
    results_file.write_text(
        json.dumps(
            [
                {
                    "score": 0.75,
                    "file": f"qmd://cli-search/{relative}",
                    "title": "CLI result",
                }
            ]
        ),
        encoding="utf-8",
    )
    queried = runner.invoke(
        app,
        [
            "search",
            "query",
            "portable",
            "--config",
            str(config),
            "--as-of",
            "2026-08-12",
            "--json",
        ],
    )
    assert queried.exit_code == 0, queried.output
    query_payload = json.loads(queried.output)
    assert query_payload["index_commit"] == index_payload["commit"]
    assert query_payload["results"][0]["citation"]["path"] == relative

    human_index = runner.invoke(
        app,
        ["search", "index", "--config", str(config), "--as-of", "2026-08-12"],
    )
    assert human_index.exit_code == 0, human_index.output
    assert "Search mode: keyword (no models downloaded)" in human_index.output
    human_query = runner.invoke(
        app,
        [
            "search",
            "query",
            "portable",
            "--config",
            str(config),
            "--as-of",
            "2026-08-12",
        ],
    )
    assert human_query.exit_code == 0, human_query.output
    assert "CLI result" in human_query.output
    assert relative in human_query.output

    retrieved = runner.invoke(
        app,
        [
            "get",
            relative,
            "--config",
            str(config),
            "--as-of",
            "2026-08-12",
            "--json",
        ],
    )
    assert retrieved.exit_code == 0, retrieved.output
    retrieved_payload = json.loads(retrieved.output)
    assert retrieved_payload["citation"]["path"] == relative
    assert retrieved_payload["item"]["body"]
    human_get = runner.invoke(
        app,
        ["get", relative, "--config", str(config), "--as-of", "2026-08-12"],
    )
    assert human_get.exit_code == 0, human_get.output
    assert "Citation: cli-search@" in human_get.output
    assert retrieved_payload["item"]["id"] in human_get.output


def test_skill_install_cli(monkeypatch) -> None:
    def installed(target, *, force=False):
        return {
            "skill": "portable-kb",
            "targets": {target.value: f"/tmp/{target.value}/portable-kb"},
            "forced": force,
            "ok": True,
        }

    monkeypatch.setattr("portable_kb.cli.install_agent_skill", installed)
    result = runner.invoke(
        app,
        ["skill", "install", "--target", "codex", "--force", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["targets"]["codex"] == "/tmp/codex/portable-kb"
    assert payload["forced"] is True

    human = runner.invoke(app, ["skill", "install", "--target", "claude"])
    assert human.exit_code == 0, human.output
    assert "Installed Portable KB agent skill" in human.output

    def failed(target, *, force=False):
        raise SkillError("cannot install skill")

    monkeypatch.setattr("portable_kb.cli.install_agent_skill", failed)
    error = runner.invoke(app, ["skill", "install"])
    assert error.exit_code == 1
    assert "cannot install skill" in error.output
