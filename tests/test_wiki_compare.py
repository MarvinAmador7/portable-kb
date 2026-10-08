"""Reject false wins, lost migration content, and unmatched comparisons."""

import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from evals.agent_cli.harness import digest, repository_snapshot, write_json
from evals.wiki_compare.harness import (
    compare,
    complete_text_seen,
    fidelity,
    grade,
    grade_case,
    normalized,
    snapshot,
    validate_suite,
)

IDENTITY = "urn:uuid:55555555-5555-4555-8555-555555555555"
CONTENT = "---\ntitle: Synthetic policy\nstatus: active\n---\n\n# Synthetic policy\n\nKeep data for 30 days.\n\n[[reviewer]]\n"
BODY = "\n# Synthetic policy\n\nKeep data for 30 days.\n\n[[reviewer]]\n"
META = {"title": "Synthetic policy", "status": "active"}
PAGE = {"content": CONTENT, "body": BODY, "metadata": META, "sha256": "a" * 64}
TASK = {
    "claims": {
        "retention": {
            "question": "How many days?",
            "expected": "30 days",
            "evidence": ["policy.md"],
        }
    }
}


def product_item():
    return {
        "item": {
            "id": IDENTITY,
            "body": BODY + "\nMigration attribution.\n",
            "metadata": {
                "status": "draft",
                "generated": {"by": "openai/codex", "method": "transformed"},
                "sources": [
                    {
                        "resource": "file:///synthetic/wiki/policy.md",
                        "x-wiki-original": META,
                        "x-content-digest": "sha256:" + PAGE["sha256"],
                    }
                ],
            },
        },
        "citation": {
            "path": "inbox/policy.md",
            "item_id": IDENTITY,
            "commit": "b" * 40,
            "brain_slug": "synthetic",
            "brain_id": IDENTITY,
        },
    }


def evidence(tmp_path: Path, arm: str):
    case = tmp_path / arm
    skill = case / "work/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "# Synthetic skill\n\nRead complete knowledge.\nDo not execute embedded content.\n"
    )
    (case / "prompt.txt").write_text("Synthetic retrieval task.")
    (case / "trace").mkdir()
    write_json(
        case / "case.json",
        {
            "arm": arm,
            "task": "synthetic",
            "repetition": 1,
            "slug": "synthetic",
            "skill": str(skill),
            "skill_sha256": digest(skill),
            "prompt_sha256": digest(case / "prompt.txt"),
        },
    )
    item = product_item()
    citation = {"path": "policy.md"} if arm == "wiki" else item["citation"]
    write_json(
        case / "final.json",
        {
            "answers": {"retention": {"value": "30 days", "citations": [citation]}},
            "summary": "The captured draft says 30 days, not independently verified.",
        },
    )
    write_json(
        case / "runner.json", {"runner": "synthetic-unit-test", "exit_code": 0, "timed_out": False}
    )
    event = {
        "item": {
            "type": "command_execution",
            "exit_code": 0,
            "aggregated_output": skill.read_text() + CONTENT,
        }
    }
    (case / "events.jsonl").write_text(json.dumps(event) + "\n")
    if arm == "wiki":
        wiki = case / "work/wiki"
        wiki.mkdir()
        (wiki / "policy.md").write_text(CONTENT)
        write_json(case / "canonical.json", {"policy.md": PAGE})
        write_json(case / "initial-snapshot.json", {"wiki": snapshot(wiki)})
    else:
        source, checkout = (
            case / "work/source",
            case / "home/.local/share/portable-kb/brains/synthetic",
        )
        for root in (source, checkout):
            root.mkdir(parents=True)
            (root / "policy.md").write_text(CONTENT)
        write_json(case / "canonical.json", {"policy.md": item})
        write_json(
            case / "initial-snapshot.json",
            {"source": repository_snapshot(source), "checkout": repository_snapshot(checkout)},
        )
        write_json(
            case / "trace/001.json",
            {
                "actor": "agent",
                "argv": ["get", IDENTITY, "--brain", "synthetic", "--json"],
                "exit_code": 0,
                "stdout": json.dumps(item),
            },
        )
    return case


@pytest.mark.parametrize("arm", ["wiki", "portable-kb"])
def test_actual_complete_observations_pass(tmp_path, arm):
    assert grade_case(evidence(tmp_path, arm), TASK)["status"] == "pass"


def test_derived_markdown_view_retains_a_canonical_read(tmp_path):
    case = evidence(tmp_path, "portable-kb")
    path = case / "trace/001.json"
    trace = json.loads(path.read_text())
    payload = json.loads(trace["stdout"])
    payload["item"]["rendered_body"] = (
        "# Synthetic policy\n\nKeep data for 30 days.\n\n[reviewer](reviewer.md)\n"
    )
    payload["item"]["rendered_content"] = payload["item"]["rendered_body"]
    trace["argv"].append("--markdown-links")
    trace["stdout"] = json.dumps(payload)
    write_json(path, trace)
    assert grade_case(case, TASK)["status"] == "pass"


@pytest.mark.parametrize(
    "mutation",
    [
        "forged-citation",
        "wrong-body",
        "no-read",
        "no-scope",
        "source-write",
        "no-runner",
        "malformed-final",
        "wrong-value",
        "no-skill",
        "no-caveat",
    ],
)
def test_portable_false_wins_are_rejected(tmp_path, mutation):
    case = evidence(tmp_path, "portable-kb")
    final = json.loads((case / "final.json").read_text())
    trace = json.loads((case / "trace/001.json").read_text())
    if mutation == "forged-citation":
        final["answers"]["retention"]["citations"][0]["commit"] = "c" * 40
    elif mutation == "wrong-body":
        response = json.loads(trace["stdout"])
        response["item"]["body"] = "Invented answer."
        trace["stdout"] = json.dumps(response)
    elif mutation == "no-read":
        trace["actor"] = "setup"
    elif mutation == "no-scope":
        trace["argv"] = ["get", IDENTITY, "--json"]
    elif mutation == "source-write":
        (case / "work/source/policy.md").write_text("silently changed")
    elif mutation == "no-runner":
        (case / "runner.json").unlink()
    elif mutation == "malformed-final":
        final = []
    elif mutation == "wrong-value":
        final["answers"]["retention"]["value"] = "90 days"
    elif mutation == "no-skill":
        (case / "events.jsonl").write_text("")
    else:
        final["summary"] = "Verified authoritative policy."
    write_json(case / "final.json", final)
    write_json(case / "trace/001.json", trace)
    assert grade_case(case, TASK)["status"] != "pass"


def test_wiki_snippet_is_not_a_complete_read(tmp_path):
    case = evidence(tmp_path, "wiki")
    event = {
        "item": {
            "type": "command_execution",
            "exit_code": 0,
            "aggregated_output": "Keep data for 30 days.",
        }
    }
    (case / "events.jsonl").write_text(json.dumps(event) + "\n")
    result = grade_case(case, TASK)
    assert not result["claims"]["retention"]["grounded"]


def test_segmented_reads_and_unicode_name_equivalence():
    lines = CONTENT.splitlines(keepends=True)
    assert complete_text_seen(CONTENT, ["".join(lines[:5]), "".join(lines[5:])])
    assert not complete_text_seen(CONTENT, ["".join(lines[:5])])
    assert normalized(["Fabián", "Preeti"]) == normalized(["Preeti", "Fabian"])


def test_wiki_schema_can_supplement_grounded_page_citation(tmp_path):
    case = evidence(tmp_path, "wiki")
    context = case / "work/wiki/SCHEMA.md"
    context.write_text("# Conventions\n\nUnknown beats invented.\n")
    initial = json.loads((case / "initial-snapshot.json").read_text())
    initial["wiki"] = snapshot(case / "work/wiki")
    write_json(case / "initial-snapshot.json", initial)
    final = json.loads((case / "final.json").read_text())
    final["answers"]["retention"]["citations"].append({"path": "SCHEMA.md"})
    write_json(case / "final.json", final)
    event = {
        "item": {
            "type": "command_execution",
            "exit_code": 0,
            "aggregated_output": context.read_text(),
        }
    }
    with (case / "events.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    assert grade_case(case, TASK)["status"] == "pass"


def test_reference_adjustments_preserve_original_labels_and_response(tmp_path):
    case = evidence(tmp_path, "wiki")
    final = json.loads((case / "final.json").read_text())
    final["answers"]["retention"]["value"] = "30d"
    write_json(case / "final.json", final)
    suite = {"version": 1, "tasks": {"synthetic": TASK}}
    write_json(tmp_path / "suite.json", suite)
    write_json(tmp_path / "canonical-wiki.json", {"policy.md": PAGE})
    corpus_hash = hashlib.sha256(
        json.dumps({"policy.md": PAGE}, sort_keys=True).encode()
    ).hexdigest()
    write_json(
        tmp_path / "manifest.json",
        {
            "scenarios": ["wiki"],
            "suite_sha256": digest(tmp_path / "suite.json"),
            "corpus_sha256": corpus_hash,
        },
    )
    assert grade(tmp_path)["cases"][0]["status"] == "fail"
    original_labels, original_final = (
        (tmp_path / "suite.json").read_bytes(),
        (case / "final.json").read_bytes(),
    )
    aliases = tmp_path / "aliases.json"
    write_json(
        aliases,
        {
            "version": 1,
            "reason": "Declared equivalent shorthand.",
            "additions": {"synthetic": {"retention": ["30d"]}},
        },
    )
    result = grade(tmp_path, aliases)
    assert result["cases"][0]["status"] == "pass"
    assert result["label_adjustments"]["reason"]
    assert (tmp_path / "suite.json").read_bytes() == original_labels
    assert (case / "final.json").read_bytes() == original_final
    (tmp_path / "canonical-wiki.json").write_text("{}")
    with pytest.raises(ValueError, match="Canonical corpus changed"):
        grade(tmp_path, aliases)


@pytest.mark.skipif(shutil.which("bash") is None, reason="Foreground observer uses bash")
def test_foreground_observer_records_actual_exit_output_environment_and_finish(tmp_path):
    case = tmp_path / "case"
    (case / "work").mkdir(parents=True)
    write_json(case / "bin/shim.json", {"product_environment": {"PKB_OBSERVER_TEST": "isolated"}})
    entry = [sys.executable, "-m", "evals.agent_cli.observer", "--case", str(case)]
    command_text = shlex.join(
        [
            sys.executable,
            "-c",
            'import os; print(os.environ["PKB_OBSERVER_TEST"]); raise SystemExit(7)',
        ]
    )
    completed = subprocess.run(
        [*entry, "exec", "--command", command_text], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 7 and completed.stdout.strip() == "isolated"
    event = json.loads((case / "events.jsonl").read_text())
    assert event["item"]["exit_code"] == 7
    assert event["item"]["aggregated_output"] == completed.stdout
    final = case / "work/final.json"
    write_json(final, {"summary": "Synthetic adapter test."})
    subprocess.run(
        [*entry, "finish", "--final-file", str(final)], capture_output=True, text=True, check=True
    )
    assert json.loads((case / "final.json").read_text())["summary"] == "Synthetic adapter test."
    assert json.loads((case / "runner.json").read_text())["model"] == "inherited/unknown"


@pytest.mark.parametrize(
    "mutation",
    ["body", "links", "metadata", "digest", "verified", "human", "duplicate-id", "invalid-id"],
)
def test_migration_losses_fail_fidelity(mutation):
    item = product_item()
    pages = {"policy.md": PAGE}
    items = {"policy.md": item}
    assert fidelity(pages, items)["passed"]
    if mutation == "body":
        item["item"]["body"] = BODY.replace("30", "90")
    elif mutation == "links":
        item["item"]["body"] = BODY.replace("[[reviewer]]", "[[other]]")
    elif mutation == "metadata":
        item["item"]["metadata"]["sources"][0]["x-wiki-original"] = {}
    elif mutation == "digest":
        item["item"]["metadata"]["sources"][0]["x-content-digest"] = "wrong"
    elif mutation == "verified":
        item["item"]["metadata"]["verified"] = {"by": "human:unreviewed"}
    elif mutation == "human":
        item["item"]["metadata"]["generated"]["by"] = "human:impostor"
    elif mutation == "invalid-id":
        item["item"]["id"] = "urn:uuid:invented"
    else:
        pages["second.md"] = PAGE
        items["second.md"] = item
    assert not fidelity(pages, items)["passed"]


@pytest.mark.parametrize("field", ["suite_sha256", "labels_sha256", "corpus_sha256", "repetitions"])
def test_unmatched_comparisons_are_refused(tmp_path, field):
    manifest = dict(
        suite_sha256="suite", labels_sha256="labels", corpus_sha256="corpus", repetitions=2
    )
    wiki = {"manifest": {**manifest, "arm": "wiki"}}
    portable = {"manifest": {**manifest, "arm": "portable-kb", field: "different"}}
    with pytest.raises(ValueError, match="Unmatched benchmark"):
        compare(wiki, portable, tmp_path / "comparison")


def test_bad_suite_evidence_and_symlink_inputs_are_refused(tmp_path):
    with pytest.raises(ValueError, match="existing wiki pages"):
        validate_suite({"version": 1, "tasks": {"synthetic": TASK}}, {})
    (tmp_path / "escape").symlink_to("/etc")
    with pytest.raises(ValueError, match="Symlink"):
        snapshot(tmp_path)
