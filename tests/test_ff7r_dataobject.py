from __future__ import annotations

import struct

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


def test_fixed_width_array_delete_rebuilds_offsets_and_patches_export_size():
    uasset, uexp = _test_package()
    header = parse_uasset(uasset)
    realistic_uasset = bytearray(uasset)
    struct.pack_into("<q", realistic_uasset, header.serial_size_offset, len(uexp))
    package = DataObjectPackage.from_bytes(bytes(realistic_uasset), uexp)

    original_power = package.entries[0].values["Power"]
    original_mode = package.entries[0].values["Mode"]
    original_description = package.entries[0].values["Description"]
    package.delete_array_element(0, "Values_Array", 1)

    assert len(package.uexp_bytes) == len(uexp) - 2
    assert package.uasset.serial_size == len(uexp) - 2
    assert package.entries[0].values["Values_Array"] == [10, 30]
    assert package.entries[0].values["Power"] == original_power
    assert package.entries[0].values["Mode"] == original_mode
    assert package.entries[0].values["Description"] == original_description

    reread = DataObjectPackage.from_bytes(bytes(package.uasset_bytes), bytes(package.uexp_bytes))
    assert reread.entries[0].values["Values_Array"] == [10, 30]
    assert reread.uasset.serial_size == len(uexp) - 2


def test_structural_delete_rejects_non_array_and_out_of_range_index():
    _uasset, _uexp, package = fixture_package()
    with pytest.raises(ValueError, match="not an array"):
        package.delete_array_element(0, "Power", 0)
    with pytest.raises(IndexError, match="Array index"):
        package.delete_array_element(0, "Values_Array", 3)


def test_write_pair_round_trips_structural_edits(tmp_path):
    uasset, uexp = _test_package()
    header = parse_uasset(uasset)
    realistic_uasset = bytearray(uasset)
    struct.pack_into("<q", realistic_uasset, header.serial_size_offset, len(uexp))
    package = DataObjectPackage.from_bytes(bytes(realistic_uasset), uexp, asset="Fixture")
    package.delete_array_element(0, "Values_Array", 0)

    uasset_target = tmp_path / "Fixture.uasset"
    uexp_target = tmp_path / "Fixture.uexp"
    package.write_pair(uasset_target, uexp_target)
    reread = DataObjectPackage(uasset_target, uexp_target, asset="Fixture")
    assert reread.entries[0].values["Values_Array"] == [20, 30]
    assert reread.uasset.serial_size == len(uexp) - 2


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
