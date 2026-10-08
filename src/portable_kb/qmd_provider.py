"""Legacy QMD BM25 adapter behind the keyword provider interface."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .brains import InstalledBrain
from .parsing import discover_concepts
from .search_provider import SearchError, SearchHit
from .settings import Settings

INDEX_SCHEMA_VERSION = 1
MAX_RESULTS = 100
QMD_MIN_VERSION = (2, 5, 0)
QMD_SUPPORTED_MAJOR = 2
QMD_VERSION = re.compile(r"\b(\d+)\.(\d+)\.(\d+)\b")


class QmdProvider:
    """Keep the existing index layout, compatibility checks, and BM25 calls."""

    name = "qmd"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def index_path(self, slug: str) -> Path:
        return self.settings.cache_dir / "search" / self.name / slug

    def status(self) -> dict[str, Any]:
        return qmd_status(self.settings)

    def load_metadata(self, slug: str) -> Mapping[str, Any]:
        return _load_index_metadata(self.index_path(slug))

    def build(self, brain: InstalledBrain, bundle: Path) -> dict[str, Any]:
        executable = _qmd_executable(self.settings)
        root = self.settings.cache_dir / "search" / "qmd"
        if root.is_symlink():
            raise SearchError(f"Search cache root must not be a symbolic link: {root}")
        root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".index-{brain.slug}-", dir=root))
        try:
            _write_qmd_config(stage, brain, bundle)
            version = _require_qmd_compatibility(executable, stage)
            _run_qmd(executable, stage, "update", timeout=300)
            database = stage / "cache" / "qmd" / "index.sqlite"
            if database.is_symlink() or not database.is_file():
                raise SearchError("QMD completed without producing its isolated index database.")
            concepts = discover_concepts(bundle)
            metadata = {
                "schema_version": INDEX_SCHEMA_VERSION,
                "provider": "qmd",
                "mode": "keyword",
                "brain_id": brain.id,
                "brain_slug": brain.slug,
                "commit": brain.commit,
                "bundle": "knowledge",
                "concept_count": len(concepts),
                "qmd_version": version,
            }
            _write_json(stage / "metadata.json", metadata)
            _publish_index(stage, self.index_path(brain.slug), root)
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        return {
            **metadata,
            "index_path": str(self.index_path(brain.slug)),
            "ok": True,
        }

    def query(self, brain: InstalledBrain, query: str, limit: int) -> Sequence[SearchHit]:
        executable = _qmd_executable(self.settings)
        state = self.index_path(brain.slug)
        _require_qmd_compatibility(executable, state)
        candidate_limit = min(MAX_RESULTS, max(limit * 5, 20))
        output = _run_qmd(
            executable,
            state,
            "search",
            query,
            "--format",
            "json",
            "--collection",
            brain.slug,
            "-n",
            str(candidate_limit),
            timeout=120,
        )
        return tuple(_search_hit(row, brain.slug) for row in _load_qmd_results(output)[:limit])


def _search_hit(row: Mapping[str, Any], slug: str) -> SearchHit:
    display_path = row.get("file")
    score = row.get("score")
    title = row.get("title")
    if (
        not isinstance(display_path, str)
        or isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not 0 <= score <= 1
        or not isinstance(title, str)
    ):
        raise SearchError("QMD returned a result with invalid file, score, or title fields.")
    prefix = f"qmd://{slug}/"
    if not display_path.startswith(prefix):
        raise SearchError("QMD returned a result outside the selected brain collection.")
    line = row.get("line")
    if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line < 1):
        raise SearchError("QMD returned an invalid result line number.")
    details = {}
    for key in ("docid", "snippet", "context"):
        value = row.get(key)
        if value is not None and not isinstance(value, str):
            raise SearchError(f"QMD returned an invalid result {key} field.")
        details[key] = value
    return SearchHit(display_path.removeprefix(prefix), float(score), title, line, **details)


def _qmd_executable(settings: Settings) -> str:
    executable = shutil.which(settings.qmd_command)
    if executable is None:
        raise SearchError(
            "QMD is not installed or configured. Install @tobilu/qmd, then run "
            "`pkb doctor` before indexing."
        )
    return executable


def qmd_status(settings: Settings) -> dict[str, Any]:
    """Inspect the configured QMD executable and supported version range."""

    executable = shutil.which(settings.qmd_command)
    result: dict[str, Any] = {
        "command": settings.qmd_command,
        "path": executable,
        "version": None,
        "compatible": False,
        "minimum_version": ".".join(str(part) for part in QMD_MIN_VERSION),
        "supported_major": QMD_SUPPORTED_MAJOR,
        "ok": False,
    }
    if executable is None:
        result["error"] = "QMD executable was not found."
        return result
    try:
        version = _qmd_version(executable)
    except SearchError as exc:
        result["error"] = str(exc)
        return result
    parsed = _parse_qmd_version(version)
    result["version"] = version
    if parsed is None:
        result["error"] = "QMD returned an unrecognized version string."
        return result
    compatible = parsed[0] == QMD_SUPPORTED_MAJOR and parsed >= QMD_MIN_VERSION
    result["compatible"] = compatible
    result["ok"] = compatible
    if not compatible:
        result["error"] = (
            f"QMD {parsed[0]}.{parsed[1]}.{parsed[2]} is outside the supported range "
            f">={'.'.join(str(part) for part in QMD_MIN_VERSION)}, "
            f"<{QMD_SUPPORTED_MAJOR + 1}.0.0."
        )
    return result


def _qmd_version(executable: str) -> str:
    environment = os.environ.copy()
    environment.update({"NO_COLOR": "1", "QMD_FORCE_CPU": "1"})
    try:
        completed = subprocess.run(
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise SearchError("QMD timed out while reporting its version.") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
        raise SearchError(
            f"QMD failed while reporting its version: {str(detail).strip()[-2_000:]}"
        ) from exc
    return completed.stdout.strip()


def _parse_qmd_version(value: str) -> tuple[int, int, int] | None:
    match = QMD_VERSION.search(value)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def _require_qmd_compatibility(executable: str, state: Path | None = None) -> str:
    version = (
        _run_qmd(executable, state, "--version", timeout=30).strip()
        if state is not None
        else _qmd_version(executable)
    )
    parsed = _parse_qmd_version(version)
    if parsed is None:
        raise SearchError("QMD returned an unrecognized version string; run `pkb doctor`.")
    if parsed[0] != QMD_SUPPORTED_MAJOR or parsed < QMD_MIN_VERSION:
        raise SearchError(
            f"Unsupported QMD version {version!r}; Portable KB requires "
            f">={'.'.join(str(part) for part in QMD_MIN_VERSION)} and "
            f"<{QMD_SUPPORTED_MAJOR + 1}.0.0."
        )
    return version


def _write_qmd_config(state: Path, brain: InstalledBrain, bundle: Path) -> None:
    config_dir = state / "config"
    config_dir.mkdir(parents=True)
    payload = {
        "global_context": f"Portable KB brain: {brain.name}",
        "collections": {
            brain.slug: {
                "path": str(bundle),
                "pattern": "**/*.md",
                "ignore": ["index.md", "log.md", "**/index.md", "**/log.md"],
                "includeByDefault": True,
                "context": {"/": f"Portable KB brain {brain.name} at commit {brain.commit}"},
            }
        },
    }
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    path = config_dir / "index.yml"
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(payload, stream)
    path.chmod(0o600)


def _qmd_environment(state: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("INDEX_PATH", None)
    environment.update(
        {
            "QMD_CONFIG_DIR": str(state / "config"),
            "XDG_CACHE_HOME": str(state / "cache"),
            "QMD_FORCE_CPU": "1",
            "NO_COLOR": "1",
            "PWD": str(state),
        }
    )
    return environment


def _run_qmd(executable: str, state: Path, *arguments: str, timeout: int) -> str:
    try:
        completed = subprocess.run(
            [executable, *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=state,
            env=_qmd_environment(state),
        )
    except subprocess.TimeoutExpired as exc:
        raise SearchError(f"QMD timed out while running: {arguments[0]}") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
        detail = str(detail).strip()[-2_000:]
        raise SearchError(f"QMD failed while running {arguments[0]}: {detail}") from exc
    return completed.stdout


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _publish_index(stage: Path, target: Path, root: Path) -> None:
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise SearchError(f"Search index target is unsafe: {target}")
    if not target.exists():
        os.replace(stage, target)
        return
    backup = Path(tempfile.mkdtemp(prefix=f".previous-{target.name}-", dir=root))
    backup.rmdir()
    os.replace(target, backup)
    try:
        os.replace(stage, target)
    except Exception:
        os.replace(backup, target)
        raise
    shutil.rmtree(backup)


def _load_index_metadata(state: Path) -> Mapping[str, Any]:
    path = state / "metadata.json"
    if state.is_symlink() or not state.is_dir() or path.is_symlink() or not path.is_file():
        raise SearchError(f"Keyword index is missing; run `pkb search index {state.name}` first.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SearchError(f"Keyword index metadata is invalid; run `pkb search index {state.name}`.") from exc
    expected = {
        "schema_version",
        "provider",
        "mode",
        "brain_id",
        "brain_slug",
        "commit",
        "bundle",
        "concept_count",
        "qmd_version",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise SearchError(f"Keyword index metadata has an unsupported structure; run `pkb search index {state.name}`.")
    if (
        payload.get("schema_version") != INDEX_SCHEMA_VERSION
        or payload.get("provider") != "qmd"
        or payload.get("mode") != "keyword"
        or payload.get("bundle") != "knowledge"
        or not all(
            isinstance(payload.get(key), str) and payload.get(key)
            for key in ("brain_id", "brain_slug", "commit", "qmd_version")
        )
        or isinstance(payload.get("concept_count"), bool)
        or not isinstance(payload.get("concept_count"), int)
        or payload.get("concept_count", -1) < 0
    ):
        raise SearchError(f"Keyword index metadata is incompatible; run `pkb search index {state.name}`.")
    return payload


def _load_qmd_results(output: str) -> Sequence[Mapping[str, Any]]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SearchError("QMD returned invalid JSON search output.") from exc
    if not isinstance(payload, list) or not all(isinstance(row, Mapping) for row in payload):
        raise SearchError("QMD returned an unsupported JSON search result structure.")
    return payload
