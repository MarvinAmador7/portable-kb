"""Native store contract: process death, competing writers, and live readers."""
from __future__ import annotations

import errno
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from benchmarks.corpus import synthetic_corpus
from benchmarks.search import Worker


@pytest.fixture
def native_command():
    executable = os.environ.get("PKB_TANTIVY_COMMAND")
    if not executable:
        pytest.skip("set PKB_TANTIVY_COMMAND to exercise native generation recovery")
    return [executable]


def rebuild(worker, store, records):
    return worker.call(
        {"op": "rebuild", "index_path": str(store), "records_path": str(records)}
    )["result"]["manifest"]


def query(worker, store):
    return worker.call(
        {
            "op": "query_store",
            "index_path": str(store),
            "query": "Aurora000000",
            "tokens": ["Aurora000000"],
            "limit": 10,
        }
    )["result"]


def until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("native process did not reach the expected build boundary")


@pytest.mark.skipif(os.name != "posix", reason="process interruption fixture uses a FIFO")
@pytest.mark.parametrize("published", [False, True])
def test_killed_builder_releases_lock_and_preserves_published_reader(
    tmp_path, native_command, published
):
    synthetic_corpus(tmp_path / "corpus", 16)
    records = tmp_path / "corpus/records.jsonl"
    store = tmp_path / "store"
    reader = Worker(native_command)
    builder = Worker(native_command)
    contender = Worker(native_command)
    pipe_fd = None
    try:
        if published:
            old = rebuild(builder, store, records)
            before = (store / "CURRENT.json").read_bytes()
            assert query(reader, store)["manifest"] == old
        fifo = tmp_path / "slow-export"
        os.mkfifo(fifo)
        request = {
            "protocol_version": 1,
            "op": "rebuild",
            "index_path": str(store),
            "records_path": str(fifo),
        }
        builder.process.stdin.write((json.dumps(request) + "\n").encode())
        builder.process.stdin.flush()
        until(lambda: list((store / "generations").glob(".build-*")))

        def open_fifo():
            try:
                return os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError as error:
                if error.errno == errno.ENXIO:
                    return None
                raise

        pipe_fd = until(open_fifo)
        # Keep the input stream open so the builder remains inside the actual
        # snapshot copy. SIGKILL bypasses all Rust cleanup and destructors.
        os.write(pipe_fd, records.read_bytes().splitlines(keepends=True)[0])
        until(lambda: any(
            path.stat().st_size > 0
            for path in (store / "generations").glob(".build-*/records.jsonl")
        ))
        with pytest.raises(ValueError, match="writer lock"):
            contender.call({"op": "recover", "index_path": str(store)})
        with pytest.raises(ValueError, match="writer lock"):
            rebuild(contender, store, records)
        if published:
            assert query(reader, store)["manifest"] == old
            assert query(contender, store)["manifest"] == old
        else:
            with pytest.raises(ValueError, match="no published"):
                query(reader, store)
        builder.process.kill()
        builder.process.wait(timeout=5)
        os.close(pipe_fd)
        pipe_fd = None
        recovered = contender.call({"op": "recover", "index_path": str(store)})["result"]
        assert recovered["removed_staging_entries"] == 1
        assert not list((store / "generations").glob(".build-*"))
        if published:
            assert recovered["current"] == old
            assert (store / "CURRENT.json").read_bytes() == before
            assert query(reader, store)["manifest"] == old
        else:
            assert recovered["current"] is None
        new = rebuild(contender, store, records)
        refreshed = query(reader, store)
        assert refreshed["manifest"] == new
        assert refreshed["opened"] is True
        assert refreshed["hits"]
    finally:
        if pipe_fd is not None:
            os.close(pipe_fd)
        if builder.process.poll() is None:
            builder.process.kill()
        for worker in (reader, builder, contender):
            worker.close()


def test_concurrent_readers_refresh_and_citations_follow_the_same_generation(
    tmp_path, native_command
):
    synthetic_corpus(tmp_path / "corpus", 16)
    source = tmp_path / "corpus/records.jsonl"
    original = [json.loads(line) for line in source.read_text().splitlines()]
    store = tmp_path / "store"
    builder = Worker(native_command)
    readers = [Worker(native_command), Worker(native_command)]
    try:
        manifest = rebuild(builder, store, source)
        assert query(readers[0], store)["opened"] is True
        assert query(readers[0], store)["opened"] is False
        old_records = Path(query(readers[0], store)["records_path"])
        old_snapshot = old_records.read_bytes()
        source.write_text("invalid\n")
        with pytest.raises(ValueError):
            rebuild(builder, store, source)
        assert query(readers[0], store)["manifest"] == manifest
        assert old_records.read_bytes() == old_snapshot
        # Reader responses must contain IDs and record mappings from one
        # generation even while a separate process publishes the next one.
        with ThreadPoolExecutor(max_workers=3) as executor:
            for revision in range(3):
                rows = [dict(row, section_id=f"revision-{revision}-{row['section_id']}")
                        for row in original[:2]]
                source.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
                future = executor.submit(rebuild, builder, store, source)

                def check_reader(reader):
                    for _ in range(20):
                        response = query(reader, store)
                        snapshot = {
                            json.loads(line)["section_id"]
                            for line in Path(response["records_path"]).read_text().splitlines()
                        }
                        assert all(hit["section_id"] in snapshot for hit in response["hits"])
                        assert len(response["hits"]) == 2

                checks = [executor.submit(check_reader, reader) for reader in readers]
                manifest = future.result(timeout=10)
                for checked in checks:
                    checked.result(timeout=10)
                for reader in readers:
                    response = query(reader, store)
                    assert response["manifest"] == manifest
                    assert all(hit["section_id"].startswith(f"revision-{revision}-")
                               for hit in response["hits"])
        assert old_records.read_bytes() == old_snapshot
        assert manifest["record_count"] == 2  # Deleted sections do not survive a full rebuild.
    finally:
        for worker in [builder, *readers]:
            worker.close()


def test_cached_reader_rejects_version_changes_and_future_manifests(tmp_path, native_command):
    synthetic_corpus(tmp_path / "corpus", 16)
    source = tmp_path / "corpus/records.jsonl"
    store = tmp_path / "store"
    worker = Worker(native_command)
    try:
        original = rebuild(worker, store, source)
        query(worker, store)
        pointer = store / "CURRENT.json"
        for field, value in [("engine_version", "older-engine"), ("index_format", 99)]:
            pointer.write_text(json.dumps({**original, field: value}))
            with pytest.raises(ValueError, match="incompatible index version"):
                query(worker, store)
            with pytest.raises(ValueError, match="incompatible index version"):
                worker.call({"op": "recover", "index_path": str(store)})
            original = rebuild(worker, store, source)
            assert query(worker, store)["manifest"] == original
        pointer.write_text(json.dumps({**original, "schema_version": 2}))
        before = pointer.read_bytes()
        with pytest.raises(ValueError, match="unsupported"):
            query(worker, store)
        with pytest.raises(ValueError, match="unsupported"):
            rebuild(worker, store, source)
        assert pointer.read_bytes() == before
    finally:
        worker.close()


def cleanup(worker, store):
    return worker.call({"op": "cleanup", "index_path": str(store)})["result"]


def test_cleanup_protects_each_reader_and_reclaims_after_reader_process_death(
    tmp_path, native_command
):
    synthetic_corpus(tmp_path / "corpus", 16)
    records = tmp_path / "corpus/records.jsonl"
    store = tmp_path / "store"
    manager = Worker(native_command)
    readers = [Worker(native_command), Worker(native_command)]
    try:
        old = rebuild(manager, store, records)
        snapshots = [Path(query(reader, store)["records_path"]) for reader in readers]
        before = snapshots[0].read_bytes()
        new = rebuild(manager, store, records)
        pointer = (store / "CURRENT.json").read_bytes()
        result = cleanup(manager, store)
        assert result["pinned_generations"] == [old["generation"]]
        assert result["removed_generations"] == []
        assert snapshots[0].read_bytes() == before
        readers[0].process.kill()
        readers[0].process.wait(timeout=5)
        assert cleanup(manager, store)["pinned_generations"] == [old["generation"]]
        assert snapshots[1].read_bytes() == before
        readers[1].process.kill()
        readers[1].process.wait(timeout=5)
        result = cleanup(manager, store)
        assert result["removed_generations"] == [old["generation"]]
        assert not snapshots[0].exists()
        assert (store / "CURRENT.json").read_bytes() == pointer
        assert query(manager, store)["manifest"] == new
        assert cleanup(manager, store)["removed_generations"] == []
    finally:
        for worker in [manager, *readers]:
            worker.close()


def test_refresh_and_explicit_release_allow_old_generation_cleanup(tmp_path, native_command):
    synthetic_corpus(tmp_path / "corpus", 16)
    records = tmp_path / "corpus/records.jsonl"
    store = tmp_path / "store"
    manager = Worker(native_command)
    reader = Worker(native_command)
    try:
        first = rebuild(manager, store, records)
        query(reader, store)
        second = rebuild(manager, store, records)
        assert cleanup(manager, store)["pinned_generations"] == [first["generation"]]
        assert query(reader, store)["manifest"] == second
        assert cleanup(manager, store)["removed_generations"] == [first["generation"]]
        third = rebuild(manager, store, records)
        assert cleanup(manager, store)["pinned_generations"] == [second["generation"]]
        released = reader.call({"op": "release_store", "index_path": str(store)})["result"]
        assert released == {"released": True}
        assert cleanup(manager, store)["removed_generations"] == [second["generation"]]
        assert query(reader, store)["manifest"] == third
    finally:
        manager.close()
        reader.close()


def test_cleanup_during_rebuilds_keeps_each_query_record_snapshot(tmp_path, native_command):
    synthetic_corpus(tmp_path / "corpus", 16)
    records = tmp_path / "corpus/records.jsonl"
    store = tmp_path / "store"
    manager = Worker(native_command)
    cleaner = Worker(native_command)
    readers = [Worker(native_command), Worker(native_command)]
    try:
        rebuild(manager, store, records)
        with ThreadPoolExecutor(max_workers=3) as executor:
            for _ in range(4):
                rebuild(manager, store, records)

                def check_reader(reader):
                    for _ in range(20):
                        response = query(reader, store)
                        snapshot = {json.loads(line)["section_id"]
                                    for line in Path(response["records_path"]).read_text().splitlines()}
                        assert all(hit["section_id"] in snapshot for hit in response["hits"])

                checks = [executor.submit(check_reader, reader) for reader in readers]
                sweep = executor.submit(cleanup, cleaner, store)
                sweep.result(timeout=10)
                for checked in checks:
                    checked.result(timeout=10)
        for reader in readers:
            reader.call({"op": "release_store", "index_path": str(store)})
        cleanup(cleaner, store)
        assert len(list((store / "generations").glob("gen-*"))) == 1
        assert query(manager, store)["hits"]
    finally:
        for worker in [manager, cleaner, *readers]:
            worker.close()
