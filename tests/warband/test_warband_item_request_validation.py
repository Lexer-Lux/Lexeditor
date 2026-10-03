"""Malformed real-service batches must not stringify values or publish edits."""
import pytest

from plugins.warband import server
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_items_editor import SOURCE


def test_malformed_item_requests_preserve_source_backup_and_later_valid_save(tmp_path, record_service):
    source = tmp_path / "module_items.py"
    source.write_text(SOURCE, encoding="utf-8")
    backup = source.with_name(source.name + ".lexeditor.bak")
    original = source.read_bytes()
    data = server.item_data()
    valid = {"recordIndex": 0, "originalId": "sword", "fields": {"name": "Edited sword"}}
    other = {"recordIndex": 1, "originalId": "boots", "fields": {"value": "80"}}
    bad_records = [None, [], "boots", {**other, "originalId": None}, {**other, "originalId": 1},
        {**other, "originalId": ""}, {**other, "extra": True}, {"recordIndex": 1, "fields": {}},
        {**other, "fields": None}, {**other, "fields": [["value", "80"]]},
        {**other, "recordIndex": True}, {**other, "recordIndex": 1.5}]
    for value in (None, True, 1, 1.5, [], {}):
        for field in ("name", "value", "stats"):
            bad_records.append({**other, "fields": {field: value}})
    payloads = [{"sha256": data["sha256"], "edits": [valid, bad]} for bad in bad_records]
    payloads += [{"sha256": data["sha256"], "edits": value} for value in (None, {}, "", False, 1)]
    payloads += [{}, {"edits": []}, {"sha256": data["sha256"]},
                 {"sha256": None, "edits": [valid]},
                 {"sha256": data["sha256"], "edits": [valid], "extra": True}, [], "invalid", False]
    # A no-op first edit must not let a duplicate owner slip through.
    payloads.append({"sha256": data["sha256"], "edits": [
        {**valid, "fields": {"name": "Old Sword"}}, valid]})
    for existing_backup in (False, True):
        if existing_backup:
            backup.write_bytes(b"previous bounded backup")
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir() if path.is_file()}
        for payload in payloads:
            status, rejected = record_service("/save", payload, "/api/items")
            assert status == 400 and rejected["error"], payload
            assert {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir() if path.is_file()} == before
    # A valid request still writes source strings, including exact fractional
    # stat text, then the fresh HTTP reader reopens the same values.
    edits = [valid, {**other, "fields": {"stats": "weight(1.125)|leg_armor(12)"}}]
    status, result = record_service("/save", {"sha256": data["sha256"], "edits": edits}, "/api/items")
    assert status == 200 and result["saved"] == 2
    status, reopened = record_service("", endpoint="/api/items")
    assert status == 200
    assert reopened["rows"][0]["name"] == "Edited sword"
    assert reopened["rows"][1]["fields"]["stats"] == "weight(1.125)|leg_armor(12)"
    assert backup.read_bytes() == original
    for index, row in enumerate(reopened["rows"]):
        changed = edits[index]["fields"]
        for field, value in data["rows"][index]["fields"].items():
            assert row["fields"][field] == changed.get(field, value)
