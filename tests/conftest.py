from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
REFERENCE_BUNDLE = REPOSITORY / "tests" / "fixtures" / "reference-bundle"


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    target = tmp_path / "knowledge"
    shutil.copytree(REFERENCE_BUNDLE, target)
    return target


@pytest.fixture
def valid_examples(tmp_path: Path) -> Path:
    target = tmp_path / "valid"
    shutil.copytree(REPOSITORY / "examples" / "valid", target)
    return target


@pytest.fixture
def brain_repo_factory(tmp_path: Path) -> Callable[[str, str], Path]:
    """Create committed local brain repositories without network access."""

    def create(slug: str, identity: str) -> Path:
        repository = tmp_path / f"source-{slug}"
        repository.mkdir()
        shutil.copytree(REFERENCE_BUNDLE, repository / "knowledge")
        repository.joinpath("brain.yaml").write_text(
            "\n".join(
                (
                    "schema_version: 1",
                    f"id: {identity}",
                    f"slug: {slug}",
                    f"name: {slug.replace('-', ' ').title()}",
                    "bundle: knowledge",
                    "",
                )
            ),
            encoding="utf-8",
        )
        _git(repository, "init", "--quiet", "--initial-branch=main")
        _git(repository, "config", "user.name", "Portable KB Tests")
        _git(repository, "config", "user.email", "portable-kb-tests@example.invalid")
        _git(repository, "config", "commit.gpgsign", "false")
        _git(repository, "add", "brain.yaml", "knowledge")
        _git(repository, "commit", "--quiet", "-m", "Create test brain")
        return repository

    return create


@pytest.fixture
def fake_qmd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Provide a QMD-shaped executable without models or external state."""

    executable = tmp_path / "qmd"
    log = tmp_path / "qmd-calls.jsonl"
    results = tmp_path / "qmd-results.json"
    results.write_text("[]\n", encoding="utf-8")
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
config_dir = Path(os.environ["QMD_CONFIG_DIR"])
cache_home = Path(os.environ["XDG_CACHE_HOME"])
log = Path(os.environ["FAKE_QMD_LOG"])
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "arguments": arguments,
        "config_dir": str(config_dir),
        "cache_home": str(cache_home),
        "force_cpu": os.environ.get("QMD_FORCE_CPU"),
        "index_path": os.environ.get("INDEX_PATH"),
    }) + "\\n")

if arguments == ["--version"]:
    print("qmd test-1.0")
elif arguments == ["update"]:
    config = (config_dir / "index.yml").read_text(encoding="utf-8")
    if "\\n    update:" in config:
        print("unsafe update hook", file=sys.stderr)
        raise SystemExit(9)
    if os.environ.get("FAKE_QMD_FAIL_UPDATE") == "1":
        print("simulated update failure", file=sys.stderr)
        raise SystemExit(8)
    database = cache_home / "qmd" / "index.sqlite"
    database.parent.mkdir(parents=True, exist_ok=True)
    database.write_bytes(b"fake sqlite")
elif arguments and arguments[0] == "search":
    print(Path(os.environ["FAKE_QMD_RESULTS"]).read_text(encoding="utf-8"), end="")
else:
    print("unsupported fake qmd invocation", file=sys.stderr)
    raise SystemExit(7)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("FAKE_QMD_LOG", str(log))
    monkeypatch.setenv("FAKE_QMD_RESULTS", str(results))
    monkeypatch.setenv("INDEX_PATH", str(tmp_path / "must-not-be-used.sqlite"))
    return executable, log, results


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def authorize(bundle: Path, item_type: str, reviewer: str) -> None:
    path = bundle / ".core-kb.yaml"
    text = path.read_text(encoding="utf-8")
    marker = f"  {item_type}: []"
    replacement = f"  {item_type}:\n    - {reviewer}"
    if marker not in text:
        raise AssertionError(f"Missing configuration marker: {marker}")
    path.write_text(text.replace(marker, replacement), encoding="utf-8")
