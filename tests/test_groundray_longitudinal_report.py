import pytest

from evals.agent_cli.harness import write_json
from evals.groundray import longitudinal_report
from evals.groundray.longitudinal_scenarios import VARIANTS, story


def reviews(tmp_path, monkeypatch):
    mapping = {}
    rows = []
    for key, *_ in VARIANTS:
        items = []
        for arm in ("wiki", "wiki-grounded", "groundray"):
            for round_number in range(1, 7):
                label = f"{key}-{arm}-{round_number}"
                mapping[label] = {"name": f"{key}-{arm}", "round": round_number}
                items.append({"id": label, "criteria": {name: {"passed": True, "reason": "Unit fixture", "quote": "Unit answer"} for name in story(key)["rubrics"][round_number - 1]}, "material_unsupported_claims": ["Invented blanket approval"] if arm == "wiki" and round_number == 1 else []})
                for operation in ("update", "question"):
                    rows.append({"name": f"{key}-{arm}", "arm": arm, "round": round_number, "operation": operation, "completed": True, "changed_pages": [], "elapsed_seconds": 1, "preexisting_raw_unchanged": True, "incoming_preserved": {}, "skills_unchanged": True})
        write_json(tmp_path / f"review-{key}.json", {"items": items})
    write_json(tmp_path / "blind-map.json", mapping)
    monkeypatch.setattr(longitudinal_report, "audit", lambda root: {"suite": "unit-fixture", "rows": rows})
    return tmp_path


def test_material_overclaim_blocks_answer_pass_even_with_all_criteria_passed(tmp_path, monkeypatch):
    result = longitudinal_report.report(reviews(tmp_path, monkeypatch))
    assert result["summary"]["wiki"]["criteria_passed"] == 120
    assert result["summary"]["wiki"]["answers_passed"] == 25
    assert result["summary"]["wiki"]["answers_with_material_unsupported_claims"] == 5
    assert result["summary"]["groundray"]["answers_passed"] == 30


def test_missing_judgment_or_nonbinary_grade_is_rejected(tmp_path, monkeypatch):
    root = reviews(tmp_path, monkeypatch)
    from evals.wiki_compare.harness import load_json

    path = root / "review-cedar.json"
    review = load_json(path)
    first = next(iter(review["items"][0]["criteria"].values()))
    first["passed"] = "yes"
    write_json(path, review)
    with pytest.raises(ValueError, match="malformed binary"):
        longitudinal_report.report(root)
    first["passed"] = True
    review["items"].pop()
    write_json(path, review)
    with pytest.raises(ValueError, match="missing review items"):
        longitudinal_report.report(root)
