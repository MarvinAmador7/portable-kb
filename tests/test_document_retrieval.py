"""Reserved documents remain scoped, cited saved content rather than concepts."""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from portable_kb.authoring import plan_knowledge_move, save_knowledge_move
from portable_kb.brains import add_brain, load_catalog, use_brain
from portable_kb.cli import app
from portable_kb.search import (
    SearchError,
    get_knowledge,
    get_knowledge_document,
    get_knowledge_item,
)
from portable_kb.settings import Settings, save_settings

AS_OF = "2026-08-14"


@pytest.fixture
def installed(tmp_path, brain_repo_factory):
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    source = brain_repo_factory("documents", "urn:uuid:55555555-5555-4555-8555-555555555555")
    add_brain(str(source), settings, as_of=AS_OF)
    config = tmp_path / "config.yaml"
    save_settings(settings, config)
    return settings, source, config


def git(root, *args):
    return subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Document Test",
            "-c",
            "user.email=document-test@example.invalid",
            *args,
        ],
        check=True,
        capture_output=True,
    ).stdout


@pytest.mark.parametrize("path", ["index.md", "log.md", "curated/concepts/index.md"])
def test_get_complete_reserved_document_is_cited_and_read_only(installed, path):
    settings, source, config = installed
    brain = load_catalog(settings).get("documents")
    checkout = brain.checkout_path(settings)
    source_head, checkout_head = (
        git(source, "rev-parse", "HEAD"),
        git(checkout, "rev-parse", "HEAD"),
    )
    catalog = load_catalog(settings)
    expected = git(checkout, "cat-file", "blob", f"{brain.commit}:knowledge/{path}").decode()
    response = get_knowledge(settings, "knowledge/" + path, as_of=AS_OF)
    assert response["ok"]
    assert response["document"] == {"kind": Path(path).stem, "path": path, "content": expected}
    assert "item" not in response and "item_id" not in response["citation"]
    assert response["citation"] == {
        "brain_id": brain.id,
        "brain_slug": brain.slug,
        "commit": brain.commit,
        "path": path,
    }
    runner = CliRunner()
    args = ["get", path, "--brain", "documents", "--config", str(config), "--as-of", AS_OF]
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == response
    text = runner.invoke(app, args)
    assert text.exit_code == 0, text.output
    assert text.output.endswith(expected)
    assert f"documents@{brain.commit[:12]}:{path}" in text.output
    assert load_catalog(settings) == catalog
    assert git(source, "rev-parse", "HEAD") == source_head
    assert git(checkout, "rev-parse", "HEAD") == checkout_head
    assert git(source, "status", "--porcelain") == git(checkout, "status", "--porcelain") == b""
    assert not any(p.is_file() for p in settings.cache_dir.rglob("*"))


@pytest.mark.parametrize(
    "path",
    [
        "../index.md",
        "/index.md",
        "folder/../../log.md",
        ".hidden/index.md",
        "folder/.hidden/log.md",
        "./index.md",
        "folder\\index.md",
        "bad\x00/index.md",
        "brain.yaml",
        "SCHEMA.md",
        "inbox/ordinary.md",
    ],
)
def test_document_api_refuses_unsafe_and_arbitrary_paths(installed, path):
    settings, _, _ = installed
    with pytest.raises(SearchError, match="safe bundle-relative"):
        get_knowledge_document(settings, path, as_of=AS_OF)


def test_document_dispatch_missing_and_rendering_are_explicit(installed):
    settings, _, config = installed
    with pytest.raises(SearchError, match="not found"):
        get_knowledge(settings, "missing/index.md", as_of=AS_OF)
    with pytest.raises(SearchError, match="applies to knowledge items"):
        get_knowledge(settings, "index.md", markdown_links=True, as_of=AS_OF)
    with pytest.raises(SearchError, match="reserved"):
        get_knowledge_item(settings, "index.md", as_of=AS_OF)
    failed = CliRunner().invoke(app, ["get", "../index.md", "--config", str(config), "--json"])
    assert failed.exit_code == 1 and "safe bundle-relative" in failed.output
    concept = "curated/concepts/verification-is-evidence.md"
    assert get_knowledge(settings, concept, as_of=AS_OF) == get_knowledge_item(
        settings, concept, as_of=AS_OF
    )


def test_documents_do_not_leak_between_brains_or_change_selection(installed, brain_repo_factory):
    settings, _, _ = installed
    other = brain_repo_factory("other", "urn:uuid:66666666-6666-4666-8666-666666666666")
    log = other / "knowledge/log.md"
    log.write_text(log.read_text() + "\nOther brain history only.\n")
    git(other, "add", "knowledge/log.md")
    git(other, "commit", "-m", "Different saved history")
    add_brain(str(other), settings, as_of=AS_OF)
    use_brain("other", settings)
    primary = get_knowledge(settings, "log.md", "documents", as_of=AS_OF)
    alternate = get_knowledge(settings, "log.md", as_of=AS_OF)
    assert "Other brain history only" not in primary["document"]["content"]
    assert "Other brain history only" in alternate["document"]["content"]
    assert primary["citation"]["brain_slug"] == "documents"
    assert alternate["citation"]["brain_slug"] == "other"
    assert load_catalog(settings).active == "other"


@pytest.mark.parametrize("unsafe", ["dirty", "pin", "symlink", "parent-symlink"])
def test_reserved_reads_reject_unhealthy_or_symlinked_checkout(installed, unsafe):
    settings, _, _ = installed
    checkout = load_catalog(settings).get("documents").checkout_path(settings)
    bundle = checkout / "knowledge"
    if unsafe == "dirty":
        (bundle / "log.md").write_text("Uncommitted history")
    elif unsafe == "pin":
        git(checkout, "commit", "--allow-empty", "-m", "Unpinned version")
    elif unsafe == "symlink":
        (bundle / "log.md").unlink()
        (bundle / "log.md").symlink_to(bundle / "index.md")
    else:
        (bundle / "linked").symlink_to(bundle / "curated/concepts", target_is_directory=True)
    reference = "linked/index.md" if unsafe == "parent-symlink" else "log.md"
    with pytest.raises(SearchError):
        get_knowledge(settings, reference, as_of=AS_OF)


def test_post_move_indexes_and_log_are_readable_at_the_saved_commit(installed):
    settings, _, _ = installed
    old, new = "curated/concepts/verification-is-evidence.md", "curated/concepts/review-evidence.md"
    plan = plan_knowledge_move(settings, old, new, timestamp="2026-08-14T00:00:00Z", as_of=AS_OF)
    result = save_knowledge_move(settings, plan, as_of=AS_OF)
    for change in plan.change_set.changes:
        if Path(change.relative_path).name not in {"index.md", "log.md"}:
            continue
        response = get_knowledge(settings, change.relative_path, as_of=AS_OF)
        assert response["document"]["content"] == change.after
        assert response["citation"]["commit"] == result.commit
    log = get_knowledge(settings, "log.md", as_of=AS_OF)
    assert "Move" in log["document"]["content"] and new in log["document"]["content"]


def test_document_citation_stays_exact_if_checkout_changes_after_health_check(
    installed, monkeypatch
):
    from portable_kb import search

    settings, _, _ = installed
    brain = load_catalog(settings).get("documents")
    checkout = brain.checkout_path(settings)
    expected = git(checkout, "cat-file", "blob", f"{brain.commit}:knowledge/log.md").decode()
    original = search._healthy_brain

    def concurrent_edit(*args, **kwargs):
        result = original(*args, **kwargs)
        (checkout / "knowledge/log.md").write_text("Uncommitted concurrent history\n")
        return result

    monkeypatch.setattr(search, "_healthy_brain", concurrent_edit)
    response = get_knowledge(settings, "log.md", as_of=AS_OF)
    assert response["document"]["content"] == expected
    assert response["citation"]["commit"] == brain.commit
