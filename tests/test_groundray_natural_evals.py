"""Negative controls for natural-question exposure, preservation and fresh handoffs."""

import json
from pathlib import Path

import pytest

from evals.agent_cli.harness import write_json
from evals.groundray.natural import advance, audit, blind_packet, prepare, saved_records
from evals.groundray.natural_scenarios import HANDOFF_UPDATES, QUESTIONS, SOURCES, corpus


def trial(tmp_path: Path):
    skill = tmp_path / "skill.md"
    skill.write_text("# Sample skill\n")
    root = tmp_path / "run"
    manifest = prepare(root, skill, skill, repetitions=1)
    return root, manifest


def test_matched_seed_and_natural_task_without_answer_scaffolding(tmp_path):
    root, manifest = trial(tmp_path)
    assert len(manifest["cases"]) == 10
    assert manifest["corpus_files"] == len(corpus())
    for scenario in QUESTIONS:
        rows = [c for c in manifest["cases"] if c["scenario"] == scenario]
        assert rows[0]["seed_sha256"] == rows[1]["seed_sha256"]
        for metadata in rows:
            work = root / metadata["name"] / "session-1/work"
            task = (work / "prompt.txt").read_text()
            assert "rubric" not in task.lower()
            assert not (work / "rubric.json").exists()
            assert task.count("\n") <= 5
    with pytest.raises(FileExistsError):
        prepare(root, tmp_path / "skill.md", tmp_path / "skill.md")


def test_audit_rejects_correct_looking_answers_without_source_exposure(tmp_path):
    root, _ = trial(tmp_path)
    case = root / "delivery-wiki-1/session-1"
    write_json(case / "final.json", {"answer": "Delivery is unestablished."})
    measured = next(c for c in audit(root)["cases"] if c["name"] == "delivery-wiki-1")
    assert measured["completed"]
    assert not any(measured["required_sources_observed"].values())
    event = {
        "item": {
            "type": "command_execution",
            "exit_code": 0,
            "aggregated_output": "\n".join(SOURCES.values()),
        }
    }
    (case / "events.jsonl").write_text(json.dumps(event) + "\n")
    measured = next(c for c in audit(root)["cases"] if c["name"] == "delivery-wiki-1")
    assert all(measured["required_sources_observed"].values())
    (case / "work/brain/raw/cedar-delivery.md").write_text("Delivered means merged")
    measured = next(c for c in audit(root)["cases"] if c["name"] == "delivery-wiki-1")
    assert not measured["old_source_bytes_preserved"]["raw/cedar-delivery.md"]


def test_two_handoffs_copy_saved_brain_without_chat_and_keep_forecasts(tmp_path):
    root, _ = trial(tmp_path)
    case = root / "handoff-wiki-1"
    first = case / "session-1"
    write_json(first / "final.json", {"answer": "Saved the update."})
    (first / "events.jsonl").write_text("prior conversation trace")
    (first / "work/brain/raw/estimate-e2.md").write_text(HANDOFF_UPDATES[0]["estimate-e2.md"])
    second = advance(root, "handoff-wiki-1", 2)
    assert not (second / "events.jsonl").exists()
    assert not (second / "final.json").exists()
    assert (second / "work/brain/raw/estimate-e2.md").exists()
    write_json(second / "final.json", {"answer": "Saved today's update."})
    (second / "work/brain/raw/estimate-e3.md").write_text(HANDOFF_UPDATES[1]["estimate-e3.md"])
    third = advance(root, "handoff-wiki-1", 3)
    assert (third / "work/brain/raw/estimate-e2.md").exists()
    assert (third / "work/brain/raw/estimate-e3.md").exists()
    assert not list((third / "work/incoming").iterdir())
    assert QUESTIONS["handoff"][1] in (third / "work/prompt.txt").read_text()
    with pytest.raises(ValueError):
        advance(root, "../outside", 2)


def test_capture_metadata_envelope_preserves_payload_but_rewrite_does_not(tmp_path):
    body = HANDOFF_UPDATES[0]["estimate-e2.md"]
    (tmp_path / "capture.md").write_text("Captured by agent; local metadata\n" + body)
    assert saved_records(tmp_path, {"e2": body})["e2"] == ["capture.md"]
    (tmp_path / "capture.md").write_text(body.replace("November 25", "November 20"))
    assert not saved_records(tmp_path, {"e2": body})["e2"]


def test_blind_packet_excludes_arm_labels_and_keeps_missing_origin_limit(tmp_path):
    root, manifest = trial(tmp_path)
    for metadata in manifest["cases"]:
        case = root / metadata["name"] / f"session-{metadata['session_count']}"
        write_json(
            case / "final.json",
            {
                "answer": f"Groundray: source [summary](/workspace/eval/{metadata['name']}/work/brain/raw/margin-summary-a.md). Original unavailable."
            },
        )
    blind_packet(root)
    packet = (root / "blind-packet.json").read_text()
    assert "groundray" not in packet.lower()
    assert "missing-wiki-1" not in packet
    assert "Original unavailable" in packet
    assert "board-memo.md" in packet
    assert len(json.loads(packet)["items"]) == 10
