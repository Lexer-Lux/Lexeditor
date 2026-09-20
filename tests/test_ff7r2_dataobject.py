from __future__ import annotations

import pytest

from games.ff7r2.dataobject import DataObjectError, DataObjectPackage
from ff7r2_fixture import fixture


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
