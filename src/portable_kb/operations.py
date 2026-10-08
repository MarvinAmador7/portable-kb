"""Safe lifecycle operations that produce validated, reviewable change sets."""

from __future__ import annotations

import posixpath
import re
import shutil
import tempfile
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from ruamel.yaml import YAML

from .changes import ChangeSet, diff_trees
from .indexes import generate_indexes
from .links import LinkIndex
from .models import ValidationReport
from .parsing import RESERVED_NAMES, discover_concepts, parse_concept
from .serialization import load_editable, quoted, render_concept
from .validation import MARKDOWN_LINK, UTC_DATETIME, validate_bundle, validate_transition


class OperationError(RuntimeError):
    """A lifecycle operation is unsafe or violates its preconditions."""


class OperationValidationError(OperationError):
    """A proposed lifecycle operation failed deterministic validation."""

    def __init__(self, report: ValidationReport):
        self.report = report
        summary = "; ".join(
            f"{finding.code} {finding.path}: {finding.message}" for finding in report.errors[:5]
        )
        super().__init__(f"Proposed operation is invalid: {summary}")


def plan_create(
    bundle: str | Path,
    relative_path: str,
    *,
    item_type: str,
    title: str,
    description: str,
    actor: str,
    method: str,
    timestamp: str,
    body: str,
    sources: Sequence[Mapping[str, Any]] | None = None,
    confidence: Mapping[str, Any] | None = None,
    tags: Sequence[str] | None = None,
    sensitivity: str | None = None,
    as_of: date | str | None = None,
) -> ChangeSet:
    """Plan creation of a new draft with one newly generated UUID."""

    _require_timestamp(timestamp)
    clean_path = _validate_concept_path(relative_path)

    def mutate(root: Path) -> None:
        path = root / clean_path
        if path.exists():
            raise OperationError(f"Concept already exists: {clean_path}")
        metadata: MutableMapping[str, Any] = {
            "type": item_type,
            "id": f"urn:uuid:{uuid4()}",
            "title": title,
            "description": description,
            "status": "draft",
            "created_at": quoted(timestamp),
            "updated_at": quoted(timestamp),
            "generated": {"by": actor, "at": quoted(timestamp), "method": method},
        }
        if tags:
            metadata["tags"] = list(tags)
        if sources:
            metadata["sources"] = _quote_source_dates(sources)
        if confidence:
            metadata["confidence"] = dict(confidence)
        metadata["sensitivity"] = sensitivity or _load_config(root).get("default_sensitivity")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_concept(metadata, body), encoding="utf-8", newline="\n")
        _append_log(root, timestamp[:10], f"**Creation**: Added [{title}]({clean_path}).")

    return _plan(bundle, "create", mutate, as_of=as_of)


def plan_update(
    bundle: str | Path,
    relative_path: str,
    *,
    actor: str,
    method: str,
    timestamp: str,
    body: str | None = None,
    metadata_updates: Mapping[str, Any] | None = None,
    approve_sensitivity_lowering: bool = False,
    as_of: date | str | None = None,
) -> ChangeSet:
    """Plan a material update while preserving identity and imported fields."""

    _require_timestamp(timestamp)
    clean_path = _validate_concept_path(relative_path)

    def mutate(root: Path) -> None:
        path = root / clean_path
        metadata, old_body = load_editable(path, root)
        immutable_id = metadata.get("id")
        created_at = metadata.get("created_at")
        old_sensitivity = metadata.get("sensitivity") or _load_config(root).get(
            "default_sensitivity"
        )
        for key, value in (metadata_updates or {}).items():
            if key in {"id", "created_at", "verified"}:
                raise OperationError(f"plan_update cannot change protected field: {key}")
            metadata[key] = value
        new_sensitivity = metadata.get("sensitivity") or _load_config(root).get(
            "default_sensitivity"
        )
        sensitivity_rank = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
        if (
            isinstance(old_sensitivity, str)
            and isinstance(new_sensitivity, str)
            and sensitivity_rank.get(new_sensitivity, -1)
            < sensitivity_rank.get(old_sensitivity, -1)
            and (not actor.startswith("human:") or not approve_sensitivity_lowering)
        ):
            raise OperationError(
                "Lowering sensitivity requires an explicit human actor and approval flag."
            )
        metadata["id"] = immutable_id
        metadata["created_at"] = created_at
        if metadata.get("status") == "stable" and metadata.get("type") in {
            "decision",
            "procedure",
            "policy",
        }:
            metadata["status"] = "draft"
        metadata["updated_at"] = quoted(timestamp)
        metadata["generated"] = {
            "by": actor,
            "at": quoted(timestamp),
            "method": method,
        }
        metadata.pop("verified", None)
        _quote_dates_in_place(metadata)
        if isinstance(metadata.get("sources"), list):
            metadata["sources"] = _quote_source_dates(metadata["sources"])
        path.write_text(
            render_concept(metadata, body if body is not None else old_body),
            encoding="utf-8",
            newline="\n",
        )
        _append_log(
            root,
            timestamp[:10],
            f"**Update**: Revised [{metadata.get('title', clean_path)}]({clean_path}).",
        )

    return _plan(bundle, "update", mutate, as_of=as_of)


def plan_promote(
    bundle: str | Path,
    relative_path: str,
    *,
    reviewer: str,
    timestamp: str,
    verification_scope: str,
    valid_from: str | None = None,
    stale_after: str | None = None,
    as_of: date | str | None = None,
) -> ChangeSet:
    """Plan draft-to-stable promotion by a configured human reviewer."""

    _require_timestamp(timestamp)
    _require_verification_scope(verification_scope)
    clean_path = _validate_concept_path(relative_path)

    def mutate(root: Path) -> None:
        path = root / clean_path
        metadata, body = load_editable(path, root)
        if metadata.get("status") != "draft":
            raise OperationError("Only a draft can be promoted.")
        item_type = str(metadata.get("type"))
        _require_authorized_reviewer(root, item_type, reviewer)
        metadata["status"] = "stable"
        metadata["updated_at"] = quoted(timestamp)
        generated = metadata.get("generated")
        if not isinstance(generated, MutableMapping):
            raise OperationError("generated must be a mapping.")
        generated["at"] = quoted(timestamp)
        metadata["verified"] = [{"by": reviewer, "at": quoted(timestamp)}]
        if item_type in {"decision", "policy"}:
            effective = valid_from or timestamp[:10]
            metadata["valid_from"] = quoted(effective)
        if item_type in {"procedure", "policy", "system"}:
            deadline = stale_after or _default_stale_after(root, item_type, timestamp[:10])
            metadata["stale_after"] = quoted(deadline)
        body = _append_verification_scope(body, reviewer, timestamp, verification_scope)
        path.write_text(render_concept(metadata, body), encoding="utf-8", newline="\n")
        _append_log(
            root,
            timestamp[:10],
            f"**Promotion**: Promoted [{metadata.get('title', clean_path)}]({clean_path}) to stable.",
        )

    return _plan(bundle, "promote", mutate, as_of=as_of)


def plan_reverify(
    bundle: str | Path,
    relative_path: str,
    *,
    reviewer: str,
    timestamp: str,
    verification_scope: str,
    stale_after: str | None = None,
    as_of: date | str | None = None,
) -> ChangeSet:
    """Plan a current-snapshot re-verification and freshness renewal."""

    _require_timestamp(timestamp)
    _require_verification_scope(verification_scope)
    clean_path = _validate_concept_path(relative_path)

    def mutate(root: Path) -> None:
        path = root / clean_path
        metadata, body = load_editable(path, root)
        if metadata.get("status") != "stable":
            raise OperationError("Only stable knowledge can be reverified.")
        item_type = str(metadata.get("type"))
        _require_authorized_reviewer(root, item_type, reviewer)
        metadata["updated_at"] = quoted(timestamp)
        generated = metadata.get("generated")
        if not isinstance(generated, MutableMapping):
            raise OperationError("generated must be a mapping.")
        generated["at"] = quoted(timestamp)
        metadata["verified"] = [{"by": reviewer, "at": quoted(timestamp)}]
        if item_type in {"procedure", "policy", "system"}:
            metadata["stale_after"] = quoted(
                stale_after or _default_stale_after(root, item_type, timestamp[:10])
            )
        body = _append_verification_scope(body, reviewer, timestamp, verification_scope)
        path.write_text(render_concept(metadata, body), encoding="utf-8", newline="\n")
        _append_log(
            root,
            timestamp[:10],
            f"**Verification**: Reverified [{metadata.get('title', clean_path)}]({clean_path}).",
        )

    return _plan(bundle, "reverify", mutate, as_of=as_of)


def plan_move(
    bundle: str | Path,
    source_path: str,
    destination_path: str,
    *,
    timestamp: str,
    as_of: date | str | None = None,
) -> ChangeSet:
    """Plan a path move with link and index repair and no identity change."""

    _require_timestamp(timestamp)
    source = _validate_concept_path(source_path)
    destination = _validate_concept_path(destination_path)

    def mutate(root: Path) -> None:
        _move_and_rewrite(root, source, destination)
        _append_log(
            root,
            timestamp[:10],
            f"**Move**: Moved [{PurePosixPath(destination).stem}]({destination}) from `{source}`.",
        )

    return _plan(bundle, "move", mutate, as_of=as_of)


def plan_supersede(
    bundle: str | Path,
    replacement_path: str,
    predecessor_paths: Sequence[str],
    *,
    reviewer: str,
    operator: str,
    timestamp: str,
    reason: str,
    verification_scope: str,
    valid_from: str | None = None,
    stale_after: str | None = None,
    as_of: date | str | None = None,
) -> ChangeSet:
    """Plan reciprocal replacement and deprecation as one validated change."""

    _require_timestamp(timestamp)
    _require_verification_scope(verification_scope)
    if not operator.startswith("human:"):
        raise OperationError("Supersession requires an explicit human operator.")
    replacement = _validate_concept_path(replacement_path)
    predecessors = tuple(_validate_concept_path(path) for path in predecessor_paths)
    if not predecessors:
        raise OperationError("Supersession needs at least one predecessor.")

    def mutate(root: Path) -> None:
        replacement_file = root / replacement
        replacement_meta, replacement_body = load_editable(replacement_file, root)
        if replacement_meta.get("status") != "draft":
            raise OperationError("Replacement must begin as a draft.")
        item_type = str(replacement_meta.get("type"))
        _require_authorized_reviewer(root, item_type, reviewer)
        predecessor_items: list[tuple[str, MutableMapping[str, Any], str]] = []
        for predecessor in predecessors:
            metadata, body = load_editable(root / predecessor, root)
            if metadata.get("status") != "stable":
                raise OperationError(f"Predecessor is not stable: {predecessor}")
            predecessor_items.append((predecessor, metadata, body))
        predecessor_ids = [str(metadata["id"]) for _, metadata, _ in predecessor_items]
        replacement_meta["status"] = "stable"
        replacement_meta["updated_at"] = quoted(timestamp)
        replacement_meta["generated"] = {
            "by": operator,
            "at": quoted(timestamp),
            "method": replacement_meta["generated"]["method"],
        }
        replacement_meta["verified"] = [{"by": reviewer, "at": quoted(timestamp)}]
        replacement_body = _append_verification_scope(
            replacement_body, reviewer, timestamp, verification_scope
        )
        replacement_meta["supersedes"] = predecessor_ids
        if item_type in {"decision", "policy"}:
            replacement_meta["valid_from"] = quoted(valid_from or timestamp[:10])
        if item_type in {"procedure", "policy", "system"}:
            replacement_meta["stale_after"] = quoted(
                stale_after or _default_stale_after(root, item_type, timestamp[:10])
            )
        links = [_relative_link(replacement, predecessor) for predecessor in predecessors]
        replacement_body = _append_supersession(
            replacement_body,
            "Replaces "
            + ", ".join(
                f"[{path.stem}]({link})"
                for path, link in zip(map(PurePosixPath, predecessors), links, strict=True)
            )
            + f". {reason}",
        )
        replacement_file.write_text(
            render_concept(replacement_meta, replacement_body), encoding="utf-8", newline="\n"
        )
        replacement_id = str(replacement_meta["id"])
        for predecessor, metadata, body in predecessor_items:
            metadata["status"] = "deprecated"
            metadata["updated_at"] = quoted(timestamp)
            metadata["generated"] = {
                "by": operator,
                "at": quoted(timestamp),
                "method": metadata["generated"]["method"],
            }
            metadata.pop("verified", None)
            metadata["superseded_by"] = [replacement_id]
            link = _relative_link(predecessor, replacement)
            body = _append_supersession(
                body, f"Replaced by [{replacement_meta['title']}]({link}). {reason}"
            )
            (root / predecessor).write_text(
                render_concept(metadata, body), encoding="utf-8", newline="\n"
            )
        _append_log(
            root,
            timestamp[:10],
            f"**Supersession**: Promoted [{replacement_meta['title']}]({replacement}) and deprecated {len(predecessors)} predecessor(s).",
        )

    return _plan(bundle, "supersede", mutate, as_of=as_of)


def plan_archive(
    bundle: str | Path,
    relative_path: str,
    *,
    operator: str,
    timestamp: str,
    reason: str,
    as_of: date | str | None = None,
) -> ChangeSet:
    """Plan archive disposition, path move, and inbound link repair."""

    _require_timestamp(timestamp)
    source = _validate_concept_path(relative_path)
    destination = f"archive/{source}"

    def mutate(root: Path) -> None:
        metadata, body = load_editable(root / source, root)
        if metadata.get("status") == "stable":
            if not operator.startswith("human:"):
                raise OperationError("Archiving stable knowledge requires a human operator.")
            _require_authorized_reviewer(root, str(metadata.get("type")), operator)
            metadata["status"] = "deprecated"
        elif (
            not (metadata.get("status") == "draft" and metadata.get("type") == "question")
            and metadata.get("status") != "deprecated"
        ):
            raise OperationError(
                "Only deprecated items or abandoned draft questions can be archived."
            )
        metadata["updated_at"] = quoted(timestamp)
        metadata["generated"] = {
            "by": operator,
            "at": quoted(timestamp),
            "method": metadata["generated"]["method"],
        }
        metadata.pop("verified", None)
        metadata["archived"] = {"at": quoted(timestamp), "reason": reason}
        (root / source).write_text(render_concept(metadata, body), encoding="utf-8", newline="\n")
        _move_and_rewrite(root, source, destination)
        _append_log(
            root, timestamp[:10], f"**Archive**: Archived [{metadata['title']}]({destination})."
        )

    return _plan(bundle, "archive", mutate, as_of=as_of)


def _plan(
    bundle: str | Path,
    operation: str,
    mutate: Callable[[Path], None],
    *,
    as_of: date | str | None,
) -> ChangeSet:
    base = Path(bundle).resolve()
    if not base.is_dir():
        raise OperationError(f"Bundle does not exist: {base}")
    base_report = validate_bundle(base, as_of=as_of)
    if base_report.errors:
        raise OperationValidationError(base_report)
    with tempfile.TemporaryDirectory(prefix="portable-kb-plan-") as temporary:
        proposed = Path(temporary) / "knowledge"
        shutil.copytree(base, proposed)
        mutate(proposed)
        generate_indexes(proposed)
        report = validate_transition(base, proposed, as_of=as_of)
        if report.errors:
            raise OperationValidationError(report)
        return diff_trees(base, proposed, report, operation)


def _validate_concept_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.suffix != ".md"
        or path.name in RESERVED_NAMES
    ):
        raise OperationError(f"Unsafe or reserved concept path: {value}")
    if any(part.startswith(".") for part in path.parts):
        raise OperationError(f"Hidden concept paths are not allowed: {value}")
    return path.as_posix()


def _require_timestamp(value: str) -> None:
    if not UTC_DATETIME.fullmatch(value):
        raise OperationError("timestamp must be strict UTC RFC 3339 ending Z")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OperationError("timestamp is not a real datetime") from exc


def _load_config(root: Path) -> Mapping[str, Any]:
    yaml = YAML(typ="safe")
    value = yaml.load((root / ".core-kb.yaml").read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise OperationError("Bundle configuration is invalid.")
    return value


def _require_authorized_reviewer(root: Path, item_type: str, reviewer: str) -> None:
    if not reviewer.startswith("human:"):
        raise OperationError("Authoritative verification requires a human actor.")
    config = _load_config(root)
    active = config.get("active_types", [])
    if item_type not in active:
        raise OperationError(f"Type is not active for promotion: {item_type}")
    if item_type in {"decision", "procedure", "policy", "system"}:
        reviewers = config.get("authorized_reviewers", {})
        allowed = reviewers.get(item_type, []) if isinstance(reviewers, Mapping) else []
        if reviewer not in allowed:
            raise OperationError(f"Reviewer is not authorized for {item_type}: {reviewer}")


def _default_stale_after(root: Path, item_type: str, start: str) -> str:
    config = _load_config(root)
    freshness = config.get("freshness_days", {})
    days = freshness.get(item_type) if isinstance(freshness, Mapping) else None
    if not isinstance(days, int):
        raise OperationError(f"No default freshness interval for {item_type}.")
    return (date.fromisoformat(start) + timedelta(days=days)).isoformat()


def _quote_source_dates(sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = [dict(source) for source in sources]
    for source in result:
        if isinstance(source.get("last_modified"), str):
            source["last_modified"] = quoted(source["last_modified"])
        window = source.get("usage_window")
        if isinstance(window, MutableMapping):
            for key in ("from", "to"):
                if isinstance(window.get(key), str):
                    window[key] = quoted(window[key])
    return result


def _quote_dates_in_place(metadata: MutableMapping[str, Any]) -> None:
    for key in ("created_at", "updated_at", "valid_from", "stale_after"):
        if isinstance(metadata.get(key), str):
            metadata[key] = quoted(metadata[key])
    generated = metadata.get("generated")
    if isinstance(generated, MutableMapping) and isinstance(generated.get("at"), str):
        generated["at"] = quoted(generated["at"])


def _append_log(root: Path, day: str, entry: str) -> None:
    path = root / "log.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Portable KB update log\n"
    heading = f"## {day}"
    if heading in text:
        start = text.index(heading) + len(heading)
        insertion = f"\n\n* {entry}"
        text = text[:start] + insertion + text[start:]
    else:
        first_break = text.find("\n")
        text = (
            text[: first_break + 1]
            + f"\n{heading}\n\n* {entry}\n"
            + text[first_break + 1 :].lstrip("\n")
        )
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def _move_and_rewrite(root: Path, source: str, destination: str) -> None:
    source_file = root / source
    destination_file = root / destination
    if not source_file.exists():
        raise OperationError(f"Move source does not exist: {source}")
    if destination_file.exists():
        raise OperationError(f"Move destination exists: {destination}")
    parsed_items = []
    for path in discover_concepts(root):
        result = parse_concept(path, root)
        if result.item is None:
            raise OperationError(f"Cannot move while a concept is unparseable: {path}")
        parsed_items.append(result.item)
    link_index = LinkIndex(parsed_items, root)
    rewritten_wiki = {item.relative_path: link_index.rewrite_wiki_move(item, source, destination)
                      for item in parsed_items}
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.replace(destination_file)
    for item in parsed_items:
        old_item_path = item.relative_path
        new_item_path = destination if old_item_path == source else old_item_path
        rewritten = _rewrite_links(rewritten_wiki[old_item_path], old_item_path, new_item_path, source, destination)
        target_path = root / new_item_path
        if rewritten != item.body or old_item_path == source:
            metadata, _body = load_editable(target_path, root)
            target_path.write_text(
                render_concept(metadata, rewritten), encoding="utf-8", newline="\n"
            )


def _rewrite_links(body: str, old_item: str, new_item: str, moved_from: str, moved_to: str) -> str:
    def replace(match: re.Match[str]) -> str:
        target = match.group(1)
        parsed = urlsplit(target)
        if parsed.scheme or target.startswith(("#", "mailto:")) or not parsed.path.endswith(".md"):
            return match.group(0)
        if parsed.path.startswith("/"):
            resolved = posixpath.normpath(parsed.path.lstrip("/"))
        else:
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(old_item), parsed.path))
        if resolved == moved_from:
            resolved = moved_to
        if parsed.path.startswith("/"):
            new_path = "/" + resolved
        else:
            new_path = posixpath.relpath(resolved, posixpath.dirname(new_item) or ".")
        rewritten_target = urlunsplit(("", "", new_path, parsed.query, parsed.fragment))
        return match.group(0).replace(target, rewritten_target, 1)

    return MARKDOWN_LINK.sub(replace, body)


def _relative_link(from_path: str, to_path: str) -> str:
    return posixpath.relpath(to_path, posixpath.dirname(from_path) or ".")


def _append_supersession(body: str, sentence: str) -> str:
    heading = "## Supersession"
    if heading in body:
        return body.rstrip() + f"\n\n{sentence}\n"
    return body.rstrip() + f"\n\n{heading}\n\n{sentence}\n"


def _require_verification_scope(scope: str) -> None:
    if len(scope.strip()) < 10 or "\n" in scope:
        raise OperationError(
            "verification_scope must be one descriptive line of at least 10 characters."
        )


def _append_verification_scope(body: str, reviewer: str, timestamp: str, scope: str) -> str:
    marker = f"<!-- core-kb-verification: {reviewer} at {timestamp} -->"
    entry = f"{scope.strip()}\n\n{marker}"
    heading = "## Verification record"
    if heading in body:
        return body.rstrip() + f"\n\n{entry}\n"
    return body.rstrip() + f"\n\n{heading}\n\n{entry}\n"
