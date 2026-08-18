from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest

from portable_kb.locks import LockError, inspect_operation_lock, operation_lock


def test_operation_lock_is_visible_and_released(tmp_path: Path) -> None:
    assert inspect_operation_lock(tmp_path)["locked"] is False

    with operation_lock(tmp_path, "test mutation") as path:
        status = inspect_operation_lock(tmp_path)
        assert path.is_file()
        assert status["locked"] is True
        assert status["stale"] is False
        assert status["operation"] == "test mutation"
        assert status["pid"] == os.getpid()

    assert inspect_operation_lock(tmp_path)["locked"] is False


def test_operation_lock_times_out_while_owned(tmp_path: Path) -> None:
    with (
        operation_lock(tmp_path, "first"),
        pytest.raises(LockError, match="first"),
        operation_lock(tmp_path, "second", timeout=0.01, poll_interval=0.001),
    ):
        pass


def test_operation_lock_recovers_dead_same_host_owner(tmp_path: Path) -> None:
    lock_path = tmp_path / ".portable-kb-operation.lock"
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "token": "abandoned",
                "operation": "interrupted",
                "pid": 2_147_483_647,
                "hostname": socket.gethostname(),
            }
        ),
        encoding="utf-8",
    )

    with operation_lock(tmp_path, "replacement", timeout=0.1):
        assert inspect_operation_lock(tmp_path)["operation"] == "replacement"

    assert not lock_path.exists()


def test_operation_lock_does_not_remove_foreign_host_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / ".portable-kb-operation.lock"
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "token": "remote",
                "operation": "remote operation",
                "pid": 2_147_483_647,
                "hostname": "another-host.example",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(LockError, match="remote operation"), operation_lock(
        tmp_path, "replacement", timeout=0
    ):
        pass

    assert lock_path.exists()


def test_operation_lock_rejects_unsafe_lock_path(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("not a lock\n", encoding="utf-8")
    lock_path = tmp_path / ".portable-kb-operation.lock"
    lock_path.symlink_to(target)

    status = inspect_operation_lock(tmp_path)
    assert status["safe"] is False
    with pytest.raises(LockError, match="unsafe"), operation_lock(
        tmp_path, "replacement", timeout=0
    ):
        pass


def test_inspect_operation_lock_reports_invalid_metadata(tmp_path: Path) -> None:
    lock_path = tmp_path / ".portable-kb-operation.lock"
    lock_path.write_text("not json\n", encoding="utf-8")

    status = inspect_operation_lock(tmp_path)

    assert status["locked"] is True
    assert status["stale"] is False
    assert status["error"] == "Lock metadata is invalid."


def test_operation_lock_rejects_symlink_root(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)

    with pytest.raises(LockError, match="root is unsafe"), operation_lock(linked, "test"):
        pass
