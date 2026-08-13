from __future__ import annotations

from pathlib import Path

import pytest

from portable_kb.brains import (
    BrainError,
    GitHubVisibility,
    _github_repository_from_source,
    _run_gh,
    add_brain,
    brain_status,
    catalog_path,
    init_brain,
    load_catalog,
    publish_brain_to_github,
    read_manifest,
    save_catalog,
    sync_brain,
    use_brain,
)
from portable_kb.settings import Settings

ACME_ID = "urn:uuid:11111111-1111-4111-8111-111111111111"
BETA_ID = "urn:uuid:22222222-2222-4222-8222-222222222222"


def test_repository_manifest_is_valid() -> None:
    repository = Path(__file__).resolve().parents[1]
    manifest = read_manifest(repository)
    assert manifest.slug == "portable-kb-core"
    assert manifest.bundle == "knowledge"


def test_add_brain_clones_validates_pins_and_selects(
    tmp_path: Path, brain_repo_factory
) -> None:
    source = brain_repo_factory("acme", ACME_ID)
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    brain, catalog, report = add_brain(str(source), settings, as_of="2026-08-12")
    assert report.profile_passes
    assert brain.slug == "acme"
    assert len(brain.commit) == 40
    assert catalog.active == "acme"
    assert brain.checkout_path(settings).is_dir()
    assert load_catalog(settings) == catalog
    assert catalog_path(settings).stat().st_mode & 0o777 == 0o600
    assert brain_status(settings, as_of="2026-08-12")["ok"] is True


def test_init_brain_creates_commits_installs_and_activates_local_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "new-brain"
    monkeypatch.setenv("HOME", str(tmp_path / "unconfigured-home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "unconfigured-xdg"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    result, catalog, report = init_brain(
        str(repository),
        "New Business",
        "new-business",
        settings,
        as_of="2026-08-13",
    )

    assert report.profile_passes
    assert result.repository == str(repository)
    assert result.brain.id.startswith("urn:uuid:")
    assert catalog.active == "new-business"
    assert load_catalog(settings).active == "new-business"
    assert (repository / "brain.yaml").is_file()
    assert (repository / "knowledge/.core-kb.yaml").is_file()
    assert (repository / "knowledge/index.md").is_file()
    assert "## 2026-08-13" in (repository / "knowledge/log.md").read_text(encoding="utf-8")
    assert _git_output(repository, "status", "--porcelain") == ""
    assert _git_output(repository, "branch", "--show-current").strip() == "main"
    assert _git_output(repository, "rev-parse", "HEAD").strip() == result.brain.commit
    assert _git_output(repository, "show", "-s", "--format=%an <%ae>", "HEAD").strip() == (
        "Portable KB <portable-kb@localhost.invalid>"
    )
    assert brain_status(settings, as_of="2026-08-13")["ok"] is True


def test_init_brain_rejects_occupied_repository_and_remote_source(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    existing = occupied / "README.md"
    existing.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(BrainError, match="empty directory"):
        init_brain(
            str(occupied),
            "Occupied Brain",
            "occupied-brain",
            settings,
            as_of="2026-08-13",
        )
    assert existing.read_text(encoding="utf-8") == "keep me\n"

    with pytest.raises(BrainError, match="starts with a local repository"):
        init_brain(
            "https://github.com/example/empty-brain.git",
            "Remote Brain",
            "remote-brain",
            settings,
            as_of="2026-08-13",
        )


def test_publish_brain_creates_github_repo_pushes_and_updates_distribution_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "local-authoring"
    initialized, _, report = init_brain(
        str(repository),
        "Remote Business",
        "remote-business",
        settings,
        as_of="2026-08-13",
    )
    assert report.profile_passes
    remote = tmp_path / "created-on-github.git"
    real_which = __import__("shutil").which

    def which(command: str) -> str | None:
        return "/fake/gh" if command == "gh" else real_which(command)

    def create_repository(_executable: str, *arguments: str) -> str:
        assert arguments[:4] == (
            "repo",
            "create",
            "acme/remote-business",
            "--private",
        )
        _git_output(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(remote))
        _git(repository, "remote", "add", "origin", str(remote))
        return ""

    monkeypatch.setattr("portable_kb.brains.shutil.which", which)
    monkeypatch.setattr("portable_kb.brains._run_gh", create_repository)

    result, catalog = publish_brain_to_github(
        settings,
        "acme/remote-business",
        visibility=GitHubVisibility.PRIVATE,
    )

    assert result.repository == str(repository)
    assert result.github_repository == "acme/remote-business"
    assert result.visibility is GitHubVisibility.PRIVATE
    assert result.brain.source == str(remote)
    assert result.brain.authoring == str(repository)
    assert catalog.active == "remote-business"
    assert load_catalog(settings).get("remote-business").source == str(remote)
    assert load_catalog(settings).get("remote-business").authoring == str(repository)
    assert _git_output(remote, "rev-parse", "refs/heads/main").strip() == initialized.brain.commit
    assert "slug: remote-business" in _git_output(
        remote, "show", "refs/heads/main:brain.yaml"
    )
    checkout = initialized.brain.checkout_path(settings)
    assert _git_output(checkout, "remote", "get-url", "origin").strip() == str(remote)
    assert brain_status(settings, as_of="2026-08-13")["ok"] is True


def test_publish_brain_validates_target_and_preserves_local_brain_without_gh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    initialized, _, _ = init_brain(
        str(tmp_path / "local-only"),
        "Local Only",
        "local-only",
        settings,
        as_of="2026-08-13",
    )
    with pytest.raises(BrainError, match="org/repo"):
        publish_brain_to_github(settings, "not-a-repository")
    real_which = __import__("shutil").which
    monkeypatch.setattr(
        "portable_kb.brains.shutil.which",
        lambda command: None if command == "gh" else real_which(command),
    )
    with pytest.raises(BrainError, match="GitHub CLI is required"):
        publish_brain_to_github(settings, "acme/local-only")
    assert load_catalog(settings).get("local-only").source == initialized.repository
    assert brain_status(settings, as_of="2026-08-13")["ok"] is True


def test_publish_brain_refuses_missing_active_dirty_drifted_and_wrong_origin(
    tmp_path: Path,
) -> None:
    empty_settings = Settings(data_dir=tmp_path / "empty-data", cache_dir=tmp_path / "empty-cache")
    with pytest.raises(BrainError, match="No active brain"):
        publish_brain_to_github(empty_settings, "acme/missing")

    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = tmp_path / "guarded"
    initialized, _, _ = init_brain(
        str(repository),
        "Guarded",
        "guarded",
        settings,
        as_of="2026-08-13",
    )
    dirty = repository / "uncommitted.md"
    dirty.write_text("not committed\n", encoding="utf-8")
    with pytest.raises(BrainError, match="uncommitted changes"):
        publish_brain_to_github(settings, "acme/guarded")
    dirty.unlink()

    _git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "Uninstalled commit",
    )
    with pytest.raises(BrainError, match="does not match the installed commit"):
        publish_brain_to_github(settings, "acme/guarded")
    _git(repository, "reset", "--quiet", "--hard", initialized.brain.commit)

    _git(repository, "remote", "add", "origin", "git@github.com:other/brain.git")
    with pytest.raises(BrainError, match="different origin"):
        publish_brain_to_github(settings, "acme/guarded")


def test_github_runner_is_noninteractive_and_reports_cli_failure(tmp_path: Path) -> None:
    assert _github_repository_from_source("https://github.com/Acme/Brain.git") == "acme/brain"
    assert _github_repository_from_source("/local/repository") is None

    success = tmp_path / "gh-success"
    success.write_text(
        "#!/bin/sh\nprintf '%s' \"$GH_PROMPT_DISABLED:$GIT_TERMINAL_PROMPT:$*\"\n",
        encoding="utf-8",
    )
    success.chmod(0o755)
    assert _run_gh(str(success), "repo", "create", "acme/brain") == (
        "1:0:repo create acme/brain"
    )

    failure = tmp_path / "gh-failure"
    failure.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'repository already exists' >&2\nexit 7\n",
        encoding="utf-8",
    )
    failure.chmod(0o755)
    with pytest.raises(BrainError, match="repository already exists"):
        _run_gh(str(failure), "repo", "create", "acme/brain")


def test_init_brain_rolls_back_owned_files_on_precommit_failures(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    bad_date = tmp_path / "bad-date"
    with pytest.raises(ValueError, match="Invalid isoformat"):
        init_brain(
            str(bad_date),
            "Bad Date",
            "bad-date",
            settings,
            as_of="not-a-date",
        )
    assert not bad_date.exists()

    committed = tmp_path / "committed-empty"
    committed.mkdir()
    _git(committed, "init", "--quiet", "--initial-branch=main")
    _git(committed, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "--allow-empty", "-m", "Existing")
    with pytest.raises(BrainError, match="no commits"):
        init_brain(
            str(committed),
            "Committed Empty",
            "committed-empty",
            settings,
            as_of="2026-08-13",
        )


def test_add_rejects_duplicate_slug_and_invalid_bundle(
    tmp_path: Path, brain_repo_factory
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    first = brain_repo_factory("acme", ACME_ID)
    add_brain(str(first), settings, as_of="2026-08-12")
    duplicate = brain_repo_factory("acme-copy", BETA_ID)
    manifest = duplicate / "brain.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("slug: acme-copy", "slug: acme"),
        encoding="utf-8",
    )
    _commit(duplicate, "Duplicate slug")
    with pytest.raises(BrainError, match="slug is already installed"):
        add_brain(str(duplicate), settings, as_of="2026-08-12")

    invalid = brain_repo_factory("invalid", "urn:uuid:33333333-3333-4333-8333-333333333333")
    (invalid / "knowledge/.core-kb.yaml").unlink()
    _commit(invalid, "Break bundle")
    with pytest.raises(BrainError, match="failed validation"):
        add_brain(str(invalid), settings, as_of="2026-08-12")
    assert not (settings.data_dir / "brains/invalid").exists()


def test_use_brain_and_status_detect_local_drift(tmp_path: Path, brain_repo_factory) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    acme, _, _ = add_brain(
        str(brain_repo_factory("acme", ACME_ID)), settings, as_of="2026-08-12"
    )
    beta, _, _ = add_brain(
        str(brain_repo_factory("beta", BETA_ID)), settings, as_of="2026-08-12"
    )
    assert load_catalog(settings).active == "acme"
    assert use_brain("beta", settings) == beta
    assert load_catalog(settings).active == "beta"
    with pytest.raises(BrainError, match="not installed"):
        use_brain("missing", settings)

    (acme.checkout_path(settings) / "brain.yaml").write_text(
        (acme.checkout_path(settings) / "brain.yaml").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    status = brain_status(settings, "acme", as_of="2026-08-12")
    assert status["dirty"] is True
    assert status["ok"] is False


def test_catalog_and_sources_reject_unsafe_input(tmp_path: Path, brain_repo_factory) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    source = brain_repo_factory("acme", ACME_ID)
    _, catalog, _ = add_brain(str(source), settings, as_of="2026-08-12")
    path = catalog_path(settings)
    real = settings.data_dir / "catalog-real.yaml"
    path.rename(real)
    path.symlink_to(real.name)
    with pytest.raises(BrainError, match="not a regular file"):
        load_catalog(settings)
    with pytest.raises(BrainError, match="symbolic-link"):
        save_catalog(catalog, settings)
    real.unlink()
    with pytest.raises(BrainError, match="not a regular file"):
        load_catalog(settings)

    fresh = Settings(data_dir=tmp_path / "fresh", cache_dir=tmp_path / "fresh-cache")
    with pytest.raises(BrainError, match="credentials"):
        add_brain("https://token@github.com/example/brain.git", fresh)
    with pytest.raises(BrainError, match="credentials"):
        add_brain("https://github.com/example/brain.git?token=secret", fresh)

    unsafe = Settings(data_dir=tmp_path / "unsafe", cache_dir=tmp_path / "unsafe-cache")
    unsafe.data_dir.mkdir()
    catalog_path(unsafe).write_text(
        """schema_version: 1
active: ../escape
brains:
  - id: urn:uuid:55555555-5555-4555-8555-555555555555
    slug: ../escape
    name: Escape
    source: local
    checkout: brains/../escape
    commit: "5555555555555555555555555555555555555555"
""",
        encoding="utf-8",
    )
    with pytest.raises(BrainError, match="invalid identity"):
        load_catalog(unsafe)


def test_sync_validates_candidate_then_fast_forwards(tmp_path: Path, brain_repo_factory) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    source = brain_repo_factory("acme", ACME_ID)
    installed, _, _ = add_brain(str(source), settings, as_of="2026-08-12")
    previous = installed.commit
    manifest = source / "brain.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("name: Acme", "name: Acme Updated"),
        encoding="utf-8",
    )
    _commit(source, "Update brain")

    result = sync_brain(settings, "acme", as_of="2026-08-12")
    assert result["changed"] is True
    assert result["previous_commit"] == previous
    assert result["current_commit"] != previous
    updated = load_catalog(settings).get("acme")
    assert updated.commit == result["current_commit"]
    assert updated.name == "Acme Updated"
    assert brain_status(settings, "acme", as_of="2026-08-12")["ok"] is True

    unchanged = sync_brain(settings, "acme", as_of="2026-08-12")
    assert unchanged["changed"] is False
    assert unchanged["current_commit"] == result["current_commit"]


def test_sync_refuses_dirty_checkout_and_invalid_candidate(
    tmp_path: Path, brain_repo_factory
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    source = brain_repo_factory("acme", ACME_ID)
    installed, _, _ = add_brain(str(source), settings, as_of="2026-08-12")
    checkout = installed.checkout_path(settings)
    (checkout / "brain.yaml").write_text(
        (checkout / "brain.yaml").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(BrainError, match="local changes"):
        sync_brain(settings, "acme", as_of="2026-08-12")
    _git(checkout, "restore", "brain.yaml")

    (source / "knowledge/.core-kb.yaml").unlink()
    _commit(source, "Publish invalid bundle")
    with pytest.raises(BrainError, match="Remote knowledge bundle failed validation"):
        sync_brain(settings, "acme", as_of="2026-08-12")
    assert _git_output(checkout, "rev-parse", "HEAD").strip() == installed.commit
    assert load_catalog(settings).get("acme").commit == installed.commit


def test_sync_refuses_identity_change_origin_change_and_rewritten_history(
    tmp_path: Path, brain_repo_factory
) -> None:
    first_settings = Settings(data_dir=tmp_path / "first", cache_dir=tmp_path / "cache-first")
    first_source = brain_repo_factory("first", ACME_ID)
    first, _, _ = add_brain(str(first_source), first_settings, as_of="2026-08-12")
    first_manifest = first_source / "brain.yaml"
    first_manifest.write_text(
        first_manifest.read_text(encoding="utf-8").replace(ACME_ID, BETA_ID),
        encoding="utf-8",
    )
    _commit(first_source, "Change identity")
    with pytest.raises(BrainError, match="changes the installed brain identity"):
        sync_brain(first_settings, "first", as_of="2026-08-12")
    assert load_catalog(first_settings).get("first").commit == first.commit

    second_settings = Settings(data_dir=tmp_path / "second", cache_dir=tmp_path / "cache-second")
    second_source = brain_repo_factory(
        "second", "urn:uuid:33333333-3333-4333-8333-333333333333"
    )
    second, _, _ = add_brain(str(second_source), second_settings, as_of="2026-08-12")
    _git(second.checkout_path(second_settings), "remote", "set-url", "origin", str(first_source))
    with pytest.raises(BrainError, match="origin differs"):
        sync_brain(second_settings, "second", as_of="2026-08-12")

    third_settings = Settings(data_dir=tmp_path / "third", cache_dir=tmp_path / "cache-third")
    third_source = brain_repo_factory(
        "third", "urn:uuid:44444444-4444-4444-8444-444444444444"
    )
    third, _, _ = add_brain(str(third_source), third_settings, as_of="2026-08-12")
    manifest = third_source / "brain.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("name: Third", "name: Rewritten"),
        encoding="utf-8",
    )
    _git(third_source, "add", "brain.yaml")
    _git(third_source, "commit", "--quiet", "--amend", "--no-edit")
    with pytest.raises(BrainError, match="not a fast-forward"):
        sync_brain(third_settings, "third", as_of="2026-08-12")
    assert load_catalog(third_settings).get("third").commit == third.commit


def test_sync_restores_checkout_when_catalog_write_fails(
    tmp_path: Path, brain_repo_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    source = brain_repo_factory("acme", ACME_ID)
    installed, _, _ = add_brain(str(source), settings, as_of="2026-08-12")
    manifest = source / "brain.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("name: Acme", "name: Acme Next"),
        encoding="utf-8",
    )
    _commit(source, "Update before catalog failure")

    def fail_save(*args, **kwargs) -> None:
        raise OSError("simulated catalog failure")

    monkeypatch.setattr("portable_kb.brains.save_catalog", fail_save)
    with pytest.raises(BrainError, match="checkout was restored"):
        sync_brain(settings, "acme", as_of="2026-08-12")
    checkout = installed.checkout_path(settings)
    assert _git_output(checkout, "rev-parse", "HEAD").strip() == installed.commit
    assert _git_output(checkout, "status", "--porcelain").strip() == ""


def _commit(repository: Path, message: str) -> None:
    _git(repository, "add", "-A")
    _git(repository, "commit", "--quiet", "-m", message)


def _git(repository: Path, *arguments: str) -> None:
    _git_output(repository, *arguments)


def _git_output(repository: Path, *arguments: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
