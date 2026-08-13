"""Git-backed installation and selection of Portable KB brains."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .models import ValidationReport
from .settings import Settings
from .validation import validate_bundle

COMMIT = re.compile(r"^[0-9a-f]{40}$")
SCP_REMOTE = re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+:.+$")


class BrainError(RuntimeError):
    """Raised when a brain operation cannot complete safely."""


@dataclass(frozen=True, slots=True)
class BrainManifest:
    """Repository-owned identity and bundle boundary."""

    id: str
    slug: str
    name: str
    bundle: str = "knowledge"
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class InstalledBrain:
    """One locally installed and commit-pinned brain."""

    id: str
    slug: str
    name: str
    source: str
    checkout: str
    commit: str

    def checkout_path(self, settings: Settings) -> Path:
        return settings.data_dir / PurePosixPath(self.checkout)

    def as_dict(self, *, active: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "source": self.source,
            "checkout": self.checkout,
            "commit": self.commit,
            "active": active,
        }


@dataclass(frozen=True, slots=True)
class BrainCatalog:
    """Local installation catalog; canonical knowledge never lives here."""

    brains: tuple[InstalledBrain, ...] = ()
    active: str | None = None
    schema_version: int = 1

    def get(self, slug: str) -> InstalledBrain:
        for brain in self.brains:
            if brain.slug == slug:
                return brain
        raise BrainError(f"Brain is not installed: {slug}")

    def with_brain(self, brain: InstalledBrain) -> BrainCatalog:
        if any(existing.slug == brain.slug for existing in self.brains):
            raise BrainError(f"Brain slug is already installed: {brain.slug}")
        if any(existing.id == brain.id for existing in self.brains):
            raise BrainError(f"Brain identity is already installed: {brain.id}")
        brains = tuple(sorted((*self.brains, brain), key=lambda item: item.slug))
        return BrainCatalog(brains=brains, active=self.active or brain.slug)

    def selecting(self, slug: str) -> BrainCatalog:
        self.get(slug)
        return BrainCatalog(brains=self.brains, active=slug)

    def updating(self, updated: InstalledBrain) -> BrainCatalog:
        current = self.get(updated.slug)
        if current.id != updated.id:
            raise BrainError("Updated brain identity does not match the local catalog.")
        brains = tuple(updated if brain.slug == updated.slug else brain for brain in self.brains)
        return BrainCatalog(brains=brains, active=self.active)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active": self.active,
            "brains": [brain.as_dict(active=brain.slug == self.active) for brain in self.brains],
        }


def catalog_path(settings: Settings) -> Path:
    return settings.data_dir / "catalog.yaml"


def load_catalog(settings: Settings) -> BrainCatalog:
    """Load the local catalog without touching installed repositories."""

    path = catalog_path(settings)
    if path.is_symlink():
        raise BrainError(f"Brain catalog is not a regular file: {path}")
    if not path.exists():
        return BrainCatalog()
    if not path.is_file():
        raise BrainError(f"Brain catalog is not a regular file: {path}")
    yaml = YAML(typ="safe")
    try:
        payload = yaml.load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BrainError(f"Brain catalog is not valid safe YAML: {path}") from exc
    return _catalog_from_payload(payload)


def save_catalog(catalog: BrainCatalog, settings: Settings) -> Path:
    """Atomically persist the local catalog with owner-only permissions."""

    path = catalog_path(settings)
    if path.is_symlink():
        raise BrainError(f"Refusing to replace symbolic-link catalog: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": catalog.schema_version,
        "active": catalog.active,
        "brains": [
            {
                "id": brain.id,
                "slug": brain.slug,
                "name": brain.name,
                "source": brain.source,
                "checkout": brain.checkout,
                "commit": DoubleQuotedScalarString(brain.commit),
            }
            for brain in catalog.brains
        ],
    }
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            yaml.dump(payload, stream)
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def read_manifest(repository: str | Path) -> BrainManifest:
    """Read and validate a repository-root brain manifest."""

    root = Path(repository).expanduser().absolute()
    path = root / "brain.yaml"
    if path.is_symlink() or not path.is_file():
        raise BrainError(f"Repository has no regular brain.yaml manifest: {root}")
    yaml = YAML(typ="safe")
    try:
        payload = yaml.load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BrainError("brain.yaml is not valid safe YAML.") from exc
    if not isinstance(payload, Mapping):
        raise BrainError("brain.yaml must contain a mapping.")
    _validate_manifest_payload(payload)
    bundle = root / str(payload["bundle"])
    if bundle.is_symlink() or not bundle.is_dir() or not bundle.is_relative_to(root):
        raise BrainError("Manifest bundle must be a regular knowledge/ directory in the repository.")
    return BrainManifest(
        id=str(payload["id"]),
        slug=str(payload["slug"]),
        name=str(payload["name"]),
        bundle=str(payload["bundle"]),
    )


def add_brain(
    source: str,
    settings: Settings,
    *,
    as_of: str | None = None,
) -> tuple[InstalledBrain, BrainCatalog, ValidationReport]:
    """Clone, validate, pin, and atomically register a brain."""

    normalized_source = _normalize_source(source)
    catalog = load_catalog(settings)
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to install a brain.")
    brains_root = settings.data_dir / "brains"
    brains_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".install-", dir=brains_root))
    checkout = stage / "checkout"
    try:
        _run_git(
            git,
            "-c",
            "core.hooksPath=/dev/null",
            "clone",
            "--quiet",
            "--no-recurse-submodules",
            "--",
            normalized_source,
            str(checkout),
        )
        manifest = read_manifest(checkout)
        if any(brain.slug == manifest.slug for brain in catalog.brains):
            raise BrainError(f"Brain slug is already installed: {manifest.slug}")
        if any(brain.id == manifest.id for brain in catalog.brains):
            raise BrainError(f"Brain identity is already installed: {manifest.id}")
        destination = brains_root / manifest.slug
        if destination.exists() or destination.is_symlink():
            raise BrainError(f"Brain checkout path already exists: {destination}")
        report = validate_bundle(checkout / manifest.bundle, as_of=as_of)
        if not report.profile_passes:
            codes = ", ".join(finding.code for finding in report.errors[:8])
            raise BrainError(f"Knowledge bundle failed validation: {codes}")
        commit = _run_git(git, "-C", str(checkout), "rev-parse", "HEAD").strip()
        if not COMMIT.fullmatch(commit):
            raise BrainError("Git returned an invalid commit identifier.")
        entry = InstalledBrain(
            id=manifest.id,
            slug=manifest.slug,
            name=manifest.name,
            source=normalized_source,
            checkout=f"brains/{manifest.slug}",
            commit=commit,
        )
        updated = catalog.with_brain(entry)
        os.replace(checkout, destination)
        try:
            save_catalog(updated, settings)
        except Exception:
            shutil.rmtree(destination)
            raise
        return entry, updated, report
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def use_brain(slug: str, settings: Settings) -> InstalledBrain:
    """Select an installed brain after checking its local identity."""

    catalog = load_catalog(settings)
    brain = catalog.get(slug)
    checkout = brain.checkout_path(settings)
    if checkout.is_symlink() or not checkout.is_dir():
        raise BrainError(f"Brain checkout is unavailable: {checkout}")
    manifest = read_manifest(checkout)
    if manifest.id != brain.id or manifest.slug != brain.slug:
        raise BrainError("Installed brain identity does not match the local catalog.")
    save_catalog(catalog.selecting(slug), settings)
    return brain


def brain_status(
    settings: Settings,
    slug: str | None = None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Return read-only health for one installed brain."""

    catalog = load_catalog(settings)
    selected = slug or catalog.active
    if selected is None:
        raise BrainError("No active brain. Install or select one first.")
    brain = catalog.get(selected)
    checkout = brain.checkout_path(settings)
    result: dict[str, Any] = {
        **brain.as_dict(active=selected == catalog.active),
        "checkout_path": str(checkout),
        "checkout_available": False,
        "identity_matches": False,
        "current_commit": None,
        "commit_matches": False,
        "dirty": None,
        "bundle_valid": False,
        "validation_errors": [],
        "validation_warnings": [],
        "ok": False,
    }
    if checkout.is_symlink() or not checkout.is_dir():
        return result
    result["checkout_available"] = True
    try:
        manifest = read_manifest(checkout)
        result["identity_matches"] = manifest.id == brain.id and manifest.slug == brain.slug
        git = shutil.which("git")
        if git is None:
            return result
        current_commit = _run_git(git, "-C", str(checkout), "rev-parse", "HEAD").strip()
        result["current_commit"] = current_commit
        result["commit_matches"] = current_commit == brain.commit
        porcelain = _run_git(git, "-C", str(checkout), "status", "--porcelain")
        result["dirty"] = bool(porcelain.strip())
        report = validate_bundle(checkout / manifest.bundle, as_of=as_of)
        result["bundle_valid"] = report.profile_passes
        result["validation_errors"] = [finding.as_dict() for finding in report.errors]
        result["validation_warnings"] = [finding.as_dict() for finding in report.warnings]
    except BrainError as exc:
        result["error"] = str(exc)
    result["ok"] = all(
        (
            result["checkout_available"],
            result["identity_matches"],
            result["commit_matches"],
            result["dirty"] is False,
            result["bundle_valid"],
        )
    )
    return result


def sync_brain(
    settings: Settings,
    slug: str | None = None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Fetch, validate, and fast-forward one installed brain."""

    catalog = load_catalog(settings)
    selected = slug or catalog.active
    if selected is None:
        raise BrainError("No active brain. Install or select one first.")
    brain = catalog.get(selected)
    checkout = brain.checkout_path(settings)
    if checkout.is_symlink() or not checkout.is_dir():
        raise BrainError(f"Brain checkout is unavailable: {checkout}")
    manifest = read_manifest(checkout)
    if manifest.id != brain.id or manifest.slug != brain.slug:
        raise BrainError("Installed brain identity does not match the local catalog.")
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to synchronize a brain.")
    current = _run_git(git, "-C", str(checkout), "rev-parse", "HEAD").strip()
    if current != brain.commit:
        raise BrainError("Installed checkout does not match its catalog pin; refusing to sync.")
    if _run_git(git, "-C", str(checkout), "status", "--porcelain").strip():
        raise BrainError("Installed checkout has local changes; refusing to sync.")
    origin = _run_git(git, "-C", str(checkout), "remote", "get-url", "origin").strip()
    if origin != brain.source:
        raise BrainError("Installed checkout origin differs from its catalog source.")

    _run_git(
        git,
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(checkout),
        "fetch",
        "--quiet",
        "--no-tags",
        "--prune",
        "origin",
    )
    upstream = _run_git(
        git, "-C", str(checkout), "rev-parse", "--verify", "@{upstream}"
    ).strip()
    if not COMMIT.fullmatch(upstream):
        raise BrainError("Git returned an invalid upstream commit identifier.")
    if not _git_is_ancestor(git, checkout, current, upstream):
        raise BrainError("Remote history is not a fast-forward from the installed commit.")

    if upstream == current:
        report = validate_bundle(checkout / manifest.bundle, as_of=as_of)
        if not report.profile_passes:
            codes = ", ".join(finding.code for finding in report.errors[:8])
            raise BrainError(f"Installed knowledge bundle failed validation: {codes}")
        return _sync_result(brain, current, upstream, report, changed=False)

    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    worktree = Path(tempfile.mkdtemp(prefix=f".sync-{brain.slug}-", dir=settings.cache_dir))
    shutil.rmtree(worktree)
    worktree_added = False
    try:
        _run_git(
            git,
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            str(checkout),
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(worktree),
            upstream,
        )
        worktree_added = True
        candidate = read_manifest(worktree)
        if candidate.id != brain.id or candidate.slug != brain.slug:
            raise BrainError("Remote candidate changes the installed brain identity.")
        report = validate_bundle(worktree / candidate.bundle, as_of=as_of)
        if not report.profile_passes:
            codes = ", ".join(finding.code for finding in report.errors[:8])
            raise BrainError(f"Remote knowledge bundle failed validation: {codes}")
    finally:
        if worktree_added:
            try:
                _run_git(
                    git,
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-C",
                    str(checkout),
                    "worktree",
                    "remove",
                    "--force",
                    str(worktree),
                )
            finally:
                _run_git(
                    git,
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-C",
                    str(checkout),
                    "worktree",
                    "prune",
                )
        else:
            shutil.rmtree(worktree, ignore_errors=True)

    if _run_git(git, "-C", str(checkout), "rev-parse", "HEAD").strip() != current:
        raise BrainError("Installed checkout changed during synchronization.")
    if _run_git(git, "-C", str(checkout), "status", "--porcelain").strip():
        raise BrainError("Installed checkout changed during synchronization.")
    _run_git(
        git,
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(checkout),
        "merge",
        "--ff-only",
        "--no-edit",
        upstream,
    )
    updated_brain = replace(brain, name=candidate.name, commit=upstream)
    updated_catalog = catalog.updating(updated_brain)
    try:
        save_catalog(updated_catalog, settings)
    except Exception as exc:
        _run_git(
            git,
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            str(checkout),
            "reset",
            "--hard",
            current,
        )
        raise BrainError("Catalog update failed; the installed checkout was restored.") from exc
    return _sync_result(updated_brain, current, upstream, report, changed=True)


def _sync_result(
    brain: InstalledBrain,
    previous: str,
    current: str,
    report: ValidationReport,
    *,
    changed: bool,
) -> dict[str, Any]:
    return {
        "slug": brain.slug,
        "name": brain.name,
        "previous_commit": previous,
        "current_commit": current,
        "changed": changed,
        "bundle_valid": report.profile_passes,
        "validation_warnings": [finding.as_dict() for finding in report.warnings],
        "ok": report.profile_passes,
    }


def _catalog_from_payload(payload: Any) -> BrainCatalog:
    if not isinstance(payload, Mapping) or set(payload) != {"schema_version", "active", "brains"}:
        raise BrainError("Brain catalog fields do not match schema version 1.")
    if payload.get("schema_version") != 1:
        raise BrainError("Unsupported brain catalog schema version.")
    raw_brains = payload.get("brains")
    active = payload.get("active")
    if not isinstance(raw_brains, list) or not (active is None or isinstance(active, str)):
        raise BrainError("Brain catalog has invalid active or brains fields.")
    brains: list[InstalledBrain] = []
    expected = {"id", "slug", "name", "source", "checkout", "commit"}
    for raw in raw_brains:
        if not isinstance(raw, Mapping) or set(raw) != expected:
            raise BrainError("Brain catalog contains an invalid entry.")
        if not all(isinstance(raw[key], str) and raw[key] for key in expected):
            raise BrainError("Brain catalog entry fields must be non-empty strings.")
        checkout = str(raw["checkout"])
        slug = str(raw["slug"])
        try:
            _validate_manifest_payload(
                {
                    "schema_version": 1,
                    "id": raw["id"],
                    "slug": slug,
                    "name": raw["name"],
                    "bundle": "knowledge",
                }
            )
        except BrainError as exc:
            raise BrainError("Brain catalog contains an invalid identity entry.") from exc
        if PurePosixPath(checkout) != PurePosixPath("brains") / slug:
            raise BrainError("Brain catalog checkout path is unsafe.")
        if not COMMIT.fullmatch(str(raw["commit"])):
            raise BrainError("Brain catalog commit is invalid.")
        brains.append(
            InstalledBrain(
                id=str(raw["id"]),
                slug=slug,
                name=str(raw["name"]),
                source=str(raw["source"]),
                checkout=checkout,
                commit=str(raw["commit"]),
            )
        )
    if len({brain.slug for brain in brains}) != len(brains) or len(
        {brain.id for brain in brains}
    ) != len(brains):
        raise BrainError("Brain catalog contains duplicate identities.")
    if active is not None and active not in {brain.slug for brain in brains}:
        raise BrainError("Active brain is not installed.")
    return BrainCatalog(brains=tuple(sorted(brains, key=lambda brain: brain.slug)), active=active)


def _load_manifest_schema() -> Mapping[str, Any]:
    repository_path = Path(__file__).resolve().parents[2] / "schemas" / "brain.schema.yaml"
    path = (
        repository_path
        if repository_path.exists()
        else Path(__file__).resolve().parent / "schemas" / "brain.schema.yaml"
    )
    yaml = YAML(typ="safe")
    payload = yaml.load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise BrainError("Packaged brain manifest schema is invalid.")
    Draft202012Validator.check_schema(payload)
    return payload


def _validate_manifest_payload(payload: Mapping[str, Any]) -> None:
    validator = Draft202012Validator(_load_manifest_schema())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise BrainError(f"brain.yaml is invalid: {details}")


def _normalize_source(source: str) -> str:
    value = source.strip()
    if not value or any(ord(character) < 32 for character in value):
        raise BrainError("Brain source must be a non-empty path or Git URL.")
    if "://" in value:
        parsed = urlsplit(value)
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise BrainError("Git URLs containing credentials are not allowed.")
        return value
    if "@" in value and ":" in value and not SCP_REMOTE.fullmatch(value):
        raise BrainError("Unsupported or credential-bearing Git source.")
    path = Path(value).expanduser()
    if path.exists():
        return str(path.absolute())
    return value


def _git_is_ancestor(executable: str, repository: Path, ancestor: str, descendant: str) -> bool:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            [
                executable,
                "-C",
                str(repository),
                "merge-base",
                "--is-ancestor",
                ancestor,
                descendant,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BrainError("Git ancestry check could not complete.") from exc
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "failed"
    raise BrainError(f"Git ancestry check failed: {detail}")


def _run_git(executable: str, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            [executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BrainError("Git operation could not complete.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "failed"
        raise BrainError(f"Git operation failed: {detail}")
    return completed.stdout
