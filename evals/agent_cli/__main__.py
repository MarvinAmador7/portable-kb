from __future__ import annotations

import argparse
import json
from pathlib import Path

from .harness import SCENARIOS, compare, grade, prepare, run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the actual installed Portable KB CLI + bundled skill with agents."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    preparation = subcommands.add_parser(
        "prepare", help="Create isolated synthetic scenarios, traced CLI and installed skill."
    )
    preparation.add_argument("--cli", type=Path, required=True)
    preparation.add_argument("--output", type=Path, required=True)
    preparation.add_argument("--scenario", action="append", choices=SCENARIOS)
    preparation.add_argument("--command-timeout", type=int, default=300)
    execution = subcommands.add_parser(
        "run", help="Run the configured Codex agent against each prepared scenario."
    )
    execution.add_argument("--output", type=Path, required=True)
    execution.add_argument("--runner", default="codex", help="Codex-compatible executable path.")
    execution.add_argument("--timeout", type=int, default=600)
    execution.add_argument(
        "--jobs", type=int, default=1, help="Concurrent independent scenarios (1–4)."
    )
    execution.add_argument("--ignore-user-config", action="store_true")
    grading = subcommands.add_parser(
        "grade", help="Grade observed traces, final answers and independent canonical reads."
    )
    grading.add_argument("--output", type=Path, required=True)
    comparison = subcommands.add_parser(
        "compare", help="Compare reports by stable scenario/check IDs."
    )
    comparison.add_argument("baseline", type=Path)
    comparison.add_argument("candidate", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.command == "prepare":
            result = prepare(
                arguments.output,
                arguments.cli,
                arguments.scenario or list(SCENARIOS),
                arguments.command_timeout,
            )
            print(
                json.dumps(
                    {
                        "prepared": str(arguments.output.resolve()),
                        "cli_version": result["cli_version"],
                        "scenarios": result["scenarios"],
                    },
                    indent=2,
                )
            )
        elif arguments.command == "run":
            if arguments.timeout <= 0:
                raise ValueError("--timeout must be positive.")
            run(
                arguments.output.resolve(),
                arguments.runner,
                arguments.timeout,
                arguments.ignore_user_config,
                arguments.jobs,
            )
            result = grade(arguments.output.resolve())
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "report": str(arguments.output.resolve() / "report.html"),
                    },
                    indent=2,
                )
            )
            return 0 if result["status"] == "pass" else 1
        elif arguments.command == "grade":
            result = grade(arguments.output.resolve())
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "pass" else 1
        elif arguments.command == "compare":
            print(
                json.dumps(
                    compare(
                        json.loads(arguments.baseline.read_text()),
                        json.loads(arguments.candidate.read_text()),
                    ),
                    indent=2,
                )
            )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"Evaluation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
