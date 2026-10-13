"""Creation must publish source, latest backup and origin ledger together."""
import json
from pathlib import Path

import pytest

from plugins.warband import server, source_save
from plugins.warband.module_records import SCHEMAS
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_source_publication import save_case, snapshot


def creation_case(tmp_path, kind):
    path, endpoint, save, query, before, _, _ = save_case(tmp_path, kind)
    row = before["rows"][0]
    payload = {"sha256": save["sha256"], "recordIndex": 0,
               "originalId": row["id"], "id": "created_record"}
    if kind in ("items", "troops"):
        payload["name"] = "Created café"
    if kind == "troops":
        payload["plural"] = "Created cafés"
    if kind in SCHEMAS:
        payload["dataset"] = kind
    return path, endpoint, payload, query, before


@pytest.mark.parametrize("kind", ["items", "troops", *SCHEMAS])
def test_all_create_routes_failure_preservation_then_retry(tmp_path, monkeypatch, record_service, kind):
    path, endpoint, payload, query, before = creation_case(tmp_path, kind)
    backup, ledger = path.with_name(path.name + ".lexeditor.bak"), server.CREATED_LEDGER
    original = path.read_bytes()
    real_stage, real_replace = source_save.tempfile.NamedTemporaryFile, source_save.os.replace
    for has_backup, has_ledger in ((False, False), (False, True), (True, False), (True, True)):
        backup.unlink(missing_ok=True)
        ledger.unlink(missing_ok=True)
        if has_backup:
            backup.write_bytes(b"older source backup")
        if has_ledger:
            ledger.write_text(json.dumps({kind: ["older_record"], "other_kind": ["other_record"],
                                          "metadata": {"opaque": [1, False]}}), encoding="utf-8")
        files, entries = snapshot(tmp_path), {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
        for action in ("stage", "replace"):
            for fail_at in (1, 2, 3):
                calls = 0

                def stage(*args, **kwargs):
                    nonlocal calls
                    if kwargs.get("suffix") == ".tmp" and Path(kwargs.get("dir", "")) == tmp_path:
                        calls += 1
                        if calls == fail_at:
                            raise OSError("injected creation staging failure")
                    return real_stage(*args, **kwargs)

                def replace(src, dst):
                    nonlocal calls
                    if Path(dst) in (path, backup, ledger):
                        calls += 1
                        if calls == fail_at:
                            raise OSError("injected creation publication failure")
                    return real_replace(src, dst)

                with monkeypatch.context() as patch:
                    patch.setattr(source_save.tempfile, "NamedTemporaryFile", stage if action == "stage" else real_stage)
                    patch.setattr(source_save.os, "replace", replace if action == "replace" else real_replace)
                    status, result = record_service("/create", payload, endpoint)
                assert status == 400 and "injected" in result["error"], (kind, action, fail_at, result)
                assert calls >= fail_at
                assert snapshot(tmp_path) == files
                assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*")} == entries
                assert "created_record" not in server.created_ids(kind)
    previous = json.loads(ledger.read_text())
    status, result = record_service("/create", payload, endpoint)
    assert status == 200 and result["created"] == "created_record", result
    assert backup.read_bytes() == original
    status, reopened = record_service(query, endpoint=endpoint)
    assert status == 200
    created = next(row for row in reopened["rows"] if row["id"] == "created_record")
    assert created["created"] is True
    assert server.created_ids(kind) == {"older_record", "created_record"}
    assert json.loads(ledger.read_text()) == {**previous, kind: ["older_record", "created_record"]}
    old_rows = {row["id"]: row for row in before["rows"]}
    for row in reopened["rows"]:
        if row["id"] in old_rows:
            assert row["fields"] == old_rows[row["id"]]["fields"]
            assert not row.get("created", False)
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".lexeditor-save-recovery-*"))


@pytest.mark.parametrize("kind", ["items", "troops", "skills", "sounds"])
def test_bad_ledger_never_discards_history_or_creates_source(tmp_path, record_service, kind):
    path, endpoint, payload, _, _ = creation_case(tmp_path, kind)
    backup = path.with_name(path.name + ".lexeditor.bak")
    backup.write_bytes(b"older backup")
    for bad in ("not json", "[]", "null", json.dumps({kind: None}),
                json.dumps({kind: "wrong"}), json.dumps({kind: [1]}), json.dumps({kind: [""]})):
        server.CREATED_LEDGER.write_text(bad, encoding="utf-8")
        before = snapshot(tmp_path)
        status, result = record_service("/create", payload, endpoint)
        assert status == 400 and "ledger" in result["error"], result
        assert snapshot(tmp_path) == before
    # The legacy sounds route also uses the same transaction.
    if kind == "sounds":
        server.CREATED_LEDGER.write_text("{}", encoding="utf-8")
        status, result = record_service("/create", payload, "/api/sounds")
        assert status == 200 and result["created"] == "created_record"
        assert server.created_ids("sounds") == {"created_record"}


@pytest.mark.parametrize("when", ["stage", "publish"])
def test_external_ledger_change_preserved_with_source_rolled_back(tmp_path, monkeypatch, record_service, when):
    path, endpoint, payload, _, _ = creation_case(tmp_path, "items")
    backup = path.with_name(path.name + ".lexeditor.bak")
    backup.write_bytes(b"older backup")
    server.CREATED_LEDGER.write_text('{"other": ["original"]}', encoding="utf-8")
    before = snapshot(tmp_path)
    external = b'{"other": ["external"]}'
    real_stage, real_replace = source_save.tempfile.NamedTemporaryFile, source_save.os.replace
    calls = 0

    def stage(*args, **kwargs):
        nonlocal calls
        if kwargs.get("suffix") == ".tmp" and Path(kwargs.get("dir", "")) == tmp_path:
            calls += 1
            if calls == 3:
                server.CREATED_LEDGER.write_bytes(external)
        return real_stage(*args, **kwargs)

    def replace(src, dst):
        real_replace(src, dst)
        if Path(dst) == path:
            server.CREATED_LEDGER.write_bytes(external)

    with monkeypatch.context() as patch:
        if when == "stage":
            patch.setattr(source_save.tempfile, "NamedTemporaryFile", stage)
        else:
            patch.setattr(source_save.os, "replace", replace)
        status, result = record_service("/create", payload, endpoint)
    assert status == 400 and "changed during save" in result["error"], result
    assert snapshot(tmp_path)[path.name] == before[path.name]
    assert snapshot(tmp_path)[backup.name] == before[backup.name]
    assert server.CREATED_LEDGER.read_bytes() == external
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".lexeditor-save-recovery-*"))
    status, result = record_service("/create", payload, endpoint)
    assert status == 200, result
    assert json.loads(server.CREATED_LEDGER.read_text()) == {"other": ["external"], "items": ["created_record"]}


def test_project_ledger_and_module_source_in_separate_directories(tmp_path, monkeypatch, record_service):
    modules, project = tmp_path / "module_system", tmp_path / "project"
    modules.mkdir()
    project.mkdir()
    monkeypatch.setattr(server, "MODULE_SYSTEM", modules)
    monkeypatch.setattr(server, "CREATED_LEDGER", project / ".lexeditor-created.json")
    path, endpoint, payload, _, _ = creation_case(modules, "items")
    before = snapshot(tmp_path)
    real_replace = source_save.os.replace

    def replace(src, dst):
        if Path(dst) == server.CREATED_LEDGER:
            raise OSError("ledger publication failed")
        return real_replace(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(source_save.os, "replace", replace)
        status, result = record_service("/create", payload, endpoint)
    assert status == 400 and "ledger publication failed" in result["error"]
    assert snapshot(tmp_path) == before
    assert list(project.iterdir()) == []
    assert list(modules.iterdir()) == [path]
    status, result = record_service("/create", payload, endpoint)
    assert status == 200 and result["created"] == "created_record"
    status, reopened = record_service("", endpoint=endpoint)
    assert status == 200
    assert next(row for row in reopened["rows"] if row["id"] == "created_record")["created"]


def test_creation_rollback_failure_preserves_all_recovery_originals_and_blocks_other_sources(tmp_path, monkeypatch, record_service):
    path, endpoint, payload, _, _ = creation_case(tmp_path, "items")
    backup = path.with_name(path.name + ".lexeditor.bak")
    backup.write_bytes(b"older backup")
    server.CREATED_LEDGER.write_text('{"other": ["original"]}', encoding="utf-8")
    before = snapshot(tmp_path)
    real_replace = source_save.os.replace
    calls = 0

    def replace(src, dst):
        nonlocal calls
        calls += 1
        if calls in (3, 4):
            raise OSError("publication or source rollback failed")
        return real_replace(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(source_save.os, "replace", replace)
        status, result = record_service("/create", payload, endpoint)
    assert status == 400 and "original state retained" in result["error"]
    assert snapshot(tmp_path)[backup.name] == before[backup.name]
    assert snapshot(tmp_path)[server.CREATED_LEDGER.name] == before[server.CREATED_LEDGER.name]
    assert path.read_bytes() != before[path.name][0]
    folder = tmp_path / (".lexeditor-save-recovery-" + path.name)
    state = json.loads((folder / "state.json").read_text())
    assert len(state["files"]) == 3
    for entry in state["files"]:
        assert entry["existed"]
        assert (folder / entry["original"]).read_bytes() == before[Path(entry["target"]).name][0]
    other = tmp_path / "module_other.py"
    other.write_bytes(b"other source")
    retained = snapshot(tmp_path)
    with pytest.raises(OSError, match="unresolved recovery"):
        source_save.publish_source(other, b"candidate", b"other source")
    assert snapshot(tmp_path) == retained
    assert not list(tmp_path.glob(".*.tmp"))
