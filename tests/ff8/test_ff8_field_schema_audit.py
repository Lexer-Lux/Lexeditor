"""FF8 fields against their schema: bounded inputs, read-only unknowns.

Every kernel section's numeric fields stay inside their stored size, every
unknown/padding/unused field stays out of the editable set, every schema
lookup either resolves to a served enum/flags payload or is inventoried
below as number-rendered by design, and Shot ammo names its consumed item
through the item select instead of a bare number.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from plugins.ff8 import formats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import page, framework, ROOT  # noqa: E402


# Schema lookups with no static enum behind them. Each renders as a bounded
# number until the noted work proves the finite choice; anything else
# unresolvable fails this test instead of silently becoming a number.
NUMBER_RENDERED = {
    # No proved animation-id list exists anywhere in the schema or codex.
    "attack_animation",
    # An index into section 1 (battle commands), which no page loads yet.
    "battle_command",
    # An index into section 11 (command ability data); same, plus the names
    # would come from ability text.
    "command_ability_ref",
    # Promised as a live dropdown of section 28's sets (dynamic_lookup), but
    # no page shows sections 27/28 and nothing builds it.
    "slot_set_summary",
}


def test_schema_bounds_masks_and_lookups_are_consistent():
    for key, section in sorted(formats.SECTION_FIELDS.items()):
        for field in section["fields"]:
            size = int(field.get("size", 1))
            capacity = (1 << (size * 8)) - 1
            minimum, maximum = int(field.get("minimum", 0)), int(field.get("maximum", capacity))
            assert 0 <= minimum <= maximum <= capacity, (key, field["name"], minimum, maximum, size)
            if field.get("mask") is not None:
                assert 0 < int(field["mask"]) <= capacity, (key, field["name"])
            if field.get("bool"):
                assert size == 1, (key, field["name"])
            lookup = field.get("lookup")
            if lookup:
                assert (lookup in formats.LOOKUPS or lookup == "item"
                        or lookup in NUMBER_RENDERED), (key, field["name"], lookup)


def test_unknown_padding_and_unused_fields_are_not_editable():
    for key, section in sorted(formats.SECTION_FIELDS.items()):
        public = {field["name"] for field in formats._public_fields(key)}
        for field in section["fields"]:
            name, label = str(field.get("name", "")), str(field.get("label") or "")
            if name.startswith(("unknown", "padding", "unused")) or label.casefold() in {"padding", "unused"}:
                assert name not in public, (key, name)
            if field.get("display_readonly"):
                assert field.get("readonly"), (key, name)


def _section22_bin(tmp_path):
    section = formats.SECTIONS[22]
    raw = bytearray(512 + section["number_sub_section"] * section["sub_section_size"])
    raw[22 * 4:22 * 4 + 4] = (512).to_bytes(4, "little")
    for index in range(section["number_sub_section"]):
        raw[512 + index * section["sub_section_size"] + 18] = 101 + index
    path = tmp_path / "kernel.bin"
    path.write_bytes(raw)
    return path


def test_shot_ammo_serves_the_item_enum_and_validates_it(tmp_path):
    path = _section22_bin(tmp_path)
    with patch.object(formats, "source_path", return_value=path), \
            patch.object(formats, "output_path", return_value=path):
        rows = formats.kernel_rows(22)["rows"]
        assert len(rows) == formats.SECTIONS[22]["number_sub_section"]
        used = next(field for field in rows[0]["fields"] if field["field"] == "used_item_index")
        assert used["lookup"] == {"name": "item", "type": "enum", "entries": used["lookup"]["entries"]}
        assert len(used["lookup"]["entries"]) == len(formats.ITEMS) == 200
        assert {entry["value"] for entry in used["lookup"]["entries"]} == {
            row["id"] for row in formats.ITEMS}
        assert all(entry["name"] and not entry["readonly"] for entry in used["lookup"]["entries"])
        formats.save_kernel(22, [{"id": 0, "field": "used_item_index", "value": 103}])
        assert formats.kernel_rows(22)["rows"][0]["fields"][
            [field["field"] for field in rows[0]["fields"]].index("used_item_index")]["value"] == 103
        missing = next(i for i in range(256) if i not in {row["id"] for row in formats.ITEMS})
        with pytest.raises(ValueError, match="documented option"):
            formats.save_kernel(22, [{"id": 0, "field": "used_item_index", "value": missing}])
        with pytest.raises(ValueError, match="must be 0 to 255"):
            formats.save_kernel(22, [{"id": 0, "field": "used_item_index", "value": 300}])


def test_shipped_shot_ammo_values_are_all_documented_items():
    root = Path(os.environ["LOCALAPPDATA"]) / "Lexeditor/game-data/ff8/baseline/en/main/kernel.bin"
    if not root.is_file():
        pytest.skip("Requires extracted FF8 baseline")
    section = formats.SECTIONS[22]
    raw = root.read_bytes()
    start = int.from_bytes(raw[22 * 4:22 * 4 + 4], "little")
    known = {row["id"]: row["name"] for row in formats.ITEMS}
    for index in range(section["number_sub_section"]):
        value = raw[start + index * section["sub_section_size"] + 18]
        assert value in known, (index, value)


def _render_field(page, field, items):
    framework(page)
    page.add_script_tag(path=str(ROOT / "plugins/ff8/core.js"))
    page.add_script_tag(content="const shell={refresh(){}};function render(){}")
    page.add_script_tag(path=str(ROOT / "plugins/ff8/records.js"))
    page.add_script_tag(path=str(ROOT / "plugins/ff8/party.js"))
    page.evaluate("""([field, items]) => {
      state.data.items = {rows: items};
      state.vanilla = {ammoEffects: {rows: [{id: 0, fields: [field]}]}};
      document.querySelector('main').append(
        fieldSourceControl(structuredClone(field), 'ammoEffects', 0));
    }""", [field, items])


def test_shot_ammo_renders_the_item_select_with_names(page, tmp_path):
    path = _section22_bin(tmp_path)
    with patch.object(formats, "source_path", return_value=path):
        field = next(field for field in formats.kernel_rows(22)["rows"][0]["fields"]
                     if field["field"] == "used_item_index")
    assert field["value"] == 101
    _render_field(page, field, formats.item_choices())
    select = page.get_by_role("combobox").first
    assert select.evaluate("n=>n.tagName") == "SELECT"
    assert select.locator("option").first.inner_text() == "Normal Ammo"
    select.focus()
    page.wait_for_function(
        "()=>document.querySelectorAll('select option').length>100", timeout=5000)
    assert select.locator("option").count() == 200
    # The item select carries its icon slot beside the dropdown (the game
    # icon itself cannot load on this fixture, so only the slot is asserted).
    assert select.evaluate("n=>n.closest('.lex-inline-label')!==null")


def test_attack_animation_renders_a_bounded_number(page):
    framework(page)
    page.add_script_tag(path=str(ROOT / "plugins/ff8/core.js"))
    page.add_script_tag(content="const shell={refresh(){}};function render(){}")
    page.add_script_tag(path=str(ROOT / "plugins/ff8/party.js"))
    field = {"field": "attack_animation", "label": "Attack animation", "help": "",
             "value": 0, "minimum": 0, "maximum": 65535, "lookup": None}
    page.evaluate("""field => {
      state.vanilla = {};
      document.querySelector('main').append(fieldControl(field));
    }""", field)
    number = page.locator("input[type=number]")
    assert number.get_attribute("min") == "0"
    assert number.get_attribute("max") == "65535"
