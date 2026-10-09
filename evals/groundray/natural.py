"""Opt-in natural-question trials: fixture preparation and mechanical evidence audit."""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
from pathlib import Path

from evals.agent_cli.harness import digest, write_json
from evals.wiki_compare.harness import complete_text_seen, load_json

from .harness import command_outputs, session, tree_fingerprint
from .natural_scenarios import (
    HANDOFF_UPDATES,
    QUESTIONS,
    REQUIRED_READS,
    RUBRICS,
    SOURCES,
    checksum,
    corpus,
)


def prepare(root: Path, groundray: Path, wiki_skill: Path, repetitions: int = 2) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    root.mkdir(parents=True, exist_ok=False)
    seed = corpus()
    manifest = {
        "suite": "natural-business-v1",
        "synthetic": True,
        "repetitions": repetitions,
        "cases": [],
        "corpus_files": len(seed),
        "corpus_words": sum(len(body.split()) for body in seed.values()),
        "source_sha256": {name: checksum(body) for name, body in SOURCES.items()},
        "rubric_sha256": checksum(json.dumps(RUBRICS, sort_keys=True)),
        "evaluator_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
    }
    for repetition in range(1, repetitions + 1):
        # Same seed/order within each paired repetition; alternate navigation order.
        files = dict(seed)
        lines = files["index.md"].splitlines()
        items = [line for line in lines if line.startswith("- ")]
        random.Random(90210 + repetition).shuffle(items)
        files["index.md"] = "# Company archive\n\n" + "\n".join(items) + "\n"
        for scenario, (date, question) in QUESTIONS.items():
            for arm, skill in (("wiki", wiki_skill), ("groundray", groundray)):
                name = f"{scenario}-{arm}-{repetition}"
                case = root / name
                phase = case / "session-1"
                if scenario == "handoff":
                    task = "Company: Cedar Commerce\nAs of: 2026-10-20\n\nAdd today's engineering update to the brain.\n"
                    incoming = HANDOFF_UPDATES[0]
                else:
                    task = f"Company: Cedar Commerce\nAs of: {date}\n\n{question}\n"
                    incoming = {}
                session(phase, skill, incoming, task)
                for relative, body in files.items():
                    path = phase / "work/brain" / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(body)
                write_json(
                    case / "initial.json", {"files": {n: checksum(t) for n, t in files.items()}}
                )
                manifest["cases"].append(
                    {
                        "name": name,
                        "scenario": scenario,
                        "arm": arm,
                        "repetition": repetition,
                        "session_count": 3 if scenario == "handoff" else 1,
                        "skill_sha256": tree_fingerprint(phase / "work/skill"),
                        "seed_sha256": tree_fingerprint(phase / "work/brain"),
                    }
                )
    write_json(root / "manifest.json", manifest)
    write_json(root / "rubric.json", RUBRICS)
    return manifest


def advance(root: Path, name: str, phase_number: int) -> Path:
    metadata = next(
        (c for c in load_json(root / "manifest.json", {}).get("cases", []) if c["name"] == name),
        None,
    )
    if not metadata or metadata["scenario"] != "handoff" or phase_number not in (2, 3):
        raise ValueError("unknown handoff case or phase")
    case = root / name
    previous = case / f"session-{phase_number - 1}"
    if not (previous / "final.json").exists():
        raise ValueError("prior session has not finished; retain failure")
    brain = previous / "work/brain"
    if brain.is_symlink() or any(p.is_symlink() for p in brain.rglob("*")):
        raise ValueError("nonportable brain symlink")
    if phase_number == 2:
        task = "Company: Cedar Commerce\nAs of: 2026-10-21\n\nAdd today's engineering update to the brain.\n"
        records = HANDOFF_UPDATES[1]
    else:
        date, question = QUESTIONS["handoff"]
        task = f"Company: Cedar Commerce\nAs of: {date}\n\n{question}\n"
        records = {}
    destination = case / f"session-{phase_number}"
    session(destination, previous / "work/skill", records, task)
    shutil.copytree(brain, destination / "work/brain")
    write_json(
        case / f"handoff-{phase_number}.json", {"saved_brain_sha256": tree_fingerprint(brain)}
    )
    return destination


def saved_records(brain: Path, records: dict[str, str]) -> dict[str, list[str]]:
    """Credit preserved supplied payload even with a separate metadata envelope."""
    captures = {name: [] for name in records}
    for path in sorted(brain.rglob("*.md")):
        if path.is_symlink():
            continue
        text = path.read_text()
        for name, payload in records.items():
            if payload in text:
                captures[name].append(str(path.relative_to(brain)))
    return captures


def audit(root: Path) -> dict:
    manifest = load_json(root / "manifest.json")
    rows = []
    for metadata in manifest["cases"]:
        case = root / metadata["name"]
        number = metadata["session_count"]
        final_case = case / f"session-{number}"
        final = load_json(final_case / "final.json", {})
        answer = final.get("answer", "") if isinstance(final, dict) else ""
        if not isinstance(answer, str):
            answer = ""
        outputs = command_outputs(final_case)
        brain = final_case / "work/brain"
        expected = dict(SOURCES)
        if metadata["scenario"] == "handoff":
            for updates in HANDOFF_UPDATES:
                expected.update(updates)
        exposed = {name: complete_text_seen(body, outputs) for name, body in expected.items()}
        required = REQUIRED_READS[metadata["scenario"]]
        initial = load_json(case / "initial.json", {}).get("files", {})
        preserved = {
            name: (brain / name).is_file()
            and not (brain / name).is_symlink()
            and digest(brain / name) == value
            for name, value in initial.items()
            if name.startswith("raw/")
        }
        sources = saved_records(brain, expected)
        elapsed = []
        errors = 0
        for phase in range(1, number + 1):
            directory = case / f"session-{phase}"
            elapsed.append(load_json(directory / "runner.json", {}).get("elapsed_seconds"))
            if (directory / "events.jsonl").exists():
                for line in (directory / "events.jsonl").read_text().splitlines():
                    item = json.loads(line).get("item", {})
                    errors += item.get("exit_code", 0) != 0
        rows.append(
            {
                **metadata,
                "completed": bool(answer),
                "answer_sha256": checksum(answer),
                "answer_words": len(answer.split()),
                "required_sources_observed": {name: exposed[name] for name in required},
                "required_source_names_in_answer": {name: name in answer for name in required},
                "sources_observed": exposed,
                "old_source_bytes_preserved": preserved,
                "captures": sources,
                "skills_unchanged": all(
                    tree_fingerprint(case / f"session-{p}/work/skill") == metadata["skill_sha256"]
                    for p in range(1, number + 1)
                ),
                "elapsed_seconds_by_session": elapsed,
                "command_errors": errors,
                "changed_initial_pages": [
                    name
                    for name, value in initial.items()
                    if not (brain / name).is_file() or digest(brain / name) != value
                ],
            }
        )
    return {
        "suite": manifest["suite"],
        "synthetic": True,
        "cases": rows,
        "manifest_sha256": digest(root / "manifest.json"),
        "rubric_sha256": manifest["rubric_sha256"],
        "recorded_evaluator_sha256": manifest["evaluator_sha256"],
        "evaluator_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
    }


def blind_packet(root: Path) -> None:
    """Separate semantic answers from arm labels and structural observations."""
    manifest = load_json(root / "manifest.json")
    cases = list(manifest["cases"])
    random.Random(7713).shuffle(cases)
    packet = {
        "rubric": RUBRICS,
        "source_records": SOURCES,
        "handoff_records": HANDOFF_UPDATES,
        "items": [],
    }
    mapping = {}
    for i, metadata in enumerate(cases, 1):
        label = f"item-{i:02}"
        directory = root / metadata["name"] / f"session-{metadata['session_count']}"
        final = load_json(directory / "final.json", {})
        answer = final.get("answer", "") if isinstance(final, dict) else ""
        if not isinstance(answer, str):
            answer = ""
        # Paths can disclose arm labels. Remove only case prefixes, preserving citations.
        answer = re.sub(r"/workspace/[^\s)]+/work/brain/", "brain/", answer)
        answer = re.sub(r"\bgroundray\b|\bllm-wiki\b", "installed skill", answer, flags=re.I)
        packet["items"].append(
            {
                "id": label,
                "scenario": metadata["scenario"],
                "question": QUESTIONS[metadata["scenario"]][1],
                "answer": answer,
            }
        )
        mapping[label] = metadata["name"]
    write_json(root / "blind-packet.json", packet)
    write_json(root / "blind-map.json", mapping)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    first = actions.add_parser("prepare")
    first.add_argument("--root", type=Path, required=True)
    first.add_argument("--groundray", type=Path, required=True)
    first.add_argument("--wiki-skill", type=Path, required=True)
    first.add_argument("--repetitions", type=int, default=2)
    next_stage = actions.add_parser("advance")
    next_stage.add_argument("--root", type=Path, required=True)
    next_stage.add_argument("--case", required=True)
    next_stage.add_argument("--phase", type=int, required=True)
    measured = actions.add_parser("audit")
    measured.add_argument("--root", type=Path, required=True)
    measured.add_argument("--output", type=Path, required=True)
    blind = actions.add_parser("blind-packet")
    blind.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(
            args.root.resolve(),
            args.groundray.resolve(),
            args.wiki_skill.resolve(),
            args.repetitions,
        )
    elif args.action == "advance":
        advance(args.root.resolve(), args.case, args.phase)
    elif args.action == "audit":
        write_json(args.output, audit(args.root.resolve()))
    else:
        blind_packet(args.root.resolve())


if __name__ == "__main__":
    main()
