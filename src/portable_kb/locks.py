"""Small cross-process locks for local Portable KB mutations."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOCK_FILENAME = ".portable-kb-operation.lock"
INVALID_LOCK_STALE_SECONDS = 60 * 60


class LockError(RuntimeError):
    """Raised when a local mutation lock cannot be acquired safely."""


def inspect_operation_lock(root: Path) -> dict[str, Any]:
    """Describe a lock without creating or changing local state."""

    path = root.expanduser().absolute() / LOCK_FILENAME
    if not path.exists() and not path.is_symlink():
        return {"locked": False, "path": str(path), "stale": False}
    if path.is_symlink() or not path.is_file():
        return {
            "locked": True,
            "path": str(path),
            "stale": False,
            "safe": False,
            "error": "Lock path is not a regular file.",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        payload = None
    age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    stale = _is_stale(payload, age_seconds)
    result: dict[str, Any] = {
        "locked": True,
        "path": str(path),
        "stale": stale,
        "safe": True,
        "age_seconds": round(age_seconds, 3),
    }
    if isinstance(payload, Mapping):
        for key in ("operation", "pid", "hostname", "created_at"):
            if key in payload:
                result[key] = payload[key]
    else:
        result["error"] = "Lock metadata is invalid."
    return result


@contextmanager
def operation_lock(
    root: Path,
    operation: str,
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> Iterator[Path]:
    """Serialize mutations that share a local state root."""

    target = root.expanduser().absolute()
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise LockError(f"Local state lock root is unsafe: {target}")
    target.mkdir(parents=True, exist_ok=True)
    path = target / LOCK_FILENAME
    token = uuid.uuid4().hex
    payload = {
        "schema_version": 1,
        "token": token,
        "operation": operation,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    encoded = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    started = time.monotonic()
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            status = inspect_operation_lock(target)
            if status.get("safe") is False:
                raise LockError(
                    f"Local state lock path is unsafe and must be inspected manually: {path}"
                ) from None
            if status.get("safe") and status.get("stale") and _remove_stale_lock(path, status):
                continue
            if time.monotonic() - started >= timeout:
                owner = status.get("operation", "another operation")
                raise LockError(
                    f"Timed out waiting for {owner!r} to release local state lock: {path}"
                ) from None
            time.sleep(poll_interval)
            continue
        except OSError as exc:
            raise LockError(f"Could not create local state lock: {path}") from exc
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        break
    try:
        yield path
    finally:
        _release_owned_lock(path, token)


def _is_stale(payload: object, age_seconds: float) -> bool:
    if not isinstance(payload, Mapping):
        return age_seconds >= INVALID_LOCK_STALE_SECONDS
    hostname = payload.get("hostname")
    pid = payload.get("pid")
    if hostname != socket.gethostname() or not isinstance(pid, int) or pid <= 0:
        return False
    return not _pid_is_alive(pid)


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if sys.platform == "linux":
        # kill(pid, 0) also succeeds for an unreaped zombie. Such a process
        # has exited and cannot release its lock or resume a mutation.
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            fields = stat.rsplit(")", 1)[1].split()
        except (OSError, UnicodeError, IndexError):
            return True  # Unknown ownership must remain protected.
        if fields and fields[0] in {"Z", "X"}:
            return False
    return True


def _release_owned_lock(path: Path, token: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return
    if isinstance(payload, Mapping) and payload.get("token") == token:
        path.unlink(missing_ok=True)


def _remove_stale_lock(path: Path, expected: Mapping[str, Any]) -> bool:
    """Remove a stale lock only while its observable ownership remains unchanged."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not _is_stale(payload, age_seconds):
        return False
    for key in ("token", "pid", "hostname", "operation"):
        if (
            key in expected
            and isinstance(payload, Mapping)
            and payload.get(key) != expected.get(key)
        ):
            return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
