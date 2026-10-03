"""Real save routes preserve source/backup state after publication failures."""
import json
from pathlib import Path

import pytest

from plugins.warband import server, source_save
from plugins.warband.module_records import SCHEMAS, dataset_data
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_items_editor import SOURCE as ITEMS
from tests.warband.test_warband_troop_editor import SOURCE as TROOPS
from tests.warband.test_warband_module_records import FIXTURES


def save_case(tmp_path, kind):
    if kind == "items":
        filename, source, endpoint = "module_items.py", ITEMS, "/api/items"
    elif kind == "troops":
        filename, source, endpoint = "module_troops.py", TROOPS, "/api/troops"
    else:
        filename = SCHEMAS[kind]["filename"]
        source, endpoint = FIXTURES[filename], "/api/module-records"
    path = tmp_path / filename
    path.write_text(source, encoding="utf-8")
    data = (server.item_data() if kind == "items" else
            server.troop_data(tmp_path) if kind == "troops" else dataset_data(tmp_path, kind))
    row = data["rows"][0]
    if kind in ("items", "troops"):
        field, value = "name", "Saved café"
    else:
        spec = next(spec for spec in SCHEMAS[kind]["fields"] if spec["key"] != "id")
        field = spec["key"]
        if spec["kind"] in ("string", "text"):
            value = "Saved café"
        elif spec["kind"] in ("integer", "number"):
            value = 1
        else:
            value = f"({row['fields'][field]})"
    payload = {"sha256": data["sha256"], "edits": [
        {"recordIndex": 0, "originalId": row["id"], "fields": {field: value}}]}
    if kind in SCHEMAS:
        payload["dataset"] = kind
    query = "?dataset=" + kind if kind in SCHEMAS else ""
    return path, endpoint, payload, query, data, field, value


def snapshot(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("kind", ["items", "troops", *SCHEMAS])
def test_every_save_family_staging_and_publication_failure_retry(tmp_path, monkeypatch, record_service, kind):
    path, endpoint, payload, query, data, field, value = save_case(tmp_path, kind)
    backup = path.with_name(path.name + ".lexeditor.bak")
    original = path.read_bytes()
    real_stage = source_save.tempfile.NamedTemporaryFile
    real_replace = source_save.os.replace
    for existing in (False, True):
        if existing:
            backup.write_bytes(b"older source backup")
        before = snapshot(tmp_path)
        entries = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
        for action in ("stage", "replace"):
            for fail_at in (1, 2):
                calls = 0

                def stage(*args, **kwargs):
                    nonlocal calls
                    if kwargs.get("suffix") == ".tmp" and Path(kwargs.get("dir", "")) == tmp_path:
                        calls += 1
                        if calls == fail_at:
                            raise OSError("injected staging failure")
                    return real_stage(*args, **kwargs)

                def replace(src, dst):
                    nonlocal calls
                    if Path(dst) in (path, backup):
                        calls += 1
                        if calls == fail_at:
                            raise OSError("injected publication failure")
                    return real_replace(src, dst)

                with monkeypatch.context() as patch:
                    patch.setattr(source_save.tempfile, "NamedTemporaryFile", stage if action == "stage" else real_stage)
                    patch.setattr(source_save.os, "replace", replace if action == "replace" else real_replace)
                    status, result = record_service("/save", payload, endpoint)
                assert status == 400 and "injected" in result["error"], (kind, action, fail_at, result)
                assert calls >= fail_at
                assert snapshot(tmp_path) == before
                assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*")} == entries
    status, result = record_service("/save", payload, endpoint)
    assert status == 200 and result["saved"] == 1, result
    assert backup.read_bytes() == original
    status, reopened = record_service(query, endpoint=endpoint)
    assert status == 200
    assert reopened["rows"][0]["fields"] == {**data["rows"][0]["fields"], field: value}
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".lexeditor-save-recovery-*"))


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("changed_target", ["source", "backup"])
def test_external_changes_during_staging_are_not_overwritten(tmp_path, monkeypatch, existing, changed_target):
    path = tmp_path / "module_test.py"
    backup = tmp_path / "module_test.py.lexeditor.bak"
    path.write_bytes(b"original")
    if existing:
        backup.write_bytes(b"previous backup")
    target = path if changed_target == "source" else backup
    real_stage = source_save.tempfile.NamedTemporaryFile
    calls = 0

    def stage(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            target.write_bytes(b"external edit")
        return real_stage(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(source_save.tempfile, "NamedTemporaryFile", stage)
        with pytest.raises(ValueError, match="changed during save"):
            source_save.publish_source(path, b"candidate", b"original")
    assert target.read_bytes() == b"external edit"
    if target == path:
        assert (backup.read_bytes() if backup.exists() else None) == (b"previous backup" if existing else None)
    else:
        assert path.read_bytes() == b"original"
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".lexeditor-save-recovery-*"))


@pytest.mark.parametrize("failure", ["replace", "remove", "external"])
def test_rollback_failure_retains_bounded_originals_and_blocks_retry(tmp_path, monkeypatch, failure):
    path = tmp_path / "module_test.py"
    backup = tmp_path / "module_test.py.lexeditor.bak"
    path.write_bytes(b"original source")
    if failure != "remove":
        backup.write_bytes(b"original backup")
    before = snapshot(tmp_path)
    real_replace, real_unlink = source_save.os.replace, Path.unlink
    calls = 0

    def replace(src, dst):
        nonlocal calls
        calls += 1
        if calls == 2:
            if failure == "external":
                backup.write_bytes(b"external backup")
            raise OSError("source publication failed")
        if calls == 3 and failure == "replace":
            raise OSError("backup rollback failed")
        return real_replace(src, dst)

    def unlink(target, *args, **kwargs):
        if target == backup:
            raise OSError("backup removal failed")
        return real_unlink(target, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(source_save.os, "replace", replace)
        if failure == "remove":
            patch.setattr(Path, "unlink", unlink)
        with pytest.raises(RuntimeError, match="original state retained"):
            source_save.publish_source(path, b"new source", b"original source")
    folder = tmp_path / ".lexeditor-save-recovery-module_test.py"
    state = json.loads((folder / "state.json").read_text())
    assert path.read_bytes() == b"original source"
    assert backup.read_bytes() == (b"external backup" if failure == "external" else b"original source")
    for entry in state["files"]:
        original = before.get(Path(entry["target"]).name)
        assert entry["existed"] == (original is not None)
        if original is not None:
            assert (folder / entry["original"]).read_bytes() == original[0]
            assert entry["timestamps"][1] == original[1]
    retained = snapshot(tmp_path)
    with pytest.raises(OSError, match="unresolved recovery"):
        source_save.publish_source(path, b"newer source", b"original source")
    assert snapshot(tmp_path) == retained
    assert not list(tmp_path.glob(".*.tmp"))


def test_stale_source_rejects_before_staging(tmp_path, monkeypatch):
    path = tmp_path / "module_test.py"
    path.write_bytes(b"external source")
    before = snapshot(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("stale save reached staging")

    monkeypatch.setattr(source_save.tempfile, "NamedTemporaryFile", forbidden)
    with pytest.raises(ValueError, match="changed while validating"):
        source_save.publish_source(path, b"candidate", b"stale source")
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("existing", [False, True])
def test_source_changed_after_backup_publication_preserves_external_source(tmp_path, monkeypatch, existing):
    path = tmp_path / "module_test.py"
    backup = tmp_path / "module_test.py.lexeditor.bak"
    path.write_bytes(b"original")
    if existing:
        backup.write_bytes(b"previous backup")
    before = snapshot(tmp_path)
    real_replace = source_save.os.replace

    def replace(src, dst):
        real_replace(src, dst)
        if Path(dst) == backup:
            path.write_bytes(b"external source")

    monkeypatch.setattr(source_save.os, "replace", replace)
    with pytest.raises(ValueError, match="changed during save"):
        source_save.publish_source(path, b"candidate", b"original")
    assert path.read_bytes() == b"external source"
    assert (snapshot(tmp_path).get(backup.name)) == before.get(backup.name)
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".lexeditor-save-recovery-*"))


@pytest.mark.parametrize("fail_file", ["state.json", "0", "1"])
def test_recovery_initialization_failure_cannot_publish(tmp_path, monkeypatch, fail_file):
    path = tmp_path / "module_test.py"
    backup = tmp_path / "module_test.py.lexeditor.bak"
    path.write_bytes(b"original")
    backup.write_bytes(b"previous backup")
    before = snapshot(tmp_path)
    real_write_bytes, real_write_text = Path.write_bytes, Path.write_text

    def write_bytes(target, data):
        if target.name == fail_file:
            raise OSError("recovery initialization failed")
        return real_write_bytes(target, data)

    def write_text(target, data, **kwargs):
        if target.name == fail_file:
            raise OSError("recovery initialization failed")
        return real_write_text(target, data, **kwargs)

    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    monkeypatch.setattr(Path, "write_text", write_text)
    with pytest.raises(OSError, match="recovery initialization failed"):
        source_save.publish_source(path, b"candidate", b"original")
    assert snapshot(tmp_path) == before
    assert {p.name for p in tmp_path.iterdir()} == set(before)


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("fail_at", [1, 2])
def test_partial_staging_write_failure_cleans_candidate_files(tmp_path, monkeypatch, existing, fail_at):
    path = tmp_path / "module_test.py"
    backup = tmp_path / "module_test.py.lexeditor.bak"
    path.write_bytes(b"original")
    if existing:
        backup.write_bytes(b"previous backup")
    before = snapshot(tmp_path)
    real_stage = source_save.tempfile.NamedTemporaryFile
    calls = 0

    def stage(*args, **kwargs):
        nonlocal calls
        calls += 1
        stream = real_stage(*args, **kwargs)
        if calls == fail_at:
            def write(data):
                stream.file.write(data[:3])
                raise OSError("partial staging write failed")
            stream.write = write
        return stream

    monkeypatch.setattr(source_save.tempfile, "NamedTemporaryFile", stage)
    with pytest.raises(OSError, match="partial staging write failed"):
        source_save.publish_source(path, b"candidate", b"original")
    assert snapshot(tmp_path) == before
    assert {p.name for p in tmp_path.iterdir()} == set(before)
