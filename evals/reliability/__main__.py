"""Run matched reliability challenges using the actual CLI and wiki skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.agent_cli.harness import run
from evals.wiki_compare.harness import load_json

from .harness import compare, grade, prepare
from .profiling import measure


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    preparation = commands.add_parser("prepare")
    for option in ("output", "corpus", "cli", "wiki-skill"):
        preparation.add_argument("--" + option, type=Path, required=True)
    preparation.add_argument("--repetitions", type=int, default=2)
    preparation.add_argument("--scenario", action="append")
    execution = commands.add_parser("run")
    execution.add_argument("--output", type=Path, required=True)
    execution.add_argument("--runner", default="codex")
    execution.add_argument("--timeout", type=int, default=900)
    execution.add_argument("--jobs", type=int, default=1)
    grading = commands.add_parser("grade")
    grading.add_argument("--output", type=Path, required=True)
    comparison = commands.add_parser("compare")
    comparison.add_argument("wiki", type=Path)
    comparison.add_argument("portable", type=Path)
    comparison.add_argument("--output", type=Path, required=True)
    profiling = commands.add_parser("profile")
    profiling.add_argument("--case", type=Path, required=True)
    profiling.add_argument("--output", type=Path, required=True)
    profiling.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare(
                args.output,
                args.corpus,
                args.cli,
                args.wiki_skill,
                repetitions=args.repetitions,
                selected=args.scenario,
            )
        elif args.action == "run":
            run(args.output, runner=args.runner, timeout=args.timeout, jobs=args.jobs)
            return 0
        elif args.action == "grade":
            result = grade(args.output)["totals"]
        elif args.action == "profile":
            result = measure(args.case, args.output, samples=args.samples)
            result = {
                "canonical_unchanged": result["canonical_unchanged"],
                "standalone": result["standalone"],
            }
        else:
            result = compare(load_json(args.wiki), load_json(args.portable), args.output)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
