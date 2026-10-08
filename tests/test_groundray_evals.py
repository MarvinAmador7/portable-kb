"""Negative controls for the two-session pilot's deterministic measurements."""

import json
from pathlib import Path

import pytest

from evals.agent_cli.harness import write_json
from evals.groundray.harness import (
    brain_path,
    fact_checks,
    grade_session,
    navigation,
    prepare,
    stage_second,
)
from evals.groundray.scenario import EXPECTED_1, EXPECTED_2, INITIAL, UPDATE


def setup_trial(tmp_path: Path):
    skill = tmp_path / "skill.md"
    skill.write_text("# A test skill\n")
    root = tmp_path / "run"
    manifest = prepare(root, skill, skill, repetitions=1)
    return root, manifest["cases"][0]


def complete(case: Path, answers: dict, records: dict):
    brain = case / "work/brain"
    brain.mkdir(exist_ok=True)
    (brain / "sources").mkdir(exist_ok=True)
    for name, text in records.items():
        (brain / "sources" / name).write_text(text)
    decision = brain / "decision.md"
    if not decision.exists():
        decision.write_text(
            "# Original decision\n\nRecorded approval under supplied rule.\n\nOriginal forecast and its limitations.\n"
        )
    (brain / "index.md").write_text("[Decision](decision.md)\n")
    final = {
        "answers": answers,
        "evidence": {name: f"sources/{name}" for name in records},
        "artifacts": {
            key: "decision.md"
            for key in ("definition", "decision", "assumptions", "commitment", "work")
        },
    }
    write_json(case / "final.json", final)
    event = {
        "item": {
            "type": "command_execution",
            "exit_code": 0,
            "aggregated_output": "\n".join(records.values()) + decision.read_text(),
        }
    }
    (case / "events.jsonl").write_text(json.dumps(event) + "\n")


def test_fact_labels_reject_scope_promotion_and_duplicate_origins():
    assert all(fact_checks(EXPECTED_2, EXPECTED_2).values())
    wrong = {
        **EXPECTED_2,
        "company": "Orchard Services",
        "delivered": "established",
        "shipping_report_origins": 3,
        "approved_deadline": "2026-12-12",
        "commitment_status_as_of_2026_10_21": "failed",
    }
    checks = fact_checks(wrong, EXPECTED_2)
    assert not any(
        checks[k]
        for k in (
            "company",
            "delivered",
            "shipping_report_origins",
            "approved_deadline",
            "commitment_status_as_of_2026_10_21",
        )
    )
    assert not fact_checks(
        {**EXPECTED_2, "affected_ids": ["I4", "X2", "C9", "R17", "F3"]}, EXPECTED_2
    )["affected_ids"]
    assert not fact_checks({**EXPECTED_1, "shipping_report_origins": True}, EXPECTED_1)[
        "shipping_report_origins"
    ]


def test_correct_answers_require_actual_exposure_and_preserved_bytes(tmp_path):
    root, meta = setup_trial(tmp_path)
    case = root / meta["name"] / "session-1"
    complete(case, EXPECTED_1, INITIAL)
    assert grade_session(case, 1, meta["skill_sha256"])["passed"]
    (case / "events.jsonl").write_text("")
    grade = grade_session(case, 1, meta["skill_sha256"])
    assert not grade["passed"] and grade["checks"]["answers"]
    assert not grade["checks"]["original_sources_read"]
    (case / "work/brain/sources/decision-r17.md").write_text("Amended deadline without evidence")
    assert not grade_session(case, 1, meta["skill_sha256"])["checks"]["original_sources_preserved"]


def test_fresh_session_copy_and_appended_history_vs_rewrite(tmp_path):
    root, meta = setup_trial(tmp_path)
    first = root / meta["name"] / "session-1"
    complete(first, EXPECTED_1, INITIAL)
    second = stage_second(root, meta["name"])
    assert not (second / "final.json").exists()
    handoff = json.loads((root / meta["name"] / "handoff.json").read_text())
    complete(second, EXPECTED_2, {**INITIAL, **UPDATE})
    decision = second / "work/brain/decision.md"
    original = decision.read_text()
    decision.write_text(original + "\n## Review\nRisk requiring review.\n")
    assert grade_session(second, 2, meta["skill_sha256"], handoff)["passed"]
    decision.write_text(original.replace("Original forecast", "New approved deadline"))
    assert not grade_session(second, 2, meta["skill_sha256"], handoff)["checks"][
        "decision_history_preserved"
    ]
    assert (first / "work/brain/decision.md").read_text() == original


def test_case_and_evidence_paths_cannot_escape(tmp_path):
    root, _ = setup_trial(tmp_path)
    with pytest.raises(ValueError, match="unknown case"):
        stage_second(root, "../other")
    brain = tmp_path / "brain"
    brain.mkdir()
    secret = tmp_path / "outside.md"
    secret.write_text("not evidence")
    assert brain_path(brain, "../outside.md") is None
    assert brain_path(brain, str(secret)) is None
    (brain / "link.md").symlink_to(secret)
    assert brain_path(brain, "link.md") is None


def test_missing_history_and_missing_inputs_are_failures(tmp_path):
    root, meta = setup_trial(tmp_path)
    first = root / meta["name"] / "session-1"
    complete(first, EXPECTED_1, INITIAL)
    second = stage_second(root, meta["name"])
    complete(second, EXPECTED_2, {**INITIAL, **UPDATE})
    (second / "work/incoming/integration-forecast-e2.md").unlink()
    result = grade_session(second, 2, meta["skill_sha256"], {})
    assert not result["checks"]["incoming_unchanged"]
    assert not result["checks"]["decision_history_preserved"]


def test_navigation_respects_wiki_basename_and_root_paths_without_ambiguity(tmp_path):
    brain = tmp_path / "brain"
    (brain / "topics").mkdir(parents=True)
    (brain / "queries").mkdir()
    (brain / "topics/decision.md").write_text("# Decision\n")
    (brain / "queries/review.md").write_text("# Review\n[[topics/decision]]\n")
    (brain / "index.md").write_text("[[review|Current review]]\n")
    artifacts = {
        key: "queries/review.md"
        for key in ("definition", "decision", "assumptions", "commitment", "work")
    }
    assert navigation(brain, artifacts)
    artifacts["decision"] = "topics/decision.md"
    assert navigation(brain, artifacts)
    # A second basename match makes a bare wikilink ambiguous, not a valid hit.
    (brain / "topics/review.md").write_text("# Different review\n")
    assert not navigation(brain, artifacts)
