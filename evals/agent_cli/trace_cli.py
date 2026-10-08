"""Standalone shim copied to a run directory; never imports product internals."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from contextlib import suppress
from pathlib import Path


def _stop_group(process: subprocess.Popen, *, force: bool = False) -> None:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)


def main() -> int:
    configuration = json.loads(Path(__file__).with_name("shim.json").read_text())
    environment = os.environ.copy()
    environment.update(configuration["product_environment"])
    started = time.monotonic()
    started_ns = time.time_ns()
    started_utc = datetime.datetime.now(datetime.UTC).isoformat()
    input_files = {}
    for option in ("--body-file", "--sources-file", "--metadata-file"):
        if option in sys.argv:
            try:
                index = sys.argv.index(option)
                path = Path(sys.argv[index + 1])
                input_files[option] = {
                    "path": str(path.absolute()),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            except (IndexError, OSError):
                input_files[option] = {"error": "unreadable"}
    process = None
    previous_handler = signal.getsignal(signal.SIGTERM)

    def terminate(_signum, _frame) -> None:
        # Runner timeout kills its group; this independently owned CLI group must follow.
        if process is not None:
            _stop_group(process, force=True)

    signal.signal(signal.SIGTERM, terminate)
    try:
        process = subprocess.Popen(
            [configuration["cli"], *sys.argv[1:]],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=configuration["command_timeout"])
            code = process.returncode
        except subprocess.TimeoutExpired:
            _stop_group(process)
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                _stop_group(process, force=True)
                stdout, stderr = process.communicate()
            code = 124
            stderr += "\nCLI command exceeded the evaluation timeout.\n"
    except OSError as exc:
        code, stdout, stderr = 127, "", f"CLI launch failed: {exc}\n"
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
    trace = {
        "actor": os.environ.get("PKB_EVAL_ACTOR", "agent"),
        "time_utc": started_utc,
        "started_ns": started_ns,
        "completed_ns": time.time_ns(),
        "input_files": input_files,
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "exit_code": code,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "stdout": stdout,
        "stderr": stderr,
    }
    destination = Path(configuration["trace_directory"])
    destination.mkdir(parents=True, exist_ok=True)
    (destination / f"{started_ns}-{uuid.uuid4().hex}.json").write_text(
        json.dumps(trace, indent=2) + "\n"
    )
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
