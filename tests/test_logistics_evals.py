from __future__ import annotations

import json
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator

from evals.logistics.grading import allowed_changes, citation_matches, documents_read, score_fact
from evals.logistics.harness import compare, generate, prepare
from evals.logistics.oracle import MOVE_FROM, downstream, final_schema, retention, route, tasks
from evals.logistics.world import make_world, pages
from evals.wiki_compare.harness import load_json, wiki_pages
from portable_kb.parsing import discover_concepts, parse_concept


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("atlas") / "frozen"
    generate(root)
    return root


def test_world_oracle_scope_capacity_and_transitive_edges():
    world = make_world()
    assert world == make_world()
    assert len(pages(world)) == 220
    assert retention(world, "northwind") == 30
    assert retention(world, "lumen") == 7
    world["regions"]["eu-west"]["cap_days"] = 100
    assert retention(world, "northwind") == 45
    assert route(world, "northwind", 120, "15:30") == "ridge"
    assert route(world, "northwind", 120, "16:31") is None
    world["warehouses"]["cedar"]["available_units"] = 120
    assert route(world, "northwind", 120, "15:30") == "cedar"
    world["carriers"]["kitefreight"]["cold"] = False
    assert route(world, "northwind", 120, "15:30") == "ridge"
    assert downstream(world, "export-service") == [
        "delivery-hooks",
        "merchant-portal",
        "reporting-api",
        "retention-worker",
    ]
    world["systems"]["shipment-api"]["depends_on"] = ["merchant-portal"]
    assert "shipment-api" in downstream(world, "export-service")


def test_frozen_matched_corpus_valid_unique_and_qualified(corpus):
    manifest = load_json(corpus / "manifest.json")
    assert manifest["documents"] == 220
    assert manifest["warnings"] == 0
    assert manifest["move_callers"] == 10
    assert len(manifest["families"]) == 12
    identities = load_json(corpus / "identities.json")
    assert len(set(identities.values())) == 220
    assert all(UUID(value.removeprefix("urn:uuid:")).version == 4 for value in identities.values())
    wiki = wiki_pages(corpus / "wiki")
    native = corpus / "portable-kb/knowledge"
    for path in discover_concepts(native):
        item = parse_concept(path, native).item
        logical = item.relative_path.removeprefix("inbox/")
        assert item.id == identities[logical]
        assert item.body.replace("[[inbox/", "[[") == wiki[logical]["body"]
        assert item.metadata["x-fixture-seed"] == 20261008
        assert not item.metadata.get("verified")
    assert "Confirmed launch: unknown" in wiki["warehouses/solstice.md"]["body"]
    with pytest.raises(ValueError, match="fresh"):
        generate(corpus)


def test_prepare_rejects_changed_labels_before_running_cli(corpus, tmp_path):
    import shutil

    altered = tmp_path / "altered"
    shutil.copytree(corpus, altered)
    (altered / "retrieval-labels.json").write_text("{}\n")
    cli, skill = tmp_path / "cli", tmp_path / "skill"
    cli.write_text("not executable")
    skill.write_text("test skill")
    with pytest.raises(ValueError, match="changed"):
        prepare(tmp_path / "trial", altered, cli, skill)
    assert not (tmp_path / "trial").exists()


def test_fact_requires_present_null_complete_chain_and_canonical_citations(tmp_path):
    page = {"citation": {"path": "inbox/a.md", "item_id": "uuid", "commit": "a" * 40}}
    citation = {"scope": "primary", **page["citation"]}
    label = {"expected": None, "evidence": ["a.md", "b.md"]}
    pages = {
        "a.md": page,
        "b.md": {"citation": {"path": "inbox/b.md", "item_id": "uuid-b", "commit": "a" * 40}},
    }
    read = dict.fromkeys(pages)
    answer = {"value": None, "citations": [citation]}
    assert not score_fact(answer, label, read, pages, "portable-kb", tmp_path)["grounded"]
    answer["citations"].append({"scope": "primary", **pages["b.md"]["citation"]})
    assert score_fact(answer, label, read, pages, "portable-kb", tmp_path)["passed"]
    assert not score_fact(
        {"citations": answer["citations"]}, label, read, pages, "portable-kb", tmp_path
    )["accurate"]
    assert not score_fact(answer, label, {"a.md": None}, pages, "portable-kb", tmp_path)["grounded"]
    answer["citations"][0]["commit"] = "wrong"
    assert not score_fact(answer, label, read, pages, "portable-kb", tmp_path)["grounded"]
    assert not citation_matches(
        {"scope": "alternate", "path": "a.md"}, "a.md", {}, "wiki", tmp_path
    )


def test_move_permission_does_not_allow_unrelated_pages():
    initial = {
        "links": [{"source": "warehouse.md", "target": MOVE_FROM}],
        "snapshots": {"primary": {"warehouse.md": "old"}},
    }
    task = {"move": True, "writes": [MOVE_FROM, "runbooks/cold-chain-dispatch.md"]}
    state = {"snapshots": {"primary": {"warehouse.md": "new", "index.md": "derived"}}}
    assert allowed_changes(initial, state, task, "wiki")[0]
    state["snapshots"]["primary"]["unrelated.md"] = "new"
    assert not allowed_changes(initial, state, task, "wiki")[0]
    assert not allowed_changes(initial, state, {"writes": []}, "wiki")[0]


def test_saved_navigation_requires_complete_post_move_snapshot():
    document = {
        "document": {"kind": "index", "path": "index.md", "content": "all navigation"},
        "citation": {"brain_slug": "atlas-logistics", "commit": "a" * 40, "path": "index.md"},
    }
    save = {"argv": ["knowledge", "move", "--apply"], "exit_code": 0, "completed_ns": 100}
    read = {
        "argv": ["get", "index.md", "--brain", "atlas-logistics"],
        "exit_code": 0,
        "started_ns": 101,
        "stdout": json.dumps({"ok": True, **document}),
    }
    # Product payload validator expects a real UUID brain_id on document citations.
    document["citation"]["brain_id"] = "urn:uuid:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    read["stdout"] = json.dumps({"ok": True, **document})
    assert documents_read([save, read], {"index.md": document}, ["index.md"])
    read["started_ns"] = 99
    assert not documents_read([save, read], {"index.md": document}, ["index.md"])
    read["started_ns"] = 101
    read["stdout"] = json.dumps(
        {
            "ok": True,
            "document": {**document["document"], "content": "preview"},
            "citation": document["citation"],
        }
    )
    assert not documents_read([save, read], {"index.md": document}, ["index.md"])


def test_final_schema_covers_exact_typed_task_keys():
    for task in tasks(make_world()).values():
        schema = final_schema(task["claims"])
        Draft202012Validator.check_schema(schema)
        final = {
            "outcome": "completed",
            "summary": "test",
            "answers": {
                k: {"value": v["expected"], "citations": []} for k, v in task["claims"].items()
            },
        }
        Draft202012Validator(schema).validate(final)
        final["answers"][next(iter(final["answers"]))]["value"] = {"invalid": True}
        assert list(Draft202012Validator(schema).iter_errors(final))


def test_comparison_rejects_different_worlds_and_grader(tmp_path):
    manifest = dict.fromkeys(
        (
            "version",
            "world_sha256",
            "oracle_sha256",
            "native_sha256",
            "wiki_sha256",
            "cli_sha256",
            "wiki_skill_sha256",
            "repetitions",
        ),
        "same",
    )
    wiki = {
        "manifest": {**manifest, "arm": "wiki"},
        "grader_sha256": "one",
        "cases": [],
        "totals": {},
    }
    native = {**wiki, "manifest": {**manifest, "arm": "portable-kb"}}
    assert compare(wiki, native, tmp_path / "comparison.json")["pairs"] == []
    native["manifest"]["protocol_version"] = 2
    with pytest.raises(ValueError, match="Unmatched"):
        compare(wiki, native, tmp_path / "comparison.json")
    native["manifest"]["protocol_version"] = 1
    native["manifest"]["world_sha256"] = "other"
    with pytest.raises(ValueError, match="Unmatched"):
        compare(wiki, native, tmp_path / "comparison.json")


def test_full_wiki_read_survives_error_for_another_file(tmp_path):
    from evals.logistics.grading import recorded_reads

    content = "---\ntitle: Real page\n---\n\n# Complete evidence\n\nAll substantive content.\n"
    (tmp_path / "events.jsonl").write_text(
        json.dumps(
            {
                "item": {
                    "type": "command_execution",
                    "command": "cat existing.md missing.md",
                    "exit_code": 1,
                    "aggregated_output": content + "cat: missing.md: No such file\n",
                }
            }
        )
        + "\n"
    )
    read, events, _ = recorded_reads(tmp_path, "wiki", {"existing.md": {"content": content}})
    assert "existing.md" in read
    assert events[0]["exit_code"] == 1
    read, _, _ = recorded_reads(
        tmp_path, "wiki", {"existing.md": {"content": content + "unseen\n"}}
    )
    assert not read


def test_initial_retrieval_labels_include_original_moved_identity(corpus):
    from evals.logistics.oracle import retrieval_labels

    identities = load_json(corpus / "identities.json")
    labels = retrieval_labels(make_world(), identities)
    moved = next(q for q in labels["queries"] if q["id"] == "runbook-move")
    assert moved["relevance"] == {identities[MOVE_FROM]: 3}
    assert all(q["relevance"] for q in labels["queries"])


def test_historical_duration_can_be_qualified_by_section_heading():
    from evals.logistics.grading import duration_saved

    text = "## Definition\n\nCurrent recorded export retention is 14 days.\n\n## Retention history\n\nPrevious account evidence, superseded:\n\nRecorded retention is 7 days.\n"
    assert duration_saved(text)
    assert not duration_saved(
        text.replace("14 days", "7 days").replace(
            "retention is 7 days.\n", "retention is 14 days.\n"
        )
    )
    assert not duration_saved(
        "## Definition\n\nCurrent retention is 14 days.\n\n## Examples\n\nAnother client has 7 days.\n"
    )


def test_saved_search_accepts_new_amendment_section_but_rejects_stale_index():
    from evals.logistics.grading import search_verified
    from evals.logistics.oracle import CORRECTION

    citation = {"path": "inbox/" + CORRECTION, "commit": "a" * 40, "item_id": "uuid"}
    pages = {
        CORRECTION: {
            "item": {"body": "## Definition\n\nCurrent contract retention is 14 days.\n"},
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
    result = {
        "path": "inbox/" + CORRECTION,
        "citation": citation,
        "snippet": "## Retention amendment history\n\nPrevious retention was 7 days. The amendment replaces that with 14 days for Lumen only.",
    }
    query = {
        "argv": ["search", "query", "Lumen 14 amendment", "--brain", "atlas-logistics"],
        "exit_code": 0,
        "started_ns": 111,
        "stdout": json.dumps({"results": [result]}),
    }
    assert search_verified("portable-kb", [], [save, index, query], pages)
    index["started_ns"] = 99
    assert not search_verified("portable-kb", [], [save, index, query], pages)
    index["started_ns"] = 101
    query["stdout"] = json.dumps(
        {"results": [{**result, "citation": {**citation, "commit": "old"}}]}
    )
    assert not search_verified("portable-kb", [], [save, index, query], pages)


@pytest.mark.parametrize("value", [12, {}, ["good", {}], ["duplicate", "duplicate"]])
def test_malformed_array_answers_fail_instead_of_crashing(value, tmp_path):
    label = {"expected": ["duplicate"], "evidence": []}
    assert not score_fact({"value": value, "citations": []}, label, {}, {}, "wiki", tmp_path)[
        "accurate"
    ]


def test_runner_dispatch_preserves_requested_parallelism(monkeypatch, tmp_path):
    from evals.logistics import __main__

    calls = []
    monkeypatch.setattr(__main__, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(
        "sys.argv",
        ["logistics", "run", "--output", str(tmp_path), "--jobs", "3", "--timeout", "120"],
    )
    assert __main__.main() == 0
    assert calls == [((tmp_path,), {"runner": "codex", "timeout": 120, "jobs": 3})]
