"""Fresh matched reliability cases built on the frozen Atlas world."""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path

from evals.agent_cli.harness import command, digest, repository_snapshot, write_json
from evals.logistics import harness as atlas
from evals.logistics.oracle import CORRECTION, MOVE_FROM, MOVE_TO
from evals.logistics.world import SLUG
from evals.wiki_compare.harness import load_json

from .faults import compile_stop_library, external_update, interrupt_move
from .scenarios import EVIDENCE, scenarios

VERSION = 1


def observe(case: Path, *, initial=False) -> dict:
    state = atlas.observe(case, initial=initial)
    if load_json(case / "case.json")["arm"] == "wiki":
        state["snapshots"] = {
            "primary": {
                p: sha
                for p, sha in repository_snapshot(case / "work/wiki").items()
                if p != "@git_head"
            }
        }
    write_json(case / ("initial-state.json" if initial else "observed-state.json"), state)
    return state


def prepare(
    output: Path, corpus: Path, cli: Path, wiki_skill: Path, *, repetitions=2, selected=None
) -> dict:
    output, corpus, cli, wiki_skill = (p.resolve() for p in (output, corpus, cli, wiki_skill))
    if output.exists() or output.is_relative_to(corpus) or corpus.is_relative_to(output):
        raise ValueError("Use a fresh output separate from the frozen corpus")
    if not 1 <= repetitions <= 10:
        raise ValueError("Use 1–10 repetitions")
    output.mkdir(parents=True)
    library = compile_stop_library(output / "fault-tools")
    matched = output / "corpus"
    shutil.copytree(corpus, matched)
    manifest = load_json(matched / "manifest.json")
    taskset = scenarios()
    selected = list(taskset) if selected is None else selected
    if (
        not selected
        or len(set(selected)) != len(selected)
        or any(s not in taskset for s in selected)
    ):
        raise ValueError("Select unique known tasks")
    write_json(matched / "oracle.json", {"version": VERSION, "tasks": taskset})
    identities = load_json(matched / "identities.json")
    labels = {
        "schema_version": 1,
        "name": "Atlas recovery initial discovery",
        "queries": [
            {
                "id": name,
                "query": task["query"],
                "relevance": {
                    identities[MOVE_FROM if p == MOVE_TO else p]: 3
                    for label in task["claims"].values()
                    for p in label["evidence"]
                },
            }
            for name, task in taskset.items()
        ],
    }
    write_json(matched / "retrieval-labels.json", labels)
    manifest.update(
        oracle_sha256=digest(matched / "oracle.json"),
        labels_sha256=digest(matched / "retrieval-labels.json"),
        parent_manifest_sha256=digest(corpus / "manifest.json"),
    )
    write_json(matched / "manifest.json", manifest)
    trials = output / "trials"
    result = atlas.prepare(
        trials, matched, cli, wiki_skill, repetitions=repetitions, scenarios=selected
    )
    repo = Path(__file__).resolve().parents[2]
    for arm in ("wiki", "portable-kb"):
        arm_root = trials / arm
        arm_manifest = load_json(arm_root / "manifest.json")
        arm_manifest.update(
            kind="reliability",
            reliability_version=VERSION,
            fault_library_sha256=digest(library),
            parent_manifest_sha256=manifest["parent_manifest_sha256"],
        )
        write_json(arm_root / "manifest.json", arm_manifest)
        for name in arm_manifest["scenarios"]:
            case = arm_root / name
            config = load_json(case / "case.json")
            task = taskset[config["task"]]
            for source in task["incoming"]:
                if source in EVIDENCE:
                    (case / "work/evidence" / source).write_text(EVIDENCE[source])
            if config["task"] in {"stale-citation", "rollback-amendment"}:
                (case / "work/evidence/revision-source.md").write_text(
                    "# Fictional revision\n\nLumen recorded retention was revised from 7 to 21 days by another draft writer. This record preserves the revision; no human verification is claimed.\n"
                )
                if config["task"] == "stale-citation":
                    cache = (
                        command(
                            case,
                            "get",
                            "inbox/" + CORRECTION,
                            "--brain",
                            SLUG,
                            "--json",
                            actor="fault-controller",
                        )
                        if arm == "portable-kb"
                        else {
                            "page": atlas.wiki_pages(case / "work/wiki")[CORRECTION],
                            "citation": {"path": CORRECTION, "scope": "primary"},
                        }
                    )
                    write_json(case / "work/evidence/cached-answer.json", cache)
            if arm == "wiki":
                wiki = case / "work/wiki"
                # Use the same ordinary local Git backup capability as the native authoring source.
                atlas.git(case, wiki, "init", "--quiet")
                atlas.git(case, wiki, "add", ".")
                atlas.git(case, wiki, "commit", "--quiet", "-m", "Frozen fictional Atlas backup")
                source = wiki
            else:
                source = case / "work/source"
            atlas.git(case, source, "tag", "kb-eval-baseline")
            checkpoint = case / "bin/kb-fault"
            checkpoint.write_text(
                "#!/bin/sh\ncd "
                + shlex.quote(str(repo))
                + "\nexec "
                + shlex.quote(sys.executable)
                + " -m evals.reliability.faults --case "
                + shlex.quote(str(case))
                + ' "$@"\n'
            )
            checkpoint.chmod(0o755)
            prompt = (case / "prompt.txt").read_text()
            prompt += (
                "\n\nReliability experiment: `kb-fault checkpoint` is authorized only for concurrent-update when explicitly requested, and no other development controller action is authorized; do not read its implementation or private fault records. Incoming evidence/ contains "
                + ", ".join(task["incoming"])
                + ". Preserve all incoming evidence, including revision-source.md if present. This experiment permits ordinary Git backups for both arms; only the interrupted-move request authorizes native raw Git restoration, limited to work/source authoring files. Never edit the native managed checkout. A failure must be reported honestly; preserve recoverable data and use outcome blocked if the supported procedure cannot complete.\n"
            )
            if config["task"] == "interrupted-move":
                prompt = prompt.replace(
                    "Never read/write raw managed files, use raw Git or product Python APIs.",
                    "Never edit the managed consumer checkout or use product Python APIs. This recovery request authorizes Git inspection and targeted restoration of the authoring source, followed by a fresh supported CLI move plan/apply.",
                )
                prompt += (
                    "Authoring recovery path: "
                    + str(source)
                    + ". Trusted pre-fault backup tag: kb-eval-baseline.\n"
                )
            (case / "prompt.txt").write_text(prompt)
            config["prompt_sha256"] = digest(case / "prompt.txt")
            write_json(case / "case.json", config)
            if config["task"] in {"stale-citation", "rollback-amendment"}:
                external_update(case)
            observe(case, initial=True)
            if config["task"] == "interrupted-move":
                interrupt_move(case, library)
                # Preserve the healthy pre-fault baseline; the partial state is separate evidence.
                fault_state = observe(case)
                write_json(case / "fault/partial-state.json", fault_state)
    return {
        **result,
        "repetitions": repetitions,
        "output": str(output),
        "fault_library_sha256": digest(library),
    }


def grade(root: Path) -> dict:
    from .grading import grade_case, totals

    manifest = load_json(root / "manifest.json")
    oracle = load_json(root.parent / "oracle.json")
    if (
        manifest.get("kind") != "reliability"
        or digest(root.parent / "oracle.json") != manifest["oracle_sha256"]
        or digest(Path(manifest["cli"])) != manifest["cli_sha256"]
    ):
        raise ValueError("Prepared reliability inputs changed")
    cases = [
        grade_case(
            root / name,
            oracle["tasks"][load_json(root / name / "case.json")["task"]],
            observe(root / name),
        )
        for name in manifest["scenarios"]
    ]
    rules = [
        "reliability/grading.py",
        "reliability/harness.py",
        "reliability/faults.py",
        "reliability/stop_rename.c",
        "logistics/grading.py",
        "logistics/harness.py",
        "wiki_compare/harness.py",
        "wiki_compare/workflow_grading.py",
        "wiki_compare/agentic.py",
        "agent_cli/grading.py",
    ]
    result = {
        "manifest": manifest,
        "cases": cases,
        "totals": totals(cases),
        "grader_sha256": atlas.fingerprint(
            {p: digest(Path(__file__).parents[1] / p) for p in rules}
        ),
    }
    write_json(root / "report.json", result)
    return result


def compare(wiki: dict, native: dict, output: Path) -> dict:
    if any(
        wiki["manifest"].get(k) != native["manifest"].get(k)
        for k in ("kind", "reliability_version", "fault_library_sha256", "parent_manifest_sha256")
    ):
        raise ValueError("Unmatched recovery protocol/fault inputs")
    return atlas.compare(wiki, native, output)
