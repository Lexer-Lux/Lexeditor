"""Every structured dataset rejects malformed HTTP batches before publishing."""
import pytest

from plugins.warband.module_records import SCHEMAS, dataset_data
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_module_records import FIXTURES


@pytest.mark.parametrize("dataset", list(SCHEMAS))
def test_dataset_request_schema_rejection_and_valid_reopen(tmp_path, record_service, dataset):
    schema = SCHEMAS[dataset]
    source = tmp_path / schema["filename"]
    source.write_text(FIXTURES[source.name], encoding="utf-8")
    original = source.read_bytes()
    backup = source.with_name(source.name + ".lexeditor.bak")
    data = dataset_data(tmp_path, dataset)
    row = data["rows"][0]
    spec = next(spec for spec in schema["fields"] if spec["key"] != "id")
    key = spec["key"]
    if spec["kind"] in ("string", "text"):
        value = "Edited café"
    elif spec["kind"] in ("integer", "number"):
        value = 1
    else:
        value = f"({row['fields'][key]})"
    valid = {"recordIndex": 0, "originalId": row["id"], "fields": {key: value}}
    bad = [None, [], "record", {**valid, "originalId": None}, {**valid, "originalId": 1},
           {**valid, "originalId": ""}, {**valid, "extra": True}, {"recordIndex": 0, "fields": {}},
           {**valid, "fields": None}, {**valid, "fields": [[key, value]]},
           {**valid, "recordIndex": True}, {**valid, "recordIndex": 0.5},
           {**valid, "fields": {"id": "renamed"}}, {**valid, "fields": {"unknown_field": "x"}}]
    if spec["kind"] in ("string", "text", "expr"):
        bad += [{**valid, "fields": {key: invalid}} for invalid in (None, True, 1, 1.5, [], {})]
    base = {"dataset": dataset, "sha256": data["sha256"]}
    payloads = [{**base, "edits": [edit]} for edit in bad]
    payloads += [{**base, "edits": invalid} for invalid in (None, {}, "", False, 1)]
    payloads += [{}, {**base}, {"dataset": dataset, "edits": []},
                 {**base, "edits": [], "extra": True}, {**base, "sha256": None, "edits": []},
                 {**base, "dataset": [], "edits": []}, [], False]
    payloads.append({**base, "edits": [{**valid, "fields": {}}, valid]})
    for existing in (False, True):
        if existing:
            backup.write_bytes(b"previous bounded backup")
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir() if path.is_file()}
        for payload in payloads:
            status, result = record_service("/save", payload)
            assert status == 400 and result["error"], payload
            assert {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir() if path.is_file()} == before
    status, result = record_service("/save", {**base, "edits": [valid]})
    assert status == 200 and result["saved"] == 1
    status, reopened = record_service("?dataset=" + dataset)
    assert status == 200
    assert reopened["rows"][0]["fields"] == {**row["fields"], key: value}
    assert backup.read_bytes() == original
