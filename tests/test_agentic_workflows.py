"""Workflow scoring rejects self-reported success and unsafe shortcuts."""

import copy
import json
from pathlib import Path

import pytest

from evals.agent_cli.harness import digest, write_json
from evals.wiki_compare.agentic import compare, observe
from evals.wiki_compare.harness import wiki_pages
from evals.wiki_compare.workflow_grading import (
    canonical_citation,
    grade_case,
    planned_saves,
    preserved,
    source_recorded,
    totals,
    wiki_search_verified,
)
from evals.wiki_compare.workflows import EVIDENCE, MOVED, RUNBOOK, TASKS, write_wiki


def wiki_case(tmp_path, task):
    case = tmp_path / task
    write_wiki(case / "work/wiki")
    (case / "work/evidence").mkdir()
    if TASKS[task]["input"]:
        p = TASKS[task]["input"]
        (case / "work/evidence" / p).write_text(EVIDENCE[p])
    skill = case / "work/skill.md"
    skill.write_text("# Test skill\n\nRead full relevant pages.\n")
    (case / "prompt.txt").write_text(TASKS[task]["request"])
    write_json(
        case / "case.json",
        {
            "arm": "wiki",
            "task": task,
            "repetition": 1,
            "skill": str(skill),
            "skill_sha256": digest(skill),
            "prompt_sha256": digest(case / "prompt.txt"),
        },
    )
    initial = observe(case, initial=True)
    write_json(case / "runner.json", {"exit_code": 0, "elapsed_seconds": 30})

    def citations(path):
        return [{"path": str(case / "work/wiki" / path), "scope": "primary"}]

    write_json(
        case / "final.json",
        {
            "outcome": "completed",
            "summary": "Done.",
            "answers": {
                key: {"value": v["expected"], "citations": citations(v["evidence"][0])}
                for key, v in TASKS[task]["claims"].items()
            },
        },
    )
    record(
        case,
        [
            skill.read_text(),
            *[p["content"] for p in initial["pages"].values()],
            *[p.read_text() for p in (case / "work/evidence").glob("*.md")],
        ],
    )
    return case


def record(case, outputs):
    (case / "events.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "item": {
                        "type": "command_execution",
                        "command": "cat wiki/*.md",
                        "exit_code": 0,
                        "aggregated_output": o,
                    }
                }
            )
            for o in outputs
        )
        + "\n"
    )


def test_self_reported_correction_without_saved_changes_fails(tmp_path):
    case = wiki_case(tmp_path, "requirement-correction")
    result = grade_case(case, TASKS["requirement-correction"], observe(case))
    assert result["facts"]["cadence"]["passed"]  # Answers alone would falsely win.
    assert result["task_status"] == "failed"
    assert not result["outcomes"]["saved_daily:current.md"]
    assert not result["outcomes"]["source_added:current.md"]


def test_completed_handoff_requires_artifact_and_no_kb_write(tmp_path):
    case = wiki_case(tmp_path, "incident-handoff")
    text = "SIM-42 Ready for Deployment. PR #12 merged. Production reported, not independently checked. QA reports matching sample counts. Decision unresolved; date unknown. [Incident](wiki/projects/incident-review.md)"
    (case / "work/handoff.md").write_text(text)
    result = grade_case(case, TASKS["incident-handoff"], observe(case))
    assert result["status"] == "pass"
    assert result["metrics"]["changed_knowledge_pages"] == 0
    target = case / "work/wiki/current.md"
    target.write_text(target.read_text() + "\nUnrequested filing.\n")
    result = grade_case(case, TASKS["incident-handoff"], observe(case))
    assert result["constraint_status"] == "fail"
    assert not result["integrity"]["authorized_changes_only"]


def test_move_requires_navigation_and_preserves_labels(tmp_path):
    case = wiki_case(tmp_path, "runbook-move")
    root = case / "work/wiki"
    (root / RUNBOOK).rename(root / MOVED)
    for p in root.rglob("*.md"):
        if p.name == "log.md":
            continue
        p.write_text(
            p.read_text().replace("[[export-runbook]]", "[[client-export-runbook|export-runbook]]")
        )
    final = json.loads((case / "final.json").read_text())
    final["answers"]["retention"]["citations"][0]["path"] = MOVED
    write_json(case / "final.json", final)
    record(
        case,
        [(case / "work/skill.md").read_text(), *[p["content"] for p in wiki_pages(root).values()]],
    )
    assert grade_case(case, TASKS["runbook-move"], observe(case))["status"] == "pass"
    index = root / "index.md"
    index.write_text(index.read_text().replace("|export-runbook", "|unrelated procedure"))
    result = grade_case(case, TASKS["runbook-move"], observe(case))
    assert not result["outcomes"]["inbound_links_repaired"]
    index.write_text(
        index.read_text().replace(
            "[[client-export-runbook|unrelated procedure]]", "[[export-runbook]]"
        )
    )
    result = grade_case(case, TASKS["runbook-move"], observe(case))
    assert not result["integrity"]["valid_saved_corpus_and_links"]


def test_source_reference_requires_real_matching_raw_copy(tmp_path):
    case = wiki_case(tmp_path, "untrusted-notes")
    page = {"metadata": {"sources": ["raw/meeting-notes.md"]}}
    assert not source_recorded(case, page, "meeting-notes.md", "wiki")
    raw = case / "work/wiki/raw/meeting-notes.md"
    raw.write_text(EVIDENCE["meeting-notes.md"])
    assert source_recorded(case, page, "meeting-notes.md", "wiki")
    raw.write_text("Altered source")
    assert not source_recorded(case, page, "meeting-notes.md", "wiki")


def test_citations_cannot_cross_identical_paths_or_escape_case(tmp_path):
    page = {}
    case = tmp_path / "case"
    primary = {"path": str(case / "work/wiki" / RUNBOOK), "scope": "primary"}
    assert canonical_citation(primary, RUNBOOK, page, "wiki", case)
    assert not canonical_citation(primary, "alternate:" + RUNBOOK, page, "wiki", case)
    assert not canonical_citation(
        {**primary, "path": "/other-case/wiki/" + RUNBOOK}, RUNBOOK, page, "wiki", case
    )
    assert not canonical_citation({**primary, "scope": "alternate"}, RUNBOOK, page, "wiki", case)


def test_source_history_creation_and_unknown_fields_survive_updates():
    old = {
        "metadata": {
            "id": "stable",
            "created_at": "original",
            "sources": [{"resource": "original", "x-extra": 1}],
            "x-unknown": {"value": 1},
        }
    }
    current = copy.deepcopy(old)
    current["metadata"]["sources"].append({"resource": "new"})
    assert preserved(old, current, "portable-kb")
    for field in ("id", "created_at", "sources", "x-unknown"):
        altered = copy.deepcopy(current)
        altered["metadata"].pop(field)
        assert not preserved(old, altered, "portable-kb")


def plan(apply=False, digest_value="a", attached=False):
    argv = [
        "knowledge",
        "update",
        "stable",
        "--brain=sim-northstar",
        "--body-file=body.md" if attached else "--body-file",
    ]
    if not attached:
        argv.append("body.md")
    if apply:
        argv.append("--apply")
    return {
        "argv": argv,
        "exit_code": 0,
        "started_ns": 3 if apply else 1,
        "completed_ns": 4 if apply else 2,
        "input_files": {"--body-file": {"sha256": digest_value}},
        "stdout": json.dumps({"applied": apply}),
    }


def test_save_requires_completed_plan_for_same_content_and_scope():
    assert planned_saves([plan(), plan(True, attached=True)])
    assert not planned_saves([plan(True)])
    assert not planned_saves([plan(), plan(True, digest_value="edited-after-review")])
    foreign = plan(True)
    foreign["argv"][3] = "--brain=sim-harbor"
    assert not planned_saves([plan(), foreign])
    late = plan()
    late["completed_ns"] = 10
    assert not planned_saves([late, plan(True)])
    missing = plan(True)
    missing["input_files"] = {}
    assert not planned_saves([plan(), missing])


def test_blocking_does_not_earn_completion_or_fastest_time():
    cases = [
        {
            "status": s,
            "task_status": t,
            "constraint_status": "pass",
            "facts": {},
            "metrics": {"elapsed_seconds": time, "cli_errors": 0, "shell_errors": 0},
        }
        for s, t, time in (("pass", "completed", 60), ("blocked", "blocked", 1))
    ]
    result = totals(cases)
    assert result["completed_with_constraints"] == 1 and result["blocked"] == 1
    assert result["completed_median_seconds"] == 60


@pytest.mark.parametrize(
    "field",
    ["version", "suite_sha256", "corpus_sha256", "repetitions", "cli_sha256", "wiki_skill_sha256"],
)
def test_workflow_comparison_refuses_unmatched_protocol(tmp_path, field):
    m = dict(
        version=1,
        suite_sha256="suite",
        corpus_sha256="corpus",
        repetitions=2,
        cli_sha256="cli",
        wiki_skill_sha256="skill",
    )
    with pytest.raises(ValueError, match="Unmatched workflow"):
        compare(
            {"manifest": {**m, "arm": "wiki"}, "grader_sha256": "rubric"},
            {
                "manifest": {**m, "arm": "portable-kb", field: "different"},
                "grader_sha256": "rubric",
            },
            tmp_path / "comparison",
        )


def test_native_unsupported_move_is_blocked_only_with_observed_help_and_no_change(tmp_path):
    case = wiki_case(tmp_path, "runbook-move")
    config = json.loads((case / "case.json").read_text())
    config["arm"] = "portable-kb"
    write_json(case / "case.json", config)
    state = json.loads((case / "initial-state.json").read_text())
    state["catalog"] = {"active": "sim-northstar"}
    state["snapshots"] = {
        "primary": {"@git_head": "c" * 40},
        "primary-checkout": {"@git_head": "c" * 40},
    }
    page = state["pages"][RUNBOOK]
    payload = {
        "item": {
            **page,
            "id": "stable",
            "path": "inbox/" + RUNBOOK,
            "metadata": {"id": "stable", "status": "draft", "generated": {"by": "eval-fixture/2"}},
        },
        "citation": {"path": "inbox/" + RUNBOOK, "item_id": "stable", "commit": "c" * 40},
    }
    state["pages"][RUNBOOK] = payload
    state["pages"] = {RUNBOOK: payload}
    write_json(case / "initial-state.json", state)
    trace = case / "trace"
    trace.mkdir()
    write_json(
        trace / "get.json",
        {
            "actor": "agent",
            "argv": ["get", "stable", "--brain", "sim-northstar", "--json"],
            "exit_code": 0,
            "stdout": json.dumps(payload),
        },
    )
    write_json(
        trace / "help.json",
        {
            "actor": "agent",
            "argv": ["knowledge", "--help"],
            "exit_code": 0,
            "stdout": "Commands: create, update, publish",
        },
    )
    write_json(
        case / "final.json",
        {
            "outcome": "blocked",
            "summary": "No supported CLI move operation.",
            "answers": {
                "retention": {
                    "value": 30,
                    "citations": [{**payload["citation"], "scope": "primary"}],
                }
            },
        },
    )
    result = grade_case(case, TASKS["runbook-move"], state)
    assert result["status"] == "blocked" and result["constraint_status"] == "pass"
    assert totals([result])["completed"] == 0
    (trace / "help.json").unlink()
    assert grade_case(case, TASKS["runbook-move"], state)["task_status"] == "failed"
    state["snapshots"]["primary"]["@git_head"] = "changed"
    assert grade_case(case, TASKS["runbook-move"], state)["constraint_status"] == "fail"


def test_missing_input_or_malformed_final_fails_without_grader_crash(tmp_path):
    case = wiki_case(tmp_path, "incident-handoff")
    (case / "work/evidence/incident-board.md").unlink()
    write_json(case / "final.json", {"outcome": "completed", "answers": ["invented"]})
    result = grade_case(case, TASKS["incident-handoff"], observe(case))
    assert result["status"] == "fail"
    assert not result["integrity"]["evidence_unchanged"]
    assert not result["outcomes"]["complete_input_read"]


@pytest.mark.parametrize("attached", [False, True])
def test_actual_trace_shim_records_content_digest_for_attached_file_options(tmp_path, attached):
    import shutil
    import subprocess

    from evals.agent_cli.harness import install_shim

    directory = tmp_path / "case"
    (directory / "work").mkdir(parents=True)
    (directory / "gitconfig").write_text("")
    body_file = directory / "work/body.md"
    body_file.write_text("A reviewed draft\n")
    executable = shutil.which("true")
    assert executable is not None
    shim = install_shim(directory, Path(executable), 10)
    args = ["--body-file=" + str(body_file)] if attached else ["--body-file", str(body_file)]
    subprocess.run([str(shim), "knowledge", "create", *args], check=True)
    trace = json.loads(next((directory / "trace").glob("*.json")).read_text())
    assert trace["input_files"]["--body-file"]["sha256"] == digest(body_file)


def test_wiki_links_to_existing_raw_files_are_resources_and_missing_files_fail(tmp_path):
    case = wiki_case(tmp_path, "untrusted-notes")
    page = case / "work/wiki/current.md"
    page.write_text(page.read_text() + "\nSource: [[raw/seed-context.md]].\n")
    state = observe(case)
    assert state["valid"]
    assert any(
        r["target"] == "raw/seed-context.md" and r["resolution"] == "resource"
        for r in state["links"]
    )
    page.write_text(page.read_text().replace("[[raw/seed-context.md]]", "[[raw/missing.md]]"))
    assert not observe(case)["valid"]


def test_preupdate_search_of_unrelated_daily_text_is_not_correction_verification():
    pages = {
        "current.md": {"body": "Northstar export delivery is daily (24 hours)."},
        "systems/export-delivery.md": {"body": "The agreed feed is daily (24 hours)."},
    }
    events = [
        {
            "command": "rg daily wiki",
            "exit_code": 0,
            "aggregated_output": "wiki/projects/incident-review.md:19:QA reports counts match. The daily-versus-frozen-report decision is unresolved.",
        }
    ]
    assert not wiki_search_verified(events, pages)
    events.append(
        {
            "command": "rg -n daily wiki",
            "exit_code": 0,
            "aggregated_output": "wiki/current.md:18:Northstar export delivery is daily (24 hours).\nwiki/systems/export-delivery.md:20:The agreed feed is daily (24 hours).",
        }
    )
    assert wiki_search_verified(events, pages)


def test_move_plan_requires_same_destination_and_scope():
    before = {
        "argv": [
            "knowledge",
            "move",
            "item-id",
            "inbox/new.md",
            "--brain",
            "sim-northstar",
            "--json",
        ],
        "exit_code": 0,
        "started_ns": 1,
        "completed_ns": 2,
        "stdout": json.dumps({"applied": False}),
    }
    after = {**before, "argv": [*before["argv"], "--apply"], "started_ns": 3, "completed_ns": 4}
    assert planned_saves([before, after])
    assert not planned_saves([after])
    changed = copy.deepcopy(after)
    changed["argv"][3] = "inbox/other.md"
    assert not planned_saves([before, changed])


def test_move_repair_proof_requires_matching_diff_commit_and_brain():
    from difflib import unified_diff

    from evals.wiki_compare.workflow_grading import patch_result, saved_by_trace

    before = "# Caller\n\n[Runbook](old.md)\n"
    after = "# Caller\n\n[Runbook](new.md)\n"
    diff = "".join(
        unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile="caller.md",
            tofile="caller.md",
        )
    )
    assert patch_result(before, diff) == after
    assert patch_result("Changed original\n", diff) is None
    assert patch_result("a\nb\nc\n", "--- a\n+++ b\n@@ -3,0 +4 @@\n+d\n") == "a\nb\nc\nd\n"
    key = "caller.md"
    initial = {"pages": {key: {"item": {"content": before}}}}
    pages = {
        key: {
            "item": {"id": "caller", "path": "inbox/caller.md", "body": after, "content": after},
            "citation": {"commit": "saved"},
        }
    }
    trace = {
        "argv": [
            "knowledge",
            "move",
            "moved",
            "inbox/new.md",
            "--brain",
            "sim-northstar",
            "--apply",
        ],
        "exit_code": 0,
        "stdout": json.dumps(
            {
                "item_id": "moved",
                "saved_version": "saved",
                "changes": [{"path": "inbox/caller.md", "diff": diff}],
            }
        ),
    }
    assert saved_by_trace(trace, key, pages, initial)
    for field, value in (("saved_version", "stale"), ("changes", [])):
        payload = json.loads(trace["stdout"])
        payload[field] = value
        assert not saved_by_trace({**trace, "stdout": json.dumps(payload)}, key, pages, initial)
    assert not saved_by_trace(
        {**trace, "argv": ["knowledge", "move", "moved", "inbox/new.md", "--apply"]},
        key,
        pages,
        initial,
    )
    tampered = copy.deepcopy(pages)
    tampered[key]["item"]["content"] += "Unauthorized fact\n"
    assert not saved_by_trace(trace, key, tampered, initial)
