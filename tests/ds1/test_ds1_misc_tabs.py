"""Misc tab owns Bands, Stamina and Overrides; the Encumbrance tab is gone."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ds1_fixture import make_archive
from plugins.ds1 import data_map
from plugins.ds1.formats import MISC_SUBTABS
from plugins.ds1.store import ItemStore, RELATIVE, MARKER

ROOT = Path(__file__).resolve().parents[2]


def make_store(root):
    game, mod = root / "game", root / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    return ItemStore(game, mod, False)


def test_misc_subtabs_are_bands_stamina_and_overrides():
    assert [(key, label, table) for key, label, table in MISC_SUBTABS] == [
        ("encumbrance", "Bands", "NativeRules"),
        ("misc", "Stamina", "NativeRules"),
        ("encumbrance-overrides", "Overrides", "NativeRules"),
    ]


def test_state_reports_misc_tabs(tmp_path):
    tabs = make_store(tmp_path).state()["miscTabs"]
    assert [(tab["id"], tab["label"], tab["table"]) for tab in tabs] == [
        ("encumbrance", "Bands", "NativeRules"),
        ("misc", "Stamina", "NativeRules"),
        ("encumbrance-overrides", "Overrides", "NativeRules"),
    ]


def test_data_map_points_native_rows_at_misc(tmp_path):
    store = make_store(tmp_path)
    rows = data_map.payload(store, {"native": {"available": True}})["rows"]
    native = {row["id"]: row for row in rows if row["id"].startswith("native-")}
    assert set(native) == {"native-misc", "native-encumbrance", "native-levelup"}
    assert (native["native-misc"]["target"], native["native-misc"]["sub"]) == ("misc", "misc")
    assert (native["native-encumbrance"]["target"], native["native-encumbrance"]["sub"]) == ("misc", "encumbrance")
    assert (native["native-levelup"]["target"], native["native-levelup"]["sub"]) == ("stats", "levelup")
    assert native["native-misc"]["targets"] == [{"id": "misc", "label": "Misc."}]
    assert native["native-encumbrance"]["targets"] == [{"id": "misc", "label": "Misc."}]
    # Every openable row names a known tab: none falls back to a raw id.
    for row in rows:
        for target in row.get("targets", []):
            assert target["label"] == data_map.TAB_LABELS[target["id"]]


def test_tab_labels_have_misc_but_no_encumbrance_tab():
    assert data_map.TAB_LABELS["misc"] == "Misc."
    assert "encumbrance" not in data_map.TAB_LABELS


def test_editor_mounts_misc_subtabs_and_no_encumbrance_tab():
    source = (ROOT / "plugins" / "ds1" / "editor.js").read_bytes()
    assert b'{id:"encumbrance",label:"Encumbrance"' not in source
    assert b'tab==="encumbrance"?[{id:"encumbrance"' not in source
    assert b"state.miscTabs" in source
    assert b'tab==="misc"?state.miscTabs' in source
    assert b'state.tab==="misc"?detail():renderItems()' not in source
    assert b"?renderTweaks():renderItems()" in source
