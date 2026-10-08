"""Read-only resolution of Markdown and local wikilinks to canonical items.

Names are exact and case-sensitive. Bare wiki slugs must be globally unique
within the bundle; qualified wiki paths start at its root. Explicit ./ and ../
paths start at the source item. Labels affect display, never identity.
"""

from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

from .models import KnowledgeItem
from .parsing import discover_concepts, parse_concept

MARKDOWN_LINK = re.compile(r'(?<!!)\[([^\]\n]+)\]\(([^)\s]+)(?:\s+["\'][^"\']*["\'])?\)')
WIKI_LINK = re.compile(r"(?<!!)\[\[([^\]\n]*)\]\]")


def prose_mask(body: str, *, code_spans: bool = True) -> str:
    """Mask comments, fenced/indented code and code spans, retaining offsets."""
    chars = list(body)

    def mask(start: int, end: int) -> None:
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "

    for match in re.finditer(r"<!--.*?(?:-->|\Z)", body, re.S):
        mask(*match.span())
    offset = 0
    fence: str | None = None
    fence_length = 0
    for line in "".join(chars).splitlines(keepends=True):
        marker = re.match(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if fence is not None:
            mask(offset, offset + len(line))
            if (
                marker
                and marker[1][0] == fence
                and len(marker[1]) >= fence_length
                and not marker[2].strip()
            ):
                fence = None
        elif marker:
            fence, fence_length = marker[1][0], len(marker[1])
            mask(offset, offset + len(line))
        elif line.startswith(("    ", "\t")):
            mask(offset, offset + len(line))
        offset += len(line)
    visible = "".join(chars)
    spans = re.compile(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)", re.S)
    if code_spans:
        for match in spans.finditer(visible):
            mask(*match.span())
    return "".join(chars)


def _escaped(text: str, position: int) -> bool:
    count = 0
    while position > 0 and text[position - 1] == "\\":
        count += 1
        position -= 1
    return count % 2 == 1


@dataclass(frozen=True)
class LinkReference:
    kind: str
    target: str
    label: str
    start: int
    end: int
    line: int


def extract_links(body: str) -> tuple[LinkReference, ...]:
    visible = prose_mask(body)
    result = []
    for kind, pattern in (("wiki", WIKI_LINK), ("markdown", MARKDOWN_LINK)):
        for match in pattern.finditer(visible):
            if _escaped(body, match.start()):
                continue
            if kind == "wiki":
                target, separator, label = match[1].partition("|")
                label = label.strip() if separator else target.strip()
            else:
                label, target = match[1], match[2]
            result.append(
                LinkReference(
                    kind,
                    target.strip(),
                    label,
                    *match.span(),
                    body[: match.start()].count("\n") + 1,
                )
            )
    return tuple(sorted(result, key=lambda link: link.start))


def heading_slug(text: str) -> str:
    text = re.sub(r"[`*_~]", "", text).strip().lower()
    return "".join(
        "-" if c.isspace() else c for c in text if c.isalnum() or c in "_-" or c.isspace()
    )


def heading_anchors(body: str) -> set[str]:
    used: set[str] = set()
    for match in re.finditer(
        r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", prose_mask(body, code_spans=False), re.M
    ):
        base = heading_slug(match[1])
        anchor = base
        suffix = 0
        while anchor in used:
            suffix += 1
            anchor = f"{base}-{suffix}"
        used.add(anchor)
    return used


@dataclass(frozen=True)
class ResolvedLink:
    reference: LinkReference
    status: str
    item: KnowledgeItem | None = None
    fragment: str | None = None
    candidates: tuple[str, ...] = ()


class LinkIndex:
    """A disposable in-memory projection; no content or index writes."""

    def __init__(self, items: Sequence[KnowledgeItem], root: Path):
        self.root = root.resolve()
        self.items = {item.relative_path: item for item in items}
        self.slugs: dict[str, list[KnowledgeItem]] = defaultdict(list)
        self.ids: dict[str, list[KnowledgeItem]] = defaultdict(list)
        self.anchors = {item.relative_path: heading_anchors(item.body) for item in items}
        for item in items:
            self.slugs[PurePosixPath(item.relative_path).stem].append(item)
            if item.id:
                self.ids[item.id].append(item)

    @classmethod
    def load(cls, root: Path) -> LinkIndex:
        items = []
        for path in discover_concepts(root):
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Knowledge link index contains an unsafe concept path.")
            parsed = parse_concept(path, root)
            if parsed.item is None:
                raise ValueError("Knowledge link index contains an unparseable concept.")
            items.append(parsed.item)
        return cls(items, root)

    def resolve(self, source: KnowledgeItem, reference: LinkReference) -> ResolvedLink:
        target = reference.target
        if reference.kind == "wiki":
            name, separator, fragment = target.partition("#")
            fragment = fragment.strip() if separator else None
            name = name.strip()
            if name.startswith("urn:uuid:"):
                return self._matches(reference, self.ids.get(name, []), fragment)
            if "\\" in name or "\x00" in name or "?" in name or ":" in name:
                return ResolvedLink(reference, "unsafe")
            if not name:
                return (
                    self._matches(reference, [source], fragment)
                    if separator
                    else ResolvedLink(reference, "missing")
                )
            if "/" not in name and not name.startswith("."):
                return self._matches(
                    reference, self.slugs.get(name.removesuffix(".md"), []), fragment
                )
            if name.startswith(("./", "../")):
                path = posixpath.join(posixpath.dirname(source.relative_path), name)
            else:
                path = name.removeprefix("/")
            if not path.endswith(".md"):
                path += ".md"
        else:
            try:
                parsed = urlsplit(target)
            except ValueError:
                return ResolvedLink(reference, "unsafe")
            if parsed.scheme or parsed.netloc:
                return ResolvedLink(reference, "external")
            name, fragment = unquote(parsed.path), unquote(parsed.fragment) or None
            if "\\" in name or "\x00" in name:
                return ResolvedLink(reference, "unsafe")
            if not name:
                return self._matches(reference, [source], fragment)
            path = (
                name.removeprefix("/")
                if name.startswith("/")
                else posixpath.join(posixpath.dirname(source.relative_path), name)
            )
        normalized = posixpath.normpath(path)
        candidate = self.root / normalized
        if (
            normalized == ".."
            or normalized.startswith("../")
            or not candidate.resolve().is_relative_to(self.root)
        ):
            return ResolvedLink(reference, "unsafe")
        if normalized in self.items:
            return self._matches(reference, [self.items[normalized]], fragment)
        if reference.kind == "markdown" and candidate.exists():
            return ResolvedLink(reference, "resource")
        return ResolvedLink(reference, "missing")

    def _matches(
        self, reference: LinkReference, matches: Sequence[KnowledgeItem], fragment: str | None
    ) -> ResolvedLink:
        if not matches:
            return ResolvedLink(reference, "missing")
        if len(matches) > 1:
            return ResolvedLink(
                reference, "ambiguous", candidates=tuple(sorted(i.relative_path for i in matches))
            )
        item = matches[0]
        if item.path.is_symlink() or not item.path.resolve().is_relative_to(self.root):
            return ResolvedLink(reference, "unsafe")
        if fragment is not None:
            anchor = (
                fragment if fragment in self.anchors[item.relative_path] else heading_slug(fragment)
            )
            if not fragment or anchor not in self.anchors[item.relative_path]:
                return ResolvedLink(reference, "missing-heading", item, fragment)
            fragment = anchor
        return ResolvedLink(reference, "resolved", item, fragment)

    def outgoing(self, item: KnowledgeItem) -> tuple[ResolvedLink, ...]:
        return tuple(self.resolve(item, ref) for ref in extract_links(item.body))

    def find(self, reference: str) -> KnowledgeItem:
        raw = reference.strip()
        if raw.startswith("[[") and raw.endswith("]]"):
            raw = raw[2:-2].split("|", 1)[0]
        if not raw or "\x00" in raw:
            raise ValueError("Knowledge item reference must be non-empty and contain no NUL.")
        if raw.startswith(("./", "../", "#")):
            raise ValueError(
                "Knowledge item path is unsafe, reserved, or lacks a source item context."
            )
        source = next(iter(self.items.values()), None)
        if source is None:
            raise ValueError("No knowledge items exist in the selected brain.")
        result = self.resolve(source, LinkReference("wiki", raw, raw, 0, len(raw), 1))
        if result.status != "resolved" or result.item is None or result.item.id is None:
            detail = f"; candidates: {', '.join(result.candidates)}" if result.candidates else ""
            raise ValueError(
                f"Knowledge reference {raw!r} is {result.status} in the selected brain{detail}. Use an item UUID or bundle-qualified path."
            )
        return result.item

    def markdown_view(self, item: KnowledgeItem) -> str:
        body = item.body
        for link in reversed(self.outgoing(item)):
            if link.reference.kind != "wiki":
                continue
            if link.status != "resolved" or link.item is None:
                raise ValueError(
                    f"Cannot render wikilink {link.reference.target!r}: {link.status}."
                )
            target = posixpath.relpath(
                link.item.relative_path, posixpath.dirname(item.relative_path) or "."
            )
            target = quote(target, safe="/.-_")
            if link.fragment:
                target += "#" + quote(link.fragment)
            label = (
                link.reference.label.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            )
            body = (
                body[: link.reference.start] + f"[{label}]({target})" + body[link.reference.end :]
            )
        return body

    def rewrite_wiki_move(
        self,
        item: KnowledgeItem,
        moved_from: str,
        moved_to: str,
        *,
        proposed: LinkIndex | None = None,
    ) -> str:
        """Preserve resolved identity and display labels through a reviewed move."""
        body = item.body
        if proposed is None:
            proposed = LinkIndex(
                [
                    replace(i, relative_path=moved_to, path=self.root / moved_to)
                    if i.relative_path == moved_from
                    else i
                    for i in self.items.values()
                ],
                self.root,
            )
        source = proposed.items.get(
            moved_to if item.relative_path == moved_from else item.relative_path, item
        )
        for link in reversed(self.outgoing(item)):
            if link.reference.kind != "wiki" or link.status != "resolved" or link.item is None:
                continue
            if link.reference.target.startswith(("urn:uuid:", "#")):
                continue
            target = moved_to if link.item.relative_path == moved_from else link.item.relative_path
            after = proposed.resolve(source, link.reference)
            if (
                after.status == "resolved"
                and after.item is not None
                and after.item.relative_path == target
            ):
                continue
            # Qualify only affected references, including names made ambiguous
            # by the destination stem and relative links in a moved directory.
            target = target.removesuffix(".md")
            if link.fragment:
                target += "#" + link.fragment
            replacement = f"[[{target}|{link.reference.label}]]"
            body = body[: link.reference.start] + replacement + body[link.reference.end :]
        return body
