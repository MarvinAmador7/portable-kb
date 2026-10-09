"""Join unchanged blinded judgments with longitudinal mechanical observations."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median

from evals.agent_cli.harness import digest, write_json
from evals.wiki_compare.harness import load_json

from .longitudinal import audit, clean, hashes
from .longitudinal_scenarios import GROUNDING_POLICY, VARIANTS, story
from .natural import record_parts
from .natural_scenarios import checksum


def captures_with_boundary_newlines(brain: Path, records: dict[str, str]) -> dict:
    """Supplement exact-body measure; permit only boundary newline formatting."""
    captures = {name: [] for name in records}
    for path in sorted(brain.rglob("*.md")):
        text = path.read_text()
        candidate = record_parts(text)
        for name, payload in records.items():
            original = record_parts(payload)
            if payload in text or (
                original is not None
                and candidate is not None
                and original[1].strip("\n") == candidate[1].strip("\n")
                and all(candidate[0].get(k) == v for k, v in original[0].items())
            ):
                captures[name].append(str(path.relative_to(brain)))
    return captures


def report(root: Path) -> dict:
    mapping = load_json(root / "blind-map.json")
    observations = audit(root)
    for row in observations["rows"]:
        row["answer_sha256"] = checksum(row.get("answer", ""))
        row["answer"] = clean(row.get("answer", ""))
        events = (
            root
            / row["name"]
            / f"session-{(row['round'] - 1) * 2 + (2 if row['operation'] == 'question' else 1):02}"
            / "events.jsonl"
        )
        commands = (
            [json.loads(line).get("item", {}) for line in events.read_text().splitlines()]
            if events.exists()
            else []
        )
        row["recorded_commands"] = len(commands)
        row["command_errors"] = sum(c.get("exit_code", 0) != 0 for c in commands)
        key = row["name"].split("-", 1)[0]
        incoming = story(key)["updates"][row["round"] - 1] if row["operation"] == "update" else {}
        brain = events.parent / "work/brain"
        row["boundary_newline_preserving_captures"] = {
            k: bool(v) for k, v in captures_with_boundary_newlines(brain, incoming).items()
        }
    judgments = {}
    for key, *_ in VARIANTS:
        review = load_json(root / f"review-{key}.json")
        for item in review["items"]:
            label = item["id"]
            if label not in mapping or label in judgments:
                raise ValueError("unknown or duplicate review item")
            target = mapping[label]
            if not target["name"].startswith(key + "-"):
                raise ValueError("review story mismatch")
            expected = story(key)["rubrics"][target["round"] - 1]
            if set(item["criteria"]) != set(expected):
                raise ValueError("review criterion mismatch")
            if any(
                type(v["passed"]) is not bool
                or not isinstance(v["reason"], str)
                or not isinstance(v["quote"], str)
                for v in item["criteria"].values()
            ):
                raise ValueError("malformed binary review")
            if not isinstance(item["material_unsupported_claims"], list):
                raise ValueError("malformed material assertion review")
            judgments[label] = item
    if set(judgments) != set(mapping):
        raise ValueError("missing review items")
    reverse = {(v["name"], v["round"]): label for label, v in mapping.items()}
    answers = []
    for row in observations["rows"]:
        if row["operation"] == "question":
            label = reverse[(row["name"], row["round"])]
            judgment = judgments[label]
            answers.append(
                {
                    **row,
                    "blind_id": label,
                    "judgment": judgment,
                    "passed": row["completed"]
                    and all(c["passed"] for c in judgment["criteria"].values())
                    and not judgment["material_unsupported_claims"],
                }
            )
    if len(answers) != 90 or len(observations["rows"]) != 180:
        raise ValueError("incomplete suite; do not publish as completed")
    summary = {}
    for arm in ("wiki", "wiki-grounded", "groundray"):
        rows = [r for r in observations["rows"] if r["arm"] == arm]
        questions = [r for r in answers if r["arm"] == arm]
        updates = [r for r in rows if r["operation"] == "update"]

        def times(rs):
            return [
                r["elapsed_seconds"] for r in rs if isinstance(r["elapsed_seconds"], (int, float))
            ]

        final_sizes = []
        for key, *_ in VARIANTS:
            initial = story(key)["initial"]
            after = root / f"{key}-{arm}/session-12/work/brain"
            final_sizes.append(
                {
                    "story": key,
                    "initial_files": len(initial),
                    "final_files": len(hashes(after)),
                    "initial_bytes": sum(len(t.encode()) for t in initial.values()),
                    "final_bytes": sum(p.stat().st_size for p in after.rglob("*") if p.is_file()),
                }
            )
        summary[arm] = {
            "answers_passed": sum(r["passed"] for r in questions),
            "answers_total": len(questions),
            "criteria_passed": sum(
                v["passed"] for r in questions for v in r["judgment"]["criteria"].values()
            ),
            "criteria_total": 4 * len(questions),
            "answers_with_material_unsupported_claims": sum(
                bool(r["judgment"]["material_unsupported_claims"]) for r in questions
            ),
            "failed_criteria_by_round": dict(
                Counter(
                    str(r["round"])
                    for r in questions
                    for v in r["judgment"]["criteria"].values()
                    if not v["passed"]
                )
            ),
            "question_sessions_changing_brain": sum(bool(r["changed_pages"]) for r in questions),
            "sessions_completed": sum(r["completed"] for r in rows),
            "sessions_total": len(rows),
            "recorded_commands": sum(r["recorded_commands"] for r in rows),
            "command_errors": sum(r["command_errors"] for r in rows),
            "preexisting_raw_preserved_sessions": sum(r["preexisting_raw_unchanged"] for r in rows),
            "new_record_captures_preserved": sum(
                v for r in updates for v in r["incoming_preserved"].values()
            ),
            "new_record_captures_total": sum(len(r["incoming_preserved"]) for r in updates),
            "new_record_captures_preserved_allowing_boundary_newlines": sum(
                v for r in updates for v in r["boundary_newline_preserving_captures"].values()
            ),
            "skills_unchanged_sessions": sum(r["skills_unchanged"] for r in rows),
            "median_question_seconds": median(times(questions)) if times(questions) else None,
            "median_update_seconds": median(times(updates)) if times(updates) else None,
            "brain_growth": final_sizes,
        }
    return {
        "suite": observations["suite"],
        "synthetic": True,
        "grounding_policy": GROUNDING_POLICY,
        "summary": summary,
        "answers": answers,
        "mechanical_observations": observations["rows"],
        "rubrics": {key: story(key)["rubrics"] for key, *_ in VARIANTS},
        "private_artifact_sha256": {
            p.name: digest(p)
            for p in root.glob("*.json")
            if p.name.startswith(("blind-", "review-", "manifest", "rubric"))
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
