"""Compare model-free engines on shared normalized exports; development only.

Run `python -m benchmarks.search --help` from the repository checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import selectors
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ruamel.yaml import YAML

from portable_kb.qmd_provider import _require_qmd_compatibility, _run_qmd
from portable_kb.retrieval_eval import _percentiles, score_ranking

from .common import MAX_REQUEST_BYTES, literal_tokens, query_parts, records_from
from .corpus import export_brain, synthetic_corpus

MAX_RESPONSE_BYTES = 16_777_216


class Worker:
    """Persistent sidecar with bounded requests/responses and per-call timeouts."""

    def __init__(self, command: list[str]) -> None:
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        started = time.perf_counter()
        try:
            self.version = self.call({"op": "status"})["result"]["version"]
        except BaseException:
            self.close()
            raise
        self.startup_ms = (time.perf_counter() - started) * 1000

    def call(self, request: dict, timeout: float = 300) -> dict:
        raw = (json.dumps({"protocol_version": 1, **request}) + "\n").encode()
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("request exceeds 64 KiB")
        self.process.stdin.write(raw)
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise TimeoutError("benchmark sidecar timed out")
            part = os.read(self.process.stdout.fileno(), 65_536)
            if not part:
                raise RuntimeError("benchmark sidecar exited before responding")
            self.buffer.extend(part)
            if len(self.buffer) > MAX_RESPONSE_BYTES:
                raise ValueError("response exceeds 16 MiB")
        raw, _, tail = self.buffer.partition(b"\n")
        self.buffer = bytearray(tail)
        response = json.loads(raw)
        if response.get("protocol_version") != 1 or response.get("ok") is not True:
            raise ValueError(response.get("error", "invalid sidecar response"))
        return response

    def close(self) -> None:
        self.selector.close()
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()


def _disk_bytes(path: Path) -> int:
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def _mean_metrics(rows: list[dict]) -> dict:
    positive = [row for row in rows if "precision_at_5" in row]
    negative = [row["no_result_correct"] for row in rows if "no_result_correct" in row]
    return {
        **{
            key: statistics.mean(row[key] for row in positive) if positive else None
            for key in ("precision_at_5", "recall_at_10", "reciprocal_rank_at_10", "ndcg_at_10")
        },
        "no_result_accuracy": statistics.mean(negative) if negative else None,
    }


class QmdBenchmark:
    """Project the same sections into derived Markdown for unmodified QMD."""

    def __init__(self, command: str, output: Path, records: dict[str, dict]) -> None:
        executable = shutil.which(command)
        if executable is None:
            raise ValueError("benchmark QMD executable was not found")
        self.executable = executable
        projection_started = time.perf_counter()
        self.state = output / "qmd"
        self.state.mkdir()
        projection = output / "qmd-projection"
        projection.mkdir()
        self.identities = {}
        for ordinal, record in enumerate(records.values()):
            name = f"section-{ordinal:08d}.md"
            self.identities[f"qmd://benchmark/{name}"] = record["section_id"]
            # Metadata/frontmatter never become search text. IDs and paths are
            # rendered solely to support QMD's exact-identifier baseline.
            (projection / name).write_text(
                f"# {record['title']}\n\n{record['description']}\n\n"
                f"## {record['heading']}\n\n{record['body']}\n"
                f"Item: {record['item_id']}\nPath: {record['path']}\n",
                encoding="utf-8",
            )
        config = self.state / "config"
        config.mkdir()
        with (config / "index.yml").open("w") as stream:
            YAML().dump(
                {
                    "collections": {
                        "benchmark": {
                            "path": str(projection.resolve()),
                            "pattern": "*.md",
                            "includeByDefault": True,
                        }
                    }
                },
                stream,
            )
        started = time.perf_counter()
        self.projection_ms = (started - projection_started) * 1000
        self.version = _require_qmd_compatibility(self.executable, self.state)
        self.startup_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        _run_qmd(self.executable, self.state, "update", timeout=300)
        self.build_ms = (time.perf_counter() - started) * 1000

    def query(self, query: dict, records: dict[str, dict]) -> dict:
        tokens, exact = query_parts(query["query"])
        if exact:
            tokens = literal_tokens(query["query"])
        text = " ".join(f'"{token}"' for token in tokens)
        # Fetch every potential section before post-filtering; QMD does not
        # support the metadata filters in this experiment. Record this cost.
        count = len(records) if query["filters"] or exact else 100
        raw = _run_qmd(
            self.executable,
            self.state,
            "search",
            text,
            "--format",
            "json",
            "--collection",
            "benchmark",
            "-n",
            str(count),
            timeout=120,
        )
        rows = json.loads(raw)
        hits = []
        for row in rows:
            identity = self.identities.get(row["file"])
            if identity is None:
                raise ValueError("QMD returned a section outside the shared export")
            if (exact is None or records[identity][exact] == query["query"]) and all(
                records[identity][key] == value for key, value in query["filters"].items()
            ):
                hits.append({"section_id": identity, "score": row["score"]})
        return {"hits": hits[:100], "query_ms": None, "open_ms": None, "opened": None}


def run_benchmark(
    corpus: Path, output: Path, *, tantivy: Path | None, qmd: str | None, repeat: int
) -> dict:
    if not 2 <= repeat <= 20:
        raise ValueError("benchmark repeat must be between 2 and 20")
    manifest = json.loads((corpus / "corpus.json").read_text())
    records_path = corpus / "records.jsonl"
    if hashlib.sha256(records_path.read_bytes()).hexdigest() != manifest["records_sha256"]:
        raise ValueError("corpus fingerprint differs from its manifest")
    records = {record["section_id"]: record for record in records_from(records_path)}
    if len(records) != manifest["record_count"]:
        raise ValueError("duplicate or missing section records")
    queries_raw = (corpus / "queries.json").read_bytes()
    queries = json.loads(queries_raw)
    known_items = {record["item_id"] for record in records.values()}
    if (
        not isinstance(queries, list)
        or not queries
        or len({query["id"] for query in queries}) != len(queries)
    ):
        raise ValueError("benchmark queries must be non-empty with unique IDs")
    for query in queries:
        if set(query["section_relevance"]) - records.keys() or set(query["filters"]) - {
            "type",
            "status",
        }:
            raise ValueError("invalid section labels or filters")
        if set(query["item_relevance"]) - known_items or any(
            type(grade) is not int or grade not in (1, 2, 3)
            for grades in (query["section_relevance"], query["item_relevance"])
            for grade in grades.values()
        ):
            raise ValueError("invalid item labels or relevance grades")
    output.mkdir(parents=True, exist_ok=False)
    reports = {}
    commands = {"sqlite-fts5": [sys.executable, "-m", "benchmarks.sqlite_fts5"]}
    if tantivy is not None:
        commands["tantivy"] = [str(tantivy.resolve())]
    for name in [*commands, *(["qmd"] if qmd else [])]:
        worker = None
        try:
            print(
                f"Benchmarking {name}: {manifest['item_count']} items / {len(records)} sections",
                file=sys.stderr,
                flush=True,
            )
            rss = None
            if name == "qmd":
                engine = QmdBenchmark(qmd, output, records)
                version, startup_ms, build_ms = engine.version, engine.startup_ms, engine.build_ms
            else:
                worker = Worker(commands[name])
                version, startup_ms = worker.version, worker.startup_ms
                # A failed/interrupted build cannot publish a partial index.
                with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=output) as stage:
                    reply = worker.call(
                        {
                            "op": "build",
                            "index_path": str(Path(stage) / "index"),
                            "records_path": str(records_path.resolve()),
                        }
                    )
                    if reply["result"]["record_count"] != len(records):
                        raise ValueError("engine indexed an unexpected record count")
                    build_ms, rss = reply["result"]["elapsed_ms"], reply.get("peak_rss_kib")
                    os.replace(Path(stage) / "index", output / name)
            rows = []
            for query in queries:
                sample = {
                    "id": query["id"],
                    "query": query["query"],
                    "filters": query["filters"],
                    "runs": [],
                }
                for _run in range(repeat):
                    started = time.perf_counter()
                    if name == "qmd":
                        result = engine.query(query, records)
                    else:
                        tokens, exact = query_parts(query["query"])
                        reply = worker.call(
                            {
                                "op": "query",
                                "index_path": str((output / name).resolve()),
                                "query": query["query"],
                                "tokens": tokens,
                                "exact_field": exact,
                                "limit": 100,
                                "filters": query["filters"],
                            }
                        )
                        result = reply["result"]
                        rss = reply.get("peak_rss_kib", rss)
                    call_ms = (time.perf_counter() - started) * 1000
                    identities = [hit["section_id"] for hit in result["hits"]]
                    if len(set(identities)) != len(identities) or set(identities) - records.keys():
                        raise ValueError("engine returned duplicate or unknown section IDs")
                    if any(not math.isfinite(hit["score"]) for hit in result["hits"]):
                        raise ValueError("engine returned invalid scores")
                    if any(
                        any(
                            records[identity][key] != value
                            for key, value in query["filters"].items()
                        )
                        for identity in identities
                    ):
                        raise ValueError("engine returned a section excluded by explicit filters")
                    sample["runs"].append(
                        {
                            "ranked_sections": identities,
                            "call_ms": call_ms,
                            "engine_query_ms": result["query_ms"],
                            "index_open_ms": result["open_ms"],
                        }
                    )
                ranking = sample["runs"][0]["ranked_sections"]
                sample["ranking_stable"] = all(
                    row["ranked_sections"] == ranking for row in sample["runs"]
                )
                sample["section_metrics"] = score_ranking(ranking, query["section_relevance"])
                distinct_items = list(
                    dict.fromkeys(records[identity]["item_id"] for identity in ranking)
                )
                sample["item_metrics"] = score_ranking(distinct_items, query["item_relevance"])
                # Cite the canonical section range, not the projected QMD file.
                sample["citations"] = [
                    {
                        key: records[identity][key]
                        for key in (
                            "section_id",
                            "brain_id",
                            "commit",
                            "item_id",
                            "path",
                            "line_start",
                            "line_end",
                            "content_hash",
                        )
                    }
                    for identity in ranking[:10]
                ]
                rows.append(sample)
            reports[name] = {
                "version": version,
                "implementation_sha256": hashlib.sha256(
                    (
                        Path(__file__).with_name("sqlite_fts5.py")
                        if name == "sqlite-fts5"
                        else Path(engine.executable)
                        if name == "qmd"
                        else Path(commands[name][0])
                    ).read_bytes()
                ).hexdigest(),
                "startup_ms": startup_ms,
                "build_ms": build_ms,
                "index_bytes": _disk_bytes(output / name),
                "projection_bytes": _disk_bytes(output / "qmd-projection") if name == "qmd" else 0,
                "projection_ms": engine.projection_ms if name == "qmd" else 0,
                "worker_peak_rss_kib": rss,
                "section_metrics": _mean_metrics([row["section_metrics"] for row in rows]),
                "item_metrics": _mean_metrics([row["item_metrics"] for row in rows]),
                "ranking_stable": all(row["ranking_stable"] for row in rows),
                "latency": {
                    "first_pass_call_ms": _percentiles([row["runs"][0]["call_ms"] for row in rows]),
                    "repeat_call_ms": _percentiles(
                        [run["call_ms"] for row in rows for run in row["runs"][1:]]
                    ),
                    "repeat_engine_query_ms": _percentiles(
                        [
                            run["engine_query_ms"]
                            for row in rows
                            for run in row["runs"][1:]
                            if run["engine_query_ms"] is not None
                        ]
                    ),
                },
                "queries": rows,
            }
        finally:
            if worker:
                worker.close()
    report = {
        "schema_version": 1,
        "corpus": manifest,
        "queries_sha256": hashlib.sha256(queries_raw).hexdigest(),
        "labels": queries,
        "repeat": repeat,
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "timing_scope": "persistent worker IPC for prototypes; process-per-query QMD CLI; no governance validation in engine timing",
        "providers": reports,
        "ok": True,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate", help="Generate deterministic synthetic benchmark records"
    )
    generate.add_argument("--items", type=int, required=True)
    generate.add_argument("--output", type=Path, required=True)
    export = commands.add_parser("export", help="Normalize a healthy, pinned installed brain")
    export.add_argument("--config", type=Path, required=True)
    export.add_argument("--brain")
    export.add_argument("--as-of", required=True)
    export.add_argument("--labels", type=Path, required=True)
    export.add_argument("--section-labels", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    run = commands.add_parser(
        "run", help="Build isolated experimental indexes and write a comparison report"
    )
    run.add_argument("corpus", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--tantivy", type=Path)
    run.add_argument("--qmd")
    run.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            synthetic_corpus(args.output, args.items)
        elif args.command == "export":
            export_brain(
                args.config, args.brain, args.as_of, args.labels, args.section_labels, args.output
            )
        else:
            run_benchmark(
                args.corpus, args.output, tantivy=args.tantivy, qmd=args.qmd, repeat=args.repeat
            )
            print(args.output / "report.json")
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Benchmark failed: {exc}\n")


if __name__ == "__main__":
    main()
