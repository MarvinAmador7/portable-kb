"""Recorded-shell adapter for an explicitly delegated foreground chat-agent trial."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .harness import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    execute = commands.add_parser("exec")
    execute.add_argument("--command", required=True)
    execute.add_argument("--timeout", type=int, default=300)
    finish = commands.add_parser("finish")
    finish.add_argument("--final-file", type=Path, required=True)
    args = parser.parse_args()
    case = args.case.resolve()
    configuration = json.loads((case / "bin/shim.json").read_text())
    start = case / "chat-start.json"
    if not start.exists():
        write_json(start, {"started_ns": time.time_ns()})
    if args.action == "finish":
        final = json.loads(args.final_file.read_text())
        write_json(case / "final.json", final)
        write_json(
            case / "runner.json",
            {
                "runner": "codex-chat-subagent",
                "adapter": "recorded-shell-observer",
                "exit_code": 0,
                "timed_out": False,
                "elapsed_seconds": (time.time_ns() - json.loads(start.read_text())["started_ns"])
                / 1e9,
                "model": "inherited/unknown",
                "provider": "chat-host",
                "notes": "Actual delegated agent with recorded shell actions; reasoning and token/cost telemetry unavailable.",
            },
        )
        print("Final response recorded.")
        return 0
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    environment = os.environ.copy()
    environment.update(configuration["product_environment"])
    environment["PATH"] = str(case / "bin") + os.pathsep + environment.get("PATH", "")
    environment["PKB_EVAL_ACTOR"] = "agent"
    process = subprocess.Popen(
        ["/bin/bash", "--noprofile", "--norc", "-c", args.command],
        cwd=case / "work",
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    code = 124 if timed_out else process.returncode
    event = {
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "command": args.command,
            "exit_code": code,
            "aggregated_output": stdout + stderr,
        },
    }
    with (case / "events.jsonl").open("a") as destination:
        destination.write(json.dumps(event) + "\n")
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
