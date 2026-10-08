"""Navigation must preserve scope, identity, source text and review semantics."""

from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from typer.testing import CliRunner

from portable_kb.brains import add_brain, load_catalog
from portable_kb.cli import app
from portable_kb.links import LinkIndex, extract_links, heading_anchors
from portable_kb.operations import plan_move
from portable_kb.parsing import parse_concept
from portable_kb.search import SearchError, get_knowledge_item, knowledge_links
from portable_kb.serialization import quoted, render_concept
from portable_kb.settings import Settings, save_settings
from portable_kb.validation import validate_bundle, validate_transition


def write_item(root: Path, path: str, body: str, number: int = 1):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_concept(
            {
                "type": "concept",
                "id": f"urn:uuid:{UUID(int=number, version=4)}",
                "title": Path(path).stem.replace("-", " ").title(),
                "description": "Synthetic linked context used only for deterministic tests.",
                "status": "draft",
                "created_at": quoted("2026-08-14T00:00:00Z"),
                "updated_at": quoted("2026-08-14T00:00:00Z"),
                "generated": {
                    "by": "human:fixture-author",
                    "at": quoted("2026-08-14T00:00:00Z"),
                    "method": "human-authored",
                },
            },
            body,
        )
    )
    return parse_concept(target, root).item


@pytest.fixture
def graph(tmp_path):
    root = tmp_path / "knowledge"
    hub = write_item(root, "context/hub.md", "# Hub\n\n[[reviewer|QA contact]]\n", 1)
    reviewer = write_item(
        root, "people/reviewer.md", "# Reviewer\n\n## Current `scope`\n\n## Current `scope`\n", 2
    )
    return root, hub, reviewer


@pytest.mark.parametrize(
    "target,expected,fragment",
    [
        ("reviewer", "resolved", None),
        ("reviewer.md", "resolved", None),
        ("people/reviewer", "resolved", None),
        ("/people/reviewer.md", "resolved", None),
        ("../people/reviewer#Current scope", "resolved", "current-scope"),
        ("reviewer#current-scope-1", "resolved", "current-scope-1"),
        ("reviewer#missing", "missing-heading", "missing"),
        ("reviewer#", "missing-heading", ""),
        ("missing", "missing", None),
        ("../../secret", "unsafe", None),
        ("people\\reviewer", "unsafe", None),
        ("https://example.invalid", "unsafe", None),
        ("", "missing", None),
    ],
)
def test_wiki_resolution(graph, target, expected, fragment):
    root, hub, reviewer = graph
    hub.body = f"[[{target}|display label]]"
    (link,) = LinkIndex.load(root).outgoing(hub)
    assert link.status == expected
    assert link.fragment == fragment
    if expected == "resolved":
        assert link.item.id == reviewer.id


def test_short_names_never_choose_an_arbitrary_directory(graph):
    root, hub, reviewer = graph
    write_item(root, "teams/reviewer.md", "# Reviewer\n", 3)
    index = LinkIndex.load(root)
    (ambiguous,) = index.outgoing(hub)
    assert ambiguous.status == "ambiguous"
    assert ambiguous.candidates == ("people/reviewer.md", "teams/reviewer.md")
    with pytest.raises(ValueError, match="ambiguous.*people/reviewer.md.*teams/reviewer.md"):
        index.find("reviewer")
    assert index.find("people/reviewer").id == reviewer.id
    assert index.find(f"[[{reviewer.id}|contact]]").id == reviewer.id
    assert index.find("[[people/reviewer#Current scope|QA]]").id == reviewer.id
    with pytest.raises(ValueError, match="source item context"):
        index.find("[[#Heading]]")


def test_prose_links_ignore_code_comments_escapes_and_embeds():
    body = (
        "[[real]] [second](second.md)\n"
        "`[[inline]]` ``[inline](hidden.md)``\n"
        "<!-- [[comment]] -->\n\\[[escaped]] ![[attachment]]\n"
        "    [[indented-code]]\n"
        "~~~md\n[[fenced]]\n~~~\n"
        "````md\n```\n[[long-fence]]\n````\n"
        "[[final]]\n"
    )
    links = extract_links(body)
    assert [link.target for link in links] == ["real", "second.md", "final"]
    assert links[-1].line == 13
    assert body[links[-1].start : links[-1].end] == "[[final]]"


def test_standard_links_external_resources_and_safe_heading_targets(graph):
    root, hub, reviewer = graph
    (root / "asset.txt").write_text("reference artifact")
    hub.body = "[QA](../people/reviewer.md#current-scope) [external](https://example.invalid) [asset](/asset.txt) [escape](../../secret.md)"
    links = LinkIndex.load(root).outgoing(hub)
    assert [link.status for link in links] == ["resolved", "external", "resource", "unsafe"]
    assert links[0].item.id == reviewer.id
    assert heading_anchors(reviewer.body) == {"reviewer", "current-scope", "current-scope-1"}


def test_markdown_view_preserves_canonical_text_and_ignores_code(graph):
    root, hub, _reviewer = graph
    hub.body = "# Hub\n\n[[reviewer#Current scope|QA]]\n`[[reviewer]]`\n"
    before = hub.body
    rendered = LinkIndex.load(root).markdown_view(hub)
    assert rendered == "# Hub\n\n[QA](../people/reviewer.md#current-scope)\n`[[reviewer]]`\n"
    assert hub.body == before
    hub.body = "[[missing]]"
    with pytest.raises(ValueError, match="Cannot render wikilink.*missing"):
        LinkIndex.load(root).markdown_view(hub)


def test_symlink_target_cannot_escape_or_be_read(graph, tmp_path):
    root, hub, _reviewer = graph
    outside = write_item(tmp_path, "outside.md", "# Outside\n", 5)
    (root / "outside.md").symlink_to(outside.path)
    with pytest.raises(ValueError, match="unsafe concept path"):
        LinkIndex.load(root)
    index = LinkIndex([hub, outside], root)
    hub.body = "[Outside](/outside.md)"
    assert index.outgoing(hub)[0].status == "unsafe"


def test_valid_wiki_relation_explains_uuid_and_invalid_links_have_draft_severity(bundle):
    path = bundle / "curated/concepts/material-change.md"
    original = path.read_text()
    path.write_text(
        original.replace(
            "[verification is snapshot evidence](verification-is-evidence.md)",
            "[[verification-is-evidence|verification is snapshot evidence]]",
        )
    )
    report = validate_bundle(bundle, as_of="2026-08-14")
    assert not any(
        f.code in {"KB-W406", "KB-W407"} and f.path.endswith("material-change.md")
        for f in report.findings
    )
    draft = write_item(bundle, "concepts/linked-draft.md", "# Linked draft\n\n[[missing]]\n", 12)
    report = validate_bundle(bundle, as_of="2026-08-14")
    finding = next(
        f for f in report.findings if f.code == "KB-W407" and f.path == draft.relative_path
    )
    assert finding.severity.label == "warning"
    draft.path.write_text(draft.path.read_text().replace("status: draft", "status: stable"))
    report = validate_bundle(bundle, as_of="2026-08-14")
    assert any(
        f.code == "KB-W407" and f.severity.label == "error" and f.path == draft.relative_path
        for f in report.findings
    )
    draft.path.write_text(draft.path.read_text().replace("[[missing]]", "[[verification-is-evidence]]"))
    report = validate_bundle(bundle, as_of="2026-08-14")
    assert report.profile_passes, report.render_text()
    assert not any(f.code == "KB-W407" and f.path == draft.relative_path for f in report.findings)


def test_reviewed_move_preserves_wiki_identity_labels_and_code_examples(bundle):
    source = "curated/concepts/verification-is-evidence.md"
    destination = "curated/concepts/review-evidence.md"
    caller = bundle / "curated/concepts/material-change.md"
    caller.write_text(
        caller.read_text().replace(
            "[verification is snapshot evidence](verification-is-evidence.md)",
            "[[verification-is-evidence|verification is snapshot evidence]]",
        )
        + "\n`[[verification-is-evidence]]`\n"
    )
    before = parse_concept(bundle / source, bundle).item
    plan = plan_move(
        bundle, source, destination, timestamp="2026-08-14T00:00:00Z", as_of="2026-08-14"
    )
    assert plan.validation.profile_passes, plan.validation.render_text()
    plan.apply()
    after = parse_concept(bundle / destination, bundle).item
    assert after.id == before.id
    assert after.metadata == before.metadata
    assert (
        "[[curated/concepts/review-evidence|verification is snapshot evidence]]"
        in caller.read_text()
    )
    assert "`[[verification-is-evidence]]`" in caller.read_text()
    assert validate_bundle(bundle, as_of="2026-08-14").profile_passes


def test_heading_retarget_is_material_even_when_item_uuid_is_unchanged(bundle, tmp_path):
    import shutil

    base = tmp_path / "base"
    path = bundle / "curated/concepts/material-change.md"
    path.write_text(path.read_text() + "\n[[verification-is-evidence#Definition|Evidence]]\n")
    shutil.copytree(bundle, base)
    path.write_text(path.read_text().replace("#Definition|Evidence", "#Context|Evidence"))
    report = validate_transition(base, bundle, as_of="2026-08-14")
    assert any(f.code == "KB-W126" for f in report.findings)


def test_cli_navigation_is_cited_scoped_read_only_and_needs_no_search_index(
    tmp_path, brain_repo_factory
):
    source = brain_repo_factory("linked", "urn:uuid:55555555-5555-4555-8555-555555555555")
    root = source / "knowledge"
    hub = write_item(root, "inbox/hub.md", "# Hub\n\n[[reviewer#Scope|QA]]\n[[missing]]\n", 30)
    reviewer = write_item(
        root, "people/reviewer.md", "# Reviewer\n\n## Scope\n\nSynthetic QA contact.\n", 31
    )
    renderable = write_item(
        root, "inbox/renderable-hub.md", "# Renderable hub\n\n[[reviewer#Scope|QA]]\n", 32
    )
    subprocess.run(["git", "-C", str(source), "add", "knowledge"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "commit", "--quiet", "-m", "Add synthetic links"], check=True
    )
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    add_brain(str(source), settings, as_of="2026-08-14")
    checkout = settings.data_dir / "brains/linked"
    before = {
        p.relative_to(checkout).as_posix(): p.read_bytes()
        for p in checkout.rglob("*")
        if p.is_file()
    }
    links = knowledge_links(settings, "hub", "linked", as_of="2026-08-14")
    resolved, missing = links["links"]
    assert resolved["source_citation"]["item_id"] == hub.id
    assert resolved["target_citation"]["item_id"] == reviewer.id
    assert resolved["get_command"] == ["pkb", "get", reviewer.id, "--brain", "linked", "--json"]
    assert resolved["line"] == next(
        i for i, line in enumerate(hub.source_text.splitlines(), 1) if line.startswith("[[reviewer")
    )
    assert missing["resolution"] == "missing" and missing["target_citation"] is None
    back = knowledge_links(settings, "[[reviewer]]", "linked", backlinks=True, as_of="2026-08-14")
    assert back["links"][0]["source_citation"] == links["citation"]
    assert back["links"][0]["get_command"][2] == hub.id
    plain = get_knowledge_item(
        settings, "reviewer", "linked", as_of="2026-08-14", markdown_links=True
    )
    assert plain["item"]["content"] == plain["item"]["rendered_content"]
    view = get_knowledge_item(
        settings, renderable.id, "linked", as_of="2026-08-14", markdown_links=True
    )
    assert view["item"]["content"] == renderable.source_text
    assert "[QA](../people/reviewer.md#scope)" in view["item"]["rendered_content"]
    assert "[[reviewer#Scope|QA]]" in view["item"]["content"]
    assert view["citation"]["item_id"] == renderable.id
    with pytest.raises(SearchError, match="Cannot render wikilink.*missing"):
        get_knowledge_item(settings, hub.id, "linked", as_of="2026-08-14", markdown_links=True)
    assert load_catalog(settings).active == "linked"
    assert not settings.cache_dir.exists()
    assert before == {
        p.relative_to(checkout).as_posix(): p.read_bytes()
        for p in checkout.rglob("*")
        if p.is_file()
    }
    config = tmp_path / "config.yaml"
    save_settings(settings, config)
    runner = CliRunner()
    assert (
        runner.invoke(
            app, ["links", "hub", "--brain", "linked", "--config", str(config), "--json"]
        ).exit_code
        == 0
    )
    assert (
        "inbox/hub.md"
        in runner.invoke(app, ["backlinks", "reviewer", "--config", str(config)]).stdout
    )
    assert (
        "Synthetic QA contact"
        in runner.invoke(
            app, ["get", "reviewer", "--markdown-links", "--config", str(config)]
        ).stdout
    )
    (checkout / "knowledge/inbox/hub.md").write_text("dirty")
    with pytest.raises(SearchError, match="not clean"):
        knowledge_links(settings, "hub", "linked", as_of="2026-08-14")


def test_named_brain_navigation_keeps_duplicate_ids_and_slugs_separate(
    tmp_path, brain_repo_factory
):
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    for number, slug in enumerate(("primary", "alternate"), 1):
        repository = brain_repo_factory(slug, f"urn:uuid:55555555-5555-4555-8555-{number:012d}")
        root = repository / "knowledge"
        write_item(root, "inbox/hub.md", "# Hub\n\n[[reviewer]]\n", 101)
        write_item(root, "people/reviewer.md", f"# Reviewer\n\nSynthetic {slug} context.\n", 102)
        subprocess.run(["git", "-C", str(repository), "add", "knowledge"], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "commit", "--quiet", "-m", "Seed navigation"], check=True
        )
        add_brain(str(repository), settings, as_of="2026-08-14")
    primary = knowledge_links(settings, "hub", "primary", as_of="2026-08-14")
    alternate = knowledge_links(settings, "hub", "alternate", as_of="2026-08-14")
    first = primary["links"][0]["target_citation"]
    second = alternate["links"][0]["target_citation"]
    assert first["item_id"] == second["item_id"]
    assert first["path"] == second["path"]
    assert first["brain_id"] != second["brain_id"]
    assert first["commit"] != second["commit"]
    assert first["brain_slug"] == "primary" and second["brain_slug"] == "alternate"
    retrieved = get_knowledge_item(settings, second["item_id"], "alternate", as_of="2026-08-14")
    assert retrieved["citation"] == second
    assert "Synthetic alternate context" in retrieved["item"]["body"]
    assert load_catalog(settings).active == "primary"
