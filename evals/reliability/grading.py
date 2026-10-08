"""Outcome checks for declared injected faults, independent of agent self-reports."""

from __future__ import annotations

import hashlib
import re
import subprocess
from copy import deepcopy
from pathlib import Path

from evals.agent_cli.grading import _is, _payload
from evals.logistics.grading import allowed_changes, recorded_reads
from evals.logistics.grading import grade_case as base_grade
from evals.logistics.oracle import CORRECTION
from evals.logistics.world import SLUG
from evals.wiki_compare.harness import complete_text_seen, load_json
from evals.wiki_compare.workflow_grading import item, source_recorded, sources, totals

from .scenarios import AMENDMENT, COMPETING, CONTACT, ROLLBACK


def source_evidence_recorded(case, page, filename, arm):
    if source_recorded(case, page, filename, arm):
        return True
    if arm != "wiki":
        return False
    expected = case / "work/evidence" / filename
    raw = (case / "work/wiki/raw").resolve()
    for source in sources(page):
        if not isinstance(source, str) or not source.startswith("raw/"):
            continue
        path = (case / "work/wiki" / source).resolve()
        if (
            path.is_relative_to(raw)
            and path.is_file()
            and expected.is_file()
            and path.read_bytes() == expected.read_bytes()
        ):
            return True
    return False


def wiki_allowed_changes(initial, state, task):
    # The prompt explicitly permits unchanged incoming documents to be copied
    # into raw/. Their filename is a wiki convention, not source identity.
    filtered = deepcopy(state)
    before = initial["snapshots"].get("primary", {})
    evidence_hashes = set(initial["evidence"].values())
    filtered["snapshots"]["primary"] = {
        path: sha
        for path, sha in state["snapshots"]["primary"].items()
        if not (
            task["writes"]
            and path.startswith("raw/")
            and path not in before
            and sha in evidence_hashes
        )
    }
    return allowed_changes(initial, filtered, task, "wiki")[0]


def durations(body: str, current: int, historical: int) -> bool:
    sections = re.split(r"(?m)^##\s+", body.casefold())
    now = any(
        re.search(rf"\b{current}[ -]days?\b", section)
        for section in sections
        if re.match(r"definition\b|current\b", section)
    )
    history = any(
        re.search(rf"\b{historical}[ -]days?\b", section)
        for section in sections
        if re.search(r"history|historical|previous|superseded", section.split("\n", 1)[0])
    )
    history |= any(
        re.search(rf"\b{historical}[ -]days?\b", paragraph)
        and re.search(r"previous|histor|supersed|prior|mistake", paragraph)
        for paragraph in body.casefold().split("\n\n")
    )
    return bool(now and history)


def saved_duration_searchable(arm, events, traces, pages, current):
    """Require saved-snapshot search evidence, never a pre-save result."""
    page = pages.get(CORRECTION, {})
    body = item(page).get("body", "")
    pattern = rf"\b{current}[ -]days?\b"
    current_sections = [
        s
        for s in re.split(r"(?m)^##\s+", body.casefold())
        if re.match(r"definition\b|current\b", s)
    ]
    lines = [
        line.strip()
        for section in current_sections
        for line in section.splitlines()
        if re.search(pattern, line)
    ]
    if arm == "wiki":
        # Match the final current definition; a historical occurrence is insufficient.
        return any(
            e.get("exit_code") == 0
            and re.search(r"\b(?:rg|grep)\b", e.get("command", ""))
            and (
                CORRECTION in e.get("command", "")
                or CORRECTION + ":" in e.get("aggregated_output", "")
            )
            and any(line in e.get("aggregated_output", "").casefold() for line in lines)
            for e in events
        )
    saved_at = max(
        (
            t.get("completed_ns", 0)
            for t in traces
            if _is(t, "knowledge", "update")
            and t.get("exit_code") == 0
            and "--apply" in t.get("argv", [])
        ),
        default=0,
    )
    indexed_at = [
        t.get("completed_ns", 0)
        for t in traces
        if _is(t, "search", "index")
        and t.get("argv", [])[2:3] == [SLUG]
        and t.get("exit_code") == 0
        and t.get("started_ns", 0) >= saved_at
    ]
    return bool(saved_at) and any(
        _is(t, "search", "query")
        and t.get("exit_code") == 0
        and any(done <= t.get("started_ns", 0) for done in indexed_at)
        and any(
            hit.get("path") == "inbox/" + CORRECTION
            and hit.get("citation") == page.get("citation")
            and re.search(pattern, hit.get("snippet", "").casefold())
            for hit in _payload(t).get("results", [])
        )
        for t in traces
    )


def grade_case(case: Path, task: dict, state: dict) -> dict:
    result = base_grade(case, task, state)
    config = load_json(case / "case.json")
    initial = load_json(case / "initial-state.json")
    arm = config["arm"]
    read, events, traces = recorded_reads(case, arm, state["pages"])
    outputs = [e.get("aggregated_output", "") for e in events]
    page = state["pages"].get(CORRECTION, {})
    body = item(page).get("body", "")
    outcomes, integrity = result["outcomes"], result["integrity"]
    if arm == "wiki":
        integrity["authorized_changes_only"] = wiki_allowed_changes(initial, state, task)
    incoming = task["incoming"]
    outcomes["complete_incoming_evidence_read"] = all(
        complete_text_seen((case / "work/evidence" / name).read_text(), outputs)
        for name in incoming
    )
    if config["task"] == "concurrent-update":
        cp = load_json(case / "fault/checkpoint.json", {})
        original = item(initial["pages"][CORRECTION])["content"]
        outcomes["checkpoint_after_original_inspection"] = bool(cp) and (
            any(
                _is(t, "get")
                and _payload(t).get("item", {}).get("content") == original
                and t.get("completed_ns", 0) < cp.get("started_ns", 0)
                for t in traces
            )
            if arm == "portable-kb"
            else any(
                complete_text_seen(original, [e.get("aggregated_output", "") for e in events[:i]])
                for i, e in enumerate(events)
                if "kb-fault checkpoint" in e.get("command", "")
            )
        )
        integrity["no_account_save_before_checkpoint"] = (
            cp.get("before_sha256") == hashlib.sha256(original.encode()).hexdigest()
        )
        outcomes["collaborator_snapshot_reinspected"] = bool(cp) and (
            any(
                _is(t, "get")
                and _payload(t).get("item", {}).get("content") == cp.get("content")
                and t.get("started_ns", 0) >= cp.get("completed_ns", 0)
                for t in traces
            )
            if arm == "portable-kb"
            else complete_text_seen(
                cp.get("content", "MISSING-CHECKPOINT"),
                [
                    e.get("aggregated_output", "")
                    for i, e in enumerate(events)
                    if any(
                        "kb-fault checkpoint" in prior.get("command", "") for prior in events[:i]
                    )
                ],
            )
        )
        outcomes["current_and_historical_duration_saved"] = durations(body, 14, 7)
        outcomes["collaborator_contact_preserved"] = CONTACT in body
        outcomes["both_sources_recorded"] = source_evidence_recorded(
            case, page, AMENDMENT, arm
        ) and source_evidence_recorded(case, page, COMPETING, arm)
        outcomes["saved_amendment_searchable"] = saved_duration_searchable(
            arm, events, traces, state["pages"], 14
        )
    if config["task"] == "stale-citation":
        outcomes["latest_and_historical_duration_grounded"] = durations(body, 21, 7)
    if config["task"] == "rollback-amendment":
        outcomes["rollback_retains_mistake_as_history"] = durations(body, 7, 21)
        outcomes["rollback_source_recorded"] = source_evidence_recorded(case, page, ROLLBACK, arm)
        # The rollback must be a new saved revision, preserving the bad revision's
        # source/log history instead of resetting a branch to erase that event.
        outcomes["current_account_completely_read"] = CORRECTION in read
        outcomes["saved_rollback_searchable"] = saved_duration_searchable(
            arm, events, traces, state["pages"], 7
        )
        if arm == "portable-kb":
            outcomes["new_revision_saved"] = state.get("status", {}).get("commit") != initial.get(
                "status", {}
            ).get("commit")
            previous = initial.get("status", {}).get("commit")
            current = state.get("status", {}).get("commit")
            integrity["mistaken_revision_history_preserved"] = bool(previous and current) and (
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(case / "work/source"),
                        "merge-base",
                        "--is-ancestor",
                        previous,
                        current,
                    ],
                    capture_output=True,
                    timeout=10,
                ).returncode
                == 0
            )
    if task.get("move"):
        interruption = load_json(case / "fault/interruption.json", {})
        outcomes["real_interruption_observed"] = (
            interruption.get("kind") == "SIGKILL-after-destination-rename"
            and interruption.get("destination_exists") is True
            and interruption.get("exit_code") != 0
        )
        # Git restoration is explicitly authorized only here; supported CLI
        # proof still covers every final native move/caller change in base_grade.
        outcomes["recovery_inspected_before_completion"] = any(
            re.search(r"\bgit\b.*\b(?:status|diff)\b", e.get("command", "")) for e in events
        )
    final = load_json(case / "final.json", {})
    runner = load_json(case / "runner.json", {})
    completed = all(outcomes.values()) and final.get("outcome") == "completed"
    constraints = all(integrity.values())
    blocked = bool(final.get("outcome") == "blocked" and runner and constraints)
    result.update(
        task_status="completed"
        if completed
        else "blocked"
        if blocked
        else "failed"
        if runner
        else "incomplete",
        constraint_status="pass"
        if constraints and runner
        else "fail"
        if not constraints
        else "incomplete",
        status="pass" if completed and constraints else "blocked" if blocked else "fail",
    )
    return result


__all__ = ["grade_case", "totals"]
