from __future__ import annotations

import struct

import pytest

from games.ff7r.dataobject import DataObjectPackage, FormatError, parse_uasset
from games.ff7r.dataobject_structural import append_array_element, insert_array_element
from games.ff7r.plugin import _test_package


def fixture_package():
    uasset, uexp = _test_package()
    header = parse_uasset(uasset)
    realistic_uasset = bytearray(uasset)
    struct.pack_into("<q", realistic_uasset, header.serial_size_offset, len(uexp))
    package = DataObjectPackage.from_bytes(bytes(realistic_uasset), uexp, asset="Fixture")
    return bytes(realistic_uasset), uexp, package


def test_fixed_width_array_append_rebuilds_offsets_and_export_size():
    _uasset, uexp, package = fixture_package()
    original = dict(package.entries[0].values)

    index = append_array_element(package, 0, "Values_Array", 40)

    assert index == 3
    assert len(package.uexp_bytes) == len(uexp) + 2
    assert package.uasset.serial_size == len(uexp) + 2
    assert package.entries[0].values["Values_Array"] == [10, 20, 30, 40]
    assert package.entries[0].values["Power"] == original["Power"]
    assert package.entries[0].values["Mode"] == original["Mode"]
    assert package.entries[0].values["Description"] == original["Description"]

    reread = DataObjectPackage.from_bytes(bytes(package.uasset_bytes), bytes(package.uexp_bytes))
    assert reread.entries[0].values["Values_Array"] == [10, 20, 30, 40]
    assert reread.uasset.serial_size == len(uexp) + 2


def test_insert_then_delete_same_element_restores_original_pair():
    uasset, uexp, package = fixture_package()

    index = insert_array_element(package, 0, "Values_Array", -123, array_index=1)
    assert package.entries[0].values["Values_Array"] == [10, -123, 20, 30]
    package.delete_array_element(0, "Values_Array", index)

    assert bytes(package.uasset_bytes) == uasset
    assert bytes(package.uexp_bytes) == uexp


def test_insert_rejects_non_array_and_invalid_index_before_mutation():
    uasset, uexp, package = fixture_package()

    with pytest.raises(ValueError, match="not an array"):
        append_array_element(package, 0, "Power", 1)
    with pytest.raises(IndexError, match="insertion index"):
        insert_array_element(package, 0, "Values_Array", 1, array_index=4)

    assert bytes(package.uasset_bytes) == uasset
    assert bytes(package.uexp_bytes) == uexp


def test_insert_rolls_back_if_reparse_fails(monkeypatch):
    uasset, uexp, package = fixture_package()

    def fail_parse():
        raise FormatError("synthetic reparse failure")

    monkeypatch.setattr(package, "_parse_uexp", fail_parse)
    with pytest.raises(FormatError, match="synthetic reparse failure"):
        append_array_element(package, 0, "Values_Array", 40)

    assert bytes(package.uasset_bytes) == uasset
    assert bytes(package.uexp_bytes) == uexp
    assert package.entries[0].values["Values_Array"] == [10, 20, 30]


def test_insert_uses_native_numeric_validation():
    _uasset, _uexp, package = fixture_package()

    with pytest.raises(ValueError, match="outside"):
        append_array_element(package, 0, "Values_Array", 40000)
    assert package.entries[0].values["Values_Array"] == [10, 20, 30]
