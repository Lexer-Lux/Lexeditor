"""The DS1 mod loader combines every enabled mod over the game's own files.

Two mods changing different fields of one row both apply; two mods setting
the same field to different values conflict, and the later one is used. A
bitfield is merged by its own bits. A change that cannot be merged by field
(a row added, a table that is not a PARAM) takes the whole table from the
last mod. Synthetic archives only.
"""
from pathlib import Path

import pytest

from ds1_fixture import make_archive, make_text_archive
from plugins.ds1 import mod_loader, texts
from plugins.ds1.formats import ItemDocument, inflate, deflate, members, schema
from plugins.ds1.store import MARKER, RELATIVE

VANILLA = make_archive()
NAMES = make_text_archive()
GAME = {RELATIVE: VANILLA, texts.RELATIVE: NAMES}


def edited(*edits):
    document = ItemDocument(VANILLA)
    for table, row, key, value in edits:
        document.edit(table, row, key, value)
    return document.export()


def renamed(*renames):
    document = texts.TextDocument(NAMES)
    for table, row, name in renames:
        document.rename(table, row, name)
    return document.export()


def mod(name, params=None, names=None):
    files = {}
    if params is not None:
        files[RELATIVE] = params
    if names is not None:
        files[texts.RELATIVE] = names
    return mod_loader.Mod(name, Path(name), files)


def value(archive, table, row, key):
    return ItemDocument(archive).value(table, row, key)


def test_no_mods_change_nothing_and_one_mod_is_its_own_bytes():
    assert mod_loader.compose(GAME, []).files == {}
    alone = mod("A", edited(("EquipParamGoods", 100, "sellValue", 42)), renamed(("EquipParamGoods", 100, "Stone")))
    result = mod_loader.compose(GAME, [alone])
    assert result.files == alone.files and result.conflicts == []


def test_different_fields_of_one_row_both_apply():
    a = mod("A", edited(("EquipParamGoods", 100, "sellValue", 42)))
    b = mod("B", edited(("EquipParamGoods", 100, "maxNum", 7)))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    assert value(result.files[RELATIVE], "EquipParamGoods", 100, "sellValue") == 42
    assert value(result.files[RELATIVE], "EquipParamGoods", 100, "maxNum") == 7


def test_the_same_field_conflicts_and_the_later_mod_is_used():
    a = mod("A", edited(("EquipParamGoods", 100, "sellValue", 7)))
    b = mod("B", edited(("EquipParamGoods", 100, "sellValue", 11)))
    result = mod_loader.compose(GAME, [a, b])
    # Not a blend of the two numbers' bits: B's value, whole.
    assert value(result.files[RELATIVE], "EquipParamGoods", 100, "sellValue") == 11
    assert [(c.part, c.mods) for c in result.conflicts] == [("Items 100, " + label("EquipParamGoods", "sellValue"), ["A", "B"])]
    lines = result.by_mod([a, b])
    assert "B changes this too and loads later" in lines["A"][0] and "overrides A" in lines["B"][0]


def test_the_same_value_from_two_mods_is_no_conflict():
    a = mod("A", edited(("EquipParamGoods", 100, "sellValue", 9)))
    b = mod("B", edited(("EquipParamGoods", 100, "sellValue", 9)))
    assert mod_loader.compose(GAME, [a, b]).conflicts == []


def test_bitfields_sharing_a_byte_merge_by_their_own_bits():
    first, second = two_bits_in_one_byte("EquipParamGoods")
    a = mod("A", edited(("EquipParamGoods", 101, first, 1)))
    b = mod("B", edited(("EquipParamGoods", 101, second, 1)))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    assert value(result.files[RELATIVE], "EquipParamGoods", 101, first) == 1
    assert value(result.files[RELATIVE], "EquipParamGoods", 101, second) == 1


def test_a_member_that_is_not_a_param_is_taken_whole_from_the_last_mod():
    def with_member(payload):
        plain = bytearray(inflate(VANILLA))
        entry = members(plain)["Untouched.bin"]
        plain[entry.offset:entry.offset + entry.size] = payload
        return deflate(VANILLA, bytes(plain))
    a = mod("A", with_member(b"A-version payloa"[:18].ljust(18, b"!")))
    b = mod("B", with_member(b"B-version payloa"[:18].ljust(18, b"?")))
    result = mod_loader.compose(GAME, [a, b])
    plain = inflate(result.files[RELATIVE])
    entry = members(plain)["Untouched.bin"]
    assert plain[entry.offset:entry.offset + entry.size] == inflate(b.files[RELATIVE])[entry.offset:entry.offset + entry.size]
    assert [(c.part, c.mods) for c in result.conflicts] == [("Untouched.bin (whole table)", ["A", "B"])]


def test_item_names_merge_by_entry_and_conflict_on_the_same_one():
    a = mod("A", names=renamed(("EquipParamGoods", 100, "Alpha"), ("EquipParamWeapon", 100, "Blade")))
    b = mod("B", names=renamed(("EquipParamGoods", 101, "Beta"), ("EquipParamWeapon", 100, "Sword of B")))
    result = mod_loader.compose(GAME, [a, b])
    names = texts.TextDocument(result.files[texts.RELATIVE])
    assert names.name("EquipParamGoods", 100) == "Alpha" and names.name("EquipParamGoods", 101) == "Beta"
    assert names.name("EquipParamWeapon", 100) == "Sword of B"
    assert [c.mods for c in result.conflicts] == [["A", "B"]]


def test_a_library_lists_enabled_data_mods_in_order_and_the_open_project(tmp_path):
    import json
    for name, order, enabled in (("Late", 20, True), ("Early", 10, True), ("Off", 5, False), ("Open", 30, False)):
        folder = tmp_path / name
        (folder / RELATIVE).parent.mkdir(parents=True)
        (folder / MARKER).write_text("project", encoding="utf-8")
        (folder / RELATIVE).write_bytes(VANILLA)
        (folder / "mod.json").write_text(json.dumps({"name": name, "order": order, "enabled": enabled}), encoding="utf-8")
    (tmp_path / "Tweak").mkdir()
    (tmp_path / "Tweak" / "mod.json").write_text(json.dumps({"name": "Tweak", "enabled": True}), encoding="utf-8")
    names = [mod.name for mod in mod_loader.active_mods(tmp_path, tmp_path / "Open")]
    assert names == ["Early", "Late", "Open"]


def label(table, key):
    return next(item["spec"].label for item in schema(table)["fields"] if item["spec"].key == key)


def two_bits_in_one_byte(table):
    fields = [item for item in schema(table)["fields"] if item["editable"] and item["spec"].bit_size == 1]
    for item in fields:
        for other in fields:
            if other is not item and other["spec"].offset == item["spec"].offset:
                return item["spec"].key, other["spec"].key
    pytest.skip(f"{table} has no two editable one-bit fields in one byte")
