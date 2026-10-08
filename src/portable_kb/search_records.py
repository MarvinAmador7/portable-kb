"""Normalize validated concepts into derived, line-cited Markdown sections."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .brains import InstalledBrain
from .models import KnowledgeItem, Severity
from .parsing import discover_concepts, parse_concept
from .search_provider import SearchError

RECORD_SCHEMA_VERSION = 1
HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)(.*)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
SETEXT = re.compile(r"^ {0,3}(?:=+|-+)\s*$")


@dataclass(frozen=True, slots=True)
class SectionRecord:
    schema_version: int
    section_id: str
    brain_id: str
    brain_slug: str
    commit: str | None
    item_id: str
    path: str
    title: str
    description: str
    heading: str
    body: str
    line_start: int
    line_end: int
    type: str
    status: str
    sensitivity: str | None
    stale_after: str | None
    updated_at: str | None
    content_hash: str

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_bundle(brain: InstalledBrain, bundle: Path) -> tuple[SectionRecord, ...]:
    """Normalize an already validated, pinned bundle; never index reserved files.

    The consumer must check brain health before calling this function. The
    normalizer performs structural checks; it does not invent lifecycle policy.
    """
    records = []
    for path in discover_concepts(bundle):
        relative = path.relative_to(bundle)
        if bundle.is_symlink() or any(
            bundle.joinpath(*relative.parts[:length]).is_symlink()
            for length in range(1, len(relative.parts) + 1)
        ):
            raise SearchError("Section normalization refuses symbolic-link paths.")
        parsed = parse_concept(path, bundle)
        if (
            parsed.item is None
            or parsed.item.id is None
            or any(finding.severity is Severity.ERROR for finding in parsed.findings)
        ):
            # Parser findings signal unsafe/ambiguous source; validation warnings
            # elsewhere in the bundle remain the consumer's responsibility.
            raise SearchError(f"Cannot normalize concept safely: {path.relative_to(bundle)}")
        records.extend(normalize_item(brain, parsed.item))
    return tuple(records)


def normalize_item(brain: InstalledBrain, item: KnowledgeItem) -> tuple[SectionRecord, ...]:
    """Retain exact body text and source lines; exclude frontmatter from text."""
    if item.id is None or item.type is None or item.status is None:
        raise SearchError("Section normalization requires validated identity, type, and status.")
    source_lines = item.source_text.splitlines(keepends=True)
    closing = next(i for i, line in enumerate(source_lines[1:], 1) if line.rstrip("\n") == "---")
    lines = source_lines[closing + 1 :]
    headings: dict[int, str] = {}
    fence: tuple[str, int] | None = None
    for index, line in enumerate(lines):
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif (
                token[0] == fence[0] and len(token) >= fence[1] and not line[marker.end() :].strip()
            ):
                fence = None
            continue
        if fence is not None:
            continue
        heading = HEADING.match(line)
        if heading:
            headings[index] = re.sub(r"[ \t]+#+[ \t]*$", "", heading.group(2)).strip()
        elif (
            index > 0
            and SETEXT.match(line)
            and lines[index - 1].strip()
            and not FENCE.match(lines[index - 1])
            and not HEADING.match(lines[index - 1])
        ):
            # A setext underline follows its heading; a blank before --- makes
            # it a thematic break instead. Fence content never reaches here.
            headings[index - 1] = lines[index - 1].strip()
    starts = sorted({0, *headings}) if lines else []
    records = []
    for ordinal, start in enumerate(starts):
        end = starts[ordinal + 1] if ordinal + 1 < len(starts) else len(lines)
        body = "".join(lines[start:end])
        if not body.strip():
            continue
        content_start = start
        if start in headings:
            content_start += 1 if HEADING.match(lines[start]) else 2
        if not any(line.strip() for line in lines[content_start:end]):
            # Heading-only scaffolding has no passage to retrieve. The title
            # remains searchable on every substantive section of the item.
            continue
        line_start, line_end = closing + start + 2, closing + end + 1
        records.append(
            SectionRecord(
                schema_version=RECORD_SCHEMA_VERSION,
                section_id=f"{item.id}#{line_start}-{line_end}",
                brain_id=brain.id,
                brain_slug=brain.slug,
                commit=brain.commit,
                item_id=item.id,
                path=item.relative_path,
                title=str(item.metadata.get("title", "")),
                description=str(item.metadata.get("description", "")),
                heading=headings.get(start, ""),
                body=body,
                line_start=line_start,
                line_end=line_end,
                type=item.type,
                status=item.status,
                sensitivity=item.metadata.get("sensitivity"),
                stale_after=item.metadata.get("stale_after"),
                updated_at=item.metadata.get("updated_at"),
                content_hash="sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest(),
            )
        )
    return tuple(records)
