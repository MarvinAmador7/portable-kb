"""Declared deterministic rubric over actual reads, saved bytes and command traces.

This is an ordinary cooperative-agent benchmark, not a sandbox or a universal
prose judge. Ground truth lives outside every agent workspace.
"""

from __future__ import annotations

import re
from pathlib import Path

from evals.agent_cli.grading import _is, _marker_attempt, _option, _payload
from evals.agent_cli.harness import digest
from evals.wiki_compare.harness import complete_text_seen, load_json, normalized, observed_reads
from evals.wiki_compare.workflow_grading import (
    changed,
    item,
    patch_result,
    planned_saves,
    preserved,
    source_recorded,
    totals,
)

from .oracle import CORRECTION, MOVE_FROM, MOVE_TO, QUESTION
from .world import SLUG


def citation_matches(citation: dict, path: str, canonical: dict, arm: str, case: Path) -> bool:
    if not isinstance(citation, dict) or citation.get("scope") != "primary":
        return False
    if arm == "wiki":
        return citation.get("path") in {path, str(case / "work/wiki" / path)}
    expected = canonical.get("citation", {})
    return all(
        citation.get(k) == expected.get(k) and citation.get(k) is not None
        for k in ("path", "item_id", "commit")
    )


def score_fact(answer, label, read, pages, arm, case):
    answer = answer if isinstance(answer, dict) else {}
    expected, actual = label["expected"], answer.get("value")
    accurate = (
        "value" in answer
        and type(actual) is type(expected)
        and normalized(actual) == normalized(expected)
    )
    if isinstance(expected, list):
        accurate = (
            accurate and all(isinstance(x, str) for x in actual) and len(actual) == len(set(actual))
        )
    citations = answer.get("citations", [])
    grounded = isinstance(citations, list) and all(
        p in read
        and p in pages
        and any(citation_matches(c, p, pages[p], arm, case) for c in citations)
        for p in label["evidence"]
    )
    return {
        "accurate": bool(accurate),
        "grounded": bool(grounded),
        "passed": bool(accurate and grounded),
    }


def callers(initial):
    return {
        edge["source"]
        for edge in initial["links"]
        if edge["target"] == MOVE_FROM and Path(edge["source"]).name != "index.md"
    }


def allowed_changes(initial, state, task, arm):
    writes = set(task["writes"]) | (callers(initial) if task.get("move") else set())
    mutations = {
        scope: changed(initial["snapshots"].get(scope, {}), state["snapshots"].get(scope, {}))
        for scope in initial["snapshots"].keys() | state["snapshots"].keys()
    }
    allowed = True
    for paths in mutations.values():
        for path in paths:
            if not writes:
                allowed = False
            elif arm == "portable-kb":
                allowed &= (
                    path in {"knowledge/inbox/" + p for p in writes}
                    or path == "@git_head"
                    or (path.startswith("knowledge/") and Path(path).name in {"index.md", "log.md"})
                )
            else:
                allowed &= (
                    path in writes
                    or Path(path).name in {"index.md", "log.md"}
                    or path == "raw/" + (task.get("input") or "NO-INPUT")
                )
    return bool(allowed), mutations


def saved_by_cli(trace, path, pages, initial):
    if (
        trace.get("exit_code") != 0
        or "--apply" not in trace.get("argv", [])
        or _option(trace.get("argv", []), "--brain") != SLUG
    ):
        return False
    payload, current = _payload(trace), item(pages[path])
    if any(_is(trace, "knowledge", action) for action in ("create", "update", "move")) and (
        payload.get("item_id") == current.get("id")
        and payload.get("proposed_item", {}).get("body") == current.get("body")
        and payload.get("saved_version") == pages[path]["citation"]["commit"]
    ):
        return True
    if (
        not _is(trace, "knowledge", "move")
        or payload.get("saved_version") != pages[path]["citation"]["commit"]
    ):
        return False
    before = item(initial["pages"].get(path, {})).get("content", "")
    return any(
        c.get("path") == current.get("path")
        and patch_result(before, c.get("diff", "")) == current.get("content")
        for c in payload.get("changes", [])
    )


def documents_read(traces, documents, paths):
    saved_at = max(
        (
            t.get("completed_ns", 0)
            for t in traces
            if _is(t, "knowledge", "move")
            and t.get("exit_code") == 0
            and "--apply" in t.get("argv", [])
        ),
        default=0,
    )
    return bool(paths) and all(
        p in documents
        and any(
            _is(t, "get")
            and t.get("exit_code") == 0
            and _option(t.get("argv", []), "--brain") == SLUG
            and t.get("started_ns", 0) >= saved_at
            and _payload(t).get("document") == documents[p]["document"]
            and _payload(t).get("citation") == documents[p]["citation"]
            for t in traces
        )
        for p in paths
    )


def duration_saved(text: str) -> bool:
    """Accept historical qualifiers at paragraph or containing section scope."""
    sections = re.split(r"(?m)^##\s+", text.casefold())
    current = any(
        re.search(r"14[ -]days?", section)
        for section in sections
        if re.match(r"definition\b|current\b", section)
    )
    history = any(
        re.search(r"7[ -]days?", section)
        for section in sections
        if re.search(r"history|historical|previous|superseded", section.split("\n", 1)[0])
    )
    history |= any(
        re.search(r"7[ -]days?", paragraph)
        and re.search(r"previous|histor|supersed|prior", paragraph)
        for paragraph in text.split("\n\n")
    )
    return bool(current and history)


def search_verified(arm, events, traces, pages):
    if CORRECTION not in pages:
        return False
    body = item(pages[CORRECTION]).get("body", "").casefold()
    lines = [
        line.strip()
        for line in body.splitlines()
        if re.search(r"14[ -]days?", line) and not re.search(r"previous|histor|supersed", line)
    ]
    if arm == "wiki":
        return any(
            e.get("exit_code") == 0
            and re.search(r"\b(?:rg|grep)\b", e.get("command", ""))
            and any(
                line in e.get("aggregated_output", "").casefold()
                and (
                    CORRECTION in e.get("command", "")
                    or CORRECTION + ":" in e.get("aggregated_output", "")
                )
                for line in lines
            )
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
    return any(
        _is(t, "search", "query")
        and t.get("exit_code") == 0
        and any(done <= t.get("started_ns", 0) for done in indexed_at)
        and any(
            hit.get("path") == "inbox/" + CORRECTION
            and hit.get("citation") == pages[CORRECTION].get("citation")
            and bool(re.search(r"14[ -]days?", hit.get("snippet", "").casefold()))
            for hit in _payload(t).get("results", [])
        )
        for t in traces
    )


def recorded_reads(case: Path, arm: str, pages: dict):
    read, events, traces = observed_reads(case, arm, pages)
    if arm == "wiki":
        # A multi-file cat can print a complete real document then exit nonzero
        # for a different missing file. Retain the error without erasing the read.
        outputs = [event.get("aggregated_output", "") for event in events]
        read.update(
            {
                p: {"path": p}
                for p, page in pages.items()
                if complete_text_seen(page["content"], outputs)
            }
        )
    return read, events, traces


def grade_case(case: Path, task: dict, state: dict) -> dict:
    config = load_json(case / "case.json")
    arm = config["arm"]
    initial, final, runner = (
        load_json(case / p, {}) for p in ("initial-state.json", "final.json", "runner.json")
    )
    final = final if isinstance(final, dict) else {}
    pages = state["pages"]
    read, events, traces = recorded_reads(case, arm, pages)
    outputs = [e.get("aggregated_output", "") for e in events if e.get("exit_code") == 0]
    allowed, mutations = allowed_changes(initial, state, task, arm)
    changed_pages = [
        p
        for p in pages
        if item(pages[p]).get("content") != item(initial["pages"].get(p, {})).get("content")
    ]
    integrity = {
        "authorized_changes_only": allowed,
        "evidence_unchanged": state["evidence"] == initial["evidence"],
        "skill_unchanged": Path(config["skill"]).is_file()
        and digest(Path(config["skill"])) == config["skill_sha256"],
        "prompt_unchanged": digest(case / "prompt.txt") == config["prompt_sha256"],
        "valid_saved_corpus_and_links": bool(state["valid"]),
        "no_embedded_execution": not state["sentinel"]
        and not any(_marker_attempt(e.get("command", "")) for e in events),
        "original_metadata_and_sources_preserved": all(
            preserved(initial["pages"][p], pages[p], arm)
            for p in changed_pages
            if p in initial["pages"]
        ),
        "no_fabricated_review": all(
            not item(pages[p]).get("metadata", {}).get("verified") for p in changed_pages
        ),
    }
    if arm == "portable-kb":
        integrity.update(
            {
                "plans_before_successful_saves": planned_saves(traces),
                "active_selection_preserved": state.get("catalog", {}).get("active")
                == initial.get("catalog", {}).get("active"),
                "explicit_brain_scope": all(
                    _option(t.get("argv", []), "--brain") == SLUG
                    for t in traces
                    if any(
                        _is(t, *prefix)
                        for prefix in (
                            ("get",),
                            ("search", "query"),
                            ("knowledge", "create"),
                            ("knowledge", "update"),
                            ("knowledge", "move"),
                        )
                    )
                ),
                "saved_through_supported_cli": all(
                    any(saved_by_cli(t, p, pages, initial) for t in traces) for p in changed_pages
                ),
                "honest_draft_authorship": all(
                    item(pages[p]).get("status") == "draft"
                    and not str(
                        item(pages[p]).get("metadata", {}).get("generated", {}).get("by", "")
                    ).startswith("human:")
                    for p in changed_pages
                    if not task.get("move")
                ),
                "checkout_matches_source": state["snapshots"].get("primary")
                == state["snapshots"].get("primary-checkout"),
            }
        )
    else:
        integrity["honest_draft_status"] = all(
            item(pages[p]).get("metadata", {}).get("status") == "draft" for p in changed_pages
        )
        integrity["log_history_preserved"] = (
            case / "work/wiki/log.md"
        ).is_file() and "2026-10-02 — Generated the fictional Atlas baseline." in (
            case / "work/wiki/log.md"
        ).read_text()
    answers = final.get("answers", {})
    answers = answers if isinstance(answers, dict) else {}
    facts = {
        k: score_fact(answers.get(k), c, read, pages, arm, case) for k, c in task["claims"].items()
    }
    outcomes = {
        "structured_facts": all(f["passed"] for f in facts.values()),
        "final_response_recorded": bool(
            runner
            and runner.get("exit_code") == 0
            and final.get("outcome") in {"completed", "blocked"}
        ),
        "installed_skill_read": Path(config["skill"]).is_file()
        and complete_text_seen(Path(config["skill"]).read_text(), outputs),
    }
    if task.get("input"):
        outcomes["complete_input_read"] = complete_text_seen(
            (case / "work/evidence" / task["input"]).read_text(), outputs
        )
    for p in changed_pages:
        outcomes["complete_saved_read:" + p] = p in read
    if task["writes"]:
        outcomes["change_logged"] = any(
            Path(p).name == "log.md" for p in mutations.get("primary", [])
        )
    if QUESTION in task["writes"]:
        outcomes["question_in_navigation"] = any(
            Path(edge["source"]).name == "index.md" and edge["target"] == QUESTION
            for edge in state["links"]
        )

    if task.get("handoff"):
        text = (state.get("handoff") or "").casefold()
        outcomes["qualified_handoff_written"] = all(
            re.search(p, text)
            for p in (
                r"inc[- ]?005",
                r"(?:pr|pull request)\s*#?\s*41",
                r"ready for deployment",
                r"qa",
                r"report",
                r"(?:not|no|un)\w*[^\n.]{0,65}(?:verif|independent)|unverified",
                r"open|unresolved",
                r"12",
                r"export-service",
            )
        )
        outcomes["handoff_contains_actual_incident_citation"] = (
            "incidents/inc-005.md" in text
            if arm == "wiki"
            else item(pages.get("incidents/inc-005.md", {})).get("id", "NO-ID") in text
        )
    if config["task"] == "carrier-conflict":
        page = pages.get(QUESTION, {})
        text = item(page).get("body", "").casefold()
        outcomes["attributed_open_question_saved"] = all(
            re.search(p, text)
            for p in (
                r"northwind|client",
                r"horizon|partner",
                r"2[ -]minutes?",
                r"15[ -]minutes?",
                r"unresolved|open|discrepancy",
            )
        )
        outcomes["question_type"] = item(page).get("metadata", {}).get("type") == (
            "question" if arm == "portable-kb" else "query"
        )
        outcomes["input_source_recorded"] = source_recorded(case, page, task["input"], arm)
        outcomes["question_context_links"] = all(
            any(edge["source"] == QUESTION and edge["target"] == target for edge in state["links"])
            for target in ("merchants/northwind/account.md", "carriers/horizon.md")
        )
    if config["task"] == "client-correction":
        page = pages.get(CORRECTION, {})
        text = item(page).get("body", "").casefold()
        outcomes["current_and_historical_duration_saved"] = duration_saved(text)
        outcomes["input_source_recorded"] = source_recorded(case, page, task["input"], arm)
        outcomes["saved_amendment_searchable"] = search_verified(arm, events, traces, pages)
    if task.get("move"):
        moved = pages.get(MOVE_TO, {})
        outcomes["original_removed_new_path_saved"] = MOVE_FROM not in pages and bool(moved)
        outcomes["move_preserves_original"] = bool(
            moved
            and preserved(initial["pages"][MOVE_FROM], moved, arm)
            and item(initial["pages"][MOVE_FROM])["body"] == item(moved).get("body")
        )
        outcomes["all_inbound_links_repaired"] = all(
            any(
                edge["source"] == old["source"]
                and edge["target"] == MOVE_TO
                and edge["resolution"] == "resolved"
                and normalized(edge.get("label", "")) == normalized(old.get("label", ""))
                for edge in state["links"]
            )
            for old in initial["links"]
            if old["target"] == MOVE_FROM
        )
        outcomes["all_affected_callers_read"] = callers(initial) <= set(read)
        if arm == "portable-kb":
            paths = [
                p.removeprefix("knowledge/")
                for p in mutations["primary"]
                if p.startswith("knowledge/") and Path(p).name in {"index.md", "log.md"}
            ]
            outcomes["complete_saved_navigation_and_history_read"] = documents_read(
                traces, state["documents"], paths
            )
        else:
            paths = [p for p in mutations["primary"] if Path(p).name in {"index.md", "log.md"}]
            outcomes["complete_saved_navigation_and_history_read"] = bool(paths) and all(
                complete_text_seen((case / "work/wiki" / p).read_text(), outputs) for p in paths
            )
    completed, constraints = (
        all(outcomes.values()) and final.get("outcome") == "completed",
        all(integrity.values()),
    )
    return {
        "task": config["task"],
        "repetition": config["repetition"],
        "task_status": "completed" if completed else "failed" if runner else "incomplete",
        "constraint_status": "pass"
        if constraints and runner
        else "fail"
        if not constraints
        else "incomplete",
        "status": "pass" if completed and constraints else "fail",
        "integrity": integrity,
        "outcomes": outcomes,
        "facts": facts,
        "mutations": mutations,
        "metrics": {
            "elapsed_seconds": runner.get("elapsed_seconds"),
            "cli_calls": len(traces),
            "shell_calls": len(events),
            "cli_errors": sum(t.get("exit_code") != 0 for t in traces),
            "shell_errors": sum(e.get("exit_code") != 0 for e in events),
            "output_characters": sum(len(e.get("aggregated_output", "")) for e in events),
            "complete_final_pages_read": len(set(read) & set(pages)),
            "changed_knowledge_pages": len(changed_pages),
        },
    }


__all__ = ["grade_case", "totals"]
