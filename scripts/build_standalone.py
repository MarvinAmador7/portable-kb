"""Build and smoke-test one standalone Portable KB release archive."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from portable_kb import __version__


def run(*arguments: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run one required build command with captured text output."""

    return subprocess.run(arguments, check=True, capture_output=True, text=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        required=True,
        choices=("darwin-arm64", "darwin-x86_64", "linux-arm64", "linux-x86_64"),
    )
    parser.add_argument("--output", type=Path, default=Path("release"))
    arguments = parser.parse_args()

    operating_system = {"Darwin": "darwin", "Linux": "linux"}.get(platform.system())
    architecture = {
        "x86_64": "x86_64",
        "AMD64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(platform.machine())
    actual_target = f"{operating_system}-{architecture}"
    if arguments.target != actual_target:
        raise RuntimeError(
            f"Refusing to label a {actual_target} executable as {arguments.target}"
        )

    repository = Path.cwd()
    native = repository / "target/release/pkb-search"
    if not native.is_file() or native.is_symlink():
        raise RuntimeError("Build the native pkb-search sidecar before packaging pkb")
    build_root = repository / "build" / "standalone" / arguments.target
    distribution = build_root / "dist"
    specification = build_root / "spec"
    shutil.rmtree(build_root, ignore_errors=True)
    arguments.output.mkdir(parents=True, exist_ok=True)

    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--name",
        "pkb",
        "--distpath",
        str(distribution),
        "--workpath",
        str(build_root / "work"),
        "--specpath",
        str(specification),
        "--add-binary",
        f"{native}{os.pathsep}.",
        "--collect-data",
        "portable_kb",
        "--copy-metadata",
        "portable-kb-core",
        str(repository / "scripts/frozen_entrypoint.py"),
    )
    executable = distribution / "pkb"
    version_result = run(str(executable), "--version")
    if version_result.stdout.strip() != f"pkb {__version__}":
        raise RuntimeError(f"Unexpected standalone version: {version_result.stdout.strip()}")

    with tempfile.TemporaryDirectory(prefix="portable-kb-frozen-home-") as temporary_home:
        environment = {**os.environ, "HOME": temporary_home}
        temporary = Path(temporary_home)
        config = temporary / "config.yaml"
        setup_result = run(
            str(executable),
            "setup",
            "--non-interactive",
            "--search-mode",
            "keyword",
            "--config",
            str(config),
            "--data-dir",
            str(temporary / "data"),
            "--cache-dir",
            str(temporary / "cache"),
            env=environment,
        )
        if "Portable KB configured" not in setup_result.stdout:
            raise RuntimeError("Standalone executable could not complete local setup")
        brain_result = run(
            str(executable),
            "brain",
            "init",
            str(temporary / "brain"),
            "--name",
            "Frozen Smoke Brain",
            "--slug",
            "frozen-smoke",
            "--no-publish",
            "--config",
            str(config),
            "--as-of",
            "2026-08-13",
            "--json",
            env=environment,
        )
        brain_payload = json.loads(brain_result.stdout)
        if brain_payload.get("active") is not True:
            raise RuntimeError("Standalone executable could not initialize a valid local brain")
        index_result = run(
            str(executable), "search", "index", "--config", str(config),
            "--as-of", "2026-08-13", "--json", env=environment,
        )
        if json.loads(index_result.stdout).get("provider") != "builtin":
            raise RuntimeError("Standalone executable omitted its Tantivy provider")
        query_result = run(
            str(executable), "search", "query", "standalone smoke", "--config", str(config),
            "--as-of", "2026-08-13", "--json", env=environment,
        )
        if json.loads(query_result.stdout).get("provider") != "builtin":
            raise RuntimeError("Standalone executable cannot query its Tantivy index")
        skill_result = run(
            str(executable),
            "skill",
            "install",
            "--target",
            "codex",
            "--json",
            env=environment,
        )
        payload = json.loads(skill_result.stdout)
        if payload.get("ok") is not True:
            raise RuntimeError("Standalone executable could not install its bundled agent skill")
        skill = Path(temporary_home) / ".agents/skills/portable-kb/SKILL.md"
        if not skill.is_file():
            raise RuntimeError("Standalone executable omitted the bundled agent skill")

    archive = arguments.output / f"pkb-v{__version__}-{arguments.target}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(executable, arcname="pkb")
    print(archive)


if __name__ == "__main__":
    main()
