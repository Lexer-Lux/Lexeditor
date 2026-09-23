from __future__ import annotations

import pytest

from plugins.ff7r2.dataobject import DataObjectError, DataObjectPackage
from ff7r2_fixture import battle_item_possession_fixture, battle_player_parameter_fixture, fixture


def test_fixture_parses_real_record_identity_and_scalar_types():
    package = DataObjectPackage.from_bytes(fixture())
    assert [record.key.text for record in package.records[:2]] == ["Cloud", "Tifa"]
    assert len(package.records) == 24
    cloud = package.records[0]
    assert {field.name: field.value for field in cloud.fields} == {
        "HPMax": 1000, "MPMax": 50, "Strength": 30, "Spilit": 22,
        "Mode": "ModeA",
    }
    assert all(field.editable for field in cloud.fields if field.name != "Mode")
    mode = next(field for field in cloud.fields if field.name == "Mode")
    assert mode.kind == "name" and mode.editable is False


def test_fixed_width_edits_roundtrip_and_preserve_every_other_byte():
    source = fixture()
    package = DataObjectPackage.from_bytes(source)
    hp = package.records[0].fields[0]
    strength = package.records[0].fields[2]
    changed = package.apply_edits([
        {"nameIndex": 1, "nameNumber": 0, "property": "HPMax", "value": 1234},
        {"nameIndex": 1, "nameNumber": 0, "property": "Strength", "value": 44},
    ])
    assert changed == 2
    edited = package.to_bytes()
    touched = set(range(hp.offset, hp.offset + hp.size))
    touched.update(range(strength.offset, strength.offset + strength.size))
    assert all(
        before == after
        for index, (before, after) in enumerate(zip(source, edited))
        if index not in touched
    )

    reopened = DataObjectPackage.from_bytes(edited)
    values = {field.name: field.value for field in reopened.records[0].fields}
    assert values["HPMax"] == 1234
    assert values["Strength"] == 44


def test_out_of_storage_range_is_rejected_without_mutation():
    source = fixture()
    package = DataObjectPackage.from_bytes(source)
    with pytest.raises(DataObjectError, match="at most 32767"):
        package.apply_edits([
            {"nameIndex": 1, "property": "Strength", "value": 40000},
        ])
    assert package.to_bytes() == source



def test_frozen_name_property_rejects_byte_patch_edit():
    package = DataObjectPackage.from_bytes(fixture())
    with pytest.raises(DataObjectError, match="read-only"):
        package.apply_edits([
            {"nameIndex": 1, "property": "Mode", "value": "ModeB"},
        ])


def test_noop_parse_is_byte_exact():
    source = fixture()
    package = DataObjectPackage.from_bytes(source)
    assert package.to_bytes() == source


@pytest.mark.parametrize("cut", [0, 8, 63, 64, 120])
def test_truncated_assets_are_rejected(cut):
    source = fixture()[:cut]
    with pytest.raises(DataObjectError):
        DataObjectPackage.from_bytes(source)

def test_array_elements_decode_read_only_and_preserve_source_bytes():
    source = battle_item_possession_fixture()
    package = DataObjectPackage.from_bytes(source)
    assert package.to_bytes() == source
    row = package.records[0]
    values = {field.name: field.value for field in row.fields}
    assert values["NormalItemName_Array"] == ["Potion", "HiPotion"]
    assert values["NormalItemPercent_Array"] == [25, 75]
    assert values["RareItemName_Array"] == ["Ether"]
    assert values["RareItemPercent_Array"] == [10]
    assert values["StealItemName_Array"] == ["Potion", "Ether"]
    assert values["StealItemQuantity_Array"] == [1, 2]
    assert values["StealFaildCountArrayIndex"] == 3
    types = {field.name: field.type_name for field in row.fields}
    assert types["NormalItemName_Array"] == "NameProperty"
    assert types["RareItemName_Array"] == "NameProperty"
    assert types["StealItemName_Array"] == "NameProperty"
    assert types["NormalItemPercent_Array"] == "ByteProperty"
    assert types["RareItemPercent_Array"] == "ByteProperty"
    assert types["StealItemQuantity_Array"] == "ByteProperty"
    assert types["StealFaildCountArrayIndex"] == "IntProperty"
    arrays = [field for field in row.fields if field.kind == "array"]
    assert arrays
    assert all(field.editable is False for field in arrays)
    assert all("array writes remain disabled" in field.note for field in arrays)
    payload = package.payload()
    payload_arrays = {
        field["name"]: field for field in payload["records"][0]["fields"]
        if field["kind"] == "array"
    }
    assert payload_arrays["StealItemName_Array"]["arrayCount"] == 2
    assert payload_arrays["RareItemName_Array"]["arrayCount"] == 1


def test_array_edit_is_rejected_without_mutation():
    source = battle_item_possession_fixture()
    package = DataObjectPackage.from_bytes(source)
    with pytest.raises(DataObjectError, match="read-only"):
        package.apply_edits([{
            "nameIndex": package.records[0].key.index,
            "property": "NormalItemPercent_Array",
            "value": [100, 100],
        }])
    assert package.to_bytes() == source


def test_array_data_pointer_outside_asset_is_rejected():
    source = battle_item_possession_fixture()
    parsed = DataObjectPackage.from_bytes(source)
    field = next(
        item for item in parsed.records[0].fields
        if item.name == "NormalItemPercent_Array"
    )
    damaged = bytearray(source)
    bad_target = len(damaged) + 64
    offset = bad_target - field.offset
    import struct
    struct.pack_into("<Q", damaged, field.offset, (offset << 1) | 1)
    with pytest.raises(DataObjectError):
        DataObjectPackage.from_bytes(bytes(damaged))

def test_name_array_element_without_minimal_name_is_rejected():
    source = battle_item_possession_fixture(omit_first_array_name_mapping=True)
    with pytest.raises(DataObjectError, match="has no minimal-name identity"):
        DataObjectPackage.from_bytes(source)



def test_battle_player_parameter_public_storage_signature_decodes_without_writes():
    source = battle_player_parameter_fixture()
    package = DataObjectPackage.from_bytes(source)
    assert package.to_bytes() == source
    row = package.records[0]
    values = {field.name: field.value for field in row.fields}
    assert row.key.text == "BattleCharacterTest"
    assert values["CommandAbilityID_Array"] == ["AbilityTest"]
    assert values["EnableAerialShortCut"] == 1
    assert values["UniqueAbilityType0"] == 2
    assert values["UniqueAbilityParameterValue_Array"] == pytest.approx([1.25, 2.5])
    assert values["KeyDownTime"] == pytest.approx(0.4)
    assert values["KeyDownEffectCreateTime"] == pytest.approx(0.2)
    assert values["GuardParameterValue_Array"] == pytest.approx([0.5])
    assert values["DodgeType_Array"] == [1, 2]
    assert values["LimitAbilityID_Array"] == ["LimitTest"]
    arrays = [field for field in row.fields if field.kind == "array"]
    assert arrays and all(field.editable is False for field in arrays)
