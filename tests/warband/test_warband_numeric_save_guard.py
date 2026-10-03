"""Rejected numeric batches must not retarget records or touch source files."""
from pathlib import Path
from unittest.mock import patch

import pytest

from plugins.warband import module_records, server, troop_editor
from tests.warband import test_warband_items_editor as item_fixture
from tests.warband import test_warband_module_records as module_fixture
from tests.warband import test_warband_troop_editor as troop_fixture


def test_warband_record_indexes_reject_truncation_before_writing(tmp_path):
    item_path = tmp_path / "module_items.py"
    troop_path = tmp_path / "module_troops.py"
    strings_path = tmp_path / "module_strings.py"
    item_path.write_text(item_fixture.SOURCE, encoding="utf-8")
    troop_path.write_text(troop_fixture.SOURCE, encoding="utf-8")
    strings_path.write_text(module_fixture.FIXTURES[strings_path.name], encoding="utf-8")
    with patch.object(server, "MODULE_SYSTEM", tmp_path):
        item_data = server.item_data()
        troop_data = troop_editor.troop_data(tmp_path)
        strings_data = module_records.dataset_data(tmp_path, "strings")
        cases = [
            (item_path, lambda edits: server.save_item_edits(edits, item_data["sha256"]),
             {"recordIndex": 0, "originalId": "sword", "fields": {"name": "Edited sword"}},
             {"originalId": "boots", "fields": {"name": "Edited boots"}}),
            (troop_path, lambda edits: troop_editor.save_troops(tmp_path, troop_data["sha256"], edits),
             {"recordIndex": troop_data["rows"][0]["recordIndex"], "originalId": troop_data["rows"][0]["id"],
              "fields": {"name": "Edited troop"}},
             {"originalId": troop_data["rows"][0]["id"], "fields": {"plural": "Edited troops"}}),
            (strings_path, lambda edits: module_records.save_dataset(tmp_path, "strings", strings_data["sha256"], edits),
             {"recordIndex": 0, "originalId": "hello", "fields": {"value": "Edited hello"}},
             {"originalId": "bye", "fields": {"value": "Edited bye"}}),
        ]
        for path, save, valid, invalid in cases:
            original = path.read_bytes()
            for index in (1.5, True, False, "1.5", float("nan"), float("inf")):
                with pytest.raises(ValueError, match="integer"):
                    save([valid, {**invalid, "recordIndex": index}])
                assert path.read_bytes() == original
                assert not path.with_name(path.name + ".lexeditor.bak").exists()
            assert save([valid])["saved"] == 1
            assert path.read_bytes() != original
        assert server.item_data()["rows"][0]["name"] == "Edited sword"
        assert troop_editor.troop_data(tmp_path)["rows"][0]["name"] == "Edited troop"
        assert module_records.dataset_data(tmp_path, "strings")["rows"][0]["fields"]["value"] == "Edited hello"


def test_warband_structured_numeric_fields_reject_booleans_and_nonfinite_values(tmp_path):
    for name, content in module_fixture.FIXTURES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    cases = [("skills", "maxLevel", True), ("skills", "maxLevel", 1.5),
             ("factions", "coherence", True), ("factions", "coherence", float("inf")),
             ("postfx", "params1", [1, 2, True, 4]),
             ("postfx", "params1", [1, 2, float("nan"), 4])]
    for dataset, key, value in cases:
        data = module_records.dataset_data(tmp_path, dataset)
        path = tmp_path / data["filename"]
        original = path.read_bytes()
        valid_fields = {"tonemap": 2} if dataset == "postfx" else {"name": "Valid first change"}
        with pytest.raises(ValueError, match="integer|finite number"):
            module_records.save_dataset(tmp_path, dataset, data["sha256"], [{
                "recordIndex": 0, "originalId": data["rows"][0]["id"],
                "fields": {**valid_fields, key: value},
            }])
        assert path.read_bytes() == original
        assert not path.with_name(path.name + ".lexeditor.bak").exists()
    data = module_records.dataset_data(tmp_path, "postfx")
    module_records.save_dataset(tmp_path, "postfx", data["sha256"], [{
        "recordIndex": "0", "originalId": "default", "fields": {"params1": [1.5, 2, 3, 4]},
    }])
    assert module_records.dataset_data(tmp_path, "postfx")["rows"][0]["fields"]["params1"] == [1.5, 2, 3, 4]
