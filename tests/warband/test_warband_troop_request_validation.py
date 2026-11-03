"""Troop request rejection precedes publication and preserves legacy lookup."""
from plugins.warband import server
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_troop_editor import SOURCE


def test_troop_requests_reject_bad_batches_and_reopen_indexed_and_legacy_saves(tmp_path, record_service):
    source = tmp_path / "module_troops.py"
    source.write_text(SOURCE, encoding="utf-8")
    (tmp_path / "header_troops.py").write_text("str_4=4\nagi_4=1024\nint_4=262144\ncha_4=67108864\n", encoding="utf-8")
    data = server.troop_data(tmp_path)
    original = source.read_bytes()
    backup = source.with_name(source.name + ".lexeditor.bak")
    valid = {"recordIndex": 0, "originalId": "soldier", "fields": {"name": "Edited soldier"}}
    other = {"recordIndex": 1, "originalId": "cut", "fields": {"plural": "Edited cut troops"}}
    bad = [None, [], "cut", {**other, "originalId": None}, {**other, "originalId": 1},
           {**other, "originalId": ""}, {**other, "extra": True}, {"recordIndex": 1, "fields": {}},
           {**other, "fields": None}, {**other, "fields": [["plural", "Changed"]]},
           {**other, "recordIndex": True}, {**other, "recordIndex": 1.5},
           {"id": None, "fields": {}}, {"id": 1, "fields": {}},
           {"id": "cut", "fields": {}, "extra": True}]
    for value in (None, True, 1, 1.5, [], {}):
        for field in ("name", "plural", "attributes"):
            bad.append({**other, "fields": {field: value}})
    for expression in ("1e999", "-1e999", "level(1e999)"):
        bad.append({**other, "fields": {"attributes": expression}})
    payloads = [{"sha256": data["sha256"], "edits": [valid, edit]} for edit in bad]
    payloads += [{"sha256": data["sha256"], "edits": value} for value in (None, {}, "", False, 1)]
    payloads += [{}, {"edits": []}, {"sha256": data["sha256"]}, {"sha256": None, "edits": []},
                 {"sha256": data["sha256"], "edits": [valid], "extra": True}, [], "invalid", False]
    payloads.append({"sha256": data["sha256"], "edits": [
        {**valid, "fields": {"name": "Soldier"}}, {"id": "soldier", "fields": {"name": "Duplicate"}}]})
    for existing in (False, True):
        if existing:
            backup.write_bytes(b"previous bounded backup")
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir() if path.is_file()}
        for payload in payloads:
            status, rejected = record_service("/save", payload, "/api/troops")
            assert status == 400 and rejected["error"], payload
            assert {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir() if path.is_file()} == before
    fields = {"attributes": "str_4|agi_4|int_4|cha_4|level(255)", "name": 'Edited "soldier"'}
    edits = [{**valid, "fields": fields}, {"id": "cut", "fields": {"plural": "Cut cafés"}}]
    status, result = record_service("/save", {"sha256": data["sha256"], "edits": edits}, "/api/troops")
    assert status == 200 and result["saved"] == 2
    status, reopened = record_service("", endpoint="/api/troops")
    assert status == 200
    assert reopened["rows"][0]["stats"]["level"] == 255
    assert reopened["rows"][0]["name"] == 'Edited "soldier"'
    assert reopened["rows"][1]["plural"] == "Cut cafés"
    assert reopened["rows"][1]["status"] == "CUT"
    assert backup.read_bytes() == original
    assert b'upgrade(troops, "soldier", "cut")' in source.read_bytes()
    for index, row in enumerate(reopened["rows"]):
        for field, value in data["rows"][index]["fields"].items():
            assert row["fields"][field] == edits[index]["fields"].get(field, value)
