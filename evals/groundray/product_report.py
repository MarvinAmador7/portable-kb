"""Strictly join blinded product judgments and recorded work; no winner scalar."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from statistics import median

from evals.agent_cli.harness import digest, write_json
from evals.wiki_compare.harness import load_json

from .product import ARMS, audit, captures
from .product_scenarios import world

STATUSES = {"supported", "qualified", "unsupported", "missing"}
CONTINUITY = {"correction_effect", "history", "scope_dependencies", "portability"}


def validate_review(packet: dict, review: dict) -> None:
    expected = {i["id"]: i for i in packet["items"]}
    rows = {i["id"]: i for i in review["items"]}
    if set(rows) != set(expected) or len(rows) != len(review["items"]):
        raise ValueError("missing or duplicate product judgment")
    for label, row in rows.items():
        item = expected[label]
        if set(row["facets"]) != set(item["facets"]):
            raise ValueError("facet mismatch")
        for value in row["facets"].values():
            if (
                value["status"] not in STATUSES
                or type(value["provenance_supported"]) is not bool
                or type(value["useful_for_next_operator"]) is not bool
                or not isinstance(value["quote"], str)
                or not isinstance(value["reason"], str)
                or not isinstance(value["paths"], list)
            ):
                raise ValueError("malformed facet judgment")
            material = (
                item["answer"] if item["kind"] == "answer" else "\n".join(item["archive"].values())
            )
            if value["quote"] and value["quote"] not in material:
                raise ValueError("nonverbatim review quote")
            if any(path not in item["archive"] for path in value["paths"]):
                raise ValueError("unknown reviewed path")
        if not isinstance(row["material_unsupported_claims"], list):
            raise ValueError("malformed overclaim list")
        material = (
            item["answer"] if item["kind"] == "answer" else "\n".join(item["archive"].values())
        )
        for assertion in row["material_unsupported_claims"]:
            if (
                not isinstance(assertion["quote"], str)
                or not assertion["quote"]
                or assertion["quote"] not in material
                or not isinstance(assertion["reason"], str)
            ):
                raise ValueError("malformed overclaim")
        continuity = row.get("continuity", {})
        keys = CONTINUITY if item["phase"] == 6 and item["kind"] == "brain" else set()
        if set(continuity) != keys or any(
            type(v["passed"]) is not bool or not isinstance(v["reason"], str)
            for v in continuity.values()
        ):
            raise ValueError("continuity mismatch")


def report(root: Path) -> dict:
    mapping = load_json(root / "blind-map.json")
    manifest = load_json(root / "manifest.json")
    observations = audit(root)["rows"]
    if len(observations) != 6 * len(manifest["cases"]) or len(mapping) != len(manifest["cases"]):
        raise ValueError("incomplete experiment")
    judged = []
    for label, case in mapping.items():
        packet, review = (
            load_json(root / f"blind-{label}.json"),
            load_json(root / f"review-{label}.json"),
        )
        validate_review(packet, review)
        targets = {i["id"]: i for i in packet["items"]}
        for item in review["items"]:
            target = targets[item["id"]]
            judged.append(
                {
                    **case,
                    "id": item["id"],
                    "phase": target["phase"],
                    "kind": target["kind"],
                    "request": target["request"],
                    "answer": target["answer"] if target["kind"] == "answer" else None,
                    "judgment": item,
                }
            )
    owner_map = load_json(root / "owner-map.json")
    owner_rows = {}
    for key in {c["world"] for c in manifest["cases"]}:
        for item in load_json(root / f"owner-route-{key}.json")["items"]:
            if item["id"] in owner_rows or item["id"] not in owner_map:
                raise ValueError("invalid owner route join")
            owner_rows[item["id"]] = {**item, **owner_map[item["id"]]}
    if set(owner_rows) != set(owner_map):
        raise ValueError("missing owner route")
    summary = {}
    for arm in ARMS:
        rows = [r for r in observations if r["arm"] == arm]
        reviews = [r for r in judged if r["arm"] == arm]
        owner = [
            r
            for r in owner_rows.values()
            if any(c["name"] == r["name"] and c["arm"] == arm for c in manifest["cases"])
        ]
        stages = {}
        for phase, kind in ((1, "brain"), (3, "answer"), (6, "brain"), (6, "answer")):
            selected = [r for r in reviews if r["phase"] == phase and r["kind"] == kind]
            facets = [v for r in selected for v in r["judgment"]["facets"].values()]
            stages[f"phase-{phase}-{kind}"] = {
                "items": len(selected),
                "facets": len(facets),
                "status_counts": dict(Counter(v["status"] for v in facets)),
                "facets_with_supported_provenance": sum(v["provenance_supported"] for v in facets),
                "facets_useful_for_next_operator": sum(
                    v["useful_for_next_operator"] for v in facets
                ),
                "items_with_material_unsupported_claims": sum(
                    bool(r["judgment"]["material_unsupported_claims"]) for r in selected
                ),
                "continuity_passed": sum(
                    v["passed"]
                    for r in selected
                    for v in r["judgment"].get("continuity", {}).values()
                ),
                "continuity_total": sum(len(r["judgment"].get("continuity", {})) for r in selected),
            }
        final_captures = []
        for case in [c for c in manifest["cases"] if c["arm"] == arm]:
            records = dict(world(case["world"])["inputs"])
            for phase in (2, 4, 5):
                incoming = root / case["name"] / f"session-{phase:02}/work/incoming"
                records.update(
                    {
                        f"phase-{phase}/{p.relative_to(incoming)}": p.read_text()
                        for p in incoming.rglob("*")
                        if p.is_file()
                    }
                )
            paths = captures(root / case["name"] / "session-06/work/brain", records)
            final_captures.append(
                {
                    "name": case["name"],
                    "preserved": sum(bool(v) for v in paths.values()),
                    "total": len(paths),
                    "missing": [k for k, v in paths.items() if not v],
                }
            )
        times = {
            operation: median(
                r["elapsed_seconds"]
                for r in rows
                if r["operation"] == operation and isinstance(r["elapsed_seconds"], (float, int))
            )
            for operation in {r["operation"] for r in rows}
        }
        summary[arm] = {
            "stages": stages,
            "sessions_completed": sum(r["completed"] for r in rows),
            "sessions_total": len(rows),
            "owner_questions_answered": len(owner),
            "owner_redundant_questions": sum(r["redundant_with_records"] for r in owner),
            "owner_questions_without_matching_card": sum(r["card"] is None for r in owner),
            "distinct_owner_cards_requested": sum(
                len({r["card"] for r in owner if r["name"] == c["name"] and r["card"] is not None})
                for c in manifest["cases"]
                if c["arm"] == arm
            ),
            "owner_question_words": sum(len(q.split()) for r in rows for q in r["owner_questions"]),
            "owner_interface_issues": sum(bool(r["owner_interface_issues"]) for r in rows),
            "median_seconds_by_operation": times,
            "commands": sum(r["commands"] for r in rows),
            "nonzero_exits": sum(r["nonzero_exits"] for r in rows),
            "question_sessions_changing_brain": sum(
                bool(r["changed_pages"])
                for r in rows
                if r["operation"] in ("first-briefing", "handoff")
            ),
            "skills_unchanged_sessions": sum(r["skills_unchanged"] for r in rows),
            "final_source_captures": final_captures,
            "total_final_files": sum(r["brain_files"] for r in rows if r["phase"] == 6),
            "total_final_bytes": sum(r["brain_bytes"] for r in rows if r["phase"] == 6),
        }
    return {
        "suite": manifest["suite"],
        "synthetic": True,
        "summary": summary,
        "judged_items": judged,
        "mechanical_observations": observations,
        "owner_routes": list(owner_rows.values()),
        "manifest": manifest,
        "private_artifact_sha256": {
            p.name: digest(p)
            for p in root.glob("*.json")
            if p.name.startswith(("blind-", "review-", "owner-", "manifest", "private-oracle"))
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_json(args.output, report(args.root))


if __name__ == "__main__":
    main()
