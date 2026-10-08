from __future__ import annotations

import hashlib
import http.server
import importlib.util
import io
import os
import platform
import subprocess
import sys
import tarfile
import threading
from functools import partial
from pathlib import Path

import pytest

from portable_kb import __version__


@pytest.mark.parametrize("stale", ["code", "skill", "missing-module", "schema"])
def test_standalone_build_rejects_stale_installed_inputs(tmp_path: Path, stale: str) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts/build_standalone.py"
    spec = importlib.util.spec_from_file_location("standalone_build_trial", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repository, installed = tmp_path / "repository", tmp_path / "installed"
    pairs = (
        ("src/portable_kb/links.py", "links.py"),
        (".agents/skills/portable-kb/SKILL.md", "skills/portable-kb/SKILL.md"),
        ("schemas/knowledge-item.schema.yaml", "schemas/knowledge-item.schema.yaml"),
    )
    for source, target in pairs:
        for path in (repository / source, installed / target):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("current build input\n")
    module.require_current_package(repository, installed)
    target = installed / {"code": "links.py", "missing-module": "links.py",
                          "skill": "skills/portable-kb/SKILL.md",
                          "schema": "schemas/knowledge-item.schema.yaml"}[stale]
    if stale == "missing-module":
        target.unlink()
    else:
        target.write_text("previous build input\n")
    with pytest.raises(RuntimeError, match="Installed build input differs.*current wheel"):
        module.require_current_package(repository, installed)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        pass


def _subprocess_environment(**updates: str) -> dict[str, str]:
    """Return an environment that does not start a nested pytest-cov session."""

    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("COV_CORE_")
    }
    environment.update(updates)
    return environment


def _release_target() -> str:
    operating_system = {"Darwin": "darwin", "Linux": "linux"}[platform.system()]
    architecture = {
        "x86_64": "x86_64",
        "AMD64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }[platform.machine()]
    return f"{operating_system}-{architecture}"


def _write_fake_release(
    root: Path, *, executable_version: str = __version__
) -> tuple[Path, Path]:
    release = root / f"v{__version__}"
    release.mkdir(parents=True, exist_ok=True)
    archive = release / f"pkb-v{__version__}-{_release_target()}.tar.gz"
    executable = f"#!/bin/sh\necho 'pkb {executable_version}'\n".encode()
    info = tarfile.TarInfo("pkb")
    info.mode = 0o755
    info.size = len(executable)
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.addfile(info, io.BytesIO(executable))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksums = release / "SHA256SUMS"
    checksums.write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    return archive, checksums


@pytest.mark.skipif(
    platform.system() not in {"Darwin", "Linux"}, reason="installer targets macOS and Linux"
)
def test_installer_verifies_release_preserves_failure_and_uninstalls(tmp_path: Path) -> None:
    archive, checksums = _write_fake_release(tmp_path / "releases")
    handler = partial(QuietHandler, directory=str(tmp_path / "releases"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    install_dir = tmp_path / "bin"
    environment = _subprocess_environment(
        PKB_INSTALL_DIR=str(install_dir),
        PKB_RELEASE_BASE_URL=f"http://127.0.0.1:{server.server_port}",
        PKB_VERSION=__version__,
    )
    try:
        installed = subprocess.run(
            ["sh", "install"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert f"Installed pkb {__version__}" in installed.stdout
        target = install_dir / "pkb"
        original = target.read_bytes()

        checksums.write_text(f"{'0' * 64}  {archive.name}\n", encoding="utf-8")
        rejected = subprocess.run(
            ["sh", "install"], capture_output=True, text=True, env=environment
        )
        assert rejected.returncode == 1
        assert "checksum verification failed" in rejected.stderr
        assert target.read_bytes() == original

        _write_fake_release(tmp_path / "releases", executable_version="9.9.9")
        wrong_version = subprocess.run(
            ["sh", "install"], capture_output=True, text=True, env=environment
        )
        assert wrong_version.returncode == 1
        assert "unexpected version" in wrong_version.stderr
        assert target.read_bytes() == original

        removed = subprocess.run(
            ["sh", "install", "--uninstall"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert "Removed" in removed.stdout
        assert not target.exists()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_release_version_matches_cli() -> None:
    release = subprocess.run(
        [sys.executable, "scripts/release_info.py"],
        check=True,
        capture_output=True,
        text=True,
        env=_subprocess_environment(),
    )
    assert release.stdout == f"version={__version__}\ntag=v{__version__}\n"

    cli = subprocess.run(
        [sys.executable, "-m", "portable_kb", "--version"],
        check=True,
        capture_output=True,
        text=True,
        env=_subprocess_environment(),
    )
    assert cli.stdout.strip() == f"pkb {__version__}"
