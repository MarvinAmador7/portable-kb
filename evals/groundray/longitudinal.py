"""Opt-in three-arm longitudinal wiki evaluation with fresh-session handoffs."""

from __future__ import annotations

import argparse
import random
import re
import shutil
from pathlib import Path

from evals.agent_cli.harness import digest, write_json
from evals.wiki_compare.harness import load_json

from .harness import session, tree_fingerprint
from .longitudinal_scenarios import GROUNDING_POLICY, VARIANTS, story
from .natural import content_preserving_records, record_parts


def hashes(directory: Path) -> dict:
    return {str(p.relative_to(directory)): digest(p) for p in sorted(directory.rglob("*")) if p.is_file()}


def unavailable(brain: Path, payload: str) -> list[str]:
    """Simulate losing intact standalone captures; never rewrite derived pages."""
    original = record_parts(payload)
    removed = []
    for path in sorted(brain.rglob("*.md")):
        candidate = record_parts(path.read_text())
        if original and candidate and candidate[1].strip("\n") == original[1].strip("\n") and all(
            candidate[0].get(k) == v for k, v in original[0].items()
        ):
            removed.append(str(path.relative_to(brain)))
            path.unlink()
    return removed


def prepare(root: Path, groundray: Path, wiki_skill: Path) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    short = root / "wiki-grounded.md"
    short.write_text(wiki_skill.read_text() + GROUNDING_POLICY)
    manifest = {"suite": "longitudinal-business-v1", "synthetic": True, "cases": [], "evaluator_sha256": {p.name: digest(p) for p in Path(__file__).parent.glob("longitudinal*.py")}}
    rubrics = {}
    for key, *_ in VARIANTS:
        data = story(key)
        rubrics[key] = data["rubrics"]
        for arm, skill in (("wiki", wiki_skill), ("wiki-grounded", short), ("groundray", groundray)):
            name = f"{key}-{arm}"
            directory = root / name / "session-01"
            task = f"Company: {data['company']}\nAs of: {data['dates'][0]}\n\nAdd today's supplied records to the brain.\n"
            session(directory, skill, data["updates"][0], task)
            for relative, text in data["initial"].items():
                path = directory / "work/brain" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            write_json(directory / "before.json", hashes(directory / "work/brain"))
            manifest["cases"].append({"name": name, "story": key, "arm": arm, "skill_sha256": tree_fingerprint(directory / "work/skill"), "seed_sha256": tree_fingerprint(directory / "work/brain")})
    write_json(root / "manifest.json", manifest)
    write_json(root / "rubric.json", rubrics)
    return manifest


def advance(root: Path, name: str, phase: int) -> Path:
    metadata = next((c for c in load_json(root / "manifest.json")["cases"] if c["name"] == name), None)
    if metadata is None or phase not in range(2, 13):
        raise ValueError("unknown case or phase")
    previous = root / name / f"session-{phase - 1:02}"
    if not (previous / "final.json").is_file():
        raise ValueError("previous session incomplete; retain failure")
    if any(p.is_symlink() for p in (previous / "work/brain").rglob("*")):
        raise ValueError("nonportable brain")
    data = story(metadata["story"])
    round_index = (phase - 1) // 2
    question = phase % 2 == 0
    task = data["questions"][round_index] if question else "Add today's supplied records to the brain."
    destination = root / name / f"session-{phase:02}"
    session(destination, previous / "work/skill", {} if question else data["updates"][round_index], f"Company: {data['company']}\nAs of: {data['dates'][round_index]}\n\n{task}\n")
    shutil.copytree(previous / "work/brain", destination / "work/brain")
    removed = unavailable(destination / "work/brain", data["updates"][3]["finance-note.md"]) if phase == 11 else []
    write_json(destination / "handoff.json", {"previous_brain_sha256": tree_fingerprint(previous / "work/brain"), "archive_loss_removed": removed})
    write_json(destination / "before.json", hashes(destination / "work/brain"))
    return destination


def clean(text: str) -> str:
    text = re.sub(r"/workspace/[^\s)]+/work/brain/", "brain/", text)
    return re.sub(r"\bgroundray\b|\bllm-wiki\b|wiki-grounded", "installed skill", text, flags=re.I)


def audit(root: Path) -> dict:
    manifest = load_json(root / "manifest.json")
    rows = []
    for metadata in manifest["cases"]:
        data = story(metadata["story"])
        for phase in range(1, 13):
            directory = root / metadata["name"] / f"session-{phase:02}"
            if not directory.exists():
                continue
            before = load_json(directory / "before.json")
            after = hashes(directory / "work/brain")
            final = load_json(directory / "final.json", {})
            runner = load_json(directory / "runner.json", {})
            incoming = {} if phase % 2 == 0 else data["updates"][(phase - 1) // 2]
            captures = content_preserving_records(directory / "work/brain", incoming)
            rows.append({**metadata, "phase": phase, "round": (phase + 1) // 2, "operation": "question" if phase % 2 == 0 else "update", "completed": bool(final.get("answer")), "answer": final.get("answer", ""), "elapsed_seconds": runner.get("elapsed_seconds"), "changed_pages": sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k)), "preexisting_raw_unchanged": all(after.get(k) == v for k, v in before.items() if k.startswith("raw/")), "incoming_preserved": {k: bool(v) for k, v in captures.items()}, "skills_unchanged": tree_fingerprint(directory / "work/skill") == metadata["skill_sha256"], "archive_loss_removed": load_json(directory / "handoff.json", {}).get("archive_loss_removed", [])})
    return {"suite": manifest["suite"], "manifest_sha256": digest(root / "manifest.json"), "rows": rows}


def blind_packet(root: Path, only_story: str | None = None) -> None:
    manifest = load_json(root / "manifest.json")
    if only_story and only_story not in {v[0] for v in VARIANTS}:
        raise ValueError("unknown story")
    mapping = load_json(root / "blind-map.json", {}) if only_story else {}
    for key, *_ in VARIANTS:
        if only_story and key != only_story:
            continue
        data = story(key)
        candidates = [(c, r) for c in manifest["cases"] if c["story"] == key for r in range(1, 7)]
        if only_story and any(not (root / c["name"] / f"session-{r * 2:02}/final.json").exists() for c, r in candidates):
            raise ValueError("story incomplete; do not grade partial outputs")
        random.Random(803 + len(key)).shuffle(candidates)
        packet = {"story": key, "company": data["company"], "initial_archive": data["initial"], "updates_in_chronological_order": data["updates"], "rubrics": data["rubrics"], "items": []}
        for i, (case, round_number) in enumerate(candidates, 1):
            label = f"{key}-{i:02}"
            directory = root / case["name"] / f"session-{round_number * 2:02}"
            final = load_json(directory / "final.json", {})
            # All authored pages and actual remaining source captures allow citation
            # and missing-original claims to be assessed without guessing availability.
            pages = {str(p.relative_to(directory / "work/brain")): clean(p.read_text()) for p in sorted((directory / "work/brain").rglob("*.md"))}
            packet["items"].append({"id": label, "round": round_number, "as_of": data["dates"][round_number - 1], "question": data["questions"][round_number - 1], "answer": clean(final.get("answer", "")), "retained_archive": pages})
            mapping[label] = {"name": case["name"], "round": round_number}
        write_json(root / f"blind-{key}.json", packet)
    write_json(root / "blind-map.json", mapping)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    first = actions.add_parser("prepare")
    first.add_argument("--groundray", type=Path, required=True)
    first.add_argument("--wiki-skill", type=Path, required=True)
    for action in (first, actions.add_parser("advance"), actions.add_parser("audit"), actions.add_parser("blind-packet")):
        action.add_argument("--root", type=Path, required=True)
    actions.choices["advance"].add_argument("--case", required=True)
    actions.choices["advance"].add_argument("--phase", type=int, required=True)
    actions.choices["audit"].add_argument("--output", type=Path, required=True)
    actions.choices["blind-packet"].add_argument("--story")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.root, args.groundray, args.wiki_skill)
    elif args.action == "advance":
        advance(args.root, args.case, args.phase)
    elif args.action == "audit":
        write_json(args.output, audit(args.root))
    else:
        blind_packet(args.root, args.story)


if __name__ == "__main__":
    main()
