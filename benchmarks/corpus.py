"""Deterministic synthetic records and exports from healthy installed brains."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from portable_kb.retrieval_eval import load_evaluation_labels
from portable_kb.search import _healthy_brain
from portable_kb.search_records import normalize_bundle
from portable_kb.settings import load_settings


def _write_export(destination: Path, records, queries: list[dict], origin: dict) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256()
    count = 0
    with (destination / "records.jsonl").open("wb") as stream:
        for record in records:
            raw = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode()
            stream.write(raw)
            digest.update(raw)
            count += 1
    (destination / "queries.json").write_text(
        json.dumps(queries, ensure_ascii=False, indent=2) + "\n"
    )
    (destination / "corpus.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_count": count,
                "records_sha256": digest.hexdigest(),
                **origin,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def export_brain(
    config: Path,
    slug: str | None,
    as_of: str,
    labels_path: Path,
    sections_path: Path,
    destination: Path,
) -> None:
    settings = load_settings(config)
    brain, _checkout, bundle, health = _healthy_brain(settings, slug, as_of=as_of)
    records = [record.as_dict() for record in normalize_bundle(brain, bundle)]
    labels = load_evaluation_labels(labels_path)
    judgments = json.loads(sections_path.read_text())
    if set(judgments) != {query.identity for query in labels.queries}:
        raise ValueError("section judgments must cover exactly the item-label query IDs")
    queries = []
    for query in labels.queries:
        section_relevance = {}
        for target in judgments[query.identity]:
            matches = [
                record
                for record in records
                if record["item_id"] == target["item_id"] and record["heading"] == target["heading"]
            ]
            if (
                len(matches) != 1
                or type(target["grade"]) is not int
                or target["grade"] not in (1, 2, 3)
            ):
                raise ValueError(
                    f"ambiguous, absent, or invalid section judgment: {query.identity}"
                )
            section_relevance[matches[0]["section_id"]] = target["grade"]
        if bool(query.relevance) != bool(section_relevance):
            raise ValueError("item and section labels must agree on no-result queries")
        queries.append(
            {
                "id": query.identity,
                "query": query.text,
                "item_relevance": dict(query.relevance),
                "section_relevance": section_relevance,
                "filters": {},
            }
        )
    known_items = {record["item_id"] for record in records}
    if any(set(query["item_relevance"]) - known_items for query in queries):
        raise ValueError("labels contain IDs absent from the exported brain")
    _write_export(
        destination,
        records,
        queries,
        {
            "origin": "git-brain",
            "brain_id": brain.id,
            "brain_slug": brain.slug,
            "commit": brain.commit,
            "as_of": as_of,
            "item_count": len(known_items),
            "labels_sha256": labels.sha256,
            "section_labels_sha256": hashlib.sha256(sections_path.read_bytes()).hexdigest(),
            "validation_warnings": health["validation_warnings"],
        },
    )


def synthetic_corpus(destination: Path, count: int) -> None:
    """Generate benchmark fixtures, not canonical or human-verified knowledge."""
    if not 16 <= count <= 100_000:
        raise ValueError("synthetic item count must be between 16 and 100000")
    samples = {}

    def records():
        for index in range(count):
            spanish = bool(index % 2)
            identity = "urn:uuid:" + str(
                UUID(
                    bytes=hashlib.sha256(f"pkb-benchmark-v1/{index}".encode()).digest()[:16],
                    version=4,
                )
            )
            product = f"Aurora{index:06d}"
            item_type = "procedure" if index % 4 < 2 else "concept"
            status = ("draft", "stable", "deprecated")[index % 3]
            path = f"{'procedimientos/rotación' if spanish else 'procedures/rotation'}/{product}.md"
            title = f"{product} {'rotación de credenciales' if spanish else 'credential rotation'}"
            description = (
                "Rotar credenciales y recuperar el acceso."
                if spanish
                else "Rotate credentials and recover access."
            )
            for section, heading in enumerate(
                ("Pasos", "Recuperación") if spanish else ("Steps", "Recovery")
            ):
                if spanish:
                    text = f"{product} {'rotar credenciales después de comprobar la autorización' if section == 0 else 'recuperar acceso y revertir cambios después de un error'}."
                else:
                    text = f"{product} {'rotate credentials after checking authorization' if section == 0 else 'recover access and roll back changes after a failure'}."
                # Procedures include a longer passage, with discriminating
                # keywords held constant across corpus sizes.
                paragraph = (
                    text
                    + "\n"
                    + (
                        (
                            "Registrar cada resultado y revisar las fuentes.\n"
                            if spanish
                            else "Record each outcome and review the sources.\n"
                        )
                        * (8 if item_type == "procedure" else 1)
                    )
                )
                body = f"## {heading}\n\n{paragraph}"
                start = 10 if section == 0 else 40
                end = start + len(body.splitlines()) - 1
                record = {
                    "schema_version": 1,
                    "section_id": f"{identity}#{start}-{end}",
                    "brain_id": "synthetic-benchmark-v1",
                    "brain_slug": f"synthetic-{count}",
                    "commit": None,
                    "item_id": identity,
                    "path": path,
                    "title": title,
                    "description": description,
                    "heading": heading,
                    "body": body,
                    "line_start": start,
                    "line_end": end,
                    "type": item_type,
                    "status": status,
                    "sensitivity": "public",
                    "stale_after": None,
                    "updated_at": None,
                    "content_hash": "sha256:" + hashlib.sha256(body.encode()).hexdigest(),
                }
                if index < 16:
                    samples[index, section] = record
                yield record

    # Populate the small judgment set independently of streaming the full export.
    iterator = records()
    first = [next(iterator) for _ in range(32)]
    queries = []
    for index in range(8):
        record = samples[index, 0]
        product = f"Aurora{index:06d}"
        query = (
            f"{product} {'Pasos rotar autorización' if index % 2 else 'Steps rotate authorization'}"
        )
        queries.append(
            {
                "id": f"passage-{index}",
                "query": query,
                "item_relevance": {record["item_id"]: 3},
                "section_relevance": {record["section_id"]: 3},
                "filters": {},
            }
        )
    for kind, index in (("uuid", 1), ("unicode-path", 3)):
        targets = [samples[index, section] for section in (0, 1)]
        queries.append(
            {
                "id": kind,
                "query": targets[0]["item_id" if kind == "uuid" else "path"],
                "item_relevance": {targets[0]["item_id"]: 3},
                "section_relevance": {record["section_id"]: 3 for record in targets},
                "filters": {},
            }
        )
    for index, kind in ((6, "type"), (7, "status")):
        record = samples[index, 1]
        queries.append(
            {
                "id": f"filter-{kind}",
                "query": f"Aurora{index:06d} {'Recuperación' if index % 2 else 'Recovery'}",
                "item_relevance": {record["item_id"]: 3},
                "section_relevance": {record["section_id"]: 3},
                "filters": {kind: record[kind]},
            }
        )
    record = samples[0, 1]
    queries.append(
        {
            "id": "synonym-gap",
            "query": "Aurora000000 restore",
            "item_relevance": {record["item_id"]: 3},
            "section_relevance": {record["section_id"]: 3},
            "filters": {},
        }
    )
    queries.extend(
        [
            {
                "id": "no-result",
                "query": "zxqvnotincorpus92817",
                "item_relevance": {},
                "section_relevance": {},
                "filters": {},
            },
            {
                "id": "excluded-type",
                "query": "Aurora000000",
                "item_relevance": {},
                "section_relevance": {},
                "filters": {"type": "concept"},
            },
        ]
    )

    def all_records():
        yield from first
        yield from iterator

    _write_export(
        destination,
        all_records(),
        queries,
        {
            "origin": "synthetic-benchmark",
            "generator_version": 1,
            "item_count": count,
            "commit": None,
            "as_of": None,
        },
    )
