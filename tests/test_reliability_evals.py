from __future__ import annotations

import cProfile
import json
import os
import signal
import subprocess
import sys
import time

import pytest

from evals.logistics.oracle import CORRECTION
from evals.reliability.faults import compile_stop_library
from evals.reliability.grading import durations, saved_duration_searchable
from evals.reliability.harness import compare
from evals.reliability.profiling import profile_summary
from evals.reliability.scenarios import scenarios


def test_duration_labels_do_not_confuse_current_and_history():
    body = "## Definition\nCurrent contract retention is 7 days.\n\n## Retention history\nMistaken duration was 21 days.\n"
    assert durations(body, 7, 21)
    assert not durations(body, 21, 7)
    assert not durations(
        body.replace("Retention history", "Examples").replace("Mistaken", "Example"), 7, 21
    )
    assert not durations(body.replace("7 days", "17 days"), 7, 21)


def test_native_rollback_search_requires_saved_current_citation_and_index_order():
    citation = {"path": "inbox/" + CORRECTION, "commit": "current", "item_id": "uuid"}
    pages = {
        CORRECTION: {
            "item": {"body": "## Definition\nCurrent retention is 7 days.\n"},
            "citation": citation,
        }
    }
    save = {"argv": ["knowledge", "update", "--apply"], "exit_code": 0, "completed_ns": 100}
    index = {
        "argv": ["search", "index", "atlas-logistics"],
        "exit_code": 0,
        "started_ns": 101,
        "completed_ns": 110,
    }
    hit = {
        "path": citation["path"],
        "citation": citation,
        "snippet": "Current retention is 7 days.",
    }
    query = {
        "argv": ["search", "query", "Lumen retention"],
        "exit_code": 0,
        "started_ns": 111,
        "stdout": json.dumps({"results": [hit]}),
    }
    assert saved_duration_searchable("portable-kb", [], [save, index, query], pages, 7)
    assert not saved_duration_searchable("portable-kb", [], [index, query], pages, 7)
    index["started_ns"] = 99
    assert not saved_duration_searchable("portable-kb", [], [save, index, query], pages, 7)
    index["started_ns"] = 101
    query["stdout"] = json.dumps(
        {"results": [{**hit, "citation": {**citation, "commit": "stale"}}]}
    )
    assert not saved_duration_searchable("portable-kb", [], [save, index, query], pages, 7)


def test_wiki_search_requires_final_current_line_not_only_historical_value():
    body = "## Definition\nCurrent retention is 7 days.\n\n## Retention history\nPrevious retention was 21 days.\n"
    pages = {CORRECTION: {"body": body}}
    event = {
        "command": f"rg retention wiki/{CORRECTION}",
        "exit_code": 0,
        "aggregated_output": "Previous retention was 21 days.",
    }
    assert not saved_duration_searchable("wiki", [event], [], pages, 7)
    event["aggregated_output"] = "Current retention is 7 days."
    assert saved_duration_searchable("wiki", [event], [], pages, 7)


def test_profile_categories_are_exclusive():
    profile = cProfile.Profile()
    profile.runcall(lambda: json.dumps(list(range(100))))
    result = profile_summary(profile)
    assert sum(result["exclusive_categories"].values()) == pytest.approx(
        result["exclusive_seconds"]
    )
    assert sum(result["exclusive_category_fraction"].values()) == pytest.approx(1)
    assert result["parse_calls"] == 0


def test_reliability_comparison_rejects_different_faults_before_pairing(tmp_path):
    manifest = {
        "kind": "reliability",
        "reliability_version": 1,
        "fault_library_sha256": "one",
        "parent_manifest_sha256": "same",
    }
    wiki = {"manifest": manifest}
    native = {"manifest": {**manifest, "fault_library_sha256": "two"}}
    with pytest.raises(ValueError, match="fault inputs"):
        compare(wiki, native, tmp_path / "result.json")


@pytest.mark.skipif(sys.platform != "linux", reason="Linux real rename fault")
def test_real_rename_fault_stops_only_after_destination_exists(tmp_path):
    import shutil

    if not shutil.which("cc"):
        pytest.skip("C compiler required")
    library = compile_stop_library(tmp_path / "fault-tools")
    source, dest, marker = (tmp_path / name for name in ("source.md", "destination.md", "marker"))
    source.write_text("real bytes\n")
    env = {
        **os.environ,
        "LD_PRELOAD": str(library),
        "KB_EVAL_STOP_DEST": str(dest),
        "KB_EVAL_STOP_MARKER": str(marker),
    }
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os,sys;os.replace(sys.argv[1],sys.argv[2])",
            str(source),
            str(dest),
        ],
        env=env,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists()
        assert dest.read_text() == "real bytes\n"
        assert not source.exists()
        assert child.poll() is None
        os.killpg(child.pid, signal.SIGKILL)
        assert child.wait(timeout=5) == -signal.SIGKILL
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)


def test_recovery_requests_explicitly_match_controller_and_user_intent():
    taskset = scenarios()
    assert len(taskset) == 4
    assert "kb-fault checkpoint" in taskset["concurrent-update"]["request"]
    assert "checkpoint" not in taskset["rollback-amendment"]["request"]
    assert taskset["stale-citation"]["writes"] == []
    assert "Portable KB arm only" in taskset["interrupted-move"]["request"]


def test_wiki_copied_evidence_can_be_renamed_but_not_changed_or_escape_raw(tmp_path):
    from evals.agent_cli.harness import digest
    from evals.reliability.grading import source_evidence_recorded, wiki_allowed_changes

    evidence = tmp_path / "work/evidence/rollback.md"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("Original authorization\n")
    raw = tmp_path / "work/wiki/raw/lumen-rollback.md"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(evidence.read_bytes())
    page = {"metadata": {"sources": ["raw/lumen-rollback.md"]}}
    assert source_evidence_recorded(tmp_path, page, "rollback.md", "wiki")
    initial = {
        "links": [],
        "evidence": {"rollback.md": digest(evidence)},
        "snapshots": {"primary": {"account.md": "old", "raw/existing.md": "old"}},
    }
    state = {
        "snapshots": {
            "primary": {
                "account.md": "new",
                "raw/existing.md": "old",
                "raw/lumen-rollback.md": digest(raw),
            }
        }
    }
    task = {"writes": ["account.md"]}
    assert wiki_allowed_changes(initial, state, task)
    state["snapshots"]["primary"]["raw/existing.md"] = digest(raw)
    assert not wiki_allowed_changes(initial, state, task)
    state["snapshots"]["primary"]["raw/existing.md"] = "old"
    raw.write_text("Altered authorization\n")
    state["snapshots"]["primary"]["raw/lumen-rollback.md"] = digest(raw)
    assert not source_evidence_recorded(tmp_path, page, "rollback.md", "wiki")
    assert not wiki_allowed_changes(initial, state, task)
    page["metadata"]["sources"] = ["raw/../../evidence/rollback.md"]
    assert not source_evidence_recorded(tmp_path, page, "rollback.md", "wiki")
    assert not wiki_allowed_changes(initial, state, {"writes": []})
