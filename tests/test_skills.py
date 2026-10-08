from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import portable_kb.skills as skills_module
from portable_kb.skills import (
    SkillError,
    bundled_skill_path,
    install_agent_skill,
    skill_status,
)


def test_install_agent_skill_for_both_agents_and_force_replace(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = install_agent_skill(user_home=home)

    assert result["ok"] is True
    source = bundled_skill_path()
    for agent, destination_text in result["targets"].items():
        destination = Path(destination_text)
        assert agent in {"codex", "claude"}
        assert (destination / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
        installed_text = (destination / "SKILL.md").read_text(encoding="utf-8")
        assert "pkb knowledge create" in installed_text
        assert "pkb knowledge update" in installed_text
        assert "pkb brain push <slug> --json" in installed_text
        assert "Only after explicit sharing intent" in installed_text
        normalized = " ".join(installed_text.split())
        assert "Do not add names, email addresses" in normalized
        assert "selected brain's scope" in normalized

    repeated = install_agent_skill(user_home=home)
    assert set(repeated["unchanged"]) == {"codex", "claude"}

    codex_skill = home / ".agents/skills/portable-kb/SKILL.md"
    codex_skill.write_text("changed", encoding="utf-8")
    with pytest.raises(SkillError, match="already exists"):
        install_agent_skill(user_home=home)
    install_agent_skill(user_home=home, force=True)
    assert codex_skill.read_bytes() == (source / "SKILL.md").read_bytes()


def test_install_agent_skill_can_target_only_codex(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = install_agent_skill("codex", user_home=home)

    assert set(result["targets"]) == {"codex"}
    assert result["unchanged"] == []
    assert (home / ".agents/skills/portable-kb/SKILL.md").is_file()
    assert not (home / ".claude").exists()


def test_skill_status_detects_current_modified_and_missing_targets(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_agent_skill("codex", user_home=home)

    status = skill_status(user_home=home)
    assert status["ok"] is False
    assert status["targets"]["codex"]["state"] == "current"
    assert status["targets"]["codex"]["managed"] is True
    assert status["targets"]["claude"]["state"] == "missing"

    skill = home / ".agents/skills/portable-kb/SKILL.md"
    skill.write_text("locally changed\n", encoding="utf-8")
    modified = skill_status("codex", user_home=home)
    assert modified["ok"] is False
    assert modified["targets"]["codex"]["state"] == "modified"


def test_skill_status_detects_outdated_unmanaged_and_unsafe_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    install_agent_skill("codex", user_home=home)
    installed = home / ".agents/skills/portable-kb"
    replacement = tmp_path / "new-bundled-skill"
    shutil.copytree(bundled_skill_path(), replacement)
    replacement.joinpath("SKILL.md").write_text("new bundled version\n", encoding="utf-8")
    monkeypatch.setattr(skills_module, "bundled_skill_path", lambda: replacement)

    outdated = skill_status("codex", user_home=home)
    assert outdated["targets"]["codex"]["state"] == "outdated"

    receipt = installed / ".portable-kb-skill.json"
    receipt.unlink()
    unmanaged = skill_status("codex", user_home=home)
    assert unmanaged["targets"]["codex"]["state"] == "unmanaged"

    shutil.rmtree(installed)
    installed.symlink_to(replacement, target_is_directory=True)
    unsafe = skill_status("codex", user_home=home)
    assert unsafe["targets"]["codex"]["state"] == "unsafe"


def test_skill_status_treats_invalid_receipt_as_unmanaged(tmp_path: Path) -> None:
    home = tmp_path / "home"
    destination = home / ".agents/skills/portable-kb"
    destination.mkdir(parents=True)
    destination.joinpath("SKILL.md").write_text("custom\n", encoding="utf-8")
    destination.joinpath(".portable-kb-skill.json").write_text(
        json.dumps({"schema_version": 99}), encoding="utf-8"
    )

    status = skill_status("codex", user_home=home)

    assert status["targets"]["codex"]["state"] == "unmanaged"


def test_install_agent_skill_rejects_invalid_target_and_symlink(
    tmp_path: Path,
) -> None:
    with pytest.raises(SkillError, match="codex, claude, or both"):
        install_agent_skill("other", user_home=tmp_path)

    home = tmp_path / "home"
    actual = tmp_path / "actual"
    actual.mkdir()
    parent = home / ".agents" / "skills"
    parent.parent.mkdir(parents=True)
    parent.symlink_to(actual, target_is_directory=True)
    with pytest.raises(SkillError, match="parent must not be a symbolic link"):
        install_agent_skill("codex", user_home=home)


def test_install_agent_skill_rejects_non_directory_target(tmp_path: Path) -> None:
    destination = tmp_path / ".agents/skills/portable-kb"
    destination.parent.mkdir(parents=True)
    destination.write_text("occupied", encoding="utf-8")

    with pytest.raises(SkillError, match="target is unsafe"):
        install_agent_skill("codex", user_home=tmp_path)


def test_bundled_skill_path_reports_missing_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = tmp_path / "package/src/portable_kb/skills.py"
    monkeypatch.setattr(skills_module, "__file__", str(fake_module))

    with pytest.raises(SkillError, match="unavailable or unsafe"):
        bundled_skill_path()
