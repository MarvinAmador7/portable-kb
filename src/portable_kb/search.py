"""Validated keyword search and immutable citations independent of the ranker."""

from __future__ import annotations

import math
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from .brains import InstalledBrain, brain_status, load_catalog, read_manifest
from .links import LinkIndex
from .models import KnowledgeItem
from .parsing import RESERVED_NAMES, discover_concepts, parse_concept
from .qmd_provider import QmdProvider
from .search_provider import KeywordSearchProvider, SearchError, SearchHit
from .settings import SearchProvider, Settings
from .tantivy_provider import TantivyProvider

MAX_QUERY_LENGTH = 1_000
MAX_RESULTS = 100


def get_search_provider(settings: Settings) -> KeywordSearchProvider:
    """Select the configured provider without changing schema-v1 QMD settings."""
    return TantivyProvider(settings) if settings.search_provider is SearchProvider.BUILTIN else QmdProvider(settings)


def keyword_index_path(settings: Settings, slug: str) -> Path:
    """Return the disposable keyword state directory for one installed brain."""
    return get_search_provider(settings).index_path(slug)


def qmd_status(settings: Settings) -> dict[str, Any]:
    """Retain the public QMD diagnostic entry point."""
    return QmdProvider(settings).status()


def index_keyword_brain(
    settings: Settings,
    slug: str | None = None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Validate the brain before asking the provider to publish a keyword index."""
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    result = get_search_provider(settings).build(brain, bundle)
    return {**result, "validation_warnings": health["validation_warnings"]}


def search_keyword(
    settings: Settings,
    query: str,
    slug: str | None = None,
    *,
    limit: int = 10,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Search one current brain and remap discovery evidence to canonical items."""
    normalized_query = query.strip()
    if not normalized_query or len(normalized_query) > MAX_QUERY_LENGTH or "\x00" in query:
        raise SearchError(f"Search query must contain 1-{MAX_QUERY_LENGTH} non-NUL characters.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RESULTS:
        raise SearchError(f"Search result limit must be between 1 and {MAX_RESULTS}.")
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    provider = get_search_provider(settings)
    metadata = provider.load_metadata(brain.slug)
    _require_current_index(metadata, brain)
    hits = provider.query(brain, normalized_query, limit)
    concepts = set(discover_concepts(bundle))
    results = [
        _cited_result(hit, brain=brain, bundle=bundle, concepts=concepts, rank=rank)
        for rank, hit in enumerate(hits[:limit], start=1)
    ]
    return {
        "query": normalized_query,
        "provider": provider.name,
        "mode": "keyword",
        "brain": {
            "id": brain.id,
            "slug": brain.slug,
            "name": brain.name,
            "commit": brain.commit,
        },
        "index_commit": str(metadata["commit"]),
        "results": results,
        "validation_warnings": health["validation_warnings"],
        "ok": True,
    }


def get_knowledge(
    settings: Settings,
    reference: str,
    slug: str | None = None,
    *,
    as_of: str | None = None,
    markdown_links: bool = False,
) -> dict[str, Any]:
    """Retrieve a complete concept or an explicitly named reserved document."""
    normalized = reference.strip()
    if PurePosixPath(normalized).name in RESERVED_NAMES:
        if markdown_links:
            raise SearchError("--markdown-links applies to knowledge items, not reserved documents.")
        return get_knowledge_document(settings, normalized, slug, as_of=as_of)
    return get_knowledge_item(
        settings, reference, slug, as_of=as_of, markdown_links=markdown_links
    )


def get_knowledge_document(
    settings: Settings,
    reference: str,
    slug: str | None = None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Read the exact saved UTF-8 index/log blob without assigning concept metadata."""
    relative_text = reference.strip().removeprefix("knowledge/")
    relative = PurePosixPath(relative_text)
    if (
        not relative_text
        or "\\" in reference
        or "\x00" in reference
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.name not in RESERVED_NAMES
        or any(part.startswith(".") for part in relative_text.split("/"))
    ):
        raise SearchError("Reserved document requires a safe bundle-relative index.md or log.md path.")
    brain, checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    path = bundle.joinpath(*relative.parts)
    if (
        not path.resolve().is_relative_to(bundle.resolve())
        or any(bundle.joinpath(*relative.parts[:i]).is_symlink() for i in range(len(relative.parts) + 1))
        or not path.is_file()
    ):
        raise SearchError(f"Reserved document was not found safely in the selected brain: {relative_text}")
    git = shutil.which("git")
    if git is None:
        raise SearchError("Git is required to retrieve the saved document.")
    repository_path = path.relative_to(checkout).as_posix()
    try:
        saved = subprocess.run(
            [git, "--no-replace-objects", "-C", str(checkout), "cat-file", "blob", f"{brain.commit}:{repository_path}"],
            capture_output=True, check=True, timeout=120,
        )
        content = saved.stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        raise SearchError("The reserved document could not be read as saved UTF-8 content.") from exc
    return {
        "brain": {"id": brain.id, "slug": brain.slug, "name": brain.name, "commit": brain.commit},
        "document": {"kind": relative.stem, "path": relative.as_posix(), "content": content},
        "citation": {
            "brain_id": brain.id, "brain_slug": brain.slug,
            "commit": brain.commit, "path": relative.as_posix(),
        },
        "validation_warnings": health["validation_warnings"],
        "ok": True,
    }


def get_knowledge_item(
    settings: Settings,
    reference: str,
    slug: str | None = None,
    *,
    as_of: str | None = None,
    markdown_links: bool = False,
) -> dict[str, Any]:
    """Retrieve one complete, cited item by immutable ID or bundle path."""

    normalized = reference.strip()
    if not normalized or "\x00" in reference:
        raise SearchError("Knowledge item reference must be a non-empty ID or bundle path.")
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    item = _find_item(bundle, normalized)
    metadata = _plain_value(item.metadata)
    result = {
        "brain": {
            "id": brain.id,
            "slug": brain.slug,
            "name": brain.name,
            "commit": brain.commit,
        },
        "item": {
            "id": item.id,
            "path": item.relative_path,
            "title": metadata.get("title"),
            "type": item.type,
            "status": item.status,
            "stale_after": metadata.get("stale_after"),
            "metadata": metadata,
            "body": item.body,
            "content": item.source_text,
        },
        "citation": {
            "brain_id": brain.id,
            "brain_slug": brain.slug,
            "commit": brain.commit,
            "item_id": item.id,
            "path": item.relative_path,
        },
        "validation_warnings": health["validation_warnings"],
        "ok": True,
    }
    if markdown_links:
        try:
            rendered = LinkIndex.load(bundle).markdown_view(item)
        except ValueError as exc:
            raise SearchError(str(exc)) from exc
        result["item"]["rendered_body"] = rendered
        result["item"]["rendered_content"] = item.source_text[:len(item.source_text) - len(item.body)] + rendered
    return result


def _healthy_brain(
    settings: Settings,
    slug: str | None,
    *,
    as_of: str | None,
) -> tuple[InstalledBrain, Path, Path, dict[str, Any]]:
    catalog = load_catalog(settings)
    selected = slug or catalog.active
    if selected is None:
        raise SearchError("No active brain. Install or select one first.")
    brain = catalog.get(selected)
    health = brain_status(settings, brain.slug, as_of=as_of)
    if not health["ok"]:
        raise SearchError(
            "Brain checkout is not clean, pinned, identity-matched, and valid; "
            f"run `pkb brain status {brain.slug}` for details."
        )
    checkout = brain.checkout_path(settings)
    manifest = read_manifest(checkout)
    return brain, checkout, checkout / manifest.bundle, health


def _find_item(bundle: Path, reference: str) -> KnowledgeItem:
    if reference.startswith(('../', './')):
        raise SearchError("Knowledge item path is unsafe, reserved, or lacks a source item context.")
    if (reference.startswith("[[") or not reference.endswith(".md")) and not reference.startswith("urn:uuid:"):
        try:
            return LinkIndex.load(bundle).find(reference)
        except ValueError as exc:
            raise SearchError(str(exc)) from exc
    concepts = discover_concepts(bundle)
    if reference.startswith("urn:uuid:"):
        for path in concepts:
            parsed = parse_concept(path, bundle)
            if parsed.item is not None and parsed.item.id == reference:
                return parsed.item
        raise SearchError(f"Knowledge item ID was not found in the selected brain: {reference}")

    relative_text = reference.removeprefix("knowledge/")
    relative = PurePosixPath(relative_text)
    if (
        not relative_text
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix != ".md"
        or relative.name in RESERVED_NAMES
    ):
        raise SearchError("Knowledge item path is unsafe, reserved, or not a Markdown concept.")
    path = bundle.joinpath(*relative.parts)
    if path not in concepts or path.is_symlink() or not path.is_file():
        raise SearchError(
            f"Knowledge item path was not found in the selected brain: {relative_text}"
        )
    parsed = parse_concept(path, bundle)
    if parsed.item is None or parsed.item.id is None:
        raise SearchError("Knowledge item could not be mapped to a valid immutable citation.")
    return parsed.item


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain_value(child) for child in value]
    return value


def knowledge_links(
    settings: Settings,
    reference: str,
    slug: str | None = None,
    *,
    backlinks: bool = False,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Resolve live body links against one clean, validated pinned snapshot."""
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    selected = _find_item(bundle, reference.strip())
    index = LinkIndex.load(bundle)

    def cite(item: KnowledgeItem) -> dict[str, Any]:
        return {
            "brain_id": brain.id,
            "brain_slug": brain.slug,
            "commit": brain.commit,
            "item_id": item.id,
            "path": item.relative_path,
        }

    results = []
    sources = index.items.values() if backlinks else [selected]
    for source in sources:
        body_start = len(
            source.source_text[: len(source.source_text) - len(source.body)].splitlines()
        )
        for link in index.outgoing(source):
            if link.status in {"external", "resource"}:
                continue
            if backlinks and (
                link.status != "resolved" or link.item is None or link.item.id != selected.id
            ):
                continue
            target = link.item
            result = {
                "kind": link.reference.kind,
                "target": link.reference.target,
                "label": link.reference.label,
                "line": body_start + link.reference.line,
                "resolution": link.status,
                "fragment": link.fragment,
                "candidates": list(link.candidates),
                "source_citation": cite(source),
                "target_citation": cite(target)
                if target is not None and link.status == "resolved"
                else None,
                "target_status": target.status if target else None,
                "target_stale_after": target.metadata.get("stale_after") if target else None,
            }
            follow = source if backlinks else target if link.status == "resolved" else None
            result["get_command"] = (
                ["pkb", "get", follow.id, "--brain", brain.slug, "--json"] if follow else None
            )
            results.append(result)
    return {
        "brain": {"id": brain.id, "slug": brain.slug, "name": brain.name, "commit": brain.commit},
        "citation": cite(selected),
        "direction": "inbound" if backlinks else "outbound",
        "links": results,
        "validation_warnings": health["validation_warnings"],
        "ok": True,
    }


def _require_current_index(metadata: Mapping[str, Any], brain: InstalledBrain) -> None:
    if metadata.get("brain_id") != brain.id or metadata.get("brain_slug") != brain.slug:
        raise SearchError(f"Keyword index identity differs from the selected brain; run `pkb search index {brain.slug}`.")
    if metadata.get("commit") != brain.commit:
        raise SearchError(f"Keyword index is stale after a brain change; run `pkb search index {brain.slug}`.")


def _cited_result(
    hit: SearchHit,
    *,
    brain: InstalledBrain,
    bundle: Path,
    concepts: set[Path],
    rank: int,
) -> dict[str, Any]:
    if (
        not isinstance(hit.path, str)
        or not isinstance(hit.title, str)
        or isinstance(hit.score, bool)
        or not isinstance(hit.score, (int, float))
        or not math.isfinite(hit.score)
    ):
        raise SearchError("Search provider returned invalid discovery fields.")
    relative = PurePosixPath(hit.path)
    if (
        not hit.path
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix != ".md"
        or relative.name in RESERVED_NAMES
    ):
        raise SearchError("Search provider returned an unsafe or reserved knowledge path.")
    path = bundle.joinpath(*relative.parts)
    if path not in concepts or path.is_symlink() or not path.is_file():
        raise SearchError("Search result no longer resolves inside the selected brain bundle.")
    parsed = parse_concept(path, bundle)
    if parsed.item is None or parsed.item.id is None:
        raise SearchError("Search result cannot be mapped to a valid knowledge item citation.")
    item = parsed.item
    if hit.line is not None and (
        isinstance(hit.line, bool)
        or not isinstance(hit.line, int)
        or not 1 <= hit.line <= len(item.source_text.splitlines())
    ):
        raise SearchError("Search provider returned an invalid result line number.")
    result: dict[str, Any] = {
        "rank": rank,
        "score": float(hit.score),
        "title": hit.title,
        "path": item.relative_path,
        "item_id": item.id,
        "type": item.type,
        "status": item.status,
        "stale_after": item.metadata.get("stale_after"),
        "citation": {
            "brain_id": brain.id,
            "brain_slug": brain.slug,
            "commit": brain.commit,
            "item_id": item.id,
            "path": item.relative_path,
        },
    }
    for key in ("docid", "snippet", "context"):
        value = getattr(hit, key)
        if value is not None and not isinstance(value, str):
            raise SearchError(f"Search provider returned an invalid result {key} field.")
        if value is not None:
            result[key] = value
    if hit.line is not None:
        result["line"] = hit.line
    if hit.line_end is not None:
        if (type(hit.line_end) is not int or hit.line is None
                or not hit.line <= hit.line_end <= len(item.source_text.splitlines())):
            raise SearchError("Search provider returned an invalid section line range.")
        result["line_end"] = hit.line_end
    return result
