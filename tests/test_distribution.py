from __future__ import annotations

import hashlib
import http.server
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


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        pass


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
    environment = {
        **os.environ,
        "PKB_INSTALL_DIR": str(install_dir),
        "PKB_RELEASE_BASE_URL": f"http://127.0.0.1:{server.server_port}",
        "PKB_VERSION": __version__,
    }
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
    )
    assert release.stdout == f"version={__version__}\ntag=v{__version__}\n"

    cli = subprocess.run(
        [sys.executable, "-m", "portable_kb", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert cli.stdout.strip() == f"pkb {__version__}"
