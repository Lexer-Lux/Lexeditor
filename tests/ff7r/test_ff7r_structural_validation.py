"""Structural identities and failed deletion must preserve complete package state."""
import copy
import struct

import pytest

from plugins.ff7r import dataobject, dataobject_structural as structural
import test_ff7r_dataobject_structural as fixtures


@pytest.mark.parametrize("operation,value", [
    (operation, value)
    for operation in ["insert-entry", "insert-slot", "delete-entry", "delete-slot", "clone", "text"]
    for value in [True, False, 0.5, "0.5", None, [], {}, float("inf"), float("nan")]
    if operation != "insert-slot" or value is not None
])
def test_noninteger_identity_rejects_before_any_mutation(operation, value):
    uasset, uexp, item = fixtures.fixture_package()
    before = copy.deepcopy(item.api_payload())
    with pytest.raises(ValueError, match="must be an integer"):
        if operation == "insert-entry":
            structural.insert_array_element(item, value, "Values_Array", 40)
        elif operation == "insert-slot":
            structural.insert_array_element(item, 0, "Values_Array", 40, array_index=value)
        elif operation == "delete-entry":
            item.delete_array_element(value, "Values_Array", 1)
        elif operation == "delete-slot":
            item.delete_array_element(0, "Values_Array", value)
        elif operation == "clone":
            structural.append_cloned_entry(item, value, "ModeB")
        else:
            structural.replace_scalar_fstring(item, value, "Description", "new")
    assert (bytes(item.uasset_bytes), bytes(item.uexp_bytes)) == (uasset, uexp)
    assert item.api_payload() == before


@pytest.mark.parametrize("stage", ["size", "parse"])
def test_delete_rolls_back_size_bytes_and_cached_objects(monkeypatch, stage):
    uasset, uexp, item = fixtures.fixture_package()
    before = copy.deepcopy(item.api_payload())
    entry_objects, properties, header = item.entries, item.properties, item.uasset
    if stage == "size":
        adjust = item._adjust_export_serial_size
        def fail(delta):
            adjust(delta)
            raise dataobject.FormatError("synthetic size failure after mutation")
        monkeypatch.setattr(item, "_adjust_export_serial_size", fail)
    else:
        def fail():
            raise dataobject.FormatError("synthetic parse failure")
        monkeypatch.setattr(item, "_parse_uexp", fail)
    with pytest.raises(dataobject.FormatError, match="synthetic"):
        item.delete_array_element(0, "Values_Array", 1)
    assert (bytes(item.uasset_bytes), bytes(item.uexp_bytes)) == (uasset, uexp)
    assert item.api_payload() == before
    assert item.entries is entry_objects and item.properties is properties and item.uasset is header


def test_valid_delete_matches_manual_patch_preserves_tail_and_reloads():
    _uasset, _uexp, item = fixtures.fixture_package()
    item.uexp_bytes.extend(b"unknown-tail")
    item._adjust_export_serial_size(len(b"unknown-tail"))
    source_uasset, source_uexp = bytes(item.uasset_bytes), bytes(item.uexp_bytes)
    field = item.entries[0].offsets["Values_Array"]
    expected_uexp = bytearray(source_uexp)
    del expected_uexp[field.offset + 6:field.offset + 8]
    struct.pack_into("<i", expected_uexp, field.offset, 2)
    expected_uasset = bytearray(source_uasset)
    struct.pack_into("<q", expected_uasset, item.uasset.serial_size_offset, len(source_uexp) - 2)
    item.delete_array_element("0", "Values_Array", 1.0)
    assert bytes(item.uasset_bytes) == bytes(expected_uasset)
    assert bytes(item.uexp_bytes) == bytes(expected_uexp)
    reloaded = dataobject.DataObjectPackage.from_bytes(bytes(expected_uasset), bytes(expected_uexp))
    assert reloaded.entries[0].values["Values_Array"] == [10, 30]
    assert reloaded.entries[0].values["Description"] == "$Item_Test"
    assert bytes(reloaded.uexp_bytes).endswith(b"unknown-tail")


def test_valid_exact_identity_forms_and_append_sentinel():
    _uasset, _uexp, item = fixtures.fixture_package()
    assert structural.insert_array_element(item, "0", "Values_Array", 40, array_index=1.0) == 1
    assert structural.insert_array_element(item, 0.0, "Values_Array", 50, array_index=None) == 4
    assert structural.append_cloned_entry(item, "0", "ModeB") == 1
    structural.replace_scalar_fstring(item, 1.0, "Description", "$New_説明")
    reloaded = dataobject.DataObjectPackage.from_bytes(bytes(item.uasset_bytes), bytes(item.uexp_bytes))
    assert reloaded.entries[0].values["Values_Array"] == [10, 40, 20, 30, 50]
    assert reloaded.entries[1].values["Description"] == "$New_説明"
    assert reloaded.entries[0].values["Description"] == "$Item_Test"


@pytest.mark.parametrize("value", ["\ud800", "a" * 64, "é" * 32, "😀" * 16])
def test_invalid_or_oversized_encoded_string_rejects_before_mutation(monkeypatch, value):
    uasset, uexp, item = fixtures.fixture_package()
    before = copy.deepcopy(item.api_payload())
    monkeypatch.setattr(structural, "MAX_STRING_BYTES", 64)
    with pytest.raises(ValueError):
        structural.replace_scalar_fstring(item, 0, "Description", value)
    assert (bytes(item.uasset_bytes), bytes(item.uexp_bytes)) == (uasset, uexp)
    assert item.api_payload() == before


@pytest.mark.parametrize("value", ["a" * 63, "é" * 31, "😀" * 15 + "é"])
def test_encoded_string_boundary_roundtrips(monkeypatch, value):
    _uasset, _uexp, item = fixtures.fixture_package()
    monkeypatch.setattr(structural, "MAX_STRING_BYTES", 64)
    monkeypatch.setattr(dataobject, "MAX_STRING_BYTES", 64)
    structural.replace_scalar_fstring(item, 0, "Description", value)
    reloaded = dataobject.DataObjectPackage.from_bytes(bytes(item.uasset_bytes), bytes(item.uexp_bytes))
    assert reloaded.entries[0].values["Description"] == value
    assert reloaded.entries[0].values["Values_Array"] == [10, 20, 30]
