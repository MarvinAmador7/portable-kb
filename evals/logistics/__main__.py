"""Generate and evaluate a matched fictional logistics knowledge baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.agent_cli.harness import run
from evals.wiki_compare.harness import load_json

from .harness import compare, generate, grade, prepare


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    generation = commands.add_parser("generate")
    generation.add_argument("--output", type=Path, required=True)
    generation.add_argument("--seed", type=int, default=20261008)
    preparation = commands.add_parser("prepare")
    for option in ("output", "corpus", "cli", "wiki-skill"):
        preparation.add_argument("--" + option, type=Path, required=True)
    preparation.add_argument("--repetitions", type=int, default=1)
    preparation.add_argument("--scenario", action="append", dest="scenarios")
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
    args = parser.parse_args()
    try:
        if args.action == "generate":
            result = generate(args.output, args.seed)
        elif args.action == "prepare":
            result = prepare(
                args.output,
                args.corpus,
                args.cli,
                args.wiki_skill,
                repetitions=args.repetitions,
                scenarios=args.scenarios,
            )
        elif args.action == "run":
            run(args.output, runner=args.runner, timeout=args.timeout, jobs=args.jobs)
            return 0
        elif args.action == "grade":
            result = grade(args.output)["totals"]
        else:
            result = compare(load_json(args.wiki), load_json(args.portable), args.output)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
