"""Provider boundary for disposable keyword indexes and discovery hits.

Providers own executable/index details. The search consumer owns brain health,
canonical parsing, safe paths, lifecycle metadata, and immutable citations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .brains import InstalledBrain


class SearchError(RuntimeError):
    """Raised when a search index or query cannot be handled safely."""


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Untrusted discovery evidence; contains no authority or citation claims."""

    path: str
    score: float
    title: str
    line: int | None = None
    docid: str | None = None
    snippet: str | None = None
    context: str | None = None
    line_end: int | None = None


class KeywordSearchProvider(Protocol):
    """Interface for the builtin Tantivy and optional QMD providers.

    Build receives an already validated, pinned bundle. QMD consumes Markdown
    files; the native provider normalizes sections from that same bundle.
    Index deletion stays inside the transactional brain-removal operation.
    """

    name: str

    def index_path(self, slug: str) -> Path: ...

    def status(self) -> dict[str, Any]: ...

    def build(self, brain: InstalledBrain, bundle: Path) -> dict[str, Any]: ...

    def load_metadata(self, slug: str) -> Mapping[str, Any]: ...

    def query(self, brain: InstalledBrain, query: str, limit: int) -> Sequence[SearchHit]: ...
