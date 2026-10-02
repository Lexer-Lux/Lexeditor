import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from ds1_stamina_fixture import make_stamina_archive, mutate_effect_header
from plugins.ds1.formats import FormatError, inflate
from plugins.ds1.stamina import (
    StaminaDocument, EFFECT_TABLE, RECOVERY_KEY, RECOVERY_FIELD,
)
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session


def recovery(document, row_id=6890):
    return document.read_row(EFFECT_TABLE, row_id)["fields"][0]["value"]


def project(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_stamina_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_reviewed_cell_and_exact_noop():
    raw = make_stamina_archive()
    doc = StaminaDocument(raw)
    assert RECOVERY_FIELD.offset == 0xB8 and RECOVERY_FIELD.dtype == "s32"
    assert doc.stamina_available
    assert doc.export() == raw and doc.dirty_count == 0
    assert recovery(doc) == 10
    assert doc.read_row(EFFECT_TABLE, 6890)["name"] == "Grass Crest Shield"


def test_only_selected_recovery_cells_change_and_revert():
    raw = make_stamina_archive()
    doc = StaminaDocument(raw)
    allowed = set()
    for row_id, value in ((6890, 4), (6200, -1), (40, 3)):
        start = doc._effect_row(row_id)[1] + 0xB8
        allowed.update(range(start, start + 4))
        doc.edit(EFFECT_TABLE, row_id, RECOVERY_KEY, value)
    before, after = inflate(raw), inflate(doc.export())
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    assert changed and changed <= allowed and len(before) == len(after)
    reopened = StaminaDocument(doc.export())
    assert [recovery(reopened, i) for i in (6890, 6200, 40)] == [4, -1, 3]
    assert recovery(reopened, 2013) == 0 and recovery(reopened, 6920) == 0
    assert recovery(reopened, 6201) == -2 and recovery(reopened, 41) == 0
    assert doc.dirty_count == 3
    for row_id, value in ((6890, 10), (6200, -2), (40, 0)):
        doc.edit(EFFECT_TABLE, row_id, RECOVERY_KEY, value)
    assert doc.export() == raw and doc.dirty_count == 0


@pytest.mark.parametrize("value", [-101, 101, 0.25, float("nan"), float("inf"),
                                  float("-inf"), True, False, "4", None, []])
def test_invalid_values_do_not_write(value):
    raw = make_stamina_archive()
    doc = StaminaDocument(raw)
    with pytest.raises(FormatError):
        doc.edit(EFFECT_TABLE, 6890, RECOVERY_KEY, value)
    assert doc.export() == raw and doc.dirty_count == 0


@pytest.mark.parametrize("value", [-100, 0, 100, 4.0])
def test_signed_boundaries_and_integral_floats(value):
    doc = StaminaDocument(make_stamina_archive())
    doc.edit(EFFECT_TABLE, 6890, RECOVERY_KEY, value)
    assert recovery(StaminaDocument(doc.export())) == int(value)


@pytest.mark.parametrize("row_id,key", [(6890, "changeStaminaPoint"),
                                       (True, RECOVERY_KEY), (999, RECOVERY_KEY)])
def test_unreviewed_fields_and_bad_ids_are_rejected(row_id, key):
    raw = make_stamina_archive()
    doc = StaminaDocument(raw)
    with pytest.raises(FormatError):
        doc.edit(EFFECT_TABLE, row_id, key, 4)
    assert doc.export() == raw


def test_actual_equipment_links_and_reference_categories():
    doc = StaminaDocument(make_stamina_archive())
    sources = doc.equipment_sources()[6890]
    assert {(s["table"], s["id"]) for s in sources} == {
        ("EquipParamWeapon", 100), ("EquipParamAccessory", 100)}
    assert doc.read_row("EquipParamWeapon", 100)["staminaEffects"][0]["id"] == 6890
    assert "staminaEffects" not in doc.read_row("EquipParamAccessory", 101)
    doc.edit("EquipParamWeapon", 100, "residentSpEffectId", 99001)
    assert doc.read_row("EquipParamWeapon", 100)["staminaEffects"][0]["id"] == 99001
    assert len(doc.equipment_sources()[6890]) == 1
    doc.edit("EquipParamAccessory", 101, "refCategory", 2)
    assert len(doc.equipment_sources()[6890]) == 2


def test_armor_and_player_effects_are_not_mislabelled_tiers_or_base():
    doc = StaminaDocument(make_stamina_archive())
    assert {r["id"] for r in doc.list_rows("stamina-armor")} == {6200, 6201}
    assert {r["id"] for r in doc.list_rows("stamina-player")} == set(range(40, 45))
    assert "not an equip-load percentage tier" in doc.read_row(EFFECT_TABLE, 6200)["staminaContext"]
    assert "not the engine's base recovery" in doc.read_row(EFFECT_TABLE, 40)["staminaContext"]
    assert 99001 in {r["id"] for r in doc.list_rows("stamina-equipment")}
    assert len(doc.list_rows("stamina-all")) == 12


def test_optional_missing_table_keeps_existing_items_readable():
    raw = make_archive()
    doc = StaminaDocument(raw)
    assert not doc.stamina_available and doc.export() == raw
    assert doc.list_rows("consumables")
    with pytest.raises(FormatError, match="missing"):
        doc.list_rows("stamina-equipment")


@pytest.mark.parametrize("options", [{"version": 2}, {"effect_size": 364}, {"effect_size": 372}])
def test_wrong_layouts_are_rejected(options):
    with pytest.raises(FormatError):
        StaminaDocument(make_stamina_archive(**options))


@pytest.mark.parametrize("offset,fmt,value", [
    (0, "<I", 1), (10, "<H", 0), (60, "<i", 40),
    (64, "<I", 48 + 12 * 12), (44, "<B", 1),
])
def test_bad_boundaries_duplicate_ids_and_headers(offset, fmt, value):
    with pytest.raises(FormatError):
        StaminaDocument(mutate_effect_header(make_stamina_archive(), offset, fmt, value))


def test_project_save_discard_readonly_and_stale_write(tmp_path):
    game, mod = project(tmp_path)
    original = (game / RELATIVE).read_bytes()
    store = ItemStore(game, mod, False)
    assert store.state()["staminaAvailable"]
    assert len(store.state()["staminaTabs"]) == 4
    store.edit(EFFECT_TABLE, 6890, RECOVERY_KEY, 4)
    store.save()
    assert (game / RELATIVE).read_bytes() == original
    assert recovery(ItemStore(game, mod, False).get()) == 4
    store.edit(EFFECT_TABLE, 6890, RECOVERY_KEY, 7)
    store.discard()
    assert recovery(store.get()) == 4
    with pytest.raises(PermissionError):
        ItemStore(game).edit(EFFECT_TABLE, 6890, RECOVERY_KEY, 1)
    store.edit(EFFECT_TABLE, 6890, RECOVERY_KEY, 8)
    (mod / RELATIVE).write_bytes(original)
    with pytest.raises(ValueError, match="changed outside"):
        store.save()


def test_service_stamina_edit_save_and_reload(tmp_path):
    game, mod = project(tmp_path)
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                          "LEXEDITOR_MOD_READ_ONLY": "0", "LEXEDITOR_NO_MOD": "0"})
    def request(path, payload=None):
        req = Request(session.url.rstrip("/") + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
        with urlopen(req) as reply:
            return json.load(reply)
    try:
        session.start()
        assert request("/api/state")["staminaAvailable"]
        assert request("/api/table?tab=stamina-equipment")["rows"]
        result = request("/api/edit", {"table": EFFECT_TABLE, "id": 6890,
                                       "field": RECOVERY_KEY, "value": 4})
        assert result["dirtyCount"] == 1
        assert request("/api/save", {})["saved"]
        request("/api/discard", {})
        assert request("/api/row?table=SpEffectParam&id=6890")["row"]["fields"][0]["value"] == 4
        with pytest.raises(HTTPError):
            request("/api/edit", {"table": EFFECT_TABLE, "id": 6890,
                                  "field": RECOVERY_KEY, "value": 101})
    finally:
        session.stop()
