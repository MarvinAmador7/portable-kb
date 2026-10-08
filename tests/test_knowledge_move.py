"""Moves preserve governed snapshots while repairing only affected references."""

from __future__ import annotations

import json
import subprocess

import pytest
from typer.testing import CliRunner

from portable_kb.authoring import plan_knowledge_move, save_knowledge_move
from portable_kb.brains import BrainError, add_brain, load_catalog, use_brain
from portable_kb.cli import app
from portable_kb.links import LinkIndex
from portable_kb.operations import OperationError, plan_move
from portable_kb.parsing import parse_concept
from portable_kb.serialization import render_concept
from portable_kb.settings import Settings, save_settings
from portable_kb.validation import validate_bundle

SOURCE = "curated/concepts/verification-is-evidence.md"
DESTINATION = "curated/concepts/review-evidence.md"
CALLER = "curated/concepts/material-change.md"
TIMESTAMP = "2026-08-14T00:00:00Z"
AS_OF = "2026-08-14"


def git(repository, *arguments):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def installed(tmp_path, brain_repo_factory):
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    repository = brain_repo_factory("moving", "urn:uuid:55555555-5555-4555-8555-555555555555")
    add_brain(str(repository), settings, as_of=AS_OF)
    config = tmp_path / "config.yaml"
    save_settings(settings, config)
    return settings, repository, config


def test_cli_move_preview_save_and_cited_retrieval(installed):
    settings, repository, config = installed
    root = repository / "knowledge"
    original = parse_concept(root / SOURCE, root).item
    before, head = snapshot(root), git(repository, "rev-parse", "HEAD")
    args = [
        "knowledge",
        "move",
        original.id,
        DESTINATION,
        "--brain",
        "moving",
        "--timestamp",
        TIMESTAMP,
        "--config",
        str(config),
        "--as-of",
        AS_OF,
    ]
    runner = CliRunner()
    text = runner.invoke(app, args)
    assert text.exit_code == 0, text.output
    assert "Plan only; no files changed" in text.output
    preview = runner.invoke(app, [*args, "--json"])
    assert preview.exit_code == 0, preview.output
    payload = json.loads(preview.output)
    assert payload["identity_preserved"] and not payload["verification_invalidated"]
    assert payload["proposed_item"]["metadata"] == original.metadata
    assert snapshot(root) == before and git(repository, "rev-parse", "HEAD") == head
    applied = runner.invoke(app, [*args, "--apply", "--json"])
    assert applied.exit_code == 0, applied.output
    saved = json.loads(applied.output)
    assert saved["citation"]["path"] == DESTINATION
    assert saved["retrieval_ready"] and saved["needs_reindex"] and not saved["search_ready"]
    retrieved = runner.invoke(app, saved["get_command"][1:])
    assert retrieved.exit_code == 0, retrieved.output
    final = json.loads(retrieved.output)
    assert final["citation"] == saved["citation"]
    assert final["item"]["metadata"] == original.metadata
    assert final["item"]["body"] == original.body
    assert not (root / SOURCE).exists()
    assert "review-evidence.md" in (root / CALLER).read_text()
    assert "review-evidence.md" in (root / "curated/concepts/index.md").read_text()
    assert git(repository, "status", "--porcelain") == ""
    assert git(repository, "rev-list", "--count", f"{head}..HEAD") == "1"
    changed = set(
        git(repository, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
    )
    assert changed == {"knowledge/" + c["path"] for c in saved["changes"]}
    assert load_catalog(settings).get("moving").commit == saved["saved_version"]
    missing = runner.invoke(
        app, ["get", SOURCE, "--brain", "moving", "--config", str(config), "--json"]
    )
    assert missing.exit_code == 1


def test_scoped_move_does_not_select_or_mutate_other_brain(installed, brain_repo_factory):
    settings, repository, _ = installed
    other = brain_repo_factory("other", "urn:uuid:66666666-6666-4666-8666-666666666666")
    add_brain(str(other), settings, as_of=AS_OF)
    use_brain("other", settings)
    before = snapshot(other / "knowledge")
    plan = plan_knowledge_move(
        settings,
        "knowledge/" + SOURCE,
        "knowledge/" + DESTINATION,
        slug="moving",
        timestamp=TIMESTAMP,
        as_of=AS_OF,
    )
    result = save_knowledge_move(settings, plan, as_of=AS_OF)
    assert load_catalog(settings).active == "other"
    assert snapshot(other / "knowledge") == before
    assert result.as_dict()["citation"]["brain_slug"] == "moving"
    assert (repository / "knowledge" / DESTINATION).exists()


@pytest.mark.parametrize("change", ["head", "source-dirty", "checkout-dirty", "catalog"])
def test_move_refuses_changed_state_before_writing(installed, change):
    settings, repository, _ = installed
    root = repository / "knowledge"
    plan = plan_knowledge_move(settings, SOURCE, DESTINATION, timestamp=TIMESTAMP, as_of=AS_OF)
    if change == "head":
        git(repository, "commit", "--quiet", "--allow-empty", "-m", "Concurrent version")
    elif change == "source-dirty":
        (repository / "unrelated.txt").write_text("Unfinished work")
    elif change == "checkout-dirty":
        checkout = load_catalog(settings).get("moving").checkout_path(settings)
        (checkout / "unrelated.txt").write_text("Unfinished work")
    else:
        from dataclasses import replace

        from portable_kb.brains import save_catalog

        catalog = load_catalog(settings)
        save_catalog(catalog.updating(replace(catalog.get("moving"), name="Changed")), settings)
    before = snapshot(root)
    with pytest.raises((BrainError, ValueError)):
        save_knowledge_move(settings, plan, as_of=AS_OF)
    assert snapshot(root) == before
    assert not (root / DESTINATION).exists()


@pytest.mark.parametrize(
    "destination",
    [
        SOURCE,
        CALLER,
        "../escape.md",
        "/escape.md",
        "x\\y.md",
        "bad\x00.md",
        "index.md",
        ".hidden/item.md",
    ],
)
def test_move_refuses_unsafe_or_existing_destinations(installed, destination):
    settings, repository, config = installed
    before = snapshot(repository / "knowledge")
    result = CliRunner().invoke(
        app,
        [
            "knowledge",
            "move",
            SOURCE,
            destination,
            "--apply",
            "--config",
            str(config),
            "--as-of",
            AS_OF,
        ],
    )
    assert result.exit_code == 1, result.output
    assert snapshot(repository / "knowledge") == before


def test_move_repairs_authored_navigation_and_preserves_literal_examples(bundle):
    caller = bundle / CALLER
    text = caller.read_text().replace(
        "[verification is snapshot evidence](verification-is-evidence.md)",
        "[[verification-is-evidence|verification is snapshot evidence]]",
    )
    examples = "\n`[Example](verification-is-evidence.md)`\n<!-- [Example](verification-is-evidence.md) -->\n```md\n[Example](verification-is-evidence.md)\n```\n"
    caller.write_text(text + "\n[[immutable-knowledge-identity]]\n" + examples)
    index = bundle / "index.md"
    index.write_text(
        index.read_text()
        + "\nAuthored: [[verification-is-evidence|Review]] [Review](/curated/concepts/verification-is-evidence.md#definition)\n"
    )
    unrelated = bundle / "curated/concepts/immutable-knowledge-identity.md"
    before = unrelated.read_bytes()
    plan_move(bundle, SOURCE, DESTINATION, timestamp=TIMESTAMP, as_of=AS_OF).apply()
    assert examples in caller.read_text()
    assert "[[immutable-knowledge-identity]]" in caller.read_text()
    assert unrelated.read_bytes() == before
    assert "[[curated/concepts/review-evidence|Review]]" in index.read_text()
    assert "[Review](/curated/concepts/review-evidence.md#definition)" in index.read_text()
    assert validate_bundle(bundle, as_of=AS_OF).profile_passes


def test_directory_move_rebases_outbound_links_and_retains_review(bundle):
    original = parse_concept(bundle / SOURCE, bundle).item
    destination = "curated/review/review-evidence.md"
    plan_move(bundle, SOURCE, destination, timestamp=TIMESTAMP, as_of=AS_OF).apply()
    moved = parse_concept(bundle / destination, bundle).item
    assert moved.metadata == original.metadata
    before = LinkIndex(
        [original, *[i for i in LinkIndex.load(bundle).items.values() if i.id != original.id]],
        bundle,
    )
    assert [link.item.id for link in before.outgoing(original) if link.item] == [
        link.item.id for link in LinkIndex.load(bundle).outgoing(moved) if link.item
    ]
    assert validate_bundle(bundle, as_of=AS_OF).profile_passes


def test_move_blocks_relative_source_retargeting_without_metadata_edits(bundle):
    path = bundle / SOURCE
    original = parse_concept(path, bundle).item
    metadata = dict(original.metadata)
    metadata["sources"] = [*metadata.get("sources", []), {"resource": "evidence.txt"}]
    (path.parent / "evidence.txt").write_text("Local evidence")
    path.write_text(render_concept(metadata, original.body))
    before = snapshot(bundle)
    with pytest.raises(OperationError, match="local source provenance"):
        plan_move(
            bundle, SOURCE, "curated/review/review-evidence.md", timestamp=TIMESTAMP, as_of=AS_OF
        )
    assert snapshot(bundle) == before


def test_move_rolls_back_partial_file_writes_before_source_deletion(bundle, monkeypatch):
    import portable_kb.changes as changes

    plan = plan_move(bundle, SOURCE, DESTINATION, timestamp=TIMESTAMP, as_of=AS_OF)
    before = snapshot(bundle)
    real_write, attempts = changes._atomic_write, 0

    def fail_once(path, content):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise OSError("Injected write failure")
        real_write(path, content)

    monkeypatch.setattr(changes, "_atomic_write", fail_once)
    with pytest.raises(OSError, match="Injected"):
        plan.apply()
    assert snapshot(bundle) == before


def test_move_repairs_new_stem_ambiguity_without_changing_unrelated_wikilinks(bundle):
    from test_links import write_item

    write_item(bundle, "teams/review-evidence.md", "# Other review evidence\n", 901)
    caller = write_item(
        bundle,
        "inbox/collision.md",
        "# Collision\n\n[[review-evidence|Team context]] [[immutable-knowledge-identity]]\n",
        902,
    )
    target = "curated/concepts/review-evidence.md"
    plan_move(bundle, SOURCE, target, timestamp=TIMESTAMP, as_of=AS_OF).apply()
    text = caller.path.read_text()
    assert "[[teams/review-evidence|Team context]]" in text
    assert "[[immutable-knowledge-identity]]" in text
    assert validate_bundle(bundle, as_of=AS_OF).profile_passes


def test_move_preserves_verified_stable_snapshot(bundle):
    from conftest import authorize

    from portable_kb.operations import plan_promote

    reviewer = "human:reviewer-42"
    authorize(bundle, "procedure", reviewer)
    source = "procedures/review-stale-knowledge.md"
    plan_promote(
        bundle,
        source,
        reviewer=reviewer,
        timestamp=TIMESTAMP,
        verification_scope="Reviewed these exact procedure steps against the lifecycle design.",
        as_of=AS_OF,
    ).apply()
    before = parse_concept(bundle / source, bundle).item
    destination = "procedures/review-knowledge-freshness.md"
    plan_move(bundle, source, destination, timestamp=TIMESTAMP, as_of=AS_OF).apply()
    after = parse_concept(bundle / destination, bundle).item
    assert after.status == "stable" and after.metadata["verified"]
    assert after.metadata == before.metadata and after.body == before.body


def test_move_preserves_markdown_labels_queries_and_encoded_targets(bundle):
    source = "curated/concepts/verification-is-evidence.md"
    caller = bundle / CALLER
    caller.write_text(
        caller.read_text()
        + '\n[verification-is-evidence.md](/curated/concepts/verification-is-evidence.md?view=full#definition "Review")\n'
    )
    destination = "curated/concepts/review evidence.md"
    plan_move(bundle, source, destination, timestamp=TIMESTAMP, as_of=AS_OF).apply()
    assert (
        '[verification-is-evidence.md](/curated/concepts/review%20evidence.md?view=full#definition "Review")'
        in caller.read_text()
    )
    assert validate_bundle(bundle, as_of=AS_OF).profile_passes
