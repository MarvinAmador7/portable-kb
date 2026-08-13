"""Isolated QMD keyword indexing and cited search for installed brains."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from ruamel.yaml import YAML

from .brains import InstalledBrain, brain_status, load_catalog, read_manifest
from .models import KnowledgeItem
from .parsing import RESERVED_NAMES, discover_concepts, parse_concept
from .settings import Settings

INDEX_SCHEMA_VERSION = 1
MAX_QUERY_LENGTH = 1_000
MAX_RESULTS = 100


class SearchError(RuntimeError):
    """Raised when a search index or query cannot be handled safely."""


def keyword_index_path(settings: Settings, slug: str) -> Path:
    """Return the disposable QMD state directory for one installed brain."""

    return settings.cache_dir / "search" / "qmd" / slug


def index_keyword_brain(
    settings: Settings,
    slug: str | None = None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build and atomically publish a model-free QMD BM25 index."""

    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    executable = _qmd_executable(settings)
    root = settings.cache_dir / "search" / "qmd"
    if root.is_symlink():
        raise SearchError(f"Search cache root must not be a symbolic link: {root}")
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".index-{brain.slug}-", dir=root))
    try:
        _write_qmd_config(stage, brain, bundle)
        version = _run_qmd(executable, stage, "--version", timeout=30).strip()
        _run_qmd(executable, stage, "update", timeout=300)
        database = stage / "cache" / "qmd" / "index.sqlite"
        if database.is_symlink() or not database.is_file():
            raise SearchError("QMD completed without producing its isolated index database.")
        concepts = discover_concepts(bundle)
        metadata = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "provider": "qmd",
            "mode": "keyword",
            "brain_id": brain.id,
            "brain_slug": brain.slug,
            "commit": brain.commit,
            "bundle": "knowledge",
            "concept_count": len(concepts),
            "qmd_version": version,
        }
        _write_json(stage / "metadata.json", metadata)
        _publish_index(stage, keyword_index_path(settings, brain.slug), root)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {
        **metadata,
        "index_path": str(keyword_index_path(settings, brain.slug)),
        "validation_warnings": health["validation_warnings"],
        "ok": True,
    }


def search_keyword(
    settings: Settings,
    query: str,
    slug: str | None = None,
    *,
    limit: int = 10,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Search one current brain with BM25 and attach immutable citations."""

    normalized_query = query.strip()
    if not normalized_query or len(normalized_query) > MAX_QUERY_LENGTH or "\x00" in query:
        raise SearchError(f"Search query must contain 1-{MAX_QUERY_LENGTH} non-NUL characters.")
    if isinstance(limit, bool) or not 1 <= limit <= MAX_RESULTS:
        raise SearchError(f"Search result limit must be between 1 and {MAX_RESULTS}.")
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    executable = _qmd_executable(settings)
    state = keyword_index_path(settings, brain.slug)
    metadata = _load_index_metadata(state)
    _require_current_index(metadata, brain)
    candidate_limit = min(MAX_RESULTS, max(limit * 5, 20))
    output = _run_qmd(
        executable,
        state,
        "search",
        normalized_query,
        "--format",
        "json",
        "--collection",
        brain.slug,
        "-n",
        str(candidate_limit),
        timeout=120,
    )
    rows = _load_qmd_results(output)
    results = [
        _cited_result(row, brain=brain, bundle=bundle, rank=rank)
        for rank, row in enumerate(rows[:limit], start=1)
    ]
    return {
        "query": normalized_query,
        "provider": "qmd",
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


def get_knowledge_item(
    settings: Settings,
    reference: str,
    slug: str | None = None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Retrieve one complete, cited item by immutable ID or bundle path."""

    normalized = reference.strip()
    if not normalized or "\x00" in reference:
        raise SearchError("Knowledge item reference must be a non-empty ID or bundle path.")
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    item = _find_item(bundle, normalized)
    metadata = _plain_value(item.metadata)
    return {
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
            "run `pkb brain status` for details."
        )
    checkout = brain.checkout_path(settings)
    manifest = read_manifest(checkout)
    return brain, checkout, checkout / manifest.bundle, health


def _find_item(bundle: Path, reference: str) -> KnowledgeItem:
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
        raise SearchError(f"Knowledge item path was not found in the selected brain: {relative_text}")
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


def _qmd_executable(settings: Settings) -> str:
    executable = shutil.which(settings.qmd_command)
    if executable is None:
        raise SearchError(
            "QMD is not installed or configured. Install @tobilu/qmd, then run "
            "`pkb doctor` before indexing."
        )
    return executable


def _write_qmd_config(state: Path, brain: InstalledBrain, bundle: Path) -> None:
    config_dir = state / "config"
    config_dir.mkdir(parents=True)
    payload = {
        "global_context": f"Portable KB brain: {brain.name}",
        "collections": {
            brain.slug: {
                "path": str(bundle),
                "pattern": "**/*.md",
                "ignore": ["index.md", "log.md", "**/index.md", "**/log.md"],
                "includeByDefault": True,
                "context": {"/": f"Portable KB brain {brain.name} at commit {brain.commit}"},
            }
        },
    }
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    path = config_dir / "index.yml"
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(payload, stream)
    path.chmod(0o600)


def _qmd_environment(state: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("INDEX_PATH", None)
    environment.update(
        {
            "QMD_CONFIG_DIR": str(state / "config"),
            "XDG_CACHE_HOME": str(state / "cache"),
            "QMD_FORCE_CPU": "1",
            "NO_COLOR": "1",
            "PWD": str(state),
        }
    )
    return environment


def _run_qmd(executable: str, state: Path, *arguments: str, timeout: int) -> str:
    try:
        completed = subprocess.run(
            [executable, *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=state,
            env=_qmd_environment(state),
        )
    except subprocess.TimeoutExpired as exc:
        raise SearchError(f"QMD timed out while running: {arguments[0]}") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
        detail = str(detail).strip()[-2_000:]
        raise SearchError(f"QMD failed while running {arguments[0]}: {detail}") from exc
    return completed.stdout


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _publish_index(stage: Path, target: Path, root: Path) -> None:
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise SearchError(f"Search index target is unsafe: {target}")
    if not target.exists():
        os.replace(stage, target)
        return
    backup = Path(tempfile.mkdtemp(prefix=f".previous-{target.name}-", dir=root))
    backup.rmdir()
    os.replace(target, backup)
    try:
        os.replace(stage, target)
    except Exception:
        os.replace(backup, target)
        raise
    shutil.rmtree(backup)


def _load_index_metadata(state: Path) -> Mapping[str, Any]:
    path = state / "metadata.json"
    if state.is_symlink() or not state.is_dir() or path.is_symlink() or not path.is_file():
        raise SearchError("Keyword index is missing; run `pkb search index` first.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SearchError("Keyword index metadata is invalid; rebuild the index.") from exc
    expected = {
        "schema_version",
        "provider",
        "mode",
        "brain_id",
        "brain_slug",
        "commit",
        "bundle",
        "concept_count",
        "qmd_version",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise SearchError("Keyword index metadata has an unsupported structure; rebuild it.")
    if (
        payload.get("schema_version") != INDEX_SCHEMA_VERSION
        or payload.get("provider") != "qmd"
        or payload.get("mode") != "keyword"
        or payload.get("bundle") != "knowledge"
        or not all(
            isinstance(payload.get(key), str) and payload.get(key)
            for key in ("brain_id", "brain_slug", "commit", "qmd_version")
        )
        or isinstance(payload.get("concept_count"), bool)
        or not isinstance(payload.get("concept_count"), int)
        or payload.get("concept_count", -1) < 0
    ):
        raise SearchError("Keyword index metadata is incompatible; rebuild it.")
    return payload


def _require_current_index(metadata: Mapping[str, Any], brain: InstalledBrain) -> None:
    if metadata.get("brain_id") != brain.id or metadata.get("brain_slug") != brain.slug:
        raise SearchError("Keyword index identity differs from the selected brain; rebuild it.")
    if metadata.get("commit") != brain.commit:
        raise SearchError("Keyword index is stale after a brain change; rebuild it.")


def _load_qmd_results(output: str) -> Sequence[Mapping[str, Any]]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SearchError("QMD returned invalid JSON search output.") from exc
    if not isinstance(payload, list) or not all(isinstance(row, Mapping) for row in payload):
        raise SearchError("QMD returned an unsupported JSON search result structure.")
    return payload


def _cited_result(
    row: Mapping[str, Any],
    *,
    brain: InstalledBrain,
    bundle: Path,
    rank: int,
) -> dict[str, Any]:
    display_path = row.get("file")
    score = row.get("score")
    title = row.get("title")
    if (
        not isinstance(display_path, str)
        or isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not 0 <= score <= 1
        or not isinstance(title, str)
    ):
        raise SearchError("QMD returned a result with invalid file, score, or title fields.")
    prefix = f"qmd://{brain.slug}/"
    if not display_path.startswith(prefix):
        raise SearchError("QMD returned a result outside the selected brain collection.")
    relative_text = display_path.removeprefix(prefix)
    relative = PurePosixPath(relative_text)
    if (
        not relative_text
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.name in RESERVED_NAMES
    ):
        raise SearchError("QMD returned an unsafe or reserved knowledge path.")
    path = bundle.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file() or not path.is_relative_to(bundle):
        raise SearchError("QMD result no longer resolves inside the selected brain bundle.")
    parsed = parse_concept(path, bundle)
    if parsed.item is None or parsed.item.id is None:
        raise SearchError("QMD result cannot be mapped to a valid knowledge item citation.")
    item = parsed.item
    line = row.get("line")
    if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line < 1):
        raise SearchError("QMD returned an invalid result line number.")
    result: dict[str, Any] = {
        "rank": rank,
        "score": float(score),
        "title": title,
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
        value = row.get(key)
        if value is not None and not isinstance(value, str):
            raise SearchError(f"QMD returned an invalid result {key} field.")
        if value is not None:
            result[key] = value
    if line is not None:
        result["line"] = line
    return result
