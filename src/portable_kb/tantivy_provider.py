"""Production keyword provider; Rust ranks and Python verifies canonical sections."""
from __future__ import annotations

import json
import math
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from .brains import InstalledBrain, read_manifest
from .native_sidecar import ENGINE_VERSION, NativeSidecar
from .parsing import discover_concepts, parse_concept
from .search_provider import SearchError, SearchHit
from .search_records import normalize_bundle, normalize_item
from .settings import Settings

MAX_RECORD_BYTES = 1_048_576


class TantivyProvider:
    name = "builtin"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def index_path(self, slug: str) -> Path:
        return self.settings.cache_dir / "search" / self.name / slug

    def status(self) -> dict[str, Any]:
        result = {"command": self.settings.native_command, "path": None,
                  "version": None, "compatible": False, "ok": False}
        try:
            with NativeSidecar(self.settings.native_command) as worker:
                result.update(path=worker.command, version=ENGINE_VERSION, compatible=True, ok=True)
        except (SearchError, OSError) as exc:
            result["error"] = str(exc)
        return result

    def load_metadata(self, slug: str) -> dict[str, Any]:
        root = self.index_path(slug)
        _safe_root(root)
        path = root / "CURRENT.json"
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 65_536:
            raise SearchError(f"Native keyword index is unavailable; run `pkb search index {slug}`.")
        try:
            return _metadata(json.loads(path.read_text()))
        except SearchError as exc:
            raise SearchError(f"{exc} Run `pkb search index {slug}`.") from exc
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise SearchError(f"Native index manifest is invalid; run `pkb search index {slug}`.") from exc

    def build(self, brain: InstalledBrain, bundle: Path) -> dict[str, Any]:
        root = self.index_path(brain.slug)
        _safe_root(root)
        root.parent.mkdir(parents=True, exist_ok=True)
        records = normalize_bundle(brain, bundle)
        with tempfile.TemporaryDirectory(prefix=".export-", dir=root.parent) as temporary:
            export = Path(temporary) / "records.jsonl"
            with export.open("w", encoding="utf-8") as stream:
                for record in records:
                    line = json.dumps(record.as_dict(), ensure_ascii=False) + "\n"
                    if len(line.encode()) > MAX_RECORD_BYTES:
                        raise SearchError("A canonical section exceeds the 1 MiB index limit.")
                    stream.write(line)
            with NativeSidecar(self.settings.native_command) as worker:
                result = worker.call({"op": "rebuild", "index_path": str(root),
                                      "records_path": str(export),
                                      "brain": {"id": brain.id, "slug": brain.slug,
                                                "commit": brain.commit}}, timeout=300)
                metadata = _metadata(result["manifest"])
                # Publication succeeded; a cleanup problem is visible but cannot
                # turn this into a falsely reported failed publication.
                try:
                    cleanup = worker.call({"op": "cleanup", "index_path": str(root)})
                except SearchError as exc:
                    cleanup = {"error": str(exc)}
        return {**metadata, "index_path": str(root), "cleanup": cleanup, "concept_count": len(discover_concepts(bundle)), "ok": True}

    def query(self, brain: InstalledBrain, query: str, limit: int) -> tuple[SearchHit, ...]:
        root = self.index_path(brain.slug)
        _safe_root(root)
        exact = "item_id" if query.startswith("urn:uuid:") else (
            "path" if query.endswith(".md") else None)
        text = query.removeprefix("knowledge/") if exact == "path" else query
        tokens = re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text)) if not exact else []
        with NativeSidecar(self.settings.native_command) as worker:
            result = worker.call({"op": "query_store", "index_path": str(root),
                                  "query": text, "tokens": tokens, "exact_field": exact,
                                  "limit": min(100, max(limit * 5, 20))})
            metadata = _metadata(result.get("manifest"))
            if (metadata["brain_id"], metadata["brain_slug"], metadata["commit"]) != (
                brain.id, brain.slug, brain.commit):
                raise SearchError(f"Native index changed brain identity or commit; run `pkb search index {brain.slug}`.")
            generation = metadata["generation"]
            records_path = root / "generations" / generation / "records.jsonl"
            if not isinstance(result.get("records_path"), str) or Path(result["records_path"]) != records_path:
                raise SearchError("Native provider returned an unexpected record snapshot.")
            rows = result.get("hits")
            if not isinstance(rows, list) or len(rows) > 100:
                raise SearchError("Native provider returned invalid hits.")
            wanted = set()
            for row in rows:
                if (not isinstance(row, dict) or not isinstance(row.get("section_id"), str)
                        or isinstance(row.get("score"), bool)
                        or not isinstance(row.get("score"), (int, float))
                        or not math.isfinite(row["score"]) or row["section_id"] in wanted
                        or type(row.get("record_offset")) is not int or row["record_offset"] < 0):
                    raise SearchError("Native provider returned invalid section scores or IDs.")
                wanted.add(row["section_id"])
            found = _records(records_path, rows)
            if set(found) != wanted:
                raise SearchError("Native hits do not resolve in the leased record snapshot.")
            checkout = brain.checkout_path(self.settings)
            bundle = checkout / read_manifest(checkout).bundle
            concepts = {path.relative_to(bundle).as_posix(): path for path in discover_concepts(bundle)}
            hits = []
            item_ids = set()
            for row in rows:
                record = found[row["section_id"]]
                if not isinstance(record.get("path"), str):
                    raise SearchError("Native section has an invalid canonical path.")
                source = concepts.get(record["path"])
                if source is None or source.is_symlink():
                    raise SearchError("Native section path is outside the canonical brain.")
                parsed = parse_concept(source, bundle)
                if parsed.item is None:
                    raise SearchError("Native section cannot be remapped to canonical knowledge.")
                canonical = {section.section_id: section.as_dict()
                             for section in normalize_item(brain, parsed.item)}
                if canonical.get(row["section_id"]) != record:
                    raise SearchError("Native section differs from the canonical brain snapshot.")
                if record["item_id"] in item_ids:
                    continue
                item_ids.add(record["item_id"])
                hits.append(SearchHit(path=record["path"], score=row["score"],
                                      title=record["title"], line=record["line_start"],
                                      snippet=record["body"], docid=record["section_id"], line_end=record["line_end"]))
                if len(hits) == limit:
                    break
            return tuple(hits)


def _safe_root(root: Path) -> None:
    for path in (root, root.parent, root.parent.parent):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise SearchError("Native search cache contains an unsafe directory.")


def _metadata(manifest: Any) -> dict[str, Any]:
    if (not isinstance(manifest, dict)
            or any(type(manifest.get(key)) is not int for key in ("schema_version", "index_format", "lease_version")) or manifest.get("schema_version") != 1
            or manifest.get("index_format") != 2 or manifest.get("lease_version") != 1
            or manifest.get("engine_version") != ENGINE_VERSION
            or not isinstance(manifest.get("generation"), str)
            or re.fullmatch(r"gen-[A-Za-z0-9-]{1,124}", manifest["generation"]) is None
            or isinstance(manifest.get("record_count"), bool)
            or not isinstance(manifest.get("record_count"), int) or manifest["record_count"] < 0):
        raise SearchError("Native index format/version is incompatible; rebuild it.")
    brain = manifest.get("brain")
    if (not isinstance(brain, dict) or set(brain) != {"id", "slug", "commit"}
            or not all(isinstance(value, str) and value for value in brain.values())):
        raise SearchError("Native index has no valid brain provenance; rebuild it.")
    return {"schema_version": 1, "provider": "builtin", "mode": "keyword",
            "brain_id": brain["id"], "brain_slug": brain["slug"], "commit": brain["commit"],
            "generation": manifest["generation"], "record_count": manifest["record_count"],
            "engine_version": ENGINE_VERSION}


def _records(path: Path, rows: list[dict]) -> dict[str, dict]:
    if path.is_symlink() or not path.is_file():
        raise SearchError("Native record snapshot is unsafe or unavailable.")
    found = {}
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            for row in rows:
                offset = row["record_offset"]
                if offset >= size:
                    raise SearchError("Native record offset is outside its snapshot.")
                stream.seek(offset)
                line = stream.readline(MAX_RECORD_BYTES + 1)
                if len(line) > MAX_RECORD_BYTES:
                    raise SearchError("Native record exceeds 1 MiB.")
                record = json.loads(line)
                if not isinstance(record, dict) or record.get("section_id") != row["section_id"]:
                    raise SearchError("Native record offset does not resolve to its section ID.")
                found[row["section_id"]] = record
    except (OSError, UnicodeError, ValueError) as exc:
        raise SearchError("Native record snapshot cannot be read safely.") from exc
    return found
