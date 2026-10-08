"""Git-backed installation and selection of Portable KB brains."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
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
GITHUB_REPOSITORY = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,38})/[A-Za-z0-9](?:[A-Za-z0-9._-]{0,99})$"
)
LEGACY_DEMO_SLUG = "portable-kb-core"
LEGACY_DEMO_ID = "urn:uuid:6e7cc12e-b3f7-49da-875d-32b714fdc1e8"


class BrainError(RuntimeError):
    """Raised when a brain operation cannot complete safely."""


class GitHubVisibility(StrEnum):
    """Visibility choices supported by GitHub repository creation."""

    PRIVATE = "private"
    PUBLIC = "public"
    INTERNAL = "internal"


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
    authoring: str | None = None

    def checkout_path(self, settings: Settings) -> Path:
        return settings.data_dir / PurePosixPath(self.checkout)

    def authoring_path(self) -> Path | None:
        return Path(self.authoring).expanduser().absolute() if self.authoring else None

    def as_dict(self, *, active: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "source": self.source,
            "authoring": self.authoring,
            "checkout": self.checkout,
            "commit": self.commit,
            "active": active,
        }


@dataclass(frozen=True, slots=True)
class BrainInitResult:
    """A newly committed, installed, and activated brain."""

    brain: InstalledBrain
    repository: str

    def as_dict(self, report: ValidationReport) -> dict[str, Any]:
        return {
            **self.brain.as_dict(active=True),
            "repository": self.repository,
            "published": False,
            "validation_warnings": [finding.as_dict() for finding in report.warnings],
        }


@dataclass(frozen=True, slots=True)
class BrainPublishResult:
    """A local brain published to a GitHub repository."""

    brain: InstalledBrain
    repository: str
    github_repository: str
    visibility: GitHubVisibility

    def as_dict(self, *, active: bool) -> dict[str, Any]:
        return {
            **self.brain.as_dict(active=active),
            "repository": self.repository,
            "github_repository": self.github_repository,
            "visibility": self.visibility.value,
            "published": True,
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

    def removing(self, slug: str) -> BrainCatalog:
        self.get(slug)
        brains = tuple(brain for brain in self.brains if brain.slug != slug)
        active = None if self.active == slug else self.active
        return BrainCatalog(brains=brains, active=active)

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
                "authoring": brain.authoring,
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


def init_brain(
    source: str,
    name: str,
    slug: str,
    settings: Settings,
    *,
    as_of: str | None = None,
) -> tuple[BrainInitResult, BrainCatalog, ValidationReport]:
    """Create the first valid commit in an empty local repository and activate it."""

    normalized_source = _normalize_source(source)
    if _is_remote_source(normalized_source):
        raise BrainError(
            "Brain init starts with a local repository. Pass a local path, then publish "
            "it with the interactive prompt or `pkb brain publish`."
        )
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to initialize a brain.")

    catalog = load_catalog(settings)
    if any(brain.slug == slug for brain in catalog.brains):
        raise BrainError(f"Brain slug is already installed: {slug}")
    destination = settings.data_dir / "brains" / slug
    if destination.exists() or destination.is_symlink():
        raise BrainError(f"Brain checkout path already exists: {destination}")
    existing_ids = {brain.id for brain in catalog.brains}
    identity = f"urn:uuid:{uuid.uuid4()}"
    while identity in existing_ids:
        identity = f"urn:uuid:{uuid.uuid4()}"
    manifest_payload = {
        "schema_version": 1,
        "id": identity,
        "slug": slug,
        "name": name,
        "bundle": "knowledge",
    }
    _validate_manifest_payload(manifest_payload)

    repository = Path(normalized_source).expanduser().absolute()
    created_directory = False
    created_git = False
    prepared = False
    try:
        if repository.is_symlink():
            raise BrainError(f"Brain repository must not be a symbolic link: {repository}")
        if repository.exists() and not repository.is_dir():
            raise BrainError(f"Brain repository is not a directory: {repository}")
        if not repository.exists():
            if not repository.parent.is_dir():
                raise BrainError(
                    f"Parent directory does not exist for brain repository: {repository.parent}"
                )
            repository.mkdir()
            created_directory = True
        created_git = _require_empty_repository(git, repository, initialize=True)
        prepared = True
        _write_validate_and_commit(
            git,
            repository,
            manifest_payload,
            as_of=as_of,
        )
    except Exception:
        if prepared and not _git_has_head(git, repository):
            _remove_uncommitted_brain(git, repository, remove_git=created_git)
            if created_directory:
                with suppress(OSError):
                    repository.rmdir()
        raise

    brain, installed_catalog, installed_report = add_brain(
        str(repository),
        settings,
        as_of=as_of,
    )
    active_catalog = installed_catalog.selecting(brain.slug)
    if active_catalog != installed_catalog:
        save_catalog(active_catalog, settings)
    result = BrainInitResult(brain=brain, repository=str(repository))
    return result, active_catalog, installed_report


def publish_brain_to_github(
    settings: Settings,
    github_repository: str,
    slug: str | None = None,
    *,
    visibility: GitHubVisibility = GitHubVisibility.PRIVATE,
) -> tuple[BrainPublishResult, BrainCatalog]:
    """Create a GitHub repository for a local brain, push it, and update distribution state."""

    target = github_repository.strip()
    if not GITHUB_REPOSITORY.fullmatch(target):
        raise BrainError("GitHub repository must use the org/repo format.")
    catalog = load_catalog(settings)
    selected = slug or catalog.active
    if selected is None:
        raise BrainError("No active brain. Initialize or select one first.")
    brain = catalog.get(selected)
    if _is_remote_source(brain.source):
        raise BrainError(f"Brain is already published from: {brain.source}")
    repository = brain.authoring_path()
    if repository is None:
        raise BrainError("Brain has no local authoring repository to publish.")
    if repository.is_symlink() or not repository.is_dir():
        raise BrainError(f"Local authoring repository is unavailable: {repository}")
    manifest = read_manifest(repository)
    if manifest.id != brain.id or manifest.slug != brain.slug:
        raise BrainError("Local authoring repository identity does not match the catalog.")
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to publish a brain.")
    current = _run_git(git, "-C", str(repository), "rev-parse", "HEAD").strip()
    if current != brain.commit:
        raise BrainError("Local authoring repository does not match the installed commit.")
    if _run_git(git, "-C", str(repository), "status", "--porcelain").strip():
        raise BrainError("Local authoring repository has uncommitted changes.")
    if _git_remote_exists(git, repository, "origin"):
        existing_origin = _run_git(
            git, "-C", str(repository), "remote", "get-url", "origin"
        ).strip()
        if _github_repository_from_source(existing_origin) != target.casefold():
            raise BrainError("Local authoring repository already has a different origin remote.")
    else:
        gh = shutil.which("gh")
        if gh is None:
            raise BrainError(
                "GitHub CLI is required to publish. Install `gh`, authenticate it, then retry "
                "with `pkb brain publish`."
            )
        _run_gh(
            gh,
            "repo",
            "create",
            target,
            f"--{visibility.value}",
            "--source",
            str(repository),
            "--remote",
            "origin",
        )
    source = _normalize_source(
        _run_git(git, "-C", str(repository), "remote", "get-url", "origin").strip()
    )
    _push_initial_commit(git, repository)

    checkout = brain.checkout_path(settings)
    old_origin = _run_git(git, "-C", str(checkout), "remote", "get-url", "origin").strip()
    _run_git(git, "-C", str(checkout), "remote", "set-url", "origin", source)
    updated_brain = replace(brain, source=source)
    updated_catalog = catalog.updating(updated_brain)
    try:
        save_catalog(updated_catalog, settings)
    except Exception as exc:
        _run_git(git, "-C", str(checkout), "remote", "set-url", "origin", old_origin)
        raise BrainError(
            "GitHub publication succeeded, but local catalog publication failed."
        ) from exc
    result = BrainPublishResult(
        brain=updated_brain,
        repository=str(repository),
        github_repository=target,
        visibility=visibility,
    )
    return result, updated_catalog


def push_brain(
    settings: Settings,
    slug: str | None = None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Publish the active validated local version without rewriting remote history."""

    catalog = load_catalog(settings)
    selected = slug or catalog.active
    if selected is None:
        raise BrainError("No active brain. Initialize or select one first.")
    brain = catalog.get(selected)
    if not _is_remote_source(brain.source):
        raise BrainError(
            "Brain has not been published yet. Run `pkb brain publish --to org/repo` first."
        )
    resolved, repository, manifest = authoring_repository(settings, selected)
    current = clean_repository_head(repository)
    if resolved != brain or current != brain.commit:
        raise BrainError("Local authoring repository does not match the active saved version.")
    report = validate_bundle(repository / manifest.bundle, as_of=as_of)
    if not report.profile_passes:
        codes = ", ".join(finding.code for finding in report.errors[:8])
        raise BrainError(f"Local knowledge bundle failed validation: {codes}")
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to share a brain.")
    if not _git_remote_exists(git, repository, "origin"):
        raise BrainError("Local authoring repository has no organization remote.")
    origin = _normalize_source(
        _run_git(git, "-C", str(repository), "remote", "get-url", "origin").strip()
    )
    if origin != brain.source:
        raise BrainError("Local authoring repository origin differs from the brain source.")
    _run_git(
        git,
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(repository),
        "fetch",
        "--quiet",
        "--no-tags",
        "origin",
        "refs/heads/main",
    )
    published = _run_git(git, "-C", str(repository), "rev-parse", "FETCH_HEAD").strip()
    if not COMMIT.fullmatch(published):
        raise BrainError("Git returned an invalid published version identifier.")
    if published == current:
        return _push_result(brain, published, current, report, changed=False)
    if not _git_is_ancestor(git, repository, published, current):
        if _git_is_ancestor(git, repository, current, published):
            raise BrainError(
                "The organization has newer knowledge. Synchronize before sharing local work."
            )
        raise BrainError(
            "Local and organization knowledge have diverged; refusing to overwrite either."
        )
    changed_paths = tuple(
        path
        for path in _run_git(
            git,
            "-c",
            "core.quotepath=false",
            "-C",
            str(repository),
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-m",
            "-z",
            f"{published}..{current}",
        ).split("\0")
        if path
    )
    allowed_prefix = f"{manifest.bundle}/"
    unsafe = tuple(
        path for path in changed_paths if path != "brain.yaml" and not path.startswith(allowed_prefix)
    )
    if unsafe:
        raise BrainError(
            "Saved history contains files outside the brain boundary; refusing to share: "
            + ", ".join(unsafe[:8])
        )
    _run_git(
        git,
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(repository),
        "push",
        "--quiet",
        "origin",
        f"{current}:refs/heads/main",
    )
    return _push_result(brain, published, current, report, changed=True)


def _push_result(
    brain: InstalledBrain,
    previous: str,
    current: str,
    report: ValidationReport,
    *,
    changed: bool,
) -> dict[str, Any]:
    """Build the stable result contract for an organizational push."""

    return {
        "slug": brain.slug,
        "name": brain.name,
        "source": brain.source,
        "previous_published_commit": previous,
        "published_commit": current,
        "changed": changed,
        "validation_warnings": [finding.as_dict() for finding in report.warnings],
        "ok": report.profile_passes,
    }


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
            authoring=normalized_source if not _is_remote_source(normalized_source) else None,
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


def remove_brain(
    slug: str,
    settings: Settings,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Forget one installed snapshot and its disposable index, preserving its source."""

    catalog = load_catalog(settings)
    brain = catalog.get(slug)
    checkout = brain.checkout_path(settings)
    index = settings.cache_dir / "search" / "qmd" / slug
    native_index = settings.cache_dir / "search" / "builtin" / slug
    indexes = (index, native_index)
    _require_removable_path(native_index, settings.cache_dir / "search" / "builtin", "native search index")
    _require_removable_path(checkout, settings.data_dir / "brains", "brain checkout")
    _require_removable_path(index, settings.cache_dir / "search" / "qmd", "search index")
    if checkout.exists():
        if checkout.is_symlink() or not checkout.is_dir():
            raise BrainError(f"Brain checkout is unsafe and was not removed: {checkout}")
        if not force:
            git = shutil.which("git")
            if git is None:
                raise BrainError("Git is required to verify a brain before removing it.")
            if _run_git(
                git,
                "-C",
                str(checkout),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ).strip():
                raise BrainError(
                    "Installed checkout has local changes. Move or commit them, or use --force "
                    "to discard only this installed snapshot."
                )
    for candidate in indexes:
        if candidate.exists() and (candidate.is_symlink() or not candidate.is_dir()):
            raise BrainError(f"Search index is unsafe and was not removed: {candidate}")

    from .native_sidecar import NativeSidecar
    from .search_provider import SearchError

    native_guard = None
    if native_index.exists():
        try:
            native_guard = NativeSidecar(settings.native_command)
            native_guard.call({"op": "prepare_remove", "index_path": str(native_index)})
        except SearchError as exc:
            if native_guard is not None:
                native_guard.close()
            raise BrainError(f"Native index removal could not acquire reader leases: {exc}") from exc

    try:
        token = uuid.uuid4().hex
        staged: list[tuple[Path, Path]] = []
        try:
            for path in (checkout, *indexes):
                if not path.exists():
                    continue
                quarantine = path.parent / f".{path.name}.remove-{token}"
                os.replace(path, quarantine)
                staged.append((path, quarantine))
            updated = catalog.removing(slug)
            save_catalog(updated, settings)
        except Exception:
            for original, quarantine in reversed(staged):
                if quarantine.exists() and not original.exists():
                    os.replace(quarantine, original)
            raise

        cleanup_warnings: list[str] = []
        for _original, quarantine in staged:
            try:
                shutil.rmtree(quarantine)
            except OSError as exc:
                cleanup_warnings.append(f"Could not delete quarantined derived state: {exc}")
        return {
            "ok": not cleanup_warnings,
            "slug": brain.slug,
            "name": brain.name,
            "removed_checkout": any(original == checkout for original, _ in staged),
            "removed_index": any(original in indexes for original, _ in staged),
            "authoring_preserved": brain.authoring,
            "active": updated.active,
            "legacy_demo": brain.slug == LEGACY_DEMO_SLUG and brain.id == LEGACY_DEMO_ID,
            "cleanup_warnings": cleanup_warnings,
        }

    finally:
        if native_guard is not None:
            native_guard.close()


def legacy_demo_brains(catalog: BrainCatalog) -> tuple[InstalledBrain, ...]:
    """Return exact installations created by the retired bundled demo brain."""

    return tuple(
        brain
        for brain in catalog.brains
        if brain.slug == LEGACY_DEMO_SLUG and brain.id == LEGACY_DEMO_ID
    )


def _require_removable_path(path: Path, parent: Path, label: str) -> None:
    """Require a derived-state path to be an immediate child of its expected root."""

    expected_parent = parent.expanduser().absolute()
    if path.expanduser().absolute().parent != expected_parent:
        raise BrainError(f"Refusing unsafe {label} path: {path}")


def authoring_repository(
    settings: Settings,
    slug: str | None = None,
) -> tuple[InstalledBrain, Path, BrainManifest]:
    """Resolve and verify the local repository used to author a brain."""

    catalog = load_catalog(settings)
    selected = slug or catalog.active
    if selected is None:
        raise BrainError("No active brain. Initialize or select one first.")
    brain = catalog.get(selected)
    repository = brain.authoring_path()
    if repository is None:
        raise BrainError(
            "Brain has no local authoring repository. Clone it locally and initialize or "
            "reinstall it from that path before authoring."
        )
    if repository.is_symlink() or not repository.is_dir():
        raise BrainError(f"Local authoring repository is unavailable: {repository}")
    manifest = read_manifest(repository)
    if manifest.id != brain.id or manifest.slug != brain.slug:
        raise BrainError("Local authoring repository identity does not match the catalog.")
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to verify an authoring repository.")
    current = _run_git(git, "-C", str(repository), "rev-parse", "HEAD").strip()
    if not COMMIT.fullmatch(current) or not _git_is_ancestor(
        git,
        repository,
        brain.commit,
        current,
    ):
        raise BrainError("Local authoring repository does not contain the installed commit.")
    branch = _run_git(git, "-C", str(repository), "branch", "--show-current").strip()
    if branch != "main":
        label = branch or "detached HEAD"
        raise BrainError(
            f"Knowledge authoring requires the main branch; the repository is on {label}. "
            "Switch the brain's authoring repository to main before creating or updating knowledge."
        )
    return brain, repository, manifest


def clean_repository_head(repository: Path) -> str:
    """Return the current commit after verifying an authoring tree is clean."""

    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to save knowledge.")
    current = _run_git(git, "-C", str(repository), "rev-parse", "HEAD").strip()
    if not COMMIT.fullmatch(current):
        raise BrainError("Git returned an invalid authoring commit identifier.")
    if _run_git(
        git,
        "-C",
        str(repository),
        "status",
        "--porcelain",
        "--untracked-files=all",
    ).strip():
        raise BrainError(
            "This brain has another unfinished local change. Finish or discard it before "
            "creating new knowledge."
        )
    return current


def commit_authoring_changes(
    repository: Path,
    relative_paths: Sequence[str],
    *,
    expected_head: str,
    message: str,
) -> str:
    """Commit exactly one validated authoring change without exposing Git to callers."""

    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to save knowledge.")
    current = _run_git(git, "-C", str(repository), "rev-parse", "HEAD").strip()
    if current != expected_head:
        raise BrainError("The brain changed while this knowledge was being prepared.")
    paths = tuple(dict.fromkeys(relative_paths))
    if not paths:
        raise BrainError("The knowledge plan contains no files to save.")
    _run_git(git, "-C", str(repository), "add", "--", *paths)
    commit_arguments = [
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
    ]
    if not _git_identity_is_configured(git, repository):
        commit_arguments.extend(
            [
                "-c",
                "user.name=Portable KB",
                "-c",
                "user.email=portable-kb@localhost.invalid",
            ]
        )
    _run_git(
        git,
        *commit_arguments,
        "-C",
        str(repository),
        "commit",
        "--quiet",
        "--no-verify",
        "--only",
        "-m",
        message,
        "--",
        *paths,
    )
    commit = _run_git(git, "-C", str(repository), "rev-parse", "HEAD").strip()
    if not COMMIT.fullmatch(commit):
        raise BrainError("Git returned an invalid saved version identifier.")
    return commit


def refresh_brain_from_authoring(
    settings: Settings,
    slug: str,
    commit: str,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Validate and activate one local authoring commit in the installed snapshot."""

    catalog = load_catalog(settings)
    brain = catalog.get(slug)
    resolved_brain, repository, _manifest = authoring_repository(settings, slug)
    if resolved_brain != brain:
        raise BrainError("Local authoring state changed before the brain could be refreshed.")
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to refresh a brain.")
    authoring_head = _run_git(git, "-C", str(repository), "rev-parse", "HEAD").strip()
    if authoring_head != commit or not COMMIT.fullmatch(commit):
        raise BrainError("The saved knowledge version no longer matches the authoring brain.")
    checkout, current = _verified_installed_checkout(settings, brain, git)
    if not _git_is_ancestor(git, repository, current, commit):
        raise BrainError("The saved knowledge is not a safe continuation of the active brain.")
    _run_git(
        git,
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(checkout),
        "fetch",
        "--quiet",
        "--no-tags",
        str(repository),
        commit,
    )
    return _activate_installed_commit(
        settings,
        catalog,
        brain,
        checkout,
        current,
        commit,
        as_of=as_of,
        invalid_message="Saved knowledge failed validation",
    )


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
        "authoring_available": False,
        "authoring_branch": None,
        "authoring_clean": None,
        "authoring_ready": False,
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
        authoring = brain.authoring_path()
        if authoring is not None and not authoring.is_symlink() and authoring.is_dir():
            result["authoring_available"] = True
            authoring_branch = _run_git(
                git, "-C", str(authoring), "branch", "--show-current"
            ).strip()
            authoring_clean = not bool(
                _run_git(
                    git,
                    "-C",
                    str(authoring),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ).strip()
            )
            result["authoring_branch"] = authoring_branch or None
            result["authoring_clean"] = authoring_clean
            result["authoring_ready"] = authoring_branch == "main" and authoring_clean
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


def _verified_installed_checkout(
    settings: Settings,
    brain: InstalledBrain,
    git: str,
) -> tuple[Path, str]:
    """Return a clean installed checkout at its catalog-pinned commit."""

    checkout = brain.checkout_path(settings)
    if checkout.is_symlink() or not checkout.is_dir():
        raise BrainError(f"Brain checkout is unavailable: {checkout}")
    manifest = read_manifest(checkout)
    if manifest.id != brain.id or manifest.slug != brain.slug:
        raise BrainError("Installed brain identity does not match the local catalog.")
    current = _run_git(git, "-C", str(checkout), "rev-parse", "HEAD").strip()
    if current != brain.commit:
        raise BrainError("Installed checkout does not match its catalog pin; refusing to update.")
    if _run_git(git, "-C", str(checkout), "status", "--porcelain").strip():
        raise BrainError("Installed checkout has local changes; refusing to update.")
    return checkout, current


def _activate_installed_commit(
    settings: Settings,
    catalog: BrainCatalog,
    brain: InstalledBrain,
    checkout: Path,
    current: str,
    candidate_commit: str,
    *,
    as_of: str | None,
    invalid_message: str,
) -> dict[str, Any]:
    """Validate, fast-forward, and catalog-pin an already fetched commit."""

    manifest = read_manifest(checkout)
    if candidate_commit == current:
        report = validate_bundle(checkout / manifest.bundle, as_of=as_of)
        if not report.profile_passes:
            codes = ", ".join(finding.code for finding in report.errors[:8])
            raise BrainError(f"{invalid_message}: {codes}")
        return _sync_result(brain, current, candidate_commit, report, changed=False)

    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to update a brain.")
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
            candidate_commit,
        )
        worktree_added = True
        candidate = read_manifest(worktree)
        if candidate.id != brain.id or candidate.slug != brain.slug:
            raise BrainError("Candidate changes the installed brain identity.")
        report = validate_bundle(worktree / candidate.bundle, as_of=as_of)
        if not report.profile_passes:
            codes = ", ".join(finding.code for finding in report.errors[:8])
            raise BrainError(f"{invalid_message}: {codes}")
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
        raise BrainError("Installed checkout changed during the update.")
    if _run_git(git, "-C", str(checkout), "status", "--porcelain").strip():
        raise BrainError("Installed checkout changed during the update.")
    _run_git(
        git,
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(checkout),
        "merge",
        "--ff-only",
        "--no-edit",
        candidate_commit,
    )
    updated_brain = replace(brain, name=candidate.name, commit=candidate_commit)
    try:
        save_catalog(catalog.updating(updated_brain), settings)
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
    return _sync_result(updated_brain, current, candidate_commit, report, changed=True)


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
    git = shutil.which("git")
    if git is None:
        raise BrainError("Git is required to synchronize a brain.")
    checkout, current = _verified_installed_checkout(settings, brain, git)
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
    if upstream != current and _git_is_ancestor(git, checkout, upstream, current):
        manifest = read_manifest(checkout)
        report = validate_bundle(checkout / manifest.bundle, as_of=as_of)
        if not report.profile_passes:
            codes = ", ".join(finding.code for finding in report.errors[:8])
            raise BrainError(f"Installed knowledge bundle failed validation: {codes}")
        result = _sync_result(brain, current, current, report, changed=False)
        result["source_behind"] = True
        return result
    if not _git_is_ancestor(git, checkout, current, upstream):
        raise BrainError("Remote history is not a fast-forward from the installed commit.")
    return _activate_installed_commit(
        settings,
        catalog,
        brain,
        checkout,
        current,
        upstream,
        as_of=as_of,
        invalid_message="Remote knowledge bundle failed validation",
    )


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
        if not isinstance(raw, Mapping) or set(raw) not in (expected, expected | {"authoring"}):
            raise BrainError("Brain catalog contains an invalid entry.")
        if not all(isinstance(raw[key], str) and raw[key] for key in expected):
            raise BrainError("Brain catalog entry fields must be non-empty strings.")
        raw_authoring = raw.get("authoring")
        if raw_authoring is not None and (
            not isinstance(raw_authoring, str) or not raw_authoring.strip()
        ):
            raise BrainError("Brain catalog authoring path must be a non-empty string or null.")
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
        source = str(raw["source"])
        authoring = (
            str(raw_authoring)
            if raw_authoring is not None
            else source if not _is_remote_source(source) else None
        )
        brains.append(
            InstalledBrain(
                id=str(raw["id"]),
                slug=slug,
                name=str(raw["name"]),
                source=source,
                checkout=checkout,
                commit=str(raw["commit"]),
                authoring=authoring,
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


def _is_remote_source(source: str) -> bool:
    return "://" in source or SCP_REMOTE.fullmatch(source) is not None


def _require_empty_repository(
    executable: str,
    repository: Path,
    *,
    initialize: bool = False,
) -> bool:
    """Require a standalone unborn repository with no worktree content."""

    entries = list(repository.iterdir())
    git_directory = repository / ".git"
    created_git = False
    if not git_directory.exists():
        if entries:
            raise BrainError("Brain init requires an empty directory or empty Git repository.")
        if not initialize:
            raise BrainError("The cloned source is not a Git repository.")
        _run_git(executable, "init", "--quiet", "--initial-branch=main", str(repository))
        created_git = True
    elif git_directory.is_symlink() or not git_directory.is_dir():
        raise BrainError("Brain init requires a standalone Git repository.")
    if any(entry.name != ".git" for entry in repository.iterdir()):
        raise BrainError("Brain init requires a repository with no existing files.")
    top_level = _run_git(
        executable, "-C", str(repository), "rev-parse", "--show-toplevel"
    ).strip()
    if Path(top_level).resolve() != repository.resolve():
        raise BrainError("Brain init repository root could not be verified.")
    if _git_has_head(executable, repository):
        raise BrainError("Brain init requires a repository with no commits.")
    if _run_git(
        executable,
        "-C",
        str(repository),
        "status",
        "--porcelain",
        "--untracked-files=all",
    ).strip():
        raise BrainError("Brain init requires a clean repository with no existing files.")
    _run_git(
        executable,
        "-C",
        str(repository),
        "symbolic-ref",
        "HEAD",
        "refs/heads/main",
    )
    return created_git


def _write_validate_and_commit(
    executable: str,
    repository: Path,
    manifest_payload: Mapping[str, Any],
    *,
    as_of: str | None,
) -> ValidationReport:
    bundle = repository / "knowledge"
    bundle.mkdir()
    _write_yaml(repository / "brain.yaml", manifest_payload)
    _write_yaml(
        bundle / ".core-kb.yaml",
        {
            "profile": "core-kb/0.1",
            "okf": {
                "version": DoubleQuotedScalarString("0.2"),
                "commit": "374e0bc4c644310ff56cdf9c0fe81eccdec862b0",
            },
            "active_types": [
                "concept",
                "decision",
                "procedure",
                "source-summary",
                "question",
            ],
            "default_sensitivity": "internal",
            "inbox_review_days": 30,
            "documented_extensions": [],
            "freshness_days": {"procedure": 180, "policy": 365, "system": 90},
            "authorized_reviewers": {
                "decision": [],
                "procedure": [],
                "policy": [],
                "system": [],
            },
        },
    )
    name = str(manifest_payload["name"])
    markdown_name = (
        name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
    )
    (bundle / "index.md").write_text(
        f'---\nokf_version: "0.2"\n---\n\n# {markdown_name}\n\n'
        "This brain is ready for governed organizational knowledge.\n\n"
        "<!-- portable-kb:index:start -->\n"
        "No current knowledge is indexed in this scope.\n\n"
        "<!-- portable-kb:index:end -->\n",
        encoding="utf-8",
    )
    log_date = date.fromisoformat(as_of) if as_of is not None else date.today()
    (bundle / "log.md").write_text(
        f"# {markdown_name} update log\n\n## {log_date.isoformat()}\n\n"
        "* **Initialization**: Created the empty governed knowledge bundle.\n",
        encoding="utf-8",
    )
    report = validate_bundle(bundle, as_of=as_of)
    if not report.profile_passes:
        codes = ", ".join(finding.code for finding in report.errors[:8])
        raise BrainError(f"Generated knowledge bundle failed validation: {codes}")
    _run_git(
        executable,
        "-C",
        str(repository),
        "add",
        "--force",
        "--",
        "brain.yaml",
        "knowledge/.core-kb.yaml",
        "knowledge/index.md",
        "knowledge/log.md",
    )
    commit_arguments = [
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
    ]
    if not _git_identity_is_configured(executable, repository):
        commit_arguments.extend(
            [
                "-c",
                "user.name=Portable KB",
                "-c",
                "user.email=portable-kb@localhost.invalid",
            ]
        )
    _run_git(
        executable,
        *commit_arguments,
        "-C",
        str(repository),
        "commit",
        "--quiet",
        "--no-verify",
        "-m",
        f"Initialize {name} brain",
    )
    commit = _run_git(executable, "-C", str(repository), "rev-parse", "HEAD").strip()
    if not COMMIT.fullmatch(commit):
        raise BrainError("Git returned an invalid initial commit identifier.")
    return report


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(payload, stream)


def _git_has_head(executable: str, repository: Path) -> bool:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            [executable, "-C", str(repository), "rev-parse", "--verify", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BrainError("Git repository state could not be checked.") from exc
    if completed.returncode == 0:
        return True
    if completed.returncode in {1, 128}:
        return False
    raise BrainError("Git repository state could not be checked.")


def _git_identity_is_configured(executable: str, repository: Path) -> bool:
    for key in ("user.name", "user.email"):
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        try:
            completed = subprocess.run(
                [executable, "-C", str(repository), "config", "--get", key],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BrainError("Git author identity could not be checked.") from exc
        if completed.returncode != 0 or not completed.stdout.strip():
            return False
    return True


def _push_initial_commit(executable: str, repository: Path) -> None:
    _run_git(
        executable,
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(repository),
        "push",
        "--quiet",
        "--set-upstream",
        "origin",
        "HEAD:refs/heads/main",
    )


def _git_remote_exists(executable: str, repository: Path, remote: str) -> bool:
    names = _run_git(executable, "-C", str(repository), "remote").splitlines()
    return remote in names


def _github_repository_from_source(source: str) -> str | None:
    value = source.strip()
    path: str | None = None
    if value.startswith("git@github.com:"):
        path = value.removeprefix("git@github.com:")
    elif "://" in value:
        parsed = urlsplit(value)
        if parsed.hostname == "github.com":
            path = parsed.path.lstrip("/")
    if path is None:
        return None
    return path.removesuffix(".git").rstrip("/").casefold()


def _run_gh(executable: str, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GH_PROMPT_DISABLED"] = "1"
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
        raise BrainError("GitHub publication could not complete.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "failed"
        raise BrainError(f"GitHub publication failed: {detail}")
    return completed.stdout


def _remove_uncommitted_brain(
    executable: str,
    repository: Path,
    *,
    remove_git: bool,
) -> None:
    if not remove_git:
        with suppress(BrainError):
            _run_git(
                executable,
                "-C",
                str(repository),
                "rm",
                "--cached",
                "--recursive",
                "--force",
                "--ignore-unmatch",
                "--",
                "brain.yaml",
                "knowledge",
            )
    shutil.rmtree(repository / "knowledge", ignore_errors=True)
    (repository / "brain.yaml").unlink(missing_ok=True)
    if remove_git:
        shutil.rmtree(repository / ".git", ignore_errors=True)


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
