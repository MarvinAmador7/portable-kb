from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest
from typer.testing import CliRunner

from portable_kb.brains import add_brain, remove_brain
from portable_kb.cli import app
from portable_kb.native_sidecar import ENGINE_VERSION, NativeSidecar
from portable_kb.parsing import discover_concepts, parse_concept
from portable_kb.search import index_keyword_brain, search_keyword
from portable_kb.search_provider import SearchError
from portable_kb.settings import (
    SearchMode,
    SearchProvider,
    Settings,
    SettingsError,
    load_settings,
    save_settings,
)
from portable_kb.tantivy_provider import TantivyProvider, _metadata, _records


@pytest.fixture
def native_executable(tmp_path):
    real = os.environ.get("PKB_TANTIVY_COMMAND")
    if real:
        return real
    executable = tmp_path / "pkb-search"
    executable.write_text('''#!/usr/bin/env python3
import json, pathlib, sys, shutil, unicodedata
for raw in sys.stdin:
    try:
        req=json.loads(raw); op=req['op']
        if op == 'status':
            result={'version':'tantivy-0.25.0/keyword-1'}
        elif op == 'rebuild':
            root=pathlib.Path(req['index_path']); root.mkdir(parents=True,exist_ok=True)
            generation='gen-'+str(len(list((root/'generations').glob('gen-*'))))
            target=root/'generations'/generation; target.mkdir(parents=True)
            shutil.copyfile(req['records_path'],target/'records.jsonl')
            result={'manifest':{'schema_version':1,'index_format':2,'engine_version':'tantivy-0.25.0/keyword-1','generation':generation,'record_count':len((target/'records.jsonl').read_text().splitlines()),'lease_version':1,'brain':req['brain']}}
            (root/'CURRENT.json').write_text(json.dumps(result['manifest']))
        elif op == 'prepare_remove':
            result={'prepared':True}
        elif op == 'cleanup':
            result={'removed_generations':[],'pinned_generations':[]}
        elif op == 'query_store':
            root=pathlib.Path(req['index_path']); manifest=json.loads((root/'CURRENT.json').read_text())
            records=root/'generations'/manifest['generation']/'records.jsonl'
            hits=[]; offset=0
            for line in records.read_bytes().splitlines(keepends=True):
                record=json.loads(line); exact=req.get('exact_field')
                text=' '.join(record[k] for k in ('title','description','heading','body'))
                text=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
                match=record[exact]==req['query'] if exact else all(t.lower() in text for t in req['tokens']) and bool(req['tokens'])
                if match: hits.append({'section_id':record['section_id'],'score':1.0,'record_offset':offset})
                offset+=len(line)
            result={'manifest':manifest,'records_path':str(records),'hits':hits[:req['limit']]}
        elif op == 'malformed':
            print('{',flush=True); continue
        elif op == 'crash':
            sys.exit(3)
        else:
            raise ValueError('unsupported operation')
        print(json.dumps({'protocol_version':1,'ok':True,'result':result}),flush=True)
    except Exception as error:
        print(json.dumps({'protocol_version':1,'ok':False,'error':str(error)}),flush=True)
''')
    executable.chmod(0o755)
    return str(executable)


@pytest.fixture
def native_brain(tmp_path, brain_repo_factory, native_executable):
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache",
                        search_provider=SearchProvider.BUILTIN, native_command=native_executable)
    source = brain_repo_factory("native", "urn:uuid:88888888-8888-4888-8888-888888888888")
    brain, _, _ = add_brain(str(source), settings, as_of="2026-08-17")
    return settings, brain


def test_native_index_exact_and_keyword_queries_are_canonical_and_deduplicated(native_brain):
    settings, brain = native_brain
    provider = TantivyProvider(settings)
    assert provider.status()["ok"] is True
    indexed = index_keyword_brain(settings, as_of="2026-08-17")
    assert indexed["provider"] == "builtin"
    assert indexed["concept_count"] == 14
    assert indexed["engine_version"] == ENGINE_VERSION
    bundle = brain.checkout_path(settings) / "knowledge"
    item = parse_concept(discover_concepts(bundle)[0], bundle).item
    for text in (item.id, item.relative_path, "knowledge/" + item.relative_path):
        result = search_keyword(settings, text, as_of="2026-08-17")
        assert len(result["results"]) == 1
        hit = result["results"][0]
        assert hit["item_id"] == item.id
        assert hit["citation"]["commit"] == brain.commit
        assert hit["path"] == item.relative_path
        assert hit["line"] > 1
        assert hit["line_end"] >= hit["line"]
        assert hit["snippet"] in item.source_text
    assert search_keyword(settings, "stale", as_of="2026-08-17")["results"]
    assert search_keyword(settings, "zxqvnotincorpus92817", as_of="2026-08-17")["results"] == []
    rebuilt = index_keyword_brain(settings, as_of="2026-08-17")
    assert rebuilt["generation"] != indexed["generation"]
    assert provider.load_metadata(brain.slug)["generation"] == rebuilt["generation"]


def test_native_snapshot_tampering_fails_canonical_remapping(native_brain):
    settings, brain = native_brain
    indexed = index_keyword_brain(settings, as_of="2026-08-17")
    root = TantivyProvider(settings).index_path(brain.slug)
    records = root / "generations" / indexed["generation"] / "records.jsonl"
    lines = records.read_bytes().splitlines(keepends=True)
    first = json.loads(lines[0])
    # Preserve byte offsets while changing indexed evidence.
    assert b'"body"' in lines[0]
    original = records.read_bytes()
    modified = original.replace(first["title"].encode(), b"X" * len(first["title"].encode()))
    records.write_bytes(modified)
    with pytest.raises(SearchError, match="differs from the canonical"):
        search_keyword(settings, first["item_id"], as_of="2026-08-17")
    records.write_bytes(original)
    checkout = brain.checkout_path(settings)
    (checkout / "knowledge/untracked.md").write_text("dirty")
    before = (root / "CURRENT.json").read_bytes()
    with pytest.raises(SearchError, match="clean, pinned"):
        index_keyword_brain(settings, as_of="2026-08-17")
    assert (root / "CURRENT.json").read_bytes() == before


def test_native_missing_and_stale_metadata_fail_closed(native_brain):
    settings, brain = native_brain
    provider = TantivyProvider(settings)
    with pytest.raises(SearchError, match="unavailable"):
        provider.load_metadata(brain.slug)
    indexed = index_keyword_brain(settings, as_of="2026-08-17")
    root = provider.index_path(brain.slug)
    manifest = json.loads((root / "CURRENT.json").read_text())
    manifest["brain"]["commit"] = "0" * 40
    (root / "CURRENT.json").write_text(json.dumps(manifest))
    with pytest.raises(SearchError, match="stale"):
        search_keyword(settings, "stale", as_of="2026-08-17")
    assert indexed["commit"] == brain.commit
    unavailable = TantivyProvider(replace(settings, native_command="no-such-pkb-sidecar"))
    assert unavailable.status()["ok"] is False


def test_native_settings_doctor_and_cli_use_builtin_without_qmd(native_brain, tmp_path):
    settings, _ = native_brain
    config = save_settings(settings, tmp_path / "config.yaml")
    assert load_settings(config) == settings
    runner = CliRunner()
    indexed = runner.invoke(app, ["search", "index", "--config", str(config),
                                  "--as-of", "2026-08-17", "--json"])
    assert indexed.exit_code == 0, indexed.output
    query = runner.invoke(app, ["search", "query", "stale", "--config", str(config),
                                "--as-of", "2026-08-17", "--json"])
    assert query.exit_code == 0, query.output
    assert json.loads(query.output)["provider"] == "builtin"
    doctor = runner.invoke(app, ["doctor", "--config", str(config), "--json"])
    assert doctor.exit_code == 0, doctor.output
    report = json.loads(doctor.output)
    assert report["search_provider"] == "builtin"
    assert report["search_tool"]["compatible"] is True
    assert report["active_index"]["current"] is True
    with pytest.raises(SettingsError, match="keyword mode only"):
        replace(settings, search_mode=SearchMode.SEMANTIC)


def test_native_transport_reports_malformed_crashed_and_unsupported_responses(native_executable):
    with NativeSidecar(native_executable) as worker, pytest.raises(SearchError):
        worker.call({"op": "malformed"})
    with NativeSidecar(native_executable) as worker, pytest.raises(SearchError):
        worker.call({"op": "crash"})
    with NativeSidecar(native_executable) as worker, pytest.raises(SearchError, match="64 KiB"):
        worker.call({"op": "status", "padding": "x" * 65_536})


def test_native_manifest_and_record_bounds_reject_invalid_evidence(tmp_path):
    with pytest.raises(SearchError, match="incompatible"):
        _metadata({})
    manifest = {"schema_version": 1, "index_format": 2, "lease_version": 1,
                "engine_version": ENGINE_VERSION, "generation": "gen-test", "record_count": 1}
    with pytest.raises(SearchError, match="provenance"):
        _metadata(manifest)
    record = tmp_path / "records.jsonl"
    record.write_text('{"section_id":"section"}\n')
    with pytest.raises(SearchError, match="outside"):
        _records(record, [{"section_id": "section", "record_offset": 1000}])
    with pytest.raises(SearchError, match="does not resolve"):
        _records(record, [{"section_id": "different", "record_offset": 0}])
    record.write_bytes(b"x" * 1_048_577)
    with pytest.raises(SearchError, match="exceeds"):
        _records(record, [{"section_id": "section", "record_offset": 0}])


def test_brain_removal_disposes_native_cache_and_preserves_source(native_brain):
    settings, brain = native_brain
    index_keyword_brain(settings, as_of="2026-08-17")
    root = TantivyProvider(settings).index_path(brain.slug)
    result = remove_brain(brain.slug, settings)
    assert result["removed_index"] is True
    assert result["removed_checkout"] is True
    assert not root.exists()


def test_native_removal_rolls_back_catalog_failure(native_brain, monkeypatch):
    settings, brain = native_brain
    index_keyword_brain(settings, as_of="2026-08-17")
    root = TantivyProvider(settings).index_path(brain.slug)
    before = (root / "CURRENT.json").read_bytes()
    def fail(*args):
        raise OSError("catalog write failed")
    monkeypatch.setattr("portable_kb.brains.save_catalog", fail)
    with pytest.raises(OSError, match="catalog write failed"):
        remove_brain(brain.slug, settings)
    assert (root / "CURRENT.json").read_bytes() == before
    assert brain.checkout_path(settings).exists()
    assert search_keyword(settings, "stale", as_of="2026-08-17")["results"]


@pytest.mark.parametrize("corruption", ["brain", "records_path", "hits", "duplicate", "nan", "offset"])
def test_native_discovery_payload_is_untrusted(native_brain, monkeypatch, corruption):
    settings, _ = native_brain
    index_keyword_brain(settings, as_of="2026-08-17")
    original = NativeSidecar.call

    def corrupt(self, request, **kwargs):
        result = original(self, request, **kwargs)
        if request["op"] == "query_store":
            if corruption == "brain":
                result["manifest"]["brain"]["commit"] = "0" * 40
            elif corruption == "records_path":
                result["records_path"] = "/tmp/outside-records"
            elif corruption == "hits":
                result["hits"] = {}
            elif corruption == "duplicate":
                result["hits"] = [result["hits"][0], result["hits"][0]]
            elif corruption == "nan":
                result["hits"][0]["score"] = float("nan")
            else:
                result["hits"][0]["record_offset"] = -1
        return result

    monkeypatch.setattr(NativeSidecar, "call", corrupt)
    with pytest.raises(SearchError):
        search_keyword(settings, "stale", as_of="2026-08-17")


def test_native_cleanup_failure_reports_successful_publication(native_brain, monkeypatch):
    settings, _ = native_brain
    original = NativeSidecar.call

    def fail_cleanup(self, request, **kwargs):
        if request["op"] == "cleanup":
            raise SearchError("another writer is active")
        return original(self, request, **kwargs)

    monkeypatch.setattr(NativeSidecar, "call", fail_cleanup)
    published = index_keyword_brain(settings, as_of="2026-08-17")
    assert published["ok"] is True
    assert "another writer" in published["cleanup"]["error"]
    assert search_keyword(settings, "stale", as_of="2026-08-17")["results"]


def test_native_unsafe_and_corrupt_cache_paths_fail_closed(native_brain, tmp_path):
    settings, brain = native_brain
    provider = TantivyProvider(settings)
    root = provider.index_path(brain.slug)
    root.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SearchError, match="unsafe directory"):
        provider.load_metadata(brain.slug)
    root.unlink()
    index_keyword_brain(settings, as_of="2026-08-17")
    (root / "CURRENT.json").write_text("{")
    with pytest.raises(SearchError, match="manifest is invalid"):
        provider.load_metadata(brain.slug)


@pytest.mark.parametrize("payload", ["{", "[]", '{"protocol_version":2}',
                                     '{"protocol_version":true,"ok":true,"result":{}}',
                                     '{"protocol_version":1,"ok":true,"result":[]}'])
def test_native_transport_rejects_invalid_wire_payloads(tmp_path, payload):
    script = tmp_path / "wire-worker"
    script.write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        "for index, line in enumerate(sys.stdin):\n"
        f"    response = {payload!r} if index else json.dumps({{'protocol_version':1,'ok':True,'result':{{'version':{ENGINE_VERSION!r}}}}})\n"
        "    print(response, flush=True)\n"
    )
    script.chmod(0o755)
    with NativeSidecar(str(script)) as worker, pytest.raises(SearchError):
        worker.call({"op": "query"})


def test_native_transport_timeout_and_oversized_output_are_bounded(tmp_path):
    for action in ("import time; time.sleep(10)", "print('x'*1048577, flush=True)"):
        script = tmp_path / "slow-worker"
        script.write_text(
            "#!/usr/bin/env python3\nimport json, sys\n"
            "for index, line in enumerate(sys.stdin):\n"
            "    if index:\n"
            f"        {action}\n"
            "    else:\n"
            f"        print(json.dumps({{'protocol_version':1,'ok':True,'result':{{'version':{ENGINE_VERSION!r}}}}}), flush=True)\n"
        )
        script.chmod(0o755)
        with NativeSidecar(str(script)) as worker, pytest.raises(SearchError, match="timed out|exceeds"):
            worker.call({"op": "query"}, timeout=0.05)


def test_native_setup_defaults_and_explicit_qmd_preserve_configuration(tmp_path, native_executable):
    runner = CliRunner()
    config = tmp_path / "config.yaml"
    result = runner.invoke(app, ["setup", "--non-interactive", "--config", str(config),
                                 "--data-dir", str(tmp_path / "data"),
                                 "--cache-dir", str(tmp_path / "cache"),
                                 "--search-command", native_executable])
    assert result.exit_code == 0, result.output
    assert load_settings(config).search_provider is SearchProvider.BUILTIN
    rejected = runner.invoke(app, ["setup", "--non-interactive", "--config", str(config),
                                   "--force", "--search-mode", "semantic"])
    assert rejected.exit_code != 0
    assert "keyword mode only" in rejected.output
    qmd = Settings(data_dir=tmp_path / "qmd-data", cache_dir=tmp_path / "qmd-cache",
                   qmd_command="custom-qmd")
    save_settings(qmd, config, overwrite=True)
    preserved = runner.invoke(app, ["setup", "--non-interactive", "--config", str(config), "--force"])
    assert preserved.exit_code == 0, preserved.output
    assert load_settings(config) == qmd


def test_named_brain_recovery_and_saved_item_actions_preserve_scope(
    native_brain, brain_repo_factory,
):
    from portable_kb.authoring import (
        GenerationMethod,
        plan_knowledge_update,
        save_knowledge_update,
    )
    from portable_kb.brains import load_catalog
    from portable_kb.search import get_knowledge_item

    settings, primary = native_brain
    source = brain_repo_factory("alternate", "urn:uuid:99999999-9999-4999-8999-999999999999")
    alternate, _, _ = add_brain(str(source), settings, as_of="2026-08-17")
    identity = "urn:uuid:0adaf3c7-c3e0-4cdc-85f4-90438dd72020"
    original = get_knowledge_item(settings, identity, as_of="2026-08-17")
    update = plan_knowledge_update(
        settings, identity, slug=alternate.slug, actor="openai/codex",
        method=GenerationMethod.AGENT_GENERATED,
        body="# Review stale knowledge\n\n## Steps\n\nUse the alternate quarantine queue.\n",
        timestamp="2026-08-17T12:00:00Z", as_of="2026-08-17",
    )
    saved = save_knowledge_update(settings, update, as_of="2026-08-17").as_dict()
    assert saved["citation"]["brain_slug"] == alternate.slug
    assert saved["get_command"] == ["pkb", "get", identity, "--brain", alternate.slug, "--json"]
    assert saved["reindex_command"] == ["pkb", "search", "index", alternate.slug, "--json"]
    assert saved["needs_reindex"] is True and saved["search_ready"] is False
    selected = get_knowledge_item(settings, identity, alternate.slug, as_of="2026-08-17")
    assert selected["citation"] == saved["citation"]
    assert "quarantine queue" in selected["item"]["body"]
    assert get_knowledge_item(settings, identity, as_of="2026-08-17")["item"]["body"] == original["item"]["body"]
    assert load_catalog(settings).active == primary.slug

    with pytest.raises(SearchError, match="pkb search index alternate"):
        search_keyword(settings, "quarantine", alternate.slug, as_of="2026-08-17")
    index_keyword_brain(settings, alternate.slug, as_of="2026-08-17")
    found = search_keyword(settings, "quarantine", alternate.slug, as_of="2026-08-17")
    assert found["results"][0]["citation"] == saved["citation"]
    update = plan_knowledge_update(
        settings, identity, slug=alternate.slug, actor="openai/codex",
        method=GenerationMethod.AGENT_GENERATED,
        body="# Review stale knowledge\n\n## Steps\n\nUse the alternate quarantine queue and notify its owner.\n",
        timestamp="2026-08-17T13:00:00Z", as_of="2026-08-17",
    )
    save_knowledge_update(settings, update, as_of="2026-08-17")
    with pytest.raises(SearchError, match="stale.*pkb search index alternate"):
        search_keyword(settings, "quarantine", alternate.slug, as_of="2026-08-17")
    assert load_catalog(settings).active == primary.slug
