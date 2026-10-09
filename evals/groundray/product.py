"""Opt-in empty-brain formation, simulated owner review, correction and handoff."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

from evals.agent_cli.harness import digest, write_json
from evals.wiki_compare.harness import load_json

from .harness import session, tree_fingerprint
from .longitudinal import clean, hashes
from .longitudinal_scenarios import GROUNDING_POLICY
from .product_scenarios import WORLDS, world

ARMS = ("wiki", "wiki-grounded", "groundray")
PHASES = ("build", "owner-replies", "first-briefing", "correct", "new-records", "handoff")


def product_session(directory: Path, skill: Path, incoming: dict[str, str], prompt: str) -> None:
    session(directory, skill, {}, prompt)
    for name, text in incoming.items():
        path = directory / "work/incoming" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def questions(directory: Path) -> tuple[list[str], list[str]]:
    path = directory / "work/owner-questions.json"
    if not path.exists():
        return [], []
    try:
        value = json.loads(path.read_text())
        items = value["questions"]
        if not isinstance(items, list) or any(
            not isinstance(q, str) or not q.strip() for q in items
        ):
            raise ValueError("questions must be nonempty strings")
    except (ValueError, KeyError, TypeError) as error:
        return [], [f"Malformed question artifact: {error}"]
    return items[:6], ["More than six owner questions; only first six answered"] if len(
        items
    ) > 6 else []


def task(data: dict, phase: int) -> str:
    prefix = f"Company: {data['company']}\nCase dates are fictional. As of: "
    dates = ("2026-11-01", "2026-11-01", "2026-11-01", "2026-11-02", "2026-11-06", "2026-11-06")
    requests = (
        "Create a portable company brain in brain/ from the records in incoming/. "
        "It should help the next person run this business. Choose its organization using your installed skill. "
        "You may ask the owner up to six focused questions before we start using it, one issue per question. "
        'Save any questions as owner-questions.json with {"questions": ["question text", ...]}; '
        "an empty list is allowed. Your final response should briefly explain what you built and what needs attention.",
        "Add the owner's replies in incoming/ to the company brain. The owner answered only the requested "
        "issues they could address. Make the brain ready for a colleague to use.",
        data["first_question"],
        "The owner sent corrections and reconciled records in incoming/. Correct the company brain "
        "and the material understanding that depends on these records.",
        "Add today's records in incoming/ to the company brain.",
        data["final_question"]
        + " You have the portable saved folder, without the prior agents' conversations.",
    )
    return prefix + dates[phase - 1] + "\n\n" + requests[phase - 1] + "\n"


def prepare(root: Path, groundray: Path, wiki: Path, repetitions: int = 2) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    root.mkdir(parents=True, exist_ok=False)
    short = root / "wiki-grounded.md"
    short.write_text(wiki.read_text() + GROUNDING_POLICY)
    manifest = {
        "suite": "company-brain-product-v1",
        "synthetic": True,
        "repetitions": repetitions,
        "cases": [],
        "evaluator_sha256": {p.name: digest(p) for p in Path(__file__).parent.glob("product*.py")},
    }
    write_json(
        root / "private-oracle.json",
        {k: {"cards": world(k)["cards"], "facets": world(k)["facets"]} for k in WORLDS},
    )
    for key in WORLDS:
        data = world(key)
        for repetition in range(1, repetitions + 1):
            ordering = list(data["inputs"])
            random.Random(4200 + repetition + len(key)).shuffle(ordering)
            incoming = {
                **data["inputs"],
                "packet-order.txt": "Suggested intake order; all records remain available.\n"
                + "\n".join(ordering)
                + "\n",
            }
            for arm, skill in (("wiki", wiki), ("wiki-grounded", short), ("groundray", groundray)):
                name = f"{key}-{arm}-{repetition}"
                directory = root / name / "session-01"
                product_session(directory, skill, incoming, task(data, 1))
                (directory / "work/brain").mkdir()
                write_json(directory / "before.json", {})
                manifest["cases"].append(
                    {
                        "name": name,
                        "world": key,
                        "arm": arm,
                        "repetition": repetition,
                        "skill_sha256": tree_fingerprint(directory / "work/skill"),
                        "incoming_sha256": tree_fingerprint(directory / "work/incoming"),
                        "source_count": len(data["inputs"]),
                        "source_bytes": sum(len(t.encode()) for t in data["inputs"].values()),
                    }
                )
    write_json(root / "manifest.json", manifest)
    return manifest


def owner_packet(root: Path, key: str) -> None:
    if key not in WORLDS:
        raise ValueError("unknown business")
    cases = [c for c in load_json(root / "manifest.json")["cases"] if c["world"] == key]
    if any(not (root / c["name"] / "session-01/final.json").exists() for c in cases):
        raise ValueError("builds incomplete")
    candidates = []
    issues = {}
    for case in cases:
        qs, errors = questions(root / case["name"] / "session-01")
        issues[case["name"]] = errors
        candidates.extend((case["name"], index, q) for index, q in enumerate(qs))
    random.Random(5500 + len(key)).shuffle(candidates)
    mapping = load_json(root / "owner-map.json", {})
    items = []
    for index, (name, qindex, question) in enumerate(candidates, 1):
        label = f"{key}-q{index:02}"
        mapping[label] = {"name": name, "question_index": qindex}
        items.append({"id": label, "question": clean(question)})
    write_json(
        root / f"owner-packet-{key}.json",
        {
            "company": world(key)["company"],
            "cards": world(key)["cards"],
            "available_records": world(key)["inputs"],
            "items": items,
        },
    )
    write_json(root / "owner-map.json", mapping)
    write_json(root / f"owner-issues-{key}.json", issues)


def owner_replies(root: Path, name: str, key: str) -> dict[str, str]:
    mapping = load_json(root / "owner-map.json")
    routing = load_json(root / f"owner-route-{key}.json")
    expected = {label for label, target in mapping.items() if target["name"].startswith(key + "-")}
    rows = {item["id"]: item for item in routing["items"]}
    if set(rows) != expected or len(rows) != len(routing["items"]):
        raise ValueError("missing or duplicate owner routes")
    replies = []
    cards = world(key)["cards"]
    for label, item in rows.items():
        if item["card"] is not None and item["card"] not in cards:
            raise ValueError("unknown owner card")
        if not isinstance(item["reason"], str) or not isinstance(
            item["redundant_with_records"], bool
        ):
            raise ValueError("malformed route")
        if mapping[label]["name"] != name:
            continue
        index = mapping[label]["question_index"]
        qs, _ = questions(root / name / "session-01")
        answer = (
            cards[item["card"]]
            if item["card"]
            else "I cannot settle that from the owner information available. Please identify a specific issue or the missing evidence needed."
        )
        replies.append((index, qs[index], answer))
    text = "# Simulated owner's replies\n\nThese are fictional owner responses to this case's questions, not real-world authentication.\n\n"
    for index, question, answer in sorted(replies):
        text += f"## Question {index + 1}\n\n{question}\n\nOwner reply: {answer}\n\n"
    if not replies:
        text += "No owner questions were submitted in the supported interface. No new owner rules or facts are supplied.\n"
    return {"owner-replies.md": text}


def advance(root: Path, name: str, phase: int) -> Path:
    case = next((c for c in load_json(root / "manifest.json")["cases"] if c["name"] == name), None)
    if case is None or phase not in range(2, 7):
        raise ValueError("unknown case or phase")
    previous = root / name / f"session-{phase - 1:02}"
    if not (previous / "final.json").exists():
        raise ValueError("previous phase incomplete")
    if any(p.is_symlink() for p in (previous / "work/brain").rglob("*")):
        raise ValueError("nonportable brain")
    data = world(case["world"])
    incoming = (
        owner_replies(root, name, case["world"])
        if phase == 2
        else data["correction"]
        if phase == 4
        else data["update"]
        if phase == 5
        else {}
    )
    destination = root / name / f"session-{phase:02}"
    product_session(destination, previous / "work/skill", incoming, task(data, phase))
    shutil.copytree(previous / "work/brain", destination / "work/brain")
    write_json(destination / "before.json", hashes(destination / "work/brain"))
    write_json(
        destination / "handoff.json",
        {"previous_brain_sha256": tree_fingerprint(previous / "work/brain")},
    )
    return destination


def captures(brain: Path, records: dict[str, str]) -> dict[str, list[str]]:
    texts = {str(p.relative_to(brain)): p.read_text() for p in brain.rglob("*") if p.is_file()}
    return {
        name: [path for path, text in texts.items() if payload.strip("\n") in text]
        for name, payload in records.items()
    }


def audit(root: Path) -> dict:
    rows = []
    for case in load_json(root / "manifest.json")["cases"]:
        for phase in range(1, 7):
            directory = root / case["name"] / f"session-{phase:02}"
            if not directory.exists():
                continue
            brain = directory / "work/brain"
            before, after = load_json(directory / "before.json"), hashes(brain)
            events = (
                [
                    json.loads(line)["item"]
                    for line in (directory / "events.jsonl").read_text().splitlines()
                ]
                if (directory / "events.jsonl").exists()
                else []
            )
            final = load_json(directory / "final.json", {})
            supplied = {
                str(p.relative_to(directory / "work/incoming")): p.read_text()
                for p in (directory / "work/incoming").rglob("*")
                if p.is_file() and p.name != "packet-order.txt"
            }
            preserved = captures(brain, supplied)
            qs, errors = questions(directory) if phase == 1 else ([], [])
            rows.append(
                {
                    **case,
                    "phase": phase,
                    "operation": PHASES[phase - 1],
                    "completed": bool(final.get("answer")),
                    "answer": clean(final.get("answer", "")),
                    "answer_sha256": digest(directory / "final.json")
                    if (directory / "final.json").exists()
                    else None,
                    "elapsed_seconds": load_json(directory / "runner.json", {}).get(
                        "elapsed_seconds"
                    ),
                    "changed_pages": sorted(
                        k for k in before.keys() | after.keys() if before.get(k) != after.get(k)
                    ),
                    "skills_unchanged": tree_fingerprint(directory / "work/skill")
                    == case["skill_sha256"],
                    "incoming_preserved": {n: bool(v) for n, v in preserved.items()},
                    "commands": len(events),
                    "nonzero_exits": sum(e["exit_code"] != 0 for e in events),
                    "brain_files": len(after),
                    "brain_bytes": sum(p.stat().st_size for p in brain.rglob("*") if p.is_file()),
                    "owner_questions": [clean(q) for q in qs],
                    "owner_interface_issues": errors,
                }
            )
    return {"suite": "company-brain-product-v1", "rows": rows}


def blind_packets(root: Path) -> None:
    cases = load_json(root / "manifest.json")["cases"]
    if any(not (root / c["name"] / "session-06/final.json").exists() for c in cases):
        raise ValueError("suite incomplete")
    random.Random(6809).shuffle(cases)
    mapping = {}
    for index, case in enumerate(cases, 1):
        label = f"product-{index:02}"
        data = world(case["world"])
        items = []
        for phase, kind in ((1, "brain"), (3, "answer"), (6, "brain"), (6, "answer")):
            directory = root / case["name"] / f"session-{phase:02}"
            available = dict(data["inputs"])
            if phase >= 2:
                available.update(
                    {
                        str(
                            p.relative_to(root / case["name"] / "session-02/work/incoming")
                        ): p.read_text()
                        for p in (root / case["name"] / "session-02/work/incoming").rglob("*")
                        if p.is_file()
                    }
                )
            if phase >= 4:
                available.update(data["correction"])
            if phase >= 5:
                available.update(data["update"])
            archive = {
                str(p.relative_to(directory / "work/brain")): clean(p.read_text())
                for p in (directory / "work/brain").rglob("*")
                if p.is_file()
            }
            items.append(
                {
                    "id": f"{label}-{phase}-{kind}",
                    "phase": phase,
                    "kind": kind,
                    "request": task(data, phase),
                    "answer": clean(load_json(directory / "final.json")["answer"]),
                    "archive": archive,
                    "available_records": available,
                    "facets": data["facets"],
                }
            )
        write_json(root / f"blind-{label}.json", {"company": data["company"], "items": items})
        mapping[label] = case
    write_json(root / "blind-map.json", mapping)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("prepare", "owner-packet", "advance", "audit", "blind-packets"):
        sub.add_parser(name).add_argument("--root", type=Path, required=True)
    sub.choices["prepare"].add_argument("--groundray", type=Path, required=True)
    sub.choices["prepare"].add_argument("--wiki-skill", type=Path, required=True)
    sub.choices["prepare"].add_argument("--repetitions", type=int, default=2)
    sub.choices["owner-packet"].add_argument("--world", required=True)
    sub.choices["advance"].add_argument("--case", required=True)
    sub.choices["advance"].add_argument("--phase", type=int, required=True)
    sub.choices["audit"].add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.root, args.groundray, args.wiki_skill, args.repetitions)
    elif args.action == "owner-packet":
        owner_packet(args.root, args.world)
    elif args.action == "advance":
        advance(args.root, args.case, args.phase)
    elif args.action == "audit":
        write_json(args.output, audit(args.root))
    else:
        blind_packets(args.root)


if __name__ == "__main__":
    main()
