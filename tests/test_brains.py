from __future__ import annotations

from pathlib import Path

import pytest

from portable_kb.brains import (
    BrainError,
    add_brain,
    brain_status,
    catalog_path,
    load_catalog,
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
