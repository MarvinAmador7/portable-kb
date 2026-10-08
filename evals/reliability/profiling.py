"""Measure the frozen executable and profile equivalent unmodified core reads."""

from __future__ import annotations

import cProfile
import pstats
import statistics
import time
from pathlib import Path

from evals.agent_cli.harness import command, digest, repository_snapshot, write_json
from evals.logistics.harness import fingerprint
from evals.logistics.oracle import CORRECTION
from evals.logistics.world import AS_OF, SLUG
from evals.wiki_compare.harness import load_json
from portable_kb.brains import brain_status
from portable_kb.search import get_knowledge
from portable_kb.settings import load_settings


def profile_summary(profile: cProfile.Profile) -> dict:
    stats = pstats.Stats(profile)
    categories = dict.fromkeys(
        ("yaml", "jsonschema", "portable_kb", "subprocess", "pathlib", "other"), 0.0
    )
    rows = []
    for (file, line, name), (
        primitive,
        calls,
        exclusive,
        cumulative,
        _callers,
    ) in stats.stats.items():
        category = (
            "yaml"
            if "ruamel/yaml" in file
            else "jsonschema"
            if "jsonschema" in file or "referencing" in file
            else "portable_kb"
            if "portable_kb/" in file
            else "subprocess"
            if "subprocess.py" in file
            else "pathlib"
            if "pathlib.py" in file
            else "other"
        )
        categories[category] += exclusive
        rows.append(
            {
                "function": (
                    "portable_kb/" + file.split("portable_kb/", 1)[1]
                    if "portable_kb/" in file
                    else Path(file).name
                )
                + f":{line}:{name}",
                "primitive_calls": primitive,
                "calls": calls,
                "exclusive_seconds": exclusive,
                "cumulative_seconds": cumulative,
            }
        )
    total = sum(categories.values())
    return {
        "exclusive_seconds": total,
        "exclusive_categories": categories,
        "exclusive_category_fraction": {
            k: v / total if total else 0 for k, v in categories.items()
        },
        "top_cumulative": sorted(rows, key=lambda r: r["cumulative_seconds"], reverse=True)[:20],
        "parse_calls": sum(r["calls"] for r in rows if r["function"].endswith(":parse_concept")),
        "note": "Exclusive categories do not overlap. Cumulative rows include callees and must not be added together. Profiling overhead is excluded from normal-operation medians.",
    }


def measure(case: Path, output: Path, *, samples=3) -> dict:
    if output.exists() or not 1 <= samples <= 10:
        raise ValueError("Use fresh profile output and 1–10 samples")
    output.mkdir(parents=True)
    settings = load_settings(case / "home/.config/portable-kb/config.yaml")
    path = "inbox/" + CORRECTION
    actual = command(
        case, "get", path, "--brain", SLUG, "--as-of", AS_OF, "--json", actor="profiler"
    )
    identity = actual["item"]["id"]
    source, checkout = case / "work/source", settings.data_dir / "brains" / SLUG
    before = {"source": repository_snapshot(source), "checkout": repository_snapshot(checkout)}
    commands = {
        "help": ("--help",),
        "brain_status": ("brain", "status", SLUG, "--as-of", AS_OF, "--json"),
        "get_path": ("get", path, "--brain", SLUG, "--as-of", AS_OF, "--json"),
        "get_uuid": ("get", identity, "--brain", SLUG, "--as-of", AS_OF, "--json"),
        "get_index": ("get", "index.md", "--brain", SLUG, "--as-of", AS_OF, "--json"),
        "keyword_query": (
            "search",
            "query",
            "Lumen retention",
            "--brain",
            SLUG,
            "--as-of",
            AS_OF,
            "--json",
        ),
    }
    cli = {}
    for name, args in commands.items():
        elapsed = []
        for _ in range(samples):
            start = time.perf_counter()
            payload = command(case, *args, actor="profiler")
            elapsed.append((time.perf_counter() - start) * 1000)
            if name in {"get_path", "get_uuid"} and payload != actual:
                raise ValueError("Frozen executable read changed during profiling")
        cli[name] = {
            "samples_ms": elapsed,
            "median_ms": statistics.median(elapsed),
            "scope": "Fresh standalone CLI process plus recorded shim and JSON handling.",
        }
    core = {}
    operations = {
        "brain_status": lambda: brain_status(settings, SLUG, as_of=AS_OF),
        "get_path": lambda: get_knowledge(settings, path, SLUG, as_of=AS_OF),
        "get_uuid": lambda: get_knowledge(settings, identity, SLUG, as_of=AS_OF),
        "get_index": lambda: get_knowledge(settings, "index.md", SLUG, as_of=AS_OF),
    }
    for name, operation in operations.items():
        elapsed = []
        for _ in range(samples):
            start = time.perf_counter()
            value = operation()
            elapsed.append((time.perf_counter() - start) * 1000)
            if name in {"get_path", "get_uuid"} and value != actual:
                raise ValueError("Instrumented core differs from actual standalone complete read")
        profile = cProfile.Profile()
        profile.runcall(operation)
        profile.dump_stats(str(output / (name + ".prof")))
        core[name] = {
            "samples_ms": elapsed,
            "median_ms": statistics.median(elapsed),
            "profile": profile_summary(profile),
        }
    after = {"source": repository_snapshot(source), "checkout": repository_snapshot(checkout)}
    if before != after:
        raise ValueError("Profiling modified canonical content")
    package = Path(__file__).parents[2] / "src/portable_kb"
    result = {
        "samples": samples,
        "documents": 220,
        "cli_sha256": load_json(case / "bin/shim.json")["cli"],
        "canonical_sha256": fingerprint(before),
        "canonical_unchanged": True,
        "core_source_sha256": fingerprint(
            {str(p.relative_to(package)): digest(p) for p in package.rglob("*.py")}
        ),
        "standalone": cli,
        "core": core,
        "limitations": [
            "One 220-document world on the current Linux host; profiles explain this workload only.",
            "Core profiles instrument source/library reads, not the frozen bootloader; path/UUID payload equality with the actual executable is checked.",
            "Standalone timings include validation, CLI startup and shim overhead; help is a contextual control, not a precise decomposition.",
        ],
    }
    result["cli_sha256"] = digest(Path(result["cli_sha256"]))
    write_json(output / "profile.json", result)
    return result
