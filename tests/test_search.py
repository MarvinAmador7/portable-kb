from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from portable_kb.brains import add_brain, sync_brain
from portable_kb.parsing import discover_concepts, parse_concept
from portable_kb.search import (
    SearchError,
    get_knowledge_item,
    index_keyword_brain,
    qmd_status,
    search_keyword,
)
from portable_kb.settings import Settings


def _installed_settings(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd: tuple[Path, Path, Path],
) -> tuple[Settings, Path]:
    executable, _log, _results = fake_qmd
    settings = Settings(
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        qmd_command=str(executable),
    )
    source = brain_repo_factory(
        "search-brain",
        "urn:uuid:55555555-5555-4555-8555-555555555555",
    )
    add_brain(str(source), settings, as_of="2026-08-12")
    return settings, source


def test_keyword_index_and_search_return_pinned_citations(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd: tuple[Path, Path, Path],
) -> None:
    settings, _source = _installed_settings(tmp_path, brain_repo_factory, fake_qmd)
    _executable, log, results_file = fake_qmd
    brain_path = settings.data_dir / "brains" / "search-brain"
    concept_path = discover_concepts(brain_path / "knowledge")[0]
    relative = concept_path.relative_to(brain_path / "knowledge").as_posix()
    item = parse_concept(concept_path, brain_path / "knowledge").item
    assert item is not None
    results_file.write_text(
        json.dumps(
            [
                {
                    "docid": "#abc123",
                    "score": 0.87,
                    "file": f"qmd://search-brain/{relative}",
                    "line": 12,
                    "title": "Portable result",
                    "snippet": "A grounded keyword result.",
                    "context": "Search brain context",
                }
            ]
        ),
        encoding="utf-8",
    )

    indexed = index_keyword_brain(settings, as_of="2026-08-12")
    assert indexed["mode"] == "keyword"
    assert indexed["concept_count"] == len(discover_concepts(brain_path / "knowledge"))
    state = Path(indexed["index_path"])
    assert (state / "cache/qmd/index.sqlite").is_file()
    config = (state / "config/index.yml").read_text(encoding="utf-8")
    assert "update:" not in config
    assert "**/index.md" in config
    assert not (state / "cache/qmd/models").exists()

    found = search_keyword(settings, "portable knowledge", limit=5, as_of="2026-08-12")
    assert found["mode"] == "keyword"
    assert found["index_commit"] == indexed["commit"]
    assert len(found["results"]) == 1
    result = found["results"][0]
    assert result["item_id"] == item.id
    assert result["path"] == relative
    assert result["citation"] == {
        "brain_id": indexed["brain_id"],
        "brain_slug": "search-brain",
        "commit": indexed["commit"],
        "item_id": item.id,
        "path": relative,
    }
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [call["arguments"][0] for call in calls] == [
        "--version",
        "update",
        "--version",
        "search",
    ]
    assert all(call["force_cpu"] == "1" and call["index_path"] is None for call in calls)
    assert all(str(settings.cache_dir / "search/qmd") in call["config_dir"] for call in calls)


def test_keyword_search_refuses_missing_stale_and_unsafe_results(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd: tuple[Path, Path, Path],
) -> None:
    settings, source = _installed_settings(tmp_path, brain_repo_factory, fake_qmd)
    _executable, _log, results_file = fake_qmd
    with pytest.raises(SearchError, match="missing"):
        search_keyword(settings, "knowledge", as_of="2026-08-12")

    index_keyword_brain(settings, as_of="2026-08-12")
    results_file.write_text(
        json.dumps(
            [
                {
                    "score": 0.5,
                    "file": "qmd://search-brain/../brain.yaml",
                    "title": "Unsafe",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(SearchError, match="unsafe"):
        search_keyword(settings, "knowledge", as_of="2026-08-12")

    manifest = source / "brain.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("name: Search Brain", "name: Search Brain 2"),
        encoding="utf-8",
    )
    _git(source, "add", "brain.yaml")
    _git(source, "commit", "--quiet", "-m", "Update searchable brain")
    sync_brain(settings, as_of="2026-08-12")
    with pytest.raises(SearchError, match="stale"):
        search_keyword(settings, "knowledge", as_of="2026-08-12")


def test_failed_reindex_preserves_previous_index(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _source = _installed_settings(tmp_path, brain_repo_factory, fake_qmd)
    first = index_keyword_brain(settings, as_of="2026-08-12")
    metadata_path = Path(first["index_path"]) / "metadata.json"
    previous = metadata_path.read_bytes()
    monkeypatch.setenv("FAKE_QMD_FAIL_UPDATE", "1")
    with pytest.raises(SearchError, match="simulated update failure"):
        index_keyword_brain(settings, as_of="2026-08-12")
    assert metadata_path.read_bytes() == previous


def test_keyword_query_validation(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    with pytest.raises(SearchError, match="1-1000"):
        search_keyword(settings, "   ")
    with pytest.raises(SearchError, match="between 1 and 100"):
        search_keyword(settings, "query", limit=0)


@pytest.mark.parametrize(
    ("version", "ok", "error_fragment"),
    [
        ("qmd 2.5.0", True, None),
        ("qmd 2.4.9", False, "outside the supported range"),
        ("qmd 3.0.0", False, "outside the supported range"),
        ("development build", False, "unrecognized"),
    ],
)
def test_qmd_status_reports_version_compatibility(
    tmp_path: Path,
    version: str,
    ok: bool,
    error_fragment: str | None,
) -> None:
    executable = tmp_path / "qmd-version"
    executable.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
    executable.chmod(0o755)
    settings = Settings(
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        qmd_command=str(executable),
    )

    result = qmd_status(settings)

    assert result["ok"] is ok
    assert result["compatible"] is ok
    if error_fragment is not None:
        assert error_fragment in result["error"]


def test_qmd_status_reports_missing_executable(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        qmd_command=str(tmp_path / "missing-qmd"),
    )

    result = qmd_status(settings)

    assert result["ok"] is False
    assert "not found" in result["error"]


def test_get_knowledge_item_by_id_and_path(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd: tuple[Path, Path, Path],
) -> None:
    settings, _source = _installed_settings(tmp_path, brain_repo_factory, fake_qmd)
    bundle = settings.data_dir / "brains/search-brain/knowledge"
    concept = discover_concepts(bundle)[0]
    parsed = parse_concept(concept, bundle).item
    assert parsed is not None and parsed.id is not None

    by_id = get_knowledge_item(settings, parsed.id, as_of="2026-08-12")
    relative = concept.relative_to(bundle).as_posix()
    assert by_id["item"]["path"] == relative
    assert by_id["item"]["metadata"]["id"] == parsed.id
    assert by_id["item"]["body"] == parsed.body
    assert by_id["item"]["content"] == parsed.source_text
    assert by_id["citation"]["commit"] == by_id["brain"]["commit"]

    by_path = get_knowledge_item(settings, f"knowledge/{relative}", as_of="2026-08-12")
    assert by_path["item"]["id"] == parsed.id


def test_get_knowledge_item_rejects_missing_and_reserved_paths(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd: tuple[Path, Path, Path],
) -> None:
    settings, _source = _installed_settings(tmp_path, brain_repo_factory, fake_qmd)
    with pytest.raises(SearchError, match="not found"):
        get_knowledge_item(
            settings,
            "urn:uuid:00000000-0000-4000-8000-000000000000",
            as_of="2026-08-12",
        )
    with pytest.raises(SearchError, match="unsafe, reserved"):
        get_knowledge_item(settings, "../brain.yaml", as_of="2026-08-12")
    with pytest.raises(SearchError, match="unsafe, reserved"):
        get_knowledge_item(settings, "index.md", as_of="2026-08-12")


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
