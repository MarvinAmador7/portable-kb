"""Shared literal-query semantics and bounded normalized-record ingestion."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

MAX_RECORD_BYTES = 1_048_576
MAX_REQUEST_BYTES = 65_536


def records_from(path: Path) -> Iterator[dict]:
    with path.open("rb") as stream:
        while raw := stream.readline(MAX_RECORD_BYTES + 1):
            if len(raw) > MAX_RECORD_BYTES:
                raise ValueError("normalized record exceeds 1 MiB")
            record = json.loads(raw)
            if (
                type(record.get("schema_version")) is not int
                or record.get("schema_version") != 1
                or type(record.get("line_start")) is not int
                or type(record.get("line_end")) is not int
                or not 1 <= record["line_start"] <= record["line_end"]
            ):
                raise ValueError("unsupported or invalid normalized record")
            yield record


def literal_tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text))


def query_parts(text: str) -> tuple[list[str], str | None]:
    if text.startswith("urn:uuid:"):
        return [], "item_id"
    if text.endswith(".md"):
        return [], "path"
    return literal_tokens(text), None


def peak_rss_kib() -> int | None:
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value / 1024 if sys.platform == "darwin" else value)
    except ImportError:
        return None
