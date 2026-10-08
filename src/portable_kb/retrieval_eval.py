"""Read-only, item-level retrieval evaluation against an explicitly dated brain."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import statistics
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from .parsing import discover_concepts, parse_concept
from .search import (
    MAX_QUERY_LENGTH,
    _healthy_brain,
    _require_current_index,
    get_search_provider,
    search_keyword,
)
from .settings import Settings


class EvaluationError(ValueError):
    """Raised for invalid labels or incomparable retrieval runs."""


@dataclass(frozen=True, slots=True)
class LabeledQuery:
    identity: str
    text: str
    relevance: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class EvaluationLabels:
    name: str
    sha256: str
    queries: tuple[LabeledQuery, ...]


def load_evaluation_labels(path: Path) -> EvaluationLabels:
    """Load strict JSON labels without executing content or inferring relevance."""
    try:
        raw = path.read_bytes()
        payload = json.loads(raw, object_pairs_hook=_unique_fields)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Cannot read evaluation labels: {exc}") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "name", "queries"}
        or type(payload["schema_version"]) is not int
        or payload["schema_version"] != 1
        or not isinstance(payload["name"], str)
        or not payload["name"].strip()
        or not isinstance(payload["queries"], list)
        or not payload["queries"]
    ):
        raise EvaluationError("Labels require schema_version 1, a name, and non-empty queries.")
    queries = []
    identities = set()
    for row in payload["queries"]:
        if not isinstance(row, dict) or set(row) != {"id", "query", "relevance"}:
            raise EvaluationError("Each labeled query requires id, query, and relevance.")
        identity, text, relevance = row["id"], row["query"], row["relevance"]
        if not isinstance(identity, str) or not identity.strip() or identity in identities:
            raise EvaluationError("Query IDs must be non-empty and unique.")
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text.strip()) > MAX_QUERY_LENGTH
            or "\x00" in text
        ):
            raise EvaluationError("Labeled query text is empty, too long, or contains NUL.")
        if not isinstance(relevance, dict):
            raise EvaluationError("Relevance must map immutable item IDs to grades 1, 2, or 3.")
        for item_id, grade in relevance.items():
            try:
                valid_id = item_id.startswith("urn:uuid:") and str(UUID(item_id[9:])) == item_id[9:]
            except ValueError:
                valid_id = False
            if not valid_id or type(grade) is not int or grade not in (1, 2, 3):
                raise EvaluationError("Relevance must map immutable item IDs to grades 1, 2, or 3.")
        identities.add(identity)
        queries.append(LabeledQuery(identity, text.strip(), relevance))
    return EvaluationLabels(payload["name"], hashlib.sha256(raw).hexdigest(), tuple(queries))


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationError(f"Duplicate label field: {key}")
        result[key] = value
    return result


def score_ranking(ranked_ids: Sequence[str], relevance: Mapping[str, int]) -> dict[str, Any]:
    """Score top-ten item ranks; duplicates consume slots but earn no extra gain.

    Precision uses five slots even when fewer results are returned. Explicit
    no-result queries have separate accuracy and do not inflate relevance means.
    """
    if not relevance:
        return {"no_result_correct": not ranked_ids}
    seen = set()
    grades = []
    for item_id in ranked_ids[:10]:
        grades.append(0 if item_id in seen else relevance.get(item_id, 0))
        seen.add(item_id)
    ideal = sorted(relevance.values(), reverse=True)[:10]
    dcg = sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))
    idcg = sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(ideal))
    return {
        "precision_at_5": sum(grade > 0 for grade in grades[:5]) / 5,
        "recall_at_10": sum(grade > 0 for grade in grades) / len(relevance),
        "reciprocal_rank_at_10": next(
            (1 / rank for rank, grade in enumerate(grades, start=1) if grade > 0),
            0.0,
        ),
        "ndcg_at_10": dcg / idcg,
    }


def evaluate_retrieval(
    settings: Settings,
    labels_path: Path,
    slug: str | None = None,
    *,
    as_of: str,
    repeat: int = 2,
) -> dict[str, Any]:
    """Evaluate the existing keyword index; never install, rebuild, or mutate it."""
    if type(repeat) is not int or not 1 <= repeat <= 20:
        raise EvaluationError("Evaluation repeat must be between 1 and 20.")
    if not as_of:
        raise EvaluationError("Evaluation requires an explicit as_of date.")
    labels = load_evaluation_labels(labels_path)
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    provider = get_search_provider(settings)
    metadata = provider.load_metadata(brain.slug)
    _require_current_index(metadata, brain)
    items = {}
    corpus_hashes = []
    for path in discover_concepts(bundle):
        item = parse_concept(path, bundle).item
        if item is not None:
            items[item.id] = item.relative_path
            corpus_hashes.append(
                (item.relative_path, hashlib.sha256(item.source_text.encode()).hexdigest())
            )
    unknown = sorted(
        {item_id for query in labels.queries for item_id in query.relevance} - items.keys()
    )
    if unknown:
        raise EvaluationError(
            f"Labels reference IDs absent from the pinned brain: {', '.join(unknown)}"
        )

    measured = []
    samples = []
    checked_result_count = 0
    for query in labels.queries:
        rankings = []
        durations = []
        first_results = []
        for run in range(repeat):
            started = time.perf_counter()
            response = search_keyword(settings, query.text, brain.slug, limit=10, as_of=as_of)
            durations.append((time.perf_counter() - started) * 1_000)
            if (
                response["brain"]["id"] != brain.id
                or response["brain"]["slug"] != brain.slug
                or response["brain"]["commit"] != brain.commit
                or response["index_commit"] != brain.commit
                or response["provider"] != provider.name
            ):
                raise EvaluationError("Brain, provider, or index changed during evaluation.")
            for result in response["results"]:
                expected = {
                    "brain_id": brain.id,
                    "brain_slug": brain.slug,
                    "commit": brain.commit,
                    "item_id": result["item_id"],
                    "path": items.get(result["item_id"]),
                }
                if result["citation"] != expected or result["path"] != expected["path"]:
                    raise EvaluationError("Search returned an incorrect pinned item citation.")
                checked_result_count += 1
            rankings.append(
                [
                    (result["item_id"], result["path"], result.get("line"))
                    for result in response["results"]
                ]
            )
            if run == 0:
                first_results = response["results"]
        scores = score_ranking([result["item_id"] for result in first_results], query.relevance)
        measured.append(scores)
        samples.append(
            {
                "id": query.identity,
                "query": query.text,
                "relevance": dict(query.relevance),
                "metrics": scores,
                "results": first_results,
                "latency_ms": durations,
                "ranking_stable": (
                    all(ranking == rankings[0] for ranking in rankings[1:]) if repeat > 1 else None
                ),
            }
        )
    positive = [row for row in measured if "precision_at_5" in row]
    negative = [row["no_result_correct"] for row in measured if "no_result_correct" in row]
    metrics = {
        key: statistics.mean(row[key] for row in positive) if positive else None
        for key in ("precision_at_5", "recall_at_10", "reciprocal_rank_at_10", "ndcg_at_10")
    }
    metrics["no_result_accuracy"] = statistics.mean(negative) if negative else None
    return {
        "schema_version": 1,
        "dataset": {"name": labels.name, "sha256": labels.sha256, "granularity": "item"},
        "as_of": as_of,
        "provider": provider.name,
        "index_metadata": dict(metadata),
        "concept_count": len(items),
        "corpus_sha256": hashlib.sha256(
            json.dumps(corpus_hashes, sort_keys=True).encode()
        ).hexdigest(),
        "query_count": len(labels.queries),
        "positive_query_count": len(positive),
        "no_result_query_count": len(negative),
        "repeat": repeat,
        "environment": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "metrics": metrics,
        "latency": {
            "scope": "end-to-end CLI library query including governance and provider process startup",
            "first_pass_ms": _percentiles([row["latency_ms"][0] for row in samples]),
            "repeat_pass_ms": _percentiles(
                [value for row in samples for value in row["latency_ms"][1:]]
            ),
        },
        "checked_result_count": checked_result_count,
        "citation_correctness": 1.0 if checked_result_count else None,
        "ranking_stable": all(row["ranking_stable"] for row in samples) if repeat > 1 else None,
        "queries": samples,
        "validation_warnings": health["validation_warnings"],
        "ok": True,
    }


def _percentiles(values: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(values)
    # Nearest-rank percentiles remain defined for the small starter corpus.
    return {
        "count": len(values),
        **{
            f"p{percentile}": ordered[math.ceil(len(ordered) * percentile / 100) - 1]
            if ordered
            else None
            for percentile in (50, 95, 99)
        },
    }
