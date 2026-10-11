"""Map project overlay: vanilla or saved edits, names linked, stale-safe."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from msb_fixture import build_msb
from plugins.ds1.map_store import MapStore
from plugins.ds1.msb import MAP_DIR, MsbDocument, MsbError
from plugins.ds1.store import ItemStore, MARKER, RELATIVE

MAP = "m10_00_00_00.msb"


def setup(tmp_path, maps=(MAP,), npc=120000):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / MAP_DIR).mkdir(parents=True)
    for name in maps:
        (game / MAP_DIR / name).write_bytes(build_msb(parts=(("enemy", 2, 0, 0, npc),)))
    mod.mkdir()
    (mod / MARKER).touch()
    items = ItemStore(game, mod, False)
    return game, mod, MapStore(game, mod, False, items)


def test_list_rows_link_enemy_names_with_unknown_fallback(tmp_path):
    _game, _mod, store = setup(tmp_path, npc=120000)
    rows = store.list_rows()
    assert [(row["id"], row["table"], row["name"]) for row in rows] == [("2:0", MAP, "enemy0")]
    assert rows[0]["values"]["npcId"] == 120000 and rows[0]["display"]["npcId"]
    _game, _mod, dangling = setup(tmp_path / "other", npc=999001)
    assert dangling.list_rows()[0]["display"]["npcId"] == "Unknown (999001)"


def test_read_returns_enum_choices_and_vanilla_values(tmp_path):
    _game, _mod, store = setup(tmp_path)
    row = store.read(MAP, "2:0")
    assert (row["id"], row["table"], row["map"]) == ("2:0", MAP, MAP)
    npc = next(item for item in row["fields"] if item["key"] == "npcId")
    assert npc["type"] == "enum" and npc["enum"]["120000"] and npc["vanilla"] == 120000
    pos = next(item for item in row["fields"] if item["key"] == "posX")
    assert (pos["value"], pos["vanilla"]) == (1.0, 1.0)


def test_edit_save_reload_and_discard_round_trip(tmp_path):
    game, mod, store = setup(tmp_path)
    store.edit(MAP, "2:0", "posX", 10.5)
    store.edit(MAP, "2:0", "npcId", 120100)
    assert store.dirty_count == 2
    changes = store.pending_changes()
    assert len(changes) == 1 + 1 and all(change["label"].startswith(MAP) for change in changes)
    store.save()
    assert store.dirty_count == 0
    assert (mod / MAP_DIR / MAP).is_file()
    fresh = MapStore(game, mod, False, ItemStore(game, mod, False))
    row = fresh.read(MAP, "2:0")
    assert next(item for item in row["fields"] if item["key"] == "posX")["value"] == 10.5
    assert next(item for item in row["fields"] if item["key"] == "npcId")["value"] == 120100
    fresh.edit(MAP, "2:0", "posX", 1.0)
    fresh.discard()
    assert fresh.dirty_count == 0
    assert next(item for item in fresh.read(MAP, "2:0")["fields"] if item["key"] == "posX")["value"] == 10.5


def test_stale_project_and_live_files_refuse_save(tmp_path):
    game, mod, store = setup(tmp_path)
    store.edit(MAP, "2:0", "posX", 10.5)
    (mod / MAP_DIR).mkdir(parents=True)
    (mod / MAP_DIR / MAP).write_bytes(build_msb())
    with pytest.raises(ValueError, match="outside Lexeditor"):
        store.save()
    _game, _mod, live = setup(tmp_path / "live")
    live.edit(MAP, "2:0", "posX", 10.5)
    (live.game_root / MAP_DIR / MAP).write_bytes(live.get(MAP).export())
    with pytest.raises(ValueError, match="outside Lexeditor"):
        live.save()


def test_read_only_and_unknown_targets_fail_closed(tmp_path):
    game, mod, _store = setup(tmp_path)
    frozen = MapStore(game, mod, True, ItemStore(game, mod, True))
    with pytest.raises(PermissionError):
        frozen.edit(MAP, "2:0", "posX", 1.0)
    store = MapStore(game, mod, False, ItemStore(game, mod, False))
    with pytest.raises(MsbError):
        store.read("m99_00_00_00.msb", "2:0")
    with pytest.raises(MsbError):
        store.read(MAP, "nope")
    with pytest.raises(MsbError):
        store.edit(MAP, "2:0", "npcId", 999001)
