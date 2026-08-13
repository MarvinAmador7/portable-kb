from __future__ import annotations

from pathlib import Path

from portable_kb.changes import diff_trees
from portable_kb.models import ValidationReport


def test_tree_diff_classifies_and_applies_all_change_kinds(tmp_path: Path) -> None:
    base = tmp_path / "base"
    proposed = tmp_path / "proposed"
    base.mkdir()
    proposed.mkdir()
    (base / "updated.md").write_text("before\n", encoding="utf-8")
    (base / "deleted.yaml").write_text("old: true\n", encoding="utf-8")
    (base / "ignored.txt").write_text("base\n", encoding="utf-8")
    (proposed / "updated.md").write_text("after\n", encoding="utf-8")
    (proposed / "created.yml").write_text("new: true\n", encoding="utf-8")
    (proposed / "ignored.txt").write_text("proposed\n", encoding="utf-8")
    report = ValidationReport(proposed, "2026-08-12", (), 0)

    change_set = diff_trees(base, proposed, report, "test")

    assert [(change.relative_path, change.kind) for change in change_set.changes] == [
        ("created.yml", "create"),
        ("deleted.yaml", "delete"),
        ("updated.md", "update"),
    ]
    change_set.apply()
    assert (base / "created.yml").read_text(encoding="utf-8") == "new: true\n"
    assert not (base / "deleted.yaml").exists()
    assert (base / "updated.md").read_text(encoding="utf-8") == "after\n"
    assert (base / "ignored.txt").read_text(encoding="utf-8") == "base\n"
