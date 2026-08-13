from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from portable_kb.cli import app
from portable_kb.parsing import discover_concepts
from portable_kb.settings import SearchMode, Settings, load_settings, save_settings

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
