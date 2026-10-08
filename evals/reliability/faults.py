"""Deterministic real-process faults, scoped only to fresh synthetic cases."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from evals.agent_cli.harness import command, digest, product_environment, write_json
from evals.logistics.harness import git
from evals.logistics.oracle import CORRECTION, MOVE_FROM, MOVE_TO
from evals.logistics.world import AS_OF, SLUG
from evals.wiki_compare.harness import load_json
from portable_kb.parsing import parse_concept
from portable_kb.serialization import quoted, render_concept

from .scenarios import COMPETING, CONTACT


def compile_stop_library(output: Path) -> Path:
    if sys.platform != "linux" or not shutil.which("cc"):
        raise ValueError("Actual rename-boundary process faults require Linux and cc")
    output.mkdir(parents=True, exist_ok=True)
    library = output / "stop-rename.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-Wall",
            "-Werror",
            "-o",
            str(library),
            str(Path(__file__).with_name("stop_rename.c")),
            "-ldl",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return library


def external_update(case: Path, *, contact=False) -> dict:
    """Save the collaborator's revision through the actual native CLI or wiki files."""
    config = load_json(case / "case.json")
    root = case / ("work/source/knowledge" if config["arm"] == "portable-kb" else "work/wiki")
    path = root / ("inbox/" + CORRECTION if config["arm"] == "portable-kb" else CORRECTION)
    parsed = parse_concept(path, root).item
    body = parsed.body
    if contact:
        body = body.replace(
            "## Context\n", f"## Context\n\nCollaborator contact window: {CONTACT} local time.\n"
        )
        source_name = COMPETING
    else:
        old = "Merchant lumen belongs to us-east. Recorded contract retention is 7 days; apply the regional cap before reporting effective retention.[^fixture]"
        new = "Merchant lumen belongs to us-east. Current recorded contract export retention is 21 days; apply the regional cap before reporting effective retention.[^revision]"
        if body.count(old) != 1:
            raise ValueError("Expected original Lumen baseline")
        body = body.replace(old, new).replace(
            "## Context\n",
            "## Retention history\n\nPrevious recorded contract retention was 7 days, retained as historical evidence.[^fixture]\n\n## Context\n",
        )
        body += "\n[^revision]: Fictional collaborator revision; no real human review.\n"
        source_name = "revision-source.md"
    if config["arm"] == "portable-kb":
        fault = case / "fault"
        fault.mkdir(exist_ok=True)
        body_file, metadata_file = fault / "external-body.md", fault / "external-metadata.json"
        body_file.write_text(body)
        metadata = {
            "sources": list(parsed.metadata["sources"])
            + [
                {
                    "id": "collaborator" if contact else "revision",
                    "resource": (case / "work/evidence" / source_name).as_uri(),
                    "title": "Fictional collaborator revision",
                }
            ]
        }
        write_json(metadata_file, metadata)
        args = (
            "knowledge",
            "update",
            parsed.id,
            "--brain",
            SLUG,
            "--actor",
            "eval-collaborator/1",
            "--method",
            "agent-generated",
            "--body-file",
            str(body_file),
            "--metadata-file",
            str(metadata_file),
            "--as-of",
            AS_OF,
            "--json",
        )
        command(case, *args, actor="fault-controller")
        result = command(case, *args, "--apply", actor="fault-controller")
        command(case, "search", "index", SLUG, "--as-of", AS_OF, "--json", actor="fault-controller")
        return {
            "commit": result["saved_version"],
            "sha256": digest(path),
            "content": path.read_text(),
        }
    metadata = dict(parsed.metadata)
    metadata["updated"] = quoted(AS_OF)
    metadata["sources"] = list(metadata["sources"]) + [
        (case / "work/evidence" / source_name).as_uri()
    ]
    temporary = path.with_suffix(".pending")
    temporary.write_text(render_concept(metadata, body))
    os.replace(temporary, path)
    with (root / "log.md").open("a") as log:
        log.write(f"\n- 2026-10-08 — Fictional collaborator updated {CORRECTION}.\n")
    git(case, root, "add", CORRECTION, "log.md")
    git(case, root, "commit", "--quiet", "-m", "Save fictional collaborator revision")
    return {"sha256": digest(path), "content": path.read_text()}


def checkpoint(case: Path) -> dict:
    config = load_json(case / "case.json")
    if config["task"] != "concurrent-update" or (case / "fault/checkpoint.json").exists():
        raise ValueError("Checkpoint is allowed exactly once for the concurrent-update case")
    root = case / ("work/source/knowledge" if config["arm"] == "portable-kb" else "work/wiki")
    page = root / ("inbox/" + CORRECTION if config["arm"] == "portable-kb" else CORRECTION)
    before_sha = digest(page)
    start = time.time_ns()
    result = external_update(case, contact=True)
    write_json(
        case / "fault/checkpoint.json",
        {
            "started_ns": start,
            "completed_ns": time.time_ns(),
            "before_sha256": before_sha,
            **result,
        },
    )
    return {
        "checkpoint": "complete",
        "notice": "The concurrent writer has saved a new account revision. Inspect the current snapshot before applying your amendment.",
    }


def interrupt_move(case: Path, library: Path) -> dict:
    config = load_json(case / "case.json")
    native = config["arm"] == "portable-kb"
    root = case / ("work/source/knowledge" if native else "work/wiki")
    prefix = "inbox/" if native else ""
    destination = root / (prefix + MOVE_TO)
    marker = case / "fault/paused-pid.txt"
    marker.parent.mkdir(exist_ok=True)
    env = {
        **os.environ,
        **product_environment(case),
        "PKB_EVAL_ACTOR": "fault-controller",
        "LD_PRELOAD": str(library),
        "KB_EVAL_STOP_DEST": str(destination),
        "KB_EVAL_STOP_MARKER": str(marker),
    }
    if native:
        args = [
            "knowledge",
            "move",
            prefix + MOVE_FROM,
            prefix + MOVE_TO,
            "--brain",
            SLUG,
            "--as-of",
            AS_OF,
            "--json",
        ]
        command(case, *args, actor="fault-controller")
        argv = [str(case / "bin/pkb"), *args, "--apply"]
    else:
        argv = [
            sys.executable,
            "-c",
            "import os,sys;os.replace(sys.argv[1],sys.argv[2])",
            str(root / MOVE_FROM),
            str(destination),
        ]
    process = subprocess.Popen(
        argv,
        cwd=case / "work",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + 60
    killed = False
    try:
        while time.monotonic() < deadline:
            if marker.exists():
                paused = int(marker.read_text())
                os.killpg(os.getpgid(paused), signal.SIGKILL)
                killed = True
                break
            if process.poll() is not None:
                break
            time.sleep(0.01)
        if not killed:
            raise ValueError("Actual process did not reach the injected rename boundary")
        stdout, stderr = process.communicate(timeout=10)
        result = {
            "kind": "SIGKILL-after-destination-rename",
            "destination_exists": destination.is_file(),
            "source_exists": (root / (prefix + MOVE_FROM)).is_file(),
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "library_sha256": digest(library),
        }
        if not destination.is_file() or process.returncode == 0:
            raise ValueError("Fault did not produce the required partial saved state")
        write_json(case / "fault/interruption.json", result)
        return result
    finally:
        if process.poll() is None:
            # The shim owns its CLI group and forwards TERM as group KILL.
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("action", choices=["checkpoint"])
    args = parser.parse_args()
    try:
        print(json.dumps(checkpoint(args.case.resolve())))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
