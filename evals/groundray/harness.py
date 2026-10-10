"""Prepare fresh sessions and grade observed evidence, facts and preservation.

This pilot has no LLM judge. Link presence is a structural check, not proof that
prose correctly describes a dependency; reviewers must also inspect saved pages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from evals.agent_cli.harness import digest, product_environment, write_json
from evals.wiki_compare.harness import complete_text_seen, load_json

from .scenario import EXPECTED_1, EXPECTED_2, INITIAL, TASK_1, TASK_2, UPDATE


def tree_fingerprint(directory: Path) -> str:
    files = {
        str(p.relative_to(directory)): digest(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def session(directory: Path, skill: Path, records: dict[str, str], task: str) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "work/incoming").mkdir(parents=True)
    (directory / "home").mkdir()
    (directory / "gitconfig").write_text("")
    if skill.is_dir():
        shutil.copytree(skill, directory / "work/skill")
    else:
        (directory / "work/skill").mkdir()
        shutil.copyfile(skill, directory / "work/skill/SKILL.md")
    for name, text in records.items():
        (directory / "work/incoming" / name).write_text(text)
    (directory / "work/prompt.txt").write_text(task)
    environment = product_environment(directory)
    environment["WIKI_PATH"] = str(directory / "work/brain")
    write_json(directory / "bin/shim.json", {"product_environment": environment})


def prepare(root: Path, groundray: Path, wiki_skill: Path, repetitions: int = 2) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    root.mkdir(parents=True, exist_ok=False)
    manifest = {
        "scenario": "cedar-decision-v1",
        "synthetic": True,
        "cases": [],
        "evaluator_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "initial_records_sha256": {
            name: hashlib.sha256(text.encode()).hexdigest() for name, text in INITIAL.items()
        },
        "update_records_sha256": {
            name: hashlib.sha256(text.encode()).hexdigest() for name, text in UPDATE.items()
        },
    }
    for arm, skill in (("wiki", wiki_skill), ("groundray", groundray)):
        for repetition in range(1, repetitions + 1):
            name = f"{arm}-{repetition}"
            first = root / name / "session-1"
            session(first, skill, INITIAL, TASK_1)
            manifest["cases"].append(
                {
                    "name": name,
                    "arm": arm,
                    "repetition": repetition,
                    "skill_sha256": tree_fingerprint(first / "work/skill"),
                }
            )
    write_json(root / "manifest.json", manifest)
    return manifest


def brain_path(brain: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    candidate = brain / value.split("#", 1)[0]
    if candidate.is_symlink():
        return None
    resolved = candidate.resolve()
    return resolved if resolved.is_relative_to(brain.resolve()) and resolved.is_file() else None


def stage_second(root: Path, name: str) -> Path:
    if name not in {c["name"] for c in load_json(root / "manifest.json", {}).get("cases", [])}:
        raise ValueError("unknown case")
    first = root / name / "session-1"
    final = load_json(first / "final.json", {})
    brain = first / "work/brain"
    decision = brain_path(brain, final.get("artifacts", {}).get("decision"))
    if decision is None:
        raise ValueError("session 1 did not identify an existing decision page; retain failure")
    if any(p.is_symlink() for p in brain.rglob("*")):
        raise ValueError("saved brain contains symlinks; cannot make a portable fresh-session copy")
    second = root / name / "session-2"
    session(second, first / "work/skill", UPDATE, TASK_2)
    shutil.copytree(brain, second / "work/brain")
    write_json(
        root / name / "handoff.json",
        {
            "decision": str(decision.relative_to(brain.resolve())),
            "decision_bytes_hex": decision.read_bytes().hex(),
            "brain_sha256": tree_fingerprint(brain),
            "skill_sha256": tree_fingerprint(second / "work/skill"),
            "artifacts": {
                key: path.read_text()
                if (path := brain_path(brain, final.get("artifacts", {}).get(key)))
                else ""
                for key in ("definition", "assumptions", "commitment", "work")
            },
        },
    )
    return second


def command_outputs(case: Path) -> list[str]:
    outputs = []
    if not (case / "events.jsonl").exists():
        return outputs
    for line in (case / "events.jsonl").read_text().splitlines():
        try:
            item = json.loads(line).get("item", {})
        except (ValueError, AttributeError):
            continue
        if item.get("type") == "command_execution" and item.get("exit_code") == 0:
            outputs.append(item.get("aggregated_output", ""))
    return outputs


def fact_checks(answers: dict, expected: dict) -> dict[str, bool]:
    result = {}
    for key, value in expected.items():
        actual = answers.get(key)
        if isinstance(value, list):
            result[key] = (
                isinstance(actual, list)
                and all(isinstance(v, str) for v in actual)
                and sorted(actual) == sorted(value)
            )
        else:
            result[key] = type(actual) is type(value) and actual == value
    return result


def navigation(brain: Path, artifacts: dict) -> bool:
    """Resolve relative Markdown links and root/unique-basename wiki links.

    This measures discoverability, not whether dependency prose is accurate.
    Ambiguous basename wikilinks receive no credit.
    """
    targets = [
        brain_path(brain, artifacts.get(k))
        for k in ("definition", "decision", "assumptions", "commitment", "work")
    ]
    if any(p is None for p in targets):
        return False
    links = set()
    for page in brain.rglob("*.md"):
        for markdown, wiki in re.findall(
            r"\[[^\]]*\]\(([^)]+)\)|\[\[([^]|]+)(?:\|[^]]*)?\]\]", page.read_text()
        ):
            value = markdown or wiki
            value = value.split("#", 1)[0]
            if not value or "://" in value:
                continue
            if wiki:
                target = Path(value)
                if not target.suffix:
                    target = target.with_suffix(".md")
                if len(target.parts) == 1:
                    matches = [p.resolve() for p in brain.rglob("*.md") if p.name == target.name]
                    if len(matches) == 1:
                        links.add(matches[0])
                else:
                    resolved = (brain / target).resolve()
                    if resolved.is_relative_to(brain.resolve()):
                        links.add(resolved)
            else:
                links.add((page.parent / value).resolve())
    return all(p in links for p in targets)


def grade_session(case: Path, phase: int, skill_sha: str, handoff: dict | None = None) -> dict:
    final = load_json(case / "final.json", {})
    if not isinstance(final, dict):
        final = {}
    answers = final.get("answers", {})
    if not isinstance(answers, dict):
        answers = {}
    evidence = final.get("evidence", {})
    artifacts = final.get("artifacts", {})
    if not isinstance(evidence, dict):
        evidence = {}
    if not isinstance(artifacts, dict):
        artifacts = {}
    records = INITIAL if phase == 1 else {**INITIAL, **UPDATE}
    outputs = command_outputs(case)
    brain = case / "work/brain"
    sources = {}
    for name, content in records.items():
        saved = brain_path(brain, evidence.get(name))
        sources[name] = {
            "observed_complete": complete_text_seen(content, outputs),
            "saved_unchanged": saved is not None and saved.read_bytes() == content.encode(),
        }
    artifacts_read = True
    history = True
    if phase == 2:
        old = handoff or {}
        prior = bytes.fromhex(old.get("decision_bytes_hex", ""))
        page = brain_path(brain, old.get("decision"))
        history = bool(prior) and page is not None and page.read_bytes().startswith(prior)
        # Credit actual recovery of the original decision, not a self-report.
        artifacts_read = (
            complete_text_seen(prior.decode(), outputs)
            and all(
                bool(text) and complete_text_seen(text, outputs)
                for text in old.get("artifacts", {}).values()
            )
            and len(old.get("artifacts", {})) == 4
        )
    checks = {
        "answers": all(fact_checks(answers, EXPECTED_1 if phase == 1 else EXPECTED_2).values()),
        "original_sources_read": all(s["observed_complete"] for s in sources.values()),
        "original_sources_preserved": all(s["saved_unchanged"] for s in sources.values()),
        "portable_navigation": navigation(brain, artifacts),
        "prior_reasoning_observed": artifacts_read,
        "decision_history_preserved": history,
        "skill_unchanged": tree_fingerprint(case / "work/skill") == skill_sha,
        "incoming_unchanged": all(
            (case / "work/incoming" / name).is_file()
            and (case / "work/incoming" / name).read_bytes() == text.encode()
            for name, text in (INITIAL if phase == 1 else UPDATE).items()
        ),
    }
    return {
        "phase": phase,
        "passed": all(checks.values()),
        "checks": checks,
        "facts": fact_checks(answers, EXPECTED_1 if phase == 1 else EXPECTED_2),
        "sources": sources,
        "elapsed_seconds": load_json(case / "runner.json", {}).get("elapsed_seconds"),
    }


def report(root: Path) -> dict:
    manifest = load_json(root / "manifest.json")
    rows = []
    for case in manifest["cases"]:
        directory = root / case["name"]
        phases = [grade_session(directory / "session-1", 1, case["skill_sha256"])]
        if (directory / "session-2/final.json").exists():
            phases.append(
                grade_session(
                    directory / "session-2",
                    2,
                    case["skill_sha256"],
                    load_json(directory / "handoff.json", {}),
                )
            )
        rows.append(
            {
                **case,
                "passed": len(phases) == 2 and all(p["passed"] for p in phases),
                "sessions": phases,
            }
        )
    return {
        "scenario": manifest["scenario"],
        "synthetic": True,
        "cases": rows,
        "recorded_evaluator_sha256": manifest.get("evaluator_sha256", {}),
        "evaluator_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "audit_note": manifest.get("audit_note"),
        "source_records_sha256": {
            "initial": manifest.get("initial_records_sha256", {}),
            "update": manifest.get("update_records_sha256", {}),
        },
        "limitations": [
            "Two repetitions per arm of one fictional scenario; no general winner can be inferred.",
            "Shared user task requests provenance and history; this tests execution, not spontaneous skill activation.",
            "Inherited chat model unknown; reasoning, tokens and cost unavailable.",
            "Observed full text is an exposure proxy, not proof of comprehension.",
            "Navigation checks link presence, not the meaning of dependency prose; manual review required.",
            "Sources are supplied fictional records, not authenticated company records.",
            "Both arms use ordinary Markdown file tools; this does not evaluate the Portable KB CLI.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    first = actions.add_parser("prepare")
    first.add_argument("--root", type=Path, required=True)
    first.add_argument("--groundray", type=Path, required=True)
    first.add_argument("--wiki-skill", type=Path, required=True)
    first.add_argument("--repetitions", type=int, default=2)
    second = actions.add_parser("stage-second")
    second.add_argument("--root", type=Path, required=True)
    second.add_argument("--case", required=True)
    grade = actions.add_parser("report")
    grade.add_argument("--root", type=Path, required=True)
    grade.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(
            args.root.resolve(),
            args.groundray.resolve(),
            args.wiki_skill.resolve(),
            args.repetitions,
        )
    elif args.action == "stage-second":
        stage_second(args.root.resolve(), args.case)
    else:
        write_json(args.output, report(args.root.resolve()))


if __name__ == "__main__":
    main()
