"""Bounded local JSONL transport for the packaged Tantivy sidecar."""
from __future__ import annotations

import contextlib
import json
import os
import selectors
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .search_provider import SearchError

ENGINE_VERSION = "tantivy-0.25.0/keyword-1"
MAX_REQUEST_BYTES = 65_536
MAX_RESPONSE_BYTES = 1_048_576


def executable(command: str) -> str:
    if command == "pkb-search" and getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "pkb-search"
        if bundled.is_file() and not bundled.is_symlink():
            return str(bundled)
    found = shutil.which(command)
    if found is None:
        raise SearchError("Tantivy sidecar was not found. Install the standalone pkb release, "
                          "or put pkb-search on PATH for a Python installation.")
    return found


class NativeSidecar:
    """Keep generation leases alive until Python finishes canonical remapping."""

    def __init__(self, command: str) -> None:
        self.command = executable(command)
        try:
            self.process = subprocess.Popen(
                [self.command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise SearchError("Cannot start the Tantivy sidecar.") from exc
        self.buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            if self.call({"op": "status"}).get("version") != ENGINE_VERSION:
                raise SearchError("Tantivy sidecar version is incompatible; reinstall pkb.")
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def call(self, request: dict[str, Any], *, timeout: float = 120) -> dict[str, Any]:
        payload = (json.dumps({"protocol_version": 1, **request}) + "\n").encode()
        if len(payload) > MAX_REQUEST_BYTES:
            raise SearchError("Native search request exceeds 64 KiB.")
        try:
            self.process.stdin.write(payload)
            self.process.stdin.flush()
            deadline = time.monotonic() + timeout
            while b"\n" not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self.selector.select(remaining):
                    raise SearchError("Tantivy sidecar timed out.")
                chunk = os.read(self.process.stdout.fileno(), 65_536)
                if not chunk:
                    raise SearchError("Tantivy sidecar exited without a response.")
                self.buffer.extend(chunk)
                if len(self.buffer) > MAX_RESPONSE_BYTES:
                    raise SearchError("Native search response exceeds 1 MiB.")
            raw, _, tail = self.buffer.partition(b"\n")
            self.buffer = bytearray(tail)
            response = json.loads(raw)
            if not isinstance(response, dict) or type(response.get("protocol_version")) is not int or response.get("protocol_version") != 1:
                raise SearchError("Invalid native search response.")
            if response.get("ok") is not True:
                raise SearchError(f"Tantivy: {response.get('error', 'invalid response')}")
            result = response.get("result")
            if not isinstance(result, dict):
                raise SearchError("Invalid native search result.")
            return result
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SearchError("Cannot communicate with the Tantivy sidecar.") from exc

    def close(self) -> None:
        self.selector.close()
        with contextlib.suppress(OSError):
            self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()
