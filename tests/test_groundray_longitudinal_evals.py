
import pytest

from evals.agent_cli.harness import write_json
from evals.groundray.longitudinal import advance, audit, blind_packet, prepare, unavailable
from evals.groundray.longitudinal_scenarios import GROUNDING_POLICY, VARIANTS, story


def setup(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text("# Installed wiki skill\n")
    root = tmp_path / "experiment"
    prepare(root, skill, skill)
    return root


def test_three_paired_arms_and_private_rubrics(tmp_path):
    root = setup(tmp_path)
    import json

    manifest = json.loads((root / "manifest.json").read_text())
    assert len(manifest["cases"]) == 15
    for key, *_ in VARIANTS:
        cases = [c for c in manifest["cases"] if c["story"] == key]
        assert len({c["seed_sha256"] for c in cases}) == 1
        for case in cases:
            work = root / case["name"] / "session-01/work"
            assert not (work / "rubric.json").exists()
            assert "applicable_terms" not in (work / "prompt.txt").read_text()
    assert GROUNDING_POLICY in (root / "cedar-wiki-grounded/session-01/work/skill/SKILL.md").read_text()
    assert GROUNDING_POLICY not in (root / "cedar-wiki/session-01/work/skill/SKILL.md").read_text()


def test_handoff_carries_question_writes_but_not_chat(tmp_path):
    root = setup(tmp_path)
    first = root / "cedar-wiki/session-01"
    write_json(first / "final.json", {"answer": "Saved records."})
    (first / "events.jsonl").write_text("private conversation")
    second = advance(root, "cedar-wiki", 2)
    assert not (second / "events.jsonl").exists()
    assert not (second / "final.json").exists()
    assert not list((second / "work/incoming").iterdir())
    (second / "work/brain/topics/answer.md").write_text("Query filed by the actual agent")
    write_json(second / "final.json", {"answer": "P1 applies."})
    third = advance(root, "cedar-wiki", 3)
    assert (third / "work/brain/topics/answer.md").read_text() == "Query filed by the actual agent"
    with pytest.raises(ValueError):
        advance(root, "../outside", 3)
    with pytest.raises(ValueError):
        advance(root, "cedar-wiki", 4)


def test_source_loss_removes_intact_capture_not_summary_or_embedded_original(tmp_path):
    payload = story("cedar")["updates"][3]["finance-note.md"]
    (tmp_path / "original.md").write_text(payload)
    header, body = payload[4:].split("\n---\n", 1)
    (tmp_path / "capture.md").write_text("---\n" + header + '\ningested: "2026-11-08"\n---\n' + body)
    (tmp_path / "formatted.md").write_text("---\n" + header + '\ningested: "2026-11-08"\n---\n' + body.lstrip("\n"))
    (tmp_path / "embedded.md").write_text("# Saved history\n\n" + payload)
    (tmp_path / "summary.md").write_text("Margin declined ten percentage points. Source F1.")
    assert unavailable(tmp_path, payload) == ["capture.md", "formatted.md", "original.md"]
    assert (tmp_path / "embedded.md").is_file()
    assert (tmp_path / "summary.md").is_file()


def test_audit_separates_query_mutations_from_ingest_and_raw_changes(tmp_path):
    root = setup(tmp_path)
    first = root / "cedar-wiki/session-01"
    write_json(first / "final.json", {"answer": "Saved."})
    second = advance(root, "cedar-wiki", 2)
    (second / "work/brain/log.md").write_text("Filed query")
    row = next(r for r in audit(root)["rows"] if r["name"] == "cedar-wiki" and r["phase"] == 2)
    assert row["changed_pages"] == ["log.md"]
    assert row["preexisting_raw_unchanged"]
    (second / "work/brain/raw/standard.md").write_text("Everyone gets the exception")
    assert not next(r for r in audit(root)["rows"] if r["name"] == "cedar-wiki" and r["phase"] == 2)["preexisting_raw_unchanged"]


def test_blind_packet_includes_actual_archive_without_case_labels(tmp_path):
    root = setup(tmp_path)
    for arm in ("wiki", "wiki-grounded", "groundray"):
        case = f"cedar-{arm}"
        first = root / case / "session-01"
        write_json(first / "final.json", {"answer": "Saved."})
        second = advance(root, case, 2)
        write_json(second / "final.json", {"answer": f"See /workspace/private/{case}/session-02/work/brain/raw/standard.md"})
    blind_packet(root)
    text = (root / "blind-cedar.json").read_text()
    assert "cedar-groundray" not in text
    assert "cedar-wiki" not in text
    assert "retained_archive" in text
    assert "brain/raw/standard.md" in text
    assert '"as_of": "2026-11-03"' in text
    with pytest.raises(ValueError, match="story incomplete"):
        blind_packet(root, "cedar")


def test_story_oracles_preserve_prospective_scope_and_temporal_causal_limit():
    for key, *_ in VARIANTS:
        data = story(key)
        assert len(data["updates"]) == len(data["questions"]) == len(data["rubrics"]) == 6
        assert all(len(r) == 4 for r in data["rubrics"])
        assert "retain their original terms" in data["updates"][4]["withdrawal.md"]
        assert "started in November" in data["updates"][3]["finance-note.md"]
        assert "does not establish" in data["updates"][3]["finance-note.md"]
