from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from benchmarks.common import query_parts, records_from
from benchmarks.corpus import export_brain, synthetic_corpus
from benchmarks.search import Worker, run_benchmark
from portable_kb.brains import add_brain
from portable_kb.settings import Settings, save_settings


@pytest.fixture(params=["sqlite", "tantivy"])
def engine_worker(request):
    if request.param == "sqlite":
        command = [sys.executable, "-m", "benchmarks.sqlite_fts5"]
    else:
        executable = os.environ.get("PKB_TANTIVY_COMMAND")
        if not executable:
            pytest.skip("set PKB_TANTIVY_COMMAND to exercise the Rust prototype")
        command = [executable]
    worker = Worker(command)
    try:
        yield worker
    finally:
        worker.close()


def test_literal_unicode_queries_exact_ids_filters_and_stable_ties(tmp_path, engine_worker):
    synthetic_corpus(tmp_path / "corpus", 16)
    records_path = tmp_path / "corpus/records.jsonl"
    records = list(records_from(records_path))
    destination = tmp_path / "index"
    result = engine_worker.call(
        {"op": "build", "index_path": str(destination), "records_path": str(records_path)}
    )
    assert result["result"]["record_count"] == 32

    def query(text, filters=None):
        tokens, exact = query_parts(text)
        return engine_worker.call(
            {
                "op": "query",
                "index_path": str(destination),
                "query": text,
                "tokens": tokens,
                "exact_field": exact,
                "filters": filters or {},
                "limit": 10,
            }
        )["result"]["hits"]

    spanish = records[2:4]
    assert query("Aurora000001 Pasos autorizacion")[0]["section_id"] == spanish[0]["section_id"]
    assert [hit["section_id"] for hit in query(spanish[0]["path"])] == [
        record["section_id"] for record in spanish
    ]
    assert [hit["section_id"] for hit in query(spanish[0]["item_id"])] == [
        record["section_id"] for record in spanish
    ]
    assert query(spanish[0]["item_id"], {"status": "draft"}) == []
    assert query(spanish[0]["item_id"], {"type": "concept"}) == []
    assert query("zxqvnotincorpus92817") == []
    assert query("Aurora000001 Recuperación") == query("Aurora000001 Recuperación")
    with pytest.raises(ValueError, match="literal"):
        engine_worker.call(
            {
                "op": "query",
                "index_path": str(destination),
                "query": "unsafe",
                "tokens": ['foo" OR bar'],
                "limit": 10,
            }
        )
    with pytest.raises(ValueError, match="protocol"):
        engine_worker.call({"op": "status", "protocol_version": 2})


def test_failed_and_repeated_builds_cannot_overwrite_previous_index(tmp_path, engine_worker):
    synthetic_corpus(tmp_path / "corpus", 16)
    records = tmp_path / "corpus/records.jsonl"
    index = tmp_path / "index"
    engine_worker.call({"op": "build", "index_path": str(index), "records_path": str(records)})
    before = {str(path): path.read_bytes() for path in index.rglob("*") if path.is_file()}
    records.write_text("broken JSON\n")
    with pytest.raises(ValueError):
        engine_worker.call({"op": "build", "index_path": str(index), "records_path": str(records)})
    assert before == {str(path): path.read_bytes() for path in index.rglob("*") if path.is_file()}
    with pytest.raises(ValueError):
        engine_worker.call(
            {
                "op": "build",
                "index_path": str(tmp_path / "incomplete"),
                "records_path": str(records),
            }
        )
    response = engine_worker.call(
        {
            "op": "query",
            "index_path": str(index),
            "query": "Aurora000000",
            "tokens": ["Aurora000000"],
            "limit": 10,
        }
    )
    assert response["result"]["hits"]


def test_synthetic_export_is_reproducible_and_honest_about_origin(tmp_path):
    synthetic_corpus(tmp_path / "a", 16)
    synthetic_corpus(tmp_path / "b", 16)
    assert (tmp_path / "a/records.jsonl").read_bytes() == (
        tmp_path / "b/records.jsonl"
    ).read_bytes()
    assert (tmp_path / "a/queries.json").read_bytes() == (tmp_path / "b/queries.json").read_bytes()
    assert json.loads((tmp_path / "a/corpus.json").read_text())["commit"] is None
    assert all(record["commit"] is None for record in records_from(tmp_path / "a/records.jsonl"))
    with pytest.raises(FileExistsError):
        synthetic_corpus(tmp_path / "a", 16)
    with pytest.raises(ValueError):
        synthetic_corpus(tmp_path / "small", 1)


def test_shared_benchmark_report_citations_and_corpus_fingerprint(tmp_path):
    corpus = tmp_path / "corpus"
    synthetic_corpus(corpus, 16)
    report = run_benchmark(corpus, tmp_path / "results", tantivy=None, qmd=None, repeat=2)
    provider = report["providers"]["sqlite-fts5"]
    assert provider["ranking_stable"] is True
    assert provider["section_metrics"]["recall_at_10"] == pytest.approx(12 / 13)
    assert provider["section_metrics"]["no_result_accuracy"] == 1
    assert provider["latency"]["repeat_engine_query_ms"]["count"] == 15
    record_map = {record["section_id"]: record for record in records_from(corpus / "records.jsonl")}
    for query in provider["queries"]:
        for citation in query["citations"]:
            assert citation == {key: record_map[citation["section_id"]][key] for key in citation}
    (corpus / "records.jsonl").write_text("changed\n")
    with pytest.raises(ValueError, match="fingerprint"):
        run_benchmark(corpus, tmp_path / "bad", tantivy=None, qmd=None, repeat=2)


def test_real_brain_export_uses_validation_and_unambiguous_section_labels(
    tmp_path, brain_repo_factory
):
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    source = brain_repo_factory("reference", "urn:uuid:88888888-8888-4888-8888-888888888888")
    add_brain(str(source), settings, as_of="2026-08-17")
    config = save_settings(settings, tmp_path / "config.yaml")
    labels = Path(__file__).parent / "fixtures/retrieval/reference-labels.json"
    sections = labels.with_name("reference-sections.json")
    destination = Path(os.environ.get("PKB_BENCHMARK_REFERENCE_EXPORT", tmp_path / "export"))
    export_brain(config, None, "2026-08-17", labels, sections, destination)
    manifest = json.loads((destination / "corpus.json").read_text())
    assert manifest["origin"] == "git-brain"
    assert len(manifest["commit"]) == 40
    assert manifest["item_count"] == 14
    assert manifest["record_count"] > 14
    judgments = json.loads(sections.read_text())
    judgments["stale-review"][0]["heading"] = "Absent"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(judgments))
    with pytest.raises(ValueError, match="ambiguous"):
        export_brain(config, None, "2026-08-17", labels, bad, tmp_path / "invalid-export")
    installed = settings.data_dir / "brains/reference/knowledge/extra.md"
    installed.write_text("dirty")
    with pytest.raises(RuntimeError, match="not clean"):
        export_brain(config, None, "2026-08-17", labels, sections, tmp_path / "dirty-export")
