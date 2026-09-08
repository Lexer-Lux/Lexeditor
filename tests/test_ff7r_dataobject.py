from __future__ import annotations

import pytest

from games.ff7r.dataobject import DataObjectPackage, FormatError, parse_uasset
from games.ff7r.plugin import _test_package


def fixture_package():
    uasset, uexp = _test_package()
    return uasset, uexp, DataObjectPackage.from_bytes(uasset, uexp, asset="End/Content/GameContents/DataObject/Resident/Fixture")


def test_generated_fixture_decodes_expected_types():
    _uasset, _uexp, package = fixture_package()
    row = package.entries[0]
    assert row.tag == "RowA"
    assert row.values == {
        "Power": 42,
        "Enabled": True,
        "Mode": "ModeA",
        "Description": "$Item_Test",
        "Values_Array": [10, 20, 30],
    }
    assert [prop["type"] for prop in package.api_payload()["properties"]] == [
        "INT32", "BOOL", "ENUM", "STRING", "INT16"
    ]


def test_same_size_edits_round_trip_and_preserve_string():
    uasset, uexp, package = fixture_package()
    package.apply_edits([
        {"entry": 0, "property": "Power", "value": -123456},
        {"entry": 0, "property": "Enabled", "value": False},
        {"entry": 0, "property": "Mode", "value": "ModeB"},
        {"entry": 0, "property": "Values_Array", "index": 2, "value": -32768},
    ])
    assert len(package.uexp_bytes) == len(uexp)
    reread = DataObjectPackage.from_bytes(uasset, bytes(package.uexp_bytes))
    row = reread.entries[0].values
    assert row["Power"] == -123456
    assert row["Enabled"] is False
    assert row["Mode"] == "ModeB"
    assert row["Values_Array"] == [10, 20, -32768]
    assert row["Description"] == "$Item_Test"


def test_rejects_size_changing_or_out_of_domain_edits():
    _uasset, _uexp, package = fixture_package()
    with pytest.raises(ValueError, match="read-only"):
        package.apply_edits([{"entry": 0, "property": "Description", "value": "Changed"}])
    with pytest.raises(ValueError, match="already exist"):
        package.apply_edits([{"entry": 0, "property": "Mode", "value": "NotInNameTable"}])
    with pytest.raises(IndexError, match="Array index"):
        package.apply_edits([{"entry": 0, "property": "Values_Array", "index": 3, "value": 1}])
    with pytest.raises(ValueError, match="outside"):
        package.apply_edits([{"entry": 0, "property": "Power", "value": 2**31}])


def test_rejects_malformed_packages():
    uasset, _uexp = _test_package()
    damaged = bytearray(uasset)
    damaged[:4] = b"NOPE"
    with pytest.raises(FormatError, match="package tag"):
        parse_uasset(bytes(damaged))
