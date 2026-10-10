import json

import pytest

from evals.agent_cli.harness import write_json
from evals.groundray.product import (
    advance,
    audit,
    blind_packets,
    captures,
    owner_packet,
    prepare,
    questions,
)
from evals.groundray.product_scenarios import WORLDS, world


def setup(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text("# Installed wiki skill\n")
    root = tmp_path / "experiment"
    prepare(root, skill, skill)
    return root


def test_empty_brains_matched_inputs_and_private_owner_oracles(tmp_path):
    root = setup(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text())
    assert len(manifest["cases"]) == 18
    for key in WORLDS:
        data = world(key)
        assert len(data["inputs"]) == 54
        assert len(data["facets"]) == 8
        for repetition in (1, 2):
            cases = [
                c for c in manifest["cases"] if c["world"] == key and c["repetition"] == repetition
            ]
            assert len({c["incoming_sha256"] for c in cases}) == 1
            for case in cases:
                work = root / case["name"] / "session-01/work"
                assert not list((work / "brain").iterdir())
                assert not (work / "private-oracle.json").exists()
                assert "facets" not in (work / "prompt.txt").read_text()


def test_question_budget_and_malformed_interface_are_retained(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert questions(tmp_path) == ([], [])
    write_json(work / "owner-questions.json", {"questions": [f"Issue {i}" for i in range(7)]})
    qs, issues = questions(tmp_path)
    assert len(qs) == 6 and issues
    write_json(work / "owner-questions.json", {"questions": "all my facts"})
    qs, issues = questions(tmp_path)
    assert not qs and "Malformed" in issues[0]


def test_owner_reply_is_limited_to_asked_issue_and_handoff_excludes_chat(tmp_path):
    root = setup(tmp_path)
    case = "kestrel-groundray-1"
    for arm in ("wiki", "wiki-grounded", "groundray"):
        for repetition in (1, 2):
            first = root / f"kestrel-{arm}-{repetition}/session-01"
            write_json(first / "final.json", {"answer": "Built."})
            write_json(
                first / "work/owner-questions.json",
                {"questions": ["Who can approve KC commercial exceptions?"]},
            )
    owner_packet(root, "kestrel")
    packet = json.loads((root / "owner-packet-kestrel.json").read_text())
    assert len(packet["items"]) == 6
    write_json(
        root / "owner-route-kestrel.json",
        {
            "items": [
                {
                    "id": i["id"],
                    "card": "authority",
                    "reason": "Authority question",
                    "redundant_with_records": False,
                }
                for i in packet["items"]
            ]
        },
    )
    first = root / case / "session-01"
    (first / "work/brain/memory.md").write_text("Saved uncertainty")
    (first / "events.jsonl").write_text("private trace")
    second = advance(root, case, 2)
    text = (second / "work/incoming/owner-replies.md").read_text()
    assert "commercial exception approver" in text
    assert "monthly-normalized" not in text
    assert (second / "work/brain/memory.md").read_text() == "Saved uncertainty"
    assert not (second / "events.jsonl").exists()
    with pytest.raises(ValueError, match="previous phase incomplete"):
        advance(root, case, 3)


def test_original_csv_capture_and_query_mutation_are_observations(tmp_path):
    payload = world("vale")["inputs"]["tables/02-stock.csv"]
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "capture.csv").write_text(payload)
    assert captures(brain, {"stock": payload})["stock"] == ["capture.csv"]
    (brain / "capture.csv").write_text(payload.replace("100,40", "90,40"))
    assert not captures(brain, {"stock": payload})["stock"]
    root = setup(tmp_path)
    row = next(r for r in audit(root)["rows"] if r["name"] == "vale-groundray-1")
    assert not row["completed"] and row["brain_files"] == 0


def test_incomplete_suite_not_exported_for_review(tmp_path):
    root = setup(tmp_path)
    with pytest.raises(ValueError, match="suite incomplete"):
        blind_packets(root)


def test_worlds_have_distinct_arithmetic_and_positive_evidence():
    k, m, v = world("kestrel"), world("mosaic"), world("vale")
    assert "7200" in k["correction"]["tables/accounts-reconciled.csv"]
    assert "accept this deliverable" in k["update"]["mail/2026-11-05-orion.txt"]
    assert "1500" in m["correction"]["tables/ledger-reconciled.csv"]
    assert "B2 remains approved" in m["update"]["mail/2026-11-06-lumen.txt"]
    assert "90,40" in v["correction"]["tables/stock-reconciled.csv"]
    assert "accepted40each" in v["update"]["warehouse/2026-11-06-receipt.txt"]
