"""Every DS1 field uses the control its schema calls for.

Global audit (todo.txt): appropriate bounded inputs; unknown or unproven
fields read-only, including save validation. This sweeps every parameter
table's schema and every shown row of the synthetic archives: booleans
render as checkboxes, enums with choices as selects, numbers bounded
except documented-unbounded floats, text with a length cap, and the
backend rejects what the controls forbid. Map placements, animation
events and native rules follow their own documented conventions, asserted
here through their fixtures: coordinates and timestamps are unbounded
floats (no range exists), npcId is an enemy select at the store layer,
whole-width integers show no range, and every native number is bounded.
"""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive, make_text_archive
from ds1_effects_fixture import make_effects_archive
from msb_fixture import build_msb
from tae_fixture import build_tae
from plugins.ds1 import encumbrance, texts
from plugins.ds1.formats import FormatError, ItemDocument, TABLES, schema
from plugins.ds1.monsters import NPC_FIELDS
from plugins.ds1.msb import MsbDocument
from plugins.ds1.native_rules import DEFAULTS
from plugins.ds1.tae import BOUNDED, KINDS, TaeDocument

FLOAT_DTYPES = ("f32", "f64", "angle32")
DTYPE_EXTREMES = {(-3.4028234663852886e38, 3.4028234663852886e38),
                  (-1.7976931348623157e308, 1.7976931348623157e308)}


def test_every_schema_field_names_its_control():
    for table in TABLES:
        for item in schema(table)["fields"]:
            field = item["spec"]
            if not item["editable"]:
                continue
            assert not field.padding and field.array_length == 1, (table, field.key)
            assert item["min"] <= item["max"], (table, field.key)
            if field.is_bool or item["enum"]:
                continue  # checkbox, or select with choices checked per row below
            assert item["enum"] == {}, (table, field.key)  # else a number


def _readable_rows(document):
    """One shown row per table; every table must show one."""
    rows, missing = [], []
    for table in document.params:
        shown = None
        for row in document.params[table].rows:
            try:
                shown = document.read_row(table, row.row_id)
            except FormatError:
                continue  # unreviewed records are not shown at all
            rows.append((table, row.row_id, shown))
            break
        if shown is None:
            missing.append(table)
    assert missing == []
    return rows


def _documents():
    base = ItemDocument(make_archive())
    base.texts = texts.TextDocument(make_text_archive())
    return base, ItemDocument(make_effects_archive())


def test_every_shown_field_uses_its_schemas_control():
    checked, text_seen, tables = 0, False, set()
    for document in _documents():
        for table, _row_id, shown in _readable_rows(document):
            tables.add(table)
            items = {item["spec"].key: item for item in document.schemas[table]["fields"]}
            for field in shown["fields"]:
                if field["type"] in ("text", "longtext"):
                    assert field["maxLength"] > 0, (table, field["key"])
                    text_seen = True
                    checked += 1
                    continue
                item = items[field["key"]]
                spec = item["spec"]
                assert item["editable"] or not field["editable"], (table, field["key"])
                if field["type"] == "bool":
                    assert spec.is_bool, (table, field["key"])
                elif field["type"] == "enum":
                    assert len(field["enum"]) > 0, (table, field["key"])
                else:
                    assert field["type"] == "number", (table, field["key"])
                    if field["minimum"] is None or field["maximum"] is None:
                        assert spec.dtype in FLOAT_DTYPES, (table, field["key"])
                        assert (item["min"], item["max"]) in DTYPE_EXTREMES, (table, field["key"])
                    else:
                        assert field["minimum"] <= field["maximum"], (table, field["key"])
                checked += 1
    assert text_seen and checked > 100
    assert "SpEffectParam" in tables


def test_backend_rejects_values_outside_the_shown_bounds():
    document = ItemDocument(make_archive())
    checked = 0
    for table, row_id, shown in _readable_rows(document):
        for field in shown["fields"]:
            if not field["editable"] or field["type"] not in ("number", "enum", "bool"):
                continue
            if field["type"] == "bool":
                with pytest.raises(FormatError):
                    document.edit(table, row_id, field["key"], 2)
                checked += 1
                continue
            if field["type"] == "enum":
                for bad in (-99999999, 99999999):
                    with pytest.raises(FormatError):
                        document.edit(table, row_id, field["key"], bad)
                checked += 1
                continue
            if field["minimum"] is None:
                continue  # documented-unbounded floats: only infinity is refused
            with pytest.raises(FormatError):
                document.edit(table, row_id, field["key"], field["minimum"] - 1)
            with pytest.raises(FormatError):
                document.edit(table, row_id, field["key"], field["maximum"] + 1)
            checked += 1
    assert checked > 50
    assert document.export() == document.original


def test_unreviewed_and_padding_fields_stay_read_only():
    document = ItemDocument(make_archive())
    padding = next(f["spec"].key for f in document.schemas["EquipParamGoods"]["fields"]
                   if f["spec"].padding)
    with pytest.raises(FormatError):
        document.edit("EquipParamGoods", 100, padding, 0)
    others = [f["spec"].key for f in document.schemas["NpcParam"]["fields"]
              if f["spec"].key not in NPC_FIELDS]
    assert others
    for key in others:
        with pytest.raises(FormatError):
            document.edit("NpcParam", 120000, key, 1)


def test_native_rule_rows_use_bounded_controls():
    config = deepcopy(DEFAULTS)
    rows = [encumbrance.row(config["bands"][0]["id"], config),
            encumbrance.overrides(config)]
    kinds = set()
    for row in rows:
        assert len(row["fields"]) > 0
        for field in row["fields"]:
            kinds.add(field["type"])
            if field["type"] == "bool":
                assert (field["minimum"], field["maximum"]) == (0, 1)
            elif field["type"] == "enum":
                assert len(field["enum"]) > 0
            elif field["type"] == "number":
                assert field["minimum"] is not None and field["maximum"] is not None
                assert field["minimum"] <= field["maximum"]
            elif field["type"] == "text":
                assert field["maxLength"] > 0
            else:
                raise AssertionError(field["type"])
    assert {"bool", "enum", "number", "text"} <= kinds


def test_placement_coordinates_are_unbounded_floats_by_design():
    """World coordinates have no valid range; the enemy stays a select.

    msb.py documents the unbounded floats; map_store.py turns npcId into
    the enemy select (test_ds1_map_store.py pins that conversion).
    """
    fields = {field["key"]: field
              for field in MsbDocument(build_msb()).read_placement((2, 0))["fields"]}
    assert set(fields) >= {"posX", "posY", "posZ", "rotX", "rotY", "rotZ", "npcId"}
    for key in ("posX", "posY", "posZ", "rotX", "rotY", "rotZ"):
        assert fields[key]["type"] == "number" and fields[key]["editable"]
        assert fields[key]["minimum"] is None and fields[key]["maximum"] is None
        assert fields[key]["dtype"] == "f32"
    assert fields["npcId"]["dtype"] == "s32" and fields["npcId"]["editable"]


def test_animation_events_bound_only_narrow_kinds():
    """Whole-width integers and timestamps show no range (tae.py BOUNDED)."""
    by_key = {field["key"]: field
              for field in TaeDocument(build_tae()).read_event(0, 0)["fields"]}
    assert by_key["start"]["minimum"] is None and by_key["end"]["minimum"] is None
    for key in ("attackType", "attackIndex", "judge"):
        assert by_key[key]["dtype"] == "s32"
        assert by_key[key]["minimum"] is None and by_key[key]["maximum"] is None
    assert BOUNDED == frozenset({"u8", "u16"})
    for kind, (_code, minimum, maximum) in KINDS.items():
        if kind in BOUNDED:
            assert minimum is not None and maximum is not None
