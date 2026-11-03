"""DS1 help has one store: the annotation files.

Every schema description is its annotation Description byte for byte: no
map, branch or formatter in code may restate it. save_description is the
only writer, and it keeps the files' own bytes (indent 2, CRLF).
"""
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1 import formats  # noqa: E402
from plugins.ds1.formats import FormatError  # noqa: E402
from plugins.ds1.effects import presentation  # noqa: E402


def annotation_file(table):
    root = ET.parse(formats.METADATA / "defs" / (table + ".xml")).getroot()
    return formats.METADATA / "annotations" / (root.findtext("ParamType") + ".json")


def test_every_schema_description_is_its_annotation():
    # Lexer: annotation-overriding code is spaghetti; there should be no
    # such code. Any branch that restates a description breaks this.
    checked = 0
    for table in sorted(formats.TABLES):
        entries = {entry["Field"]: entry
                   for entry in json.loads(annotation_file(table).read_text("utf-8"))["Fields"]}
        for item in formats.schema(table)["fields"]:
            spec = item["spec"]
            assert spec.description == entries.get(spec.key, {}).get("Description", ""), (
                table, spec.key)
            checked += 1
    assert checked > 1000, checked


def test_field_maps_carry_no_descriptions():
    for key, value in list(formats.ARMOR_FIELDS.items()) + list(formats.WEAPON_FIELDS.items()):
        assert len(value) == 2, (key, value)


def test_effect_presentation_keeps_the_annotation_text():
    label, group, description = presentation("maxHpRate", "Maximum HP (x)", "Multiplies maximum HP.")
    assert description == "Multiplies maximum HP.", description
    assert label == "Maximum HP (x)"


@pytest.fixture
def scratch_metadata(tmp_path, monkeypatch):
    target = tmp_path / "metadata"
    shutil.copytree(formats.METADATA, target)
    monkeypatch.setattr(formats, "METADATA", target)
    return target


def read_entry(target, key):
    document = json.loads((target / "annotations" / "EQUIP_PARAM_WEAPON_ST.json").read_text("utf-8"))
    return next(entry for entry in document["Fields"] if entry["Field"] == key)


def test_save_description_rewrites_one_entry(scratch_metadata):
    before = (scratch_metadata / "annotations" / "EQUIP_PARAM_WEAPON_ST.json").read_bytes()
    stem = formats.save_description("EquipParamWeapon", "trophySeqId",
                                    "Edited in the test.")
    assert stem == "EQUIP_PARAM_WEAPON_ST"
    assert read_entry(scratch_metadata, "trophySeqId")["Description"] == "Edited in the test."
    after = (scratch_metadata / "annotations" / "EQUIP_PARAM_WEAPON_ST.json").read_bytes()
    # Only that line changed; the file's own bytes are otherwise intact.
    assert after.count(b"\r\n") == before.count(b"\r\n")
    assert after.count(b"\n") == after.count(b"\r\n"), "no LF-only endings"
    assert after != before


def test_save_description_validation(scratch_metadata):
    with pytest.raises(FormatError, match="Unknown parameter table"):
        formats.save_description("NoSuchTable", "trophySeqId", "text")
    with pytest.raises(FormatError, match="has no spareKey"):
        formats.save_description("EquipParamWeapon", "spareKey", "text")
    with pytest.raises(FormatError, match="cannot be blank"):
        formats.save_description("EquipParamWeapon", "trophySeqId", "   ")
    long_text = "x" * (formats.MAX_HELP_TEXT + 1)
    with pytest.raises(FormatError, match=str(len(long_text))):
        formats.save_description("EquipParamWeapon", "trophySeqId", long_text)
    with pytest.raises(FormatError, match="one paragraph"):
        formats.save_description("EquipParamWeapon", "trophySeqId", "one\ntwo")
    with pytest.raises(FormatError, match="must be text"):
        formats.save_description("EquipParamWeapon", "trophySeqId", 42)


def test_save_description_drops_the_schema_cache(scratch_metadata):
    formats.schema("EquipParamWeapon")
    assert formats.schema.cache_info().currsize >= 1
    formats.save_description("EquipParamWeapon", "trophySeqId", "Edited in the test.")
    assert formats.schema.cache_info().currsize == 0
