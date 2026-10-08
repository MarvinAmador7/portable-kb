"""Contentless SQLite FTS5 prototype, served over the benchmark JSONL protocol."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

from .common import MAX_REQUEST_BYTES, peak_rss_kib, records_from

ENGINE_VERSION = f"sqlite-{sqlite3.sqlite_version}/fts5-prototype-1"


def build(destination: Path, records_path: Path) -> int:
    destination.mkdir()  # Refuse to replace any previous index.
    with sqlite3.connect(destination / "index.sqlite") as database:
        database.execute(
            "CREATE TABLE sections (ordinal INTEGER PRIMARY KEY, section_id TEXT UNIQUE, item_id TEXT, path TEXT, type TEXT, status TEXT)"
        )
        database.execute("CREATE INDEX by_item ON sections(item_id)")
        database.execute("CREATE INDEX by_path ON sections(path)")
        database.execute("CREATE INDEX by_filter ON sections(type, status)")
        database.execute(
            "CREATE VIRTUAL TABLE terms USING fts5(title, description, heading, body, content='', tokenize='unicode61 remove_diacritics 2')"
        )
        count = 0
        for count, record in enumerate(records_from(records_path), start=1):
            database.execute(
                "INSERT INTO sections VALUES (?, ?, ?, ?, ?, ?)",
                (
                    count,
                    record["section_id"],
                    record["item_id"],
                    record["path"],
                    record["type"],
                    record["status"],
                ),
            )
            database.execute(
                "INSERT INTO terms(rowid, title, description, heading, body) VALUES (?, ?, ?, ?, ?)",
                (
                    count,
                    record["title"],
                    record["description"],
                    record["heading"],
                    record["body"],
                ),
            )
            if count % 1000 == 0:
                # Bound FTS5's pending-term transaction memory. This index is
                # unpublished staging state until the orchestrator completes it.
                database.commit()
        database.execute("INSERT INTO terms(terms) VALUES ('optimize')")
    return count


class Engine:
    def __init__(self, path: Path) -> None:
        database = path / "index.sqlite"
        if database.is_symlink() or not database.is_file():
            raise ValueError("missing or unsafe prototype index")
        self.database = sqlite3.connect(
            database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
        )

    def query(
        self,
        text: str,
        tokens: list[str],
        exact_field: str | None,
        limit: int,
        filters: dict[str, str],
    ) -> list[dict]:
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or len(text.encode()) > 4096
            or len(tokens) > 256
        ):
            raise ValueError("invalid query bounds")
        if set(filters) - {"type", "status"}:
            raise ValueError("unsupported filter")
        conditions = [f"s.{name} = ?" for name in sorted(filters)]
        parameters = [filters[name] for name in sorted(filters)]
        if exact_field is not None:
            if exact_field not in {"item_id", "path"}:
                raise ValueError("unsupported exact field")
            conditions.insert(0, f"s.{exact_field} = ?")
            parameters.insert(0, text)
            sql = (
                "SELECT s.section_id, 1.0 FROM sections s WHERE "
                + " AND ".join(conditions)
                + " ORDER BY s.ordinal LIMIT ?"
            )
        else:
            if not tokens:
                return []
            if any(not token or not token.isalnum() for token in tokens):
                raise ValueError("query tokens must be literal alphanumeric words")
            conditions.insert(0, "terms MATCH ?")
            parameters.insert(0, " AND ".join(f'"{token}"' for token in tokens))
            sql = (
                "SELECT s.section_id, -bm25(terms, 8, 3, 5, 1) AS score FROM terms JOIN sections s ON s.ordinal = terms.rowid WHERE "
                + " AND ".join(conditions)
                + " ORDER BY score DESC, s.ordinal LIMIT ?"
            )
        return [
            {"section_id": identity, "score": score}
            for identity, score in self.database.execute(sql, (*parameters, limit))
        ]

    def close(self) -> None:
        self.database.close()


def serve() -> None:
    engines: dict[str, Engine] = {}
    try:
        while raw := sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1):
            oversized = len(raw) > MAX_REQUEST_BYTES
            try:
                if oversized:
                    raise ValueError("request exceeds 64 KiB")
                request = json.loads(raw)
                if not isinstance(request, dict) or set(request) - {
                    "protocol_version",
                    "op",
                    "index_path",
                    "records_path",
                    "query",
                    "tokens",
                    "exact_field",
                    "limit",
                    "filters",
                }:
                    raise ValueError("unsupported request structure")
                if (
                    type(request.get("protocol_version")) is not int
                    or request.get("protocol_version") != 1
                ):
                    raise ValueError("unsupported protocol version")
                operation = request["op"]
                if operation == "status":
                    result = {"version": ENGINE_VERSION}
                elif operation == "build":
                    started = time.perf_counter()
                    count = build(Path(request["index_path"]), Path(request["records_path"]))
                    result = {
                        "record_count": count,
                        "elapsed_ms": (time.perf_counter() - started) * 1000,
                    }
                elif operation == "query":
                    path = request["index_path"]
                    opened = path not in engines
                    started = time.perf_counter()
                    if opened:
                        engines[path] = Engine(Path(path))
                    open_ms = (time.perf_counter() - started) * 1000
                    started = time.perf_counter()
                    hits = engines[path].query(
                        request["query"],
                        request["tokens"],
                        request.get("exact_field"),
                        request.get("limit", 10),
                        request.get("filters", {}),
                    )
                    result = {
                        "hits": hits,
                        "query_ms": (time.perf_counter() - started) * 1000,
                        "open_ms": open_ms,
                        "opened": opened,
                    }
                else:
                    raise ValueError("unsupported operation")
                response = {
                    "protocol_version": 1,
                    "ok": True,
                    "result": result,
                    "peak_rss_kib": peak_rss_kib(),
                }
            except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
                response = {"protocol_version": 1, "ok": False, "error": str(exc)}
            print(json.dumps(response), flush=True)
            if oversized:
                break
    finally:
        for engine in engines.values():
            engine.close()


if __name__ == "__main__":
    serve()
