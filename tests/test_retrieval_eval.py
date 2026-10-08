from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from typer.testing import CliRunner

from portable_kb import retrieval_eval
from portable_kb.brains import add_brain
from portable_kb.cli import app
from portable_kb.retrieval_eval import (
    EvaluationError,
    evaluate_retrieval,
    load_evaluation_labels,
    score_ranking,
)
from portable_kb.search import index_keyword_brain, search_keyword
from portable_kb.settings import Settings, save_settings

LABELS = Path(__file__).parent / "fixtures/retrieval/reference-labels.json"
REVIEW = "urn:uuid:0adaf3c7-c3e0-4cdc-85f4-90438dd72020"
MOVE = "urn:uuid:b789bfab-271e-462d-bf06-ae61af138dee"


def test_metrics_penalize_duplicate_hits_and_missing_slots() -> None:
    scores = score_ranking(["unjudged", REVIEW, REVIEW, MOVE], {REVIEW: 3, MOVE: 1})
    assert scores["precision_at_5"] == 2 / 5
    assert scores["recall_at_10"] == 1
    assert scores["reciprocal_rank_at_10"] == 1 / 2
    assert scores["ndcg_at_10"] == pytest.approx(
        (7 / math.log2(3) + 1 / math.log2(5)) / (7 + 1 / math.log2(3)),
    )
    assert score_ranking([], {REVIEW: 3}) == {
        "precision_at_5": 0,
        "recall_at_10": 0,
        "reciprocal_rank_at_10": 0,
        "ndcg_at_10": 0,
    }
    assert score_ranking([], {}) == {"no_result_correct": True}
    assert score_ranking([REVIEW], {}) == {"no_result_correct": False}
    assert score_ranking(["miss"] * 10 + [REVIEW], {REVIEW: 3})["recall_at_10"] == 0


@pytest.mark.parametrize("change", ["version", "duplicate-id", "bad-grade", "bad-uuid", "query"])
def test_labels_fail_closed(tmp_path: Path, change: str) -> None:
    payload = json.loads(LABELS.read_text())
    if change == "version":
        payload["schema_version"] = True
    elif change == "duplicate-id":
        payload["queries"].append(payload["queries"][0])
    elif change == "bad-grade":
        payload["queries"][0]["relevance"][REVIEW] = True
    elif change == "bad-uuid":
        payload["queries"][0]["relevance"] = {"urn:uuid:wrong": 3}
    else:
        payload["queries"][0]["query"] = "\x00"
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(EvaluationError):
        load_evaluation_labels(path)


def test_duplicate_json_fields_are_not_silently_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "labels.json"
    path.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(EvaluationError, match="Duplicate label field"):
        load_evaluation_labels(path)


def _indexed(tmp_path: Path, brain_repo_factory, fake_qmd) -> Settings:
    settings = Settings(
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        qmd_command=str(fake_qmd[0]),
    )
    source = brain_repo_factory("evaluation", "urn:uuid:88888888-8888-4888-8888-888888888888")
    add_brain(str(source), settings, as_of="2026-08-17")
    index_keyword_brain(settings, as_of="2026-08-17")
    return settings


def test_evaluation_reports_metrics_and_preserves_existing_index(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _indexed(tmp_path, brain_repo_factory, fake_qmd)
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "small",
                "queries": [
                    {"id": "review", "query": "stale review", "relevance": {REVIEW: 3}},
                    {"id": "negative", "query": "absent", "relevance": {}},
                ],
            }
        )
    )
    before = {
        str(path): path.read_bytes()
        for root in (settings.data_dir, settings.cache_dir)
        for path in root.rglob("*")
        if path.is_file()
    }

    def query(settings, text, slug, **kwargs):
        fake_qmd[2].write_text(
            json.dumps(
                []
                if text == "absent"
                else [
                    {
                        "file": "qmd://evaluation/procedures/review-stale-knowledge.md",
                        "title": "Review",
                        "score": 0.8,
                    }
                ]
            )
        )
        return search_keyword(settings, text, slug, **kwargs)

    monkeypatch.setattr(retrieval_eval, "search_keyword", query)
    report = evaluate_retrieval(settings, labels, as_of="2026-08-17", repeat=2)
    assert report["metrics"] == {
        "precision_at_5": 0.2,
        "recall_at_10": 1,
        "reciprocal_rank_at_10": 1,
        "ndcg_at_10": 1,
        "no_result_accuracy": 1,
    }
    assert report["ranking_stable"] is True
    assert report["citation_correctness"] == 1
    assert report["checked_result_count"] == 2
    assert report["dataset"]["sha256"] == load_evaluation_labels(labels).sha256
    assert report["index_metadata"]["qmd_version"] == "qmd 2.5.3"
    assert report["latency"]["first_pass_ms"]["count"] == 2
    assert report["latency"]["repeat_pass_ms"]["count"] == 2
    after = {
        str(path): path.read_bytes()
        for root in (settings.data_dir, settings.cache_dir)
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_evaluation_rejects_labels_missing_from_brain_before_querying(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd,
) -> None:
    settings = _indexed(tmp_path, brain_repo_factory, fake_qmd)
    labels = tmp_path / "labels.json"
    payload = json.loads(LABELS.read_text())
    payload["queries"][0]["relevance"] = {"urn:uuid:00000000-0000-4000-8000-000000000000": 3}
    labels.write_text(json.dumps(payload))
    before = fake_qmd[1].read_bytes()
    with pytest.raises(EvaluationError, match="absent from the pinned brain"):
        evaluate_retrieval(settings, labels, as_of="2026-08-17")
    assert fake_qmd[1].read_bytes() == before


@pytest.mark.parametrize("fault", ["citation", "commit"])
def test_evaluation_rejects_incorrect_citations_and_changed_commit(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    settings = _indexed(tmp_path, brain_repo_factory, fake_qmd)
    fake_qmd[2].write_text(
        json.dumps(
            [
                {
                    "file": "qmd://evaluation/procedures/review-stale-knowledge.md",
                    "title": "Review",
                    "score": 0.8,
                }
            ]
        )
    )

    def query(settings, text, slug, **kwargs):
        result = search_keyword(settings, text, slug, **kwargs)
        if fault == "citation":
            result["results"][0]["citation"]["path"] = "wrong.md"
        else:
            result["brain"]["commit"] = "a" * 40
        return result

    monkeypatch.setattr(retrieval_eval, "search_keyword", query)
    with pytest.raises(EvaluationError, match="incorrect|changed"):
        evaluate_retrieval(settings, LABELS, as_of="2026-08-17")


def test_evaluation_cli_emits_report_and_requires_date(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd,
) -> None:
    settings = _indexed(tmp_path, brain_repo_factory, fake_qmd)
    config = save_settings(settings, tmp_path / "config.yaml")
    runner = CliRunner()
    arguments = ["search", "evaluate", str(LABELS), "--config", str(config)]
    assert runner.invoke(app, arguments).exit_code == 2
    result = runner.invoke(app, [*arguments, "--as-of", "2026-08-17", "--repeat", "1"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["query_count"] == 7
    assert report["ranking_stable"] is None
    assert report["latency"]["repeat_pass_ms"]["count"] == 0
    assert report["metrics"]["recall_at_10"] == 0
    assert report["metrics"]["no_result_accuracy"] == 1
    assert report["citation_correctness"] is None


def test_evaluation_reports_changed_rankings_without_changing_judgments(
    tmp_path: Path,
    brain_repo_factory,
    fake_qmd,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _indexed(tmp_path, brain_repo_factory, fake_qmd)
    calls = 0

    def query(settings, text, slug, **kwargs):
        nonlocal calls
        calls += 1
        rows = [
            {
                "file": "qmd://evaluation/procedures/review-stale-knowledge.md",
                "title": "Review",
                "score": 0.8,
            },
            {
                "file": "qmd://evaluation/procedures/move-knowledge-item.md",
                "title": "Move",
                "score": 0.8,
            },
        ]
        fake_qmd[2].write_text(json.dumps(rows if calls % 2 else list(reversed(rows))))
        return search_keyword(settings, text, slug, **kwargs)

    monkeypatch.setattr(retrieval_eval, "search_keyword", query)
    report = evaluate_retrieval(settings, LABELS, as_of="2026-08-17", repeat=2)
    assert report["ranking_stable"] is False
    assert all(row["ranking_stable"] is False for row in report["queries"])
    assert report["checked_result_count"] == 28
    assert report["metrics"]["no_result_accuracy"] == 0
    assert report["queries"][0]["relevance"] == {REVIEW: 3}
