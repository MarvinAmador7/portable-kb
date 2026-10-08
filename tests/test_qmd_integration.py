from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from portable_kb.brains import add_brain
from portable_kb.retrieval_eval import evaluate_retrieval
from portable_kb.search import index_keyword_brain, qmd_status, search_keyword
from portable_kb.settings import Settings


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("PKB_REAL_QMD") != "1",
    reason="set PKB_REAL_QMD=1 to exercise the installed QMD executable",
)
def test_real_qmd_keyword_adapter(tmp_path: Path, brain_repo_factory) -> None:
    settings = Settings(
        data_dir=tmp_path / "data", cache_dir=tmp_path / "cache",
        qmd_command=os.environ.get("PKB_QMD_COMMAND", "qmd"),
    )
    source = brain_repo_factory(
        "real-qmd",
        "urn:uuid:88888888-8888-4888-8888-888888888888",
    )
    add_brain(str(source), settings, as_of="2026-08-17")

    executable = qmd_status(settings)
    assert executable["ok"] is True, executable
    indexed = index_keyword_brain(settings, as_of="2026-08-17")
    result = search_keyword(settings, "review stale knowledge", as_of="2026-08-17")

    assert indexed["provider"] == "qmd"
    assert indexed["concept_count"] > 0
    assert result["results"]
    assert any(
        item["path"] == "procedures/review-stale-knowledge.md"
        for item in result["results"]
    )
    assert all(item["citation"]["commit"] == indexed["commit"] for item in result["results"])

    labels = Path(__file__).parent / "fixtures/retrieval/reference-labels.json"
    report = evaluate_retrieval(settings, labels, as_of="2026-08-17", repeat=2)
    assert report["query_count"] == 7
    assert report["citation_correctness"] == 1
    assert report["ranking_stable"] is True
    assert report["metrics"]["no_result_accuracy"] == 1
    report_path = Path(os.environ.get("PKB_QMD_EVALUATION_REPORT", tmp_path / "qmd-evaluation.json"))
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
