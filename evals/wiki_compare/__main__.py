from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.agent_cli.harness import run

from . import agentic
from .harness import compare, grade, prepare


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare wiki + skill and actual Portable KB on matched private content."
    )
    commands = parser.add_subparsers(dest="action", required=True)
    preparation = commands.add_parser("prepare")
    for option in ("output", "wiki", "wiki-skill", "suite", "cli"):
        preparation.add_argument(f"--{option}", type=Path, required=True)
    preparation.add_argument("--arm", choices=["wiki", "portable-kb"], required=True)
    preparation.add_argument("--source", type=Path)
    preparation.add_argument("--slug", default="wiki-replica")
    preparation.add_argument("--repetitions", type=int, default=2)
    execution = commands.add_parser("run")
    execution.add_argument("--output", type=Path, required=True)
    execution.add_argument("--runner", default="codex")
    execution.add_argument("--timeout", type=int, default=600)
    execution.add_argument("--jobs", type=int, default=1)
    grading = commands.add_parser("grade")
    grading.add_argument("--output", type=Path, required=True)
    grading.add_argument(
        "--aliases",
        type=Path,
        help="Reviewed additive reference-label aliases, recorded in the report.",
    )
    comparison = commands.add_parser("compare")
    comparison.add_argument("wiki", type=Path)
    comparison.add_argument("portable", type=Path)
    comparison.add_argument("--output", type=Path, required=True)
    workflow_prepare = commands.add_parser(
        "prepare-agentic", help="Seed matched fictional workplace workflows."
    )
    for option in ("output", "wiki-skill", "cli"):
        workflow_prepare.add_argument(f"--{option}", type=Path, required=True)
    workflow_prepare.add_argument("--repetitions", type=int, default=2)
    workflow_prepare.add_argument("--scenario", action="append", dest="scenarios")
    workflow_grade = commands.add_parser("grade-agentic")
    workflow_grade.add_argument("--output", type=Path, required=True)
    workflow_run = commands.add_parser("run-agentic")
    workflow_run.add_argument("--output", type=Path, required=True)
    workflow_run.add_argument("--runner", default="codex")
    workflow_run.add_argument("--timeout", type=int, default=600)
    workflow_run.add_argument("--jobs", type=int, default=1)
    workflow_compare = commands.add_parser("compare-agentic")
    workflow_compare.add_argument("wiki", type=Path)
    workflow_compare.add_argument("portable", type=Path)
    workflow_compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "prepare-agentic":
            result = agentic.prepare(
                args.output, args.cli, args.wiki_skill, args.repetitions, args.scenarios
            )
            print(json.dumps(result))
        elif args.action in {"run-agentic", "grade-agentic"}:
            if args.action == "run-agentic":
                run(args.output.resolve(), runner=args.runner, timeout=args.timeout, jobs=args.jobs)
            result = agentic.grade(args.output.resolve())
            print(json.dumps(result["totals"]))
            return 0 if all(c["status"] == "pass" for c in result["cases"]) else 1
        elif args.action == "compare-agentic":
            result = agentic.compare(
                json.loads(args.wiki.read_text()),
                json.loads(args.portable.read_text()),
                args.output,
            )
            print(json.dumps({"wiki": result["wiki"], "portable-kb": result["portable-kb"]}))
        elif args.action == "prepare":
            result = prepare(
                args.output,
                arm=args.arm,
                wiki=args.wiki,
                wiki_skill=args.wiki_skill,
                suite_file=args.suite,
                cli=args.cli,
                source=args.source,
                slug=args.slug,
                repetitions=args.repetitions,
            )
            print(json.dumps({"arm": result["arm"], "scenarios": result["scenarios"]}))
        elif args.action == "run":
            run(args.output.resolve(), runner=args.runner, timeout=args.timeout, jobs=args.jobs)
            result = grade(args.output.resolve())
            print(json.dumps(result["totals"]))
            return 0 if all(c["status"] == "pass" for c in result["cases"]) else 1
        elif args.action == "grade":
            result = grade(args.output.resolve(), aliases=args.aliases)
            print(json.dumps(result["totals"]))
            return 0 if all(c["status"] == "pass" for c in result["cases"]) else 1
        else:
            result = compare(
                json.loads(args.wiki.read_text()),
                json.loads(args.portable.read_text()),
                args.output,
            )
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"Benchmark failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
