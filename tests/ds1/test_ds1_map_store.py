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
    assert [(row["id"], row["table"], row["name"]) for row in rows] == [("2:0", MAP, "Rat")]
    assert rows[0]["values"]["npcId"] == 120000 and rows[0]["display"]["npcId"]
    assert rows[0]["values"]["part"] == "enemy0"
    assert rows[0]["values"]["mapNames"] == [MAP]
    _game, _mod, dangling = setup(tmp_path / "other", npc=999001)
    assert dangling.list_rows()[0]["display"]["npcId"] == "Unknown (999001)"
    assert dangling.list_rows()[0]["name"] == "Unknown (999001)"


def test_list_rows_carry_npc_type_for_the_directory_split(tmp_path):
    _game, _mod, foes = setup(tmp_path / "foes", npc=120000)
    assert foes.list_rows()[0]["values"]["npcType"] == 0
    _game, _mod, friends = setup(tmp_path / "friends", npc=251000)
    assert friends.list_rows()[0]["values"]["npcType"] == 2


def test_locate_drop_finds_first_placement_of_a_dropper(tmp_path):
    _game, _mod, store = setup(tmp_path)
    store.item_store.edit("NpcParam", 120000, "itemLotId_1", 100)
    assert store.locate_drop(100) == {"map": MAP, "key": "2:0"}
    assert store.locate_drop(9999) is None


def test_read_returns_enum_choices_and_vanilla_values(tmp_path):
    _game, _mod, store = setup(tmp_path)
    row = store.read(MAP, "2:0")
    assert (row["id"], row["table"], row["map"]) == ("2:0", MAP, MAP)
    assert row["name"] == "Rat"
    assert row["shortName"] == "Rat"
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

def test_read_links_the_enemy_for_face_and_finder(tmp_path):
    _game, _mod, store = setup(tmp_path)
    row = store.read(MAP, "2:0")
    (link,) = [entry for entry in row["recordLinks"] if entry["field"] == "npcId"]
    assert (link["kind"], link["table"], link["id"]) == ("npc", "NpcParam", 120000)
    assert link["resolved"] and link["name"]
    assert (link["tab"], link["sub"]) == ("enemies", "monsters")
    _game, _mod, bosses = setup(tmp_path / "bosses", npc=223000)
    (boss,) = [entry for entry in bosses.read(MAP, "2:0")["recordLinks"]
               if entry["field"] == "npcId"]
    assert (boss["tab"], boss["sub"]) == ("enemies", "bosses")
    _game, _mod, friends = setup(tmp_path / "friends", npc=251000)
    (friend,) = [entry for entry in friends.read(MAP, "2:0")["recordLinks"]
                 if entry["field"] == "npcId"]
    assert (friend["tab"], friend["sub"]) == ("npcs", "npcs")
    _game, _mod, dangling = setup(tmp_path / "dangling", npc=999001)
    (missing,) = [entry for entry in dangling.read(MAP, "2:0")["recordLinks"]
                  if entry["field"] == "npcId"]
    assert not missing["resolved"]


def test_list_rows_mark_modified_after_edit(tmp_path):
    _game, _mod, store = setup(tmp_path)
    assert all(not row.get("modified") for row in store.list_rows())
    store.get(MAP).edit((2, 0), "posX", 10.5)
    flags = {row["id"]: row.get("modified") for row in store.list_rows()}
    assert flags == {"2:0": True}


def test_npc_models_falls_back_to_same_hundred_binder(tmp_path):
    game, mod, store = setup(tmp_path, npc=120000)
    (game / "chr").mkdir(parents=True)
    (game / "chr" / "c1201.chrbnd.dcx").write_bytes(b"fake binder")
    (mod / "chr").mkdir(parents=True)
    (mod / "chr" / "c2510.chrbnd.dcx").write_bytes(b"fake binder")
    links = store.npc_models()
    assert links[120000] == ["c1200"]
    assert links[120100] == ["c1201"]
    assert links[251000] == ["c2510"]
    assert 999999 not in links


def test_npc_models_placements_beat_the_fallback(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / MAP_DIR).mkdir(parents=True)
    (game / MAP_DIR / MAP).write_bytes(build_msb(parts=(("enemy", 2, 0, 0, 120000),),
                                                  models=(("c9999", 0), ("m10piece", 0))))
    (game / "chr").mkdir(parents=True)
    (game / "chr" / "c1200.chrbnd.dcx").write_bytes(b"fake binder")
    mod.mkdir()
    (mod / MARKER).touch()
    store = MapStore(game, mod, False, ItemStore(game, mod, False))
    assert store.npc_models()[120000] == ["c9999"]
