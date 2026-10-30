"""Adding and removing param rows and map placements.

Synthetic archives and maps only; nothing touches an installed game.
"""
import json
from pathlib import Path
import struct
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from msb_fixture import build_msb
from plugins.ds1 import mod_loader
from plugins.ds1.formats import FormatError, ItemDocument, TABLES
from plugins.ds1.monsters import MONSTER_FAMILIES, base_stem, duplicate_stem
from plugins.ds1.msb import MAP_DIR, MsbDocument, MsbError
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds3.formats import ParamView

MAP = MAP_DIR / "m10_00_00_00.msb"


def goods_member():
    document = ItemDocument(make_archive())
    member = document.members["EquipParamGoods.param"]
    payload = bytes(document.plain[member.offset:member.offset + member.size])
    return document, payload


def test_duplicate_name_helpers():
    assert duplicate_stem("Rat (1000000)", 1000000) == "Rat"
    assert duplicate_stem("Rat (1000000)", 7) is None
    assert duplicate_stem("Ghost (Male)", 5) is None
    assert duplicate_stem("Rat", 5) is None
    assert duplicate_stem(None, 5) is None
    assert base_stem("Rat (1) (2)") == "Rat"
    assert base_stem("Ghost (Male)") == "Ghost (Male)"
    assert base_stem(None) == ""
    # The " (id)" suffix only ever matches names this editor wrote.
    assert not [name for name in MONSTER_FAMILIES if base_stem(name) != name]


def test_copy_and_delete_row_at_member_level():
    _, payload = goods_member()
    size = TABLES["EquipParamGoods"][0]
    view = ParamView(payload)
    grown = view.copy_row(100, 5000, "New goods (5000)", size)
    view2 = ParamView(grown)
    assert [(row.row_id, row.name) for row in view2.rows] == [
        (100, None), (101, None), (102, None), (5000, "New goods (5000)")]
    assert grown[view2.rows[3].data_offset:view2.rows[3].data_offset + size] == \
        payload[view.rows[0].data_offset:view.rows[0].data_offset + size]
    shrunk = view2.delete_row(101, size)
    view3 = ParamView(shrunk)
    assert [(row.row_id, row.name) for row in view3.rows] == [(100, None), (102, None), (5000, "New goods (5000)")]
    for row in view3.rows:
        old = next(item for item in view2.rows if item.row_id == row.row_id)
        assert shrunk[row.data_offset:row.data_offset + size] == grown[old.data_offset:old.data_offset + size]
    with pytest.raises(Exception, match="already exists"):
        view2.copy_row(100, 5000, "taken", size)
    with pytest.raises(Exception, match="one row"):
        ParamView(shrunk).delete_row(99999, size)
    lone = ParamView(shrunk).delete_row(100, size)
    lone = ParamView(lone).delete_row(102, size)
    with pytest.raises(Exception, match="at least one row"):
        ParamView(lone).delete_row(5000, size)


def test_add_row_duplicates_values_and_tracks_changes():
    document = ItemDocument(make_archive())
    before = document._row("EquipParamGoods", 100)[2]
    row = document.add_row("EquipParamGoods", 100)
    assert row["id"] == 103
    assert document._row("EquipParamGoods", 103)[2] == before
    assert all(field["vanilla"] is None for field in row["fields"])
    assert document.dirty_count == 1
    document.edit("EquipParamGoods", 103, "sellValue", 42)
    assert document.value("EquipParamGoods", 103, "sellValue") == 42
    changes = document.pending_changes()
    assert changes and all(change["before"] is None for change in changes)
    assert document.value("EquipParamGoods", 100, "sellValue") == ItemDocument(make_archive()).value(
        "EquipParamGoods", 100, "sellValue")


def test_add_row_ids_and_names():
    document = ItemDocument(make_archive())
    row = document.add_row("EquipParamGoods", 100, 5000)
    assert row["id"] == 5000
    again = document.add_row("EquipParamGoods", 5000)
    assert again["id"] == 5001
    names = [item.name for item in document.params["EquipParamGoods"].rows if item.row_id in (5000, 5001)]
    assert names[0] != names[1] and names[1].endswith(" (5001)")
    # A duplicate of a duplicate re-stems instead of stacking suffixes.
    assert "(5000)" not in names[1]
    with pytest.raises(FormatError, match="already taken"):
        document.add_row("EquipParamGoods", 100, 5000)
    for bad in (True, 2 ** 31, "x"):
        with pytest.raises(FormatError):
            document.add_row("EquipParamGoods", 100, bad)
    with pytest.raises(FormatError, match="found 0"):
        document.add_row("EquipParamGoods", 99999)
    with pytest.raises(FormatError, match="found 0"):
        document.add_row("EquipParamGoods", 99999, 6000)


def test_add_row_npc_monster_gate():
    document = ItemDocument(make_archive())
    ids = [row.row_id for row in document.params["NpcParam"].rows]
    monsters = [row_id for row_id in ids if document.is_monster(row_id)]
    assert monsters
    row = document.add_row("NpcParam", monsters[0])
    assert document.is_monster(row["id"])
    assert document.read_row("NpcParam", row["id"])["id"] == row["id"]
    assert 251000 in ids and document.is_friend(251000)
    friend = document.add_row("NpcParam", 251000)
    assert document.is_friend(friend["id"])
    assert 502 in ids and not document.is_monster(502) and not document.is_friend(502) and not document.is_boss(502)
    with pytest.raises(FormatError, match="reviewed monster or NPC"):
        document.add_row("NpcParam", 502)
    # A refused duplicate changes nothing.
    assert [row.row_id for row in document.params["NpcParam"].rows] == ids + [row["id"], friend["id"]]


def test_remove_row():
    document = ItemDocument(make_archive())
    document.edit("EquipParamGoods", 101, "sellValue", 5)
    gone = document.remove_row("EquipParamGoods", 101)
    assert gone["id"] == 101
    assert [row.row_id for row in document.params["EquipParamGoods"].rows] == [100, 102]
    assert any(change["label"].endswith("(removed)") for change in document.pending_changes())
    # Its pending field edits leave with it.
    assert all(entry[:2] != ("EquipParamGoods", 101) for entry in document.dirty)
    with pytest.raises(FormatError, match="found 0"):
        document.remove_row("EquipParamGoods", 101)
    document.remove_row("EquipParamGoods", 100)
    with pytest.raises(FormatError, match="at least one row"):
        document.remove_row("EquipParamGoods", 102)


def test_add_remove_export_roundtrip():
    document = ItemDocument(make_archive())
    ids = [row.row_id for row in document.params["NpcParam"].rows]
    monster = next(row_id for row_id in ids if document.is_monster(row_id))
    new = document.add_row("NpcParam", monster)["id"]
    document.edit("EquipParamGoods", 100, "sellValue", 42)
    document.remove_row("EquipParamGoods", 101)
    reopened = ItemDocument(document.export())
    assert reopened.value("EquipParamGoods", 100, "sellValue") == 42
    with pytest.raises(FormatError):
        reopened.value("EquipParamGoods", 101, "sellValue")
    # The duplicate still opens as a monster after a save and reload,
    # through its param name stem rather than a reference name.
    assert reopened.is_monster(new)
    assert reopened.read_row("NpcParam", new)["id"] == new
    assert reopened.params["NpcParam"].row(new).name.endswith(f" ({new})")


def test_msb_add_remove_fixture():
    document = MsbDocument(build_msb())
    row = document.add_placement([2, 0])
    assert (row["type"], row["partId"]) == (2, 1)
    assert row["name"] == "enemy0_1"
    assert len(document.placements()) == 5
    assert [field["value"] for field in row["fields"] if field["key"] == "npcId"] == [120000]
    assert all(field["vanilla"] is None for field in row["fields"])
    # The fixture entities are all 0, so the copy takes the next one.
    assert document._entity_ids().count(1) == 1
    edited = document.edit([2, 1], "posX", 9.5)
    assert edited["fields"][0]["value"] == 9.5
    reopened = MsbDocument(document.export())
    assert len(reopened.placements()) == 5
    assert reopened.read_placement([2, 1])["fields"][0]["value"] == 9.5
    gone = document.remove_placement([2, 1])
    assert (gone["type"], gone["id"]) == (2, 1)
    assert len(document.placements()) == 4
    assert any(change["label"].endswith("(removed)") for change in
               MapStore_pending(document))
    assert MsbDocument(document.export()).placements() is not None
    with pytest.raises(MsbError, match="player start"):
        document.remove_placement([4, 0])
    with pytest.raises(MsbError, match="Select an enemy"):
        document.remove_placement([2, 99])
    # A chest whose stored blob breaks the template's fixed words refuses
    # duplication instead of copying values this version does not know.
    tampered = bytearray(build_msb())
    chest_at = next(part["type_data"] for part in MsbDocument(bytes(tampered)).parts
                    if part["type"] == 1)
    struct.pack_into("<i", tampered, chest_at, 1)
    tampered_doc = MsbDocument(bytes(tampered))
    with pytest.raises(MsbError, match="does not understand"):
        tampered_doc.add_placement([1, 0])


def MapStore_pending(document):
    from plugins.ds1.map_store import MapStore
    store = MapStore.__new__(MapStore)
    store.docs = {"m10_00_00_00.msb": document}
    store.item_store = None
    return store.pending_changes()


def test_msb_minus_one_entity_stays_none():
    raw = bytearray(build_msb())
    document = MsbDocument(bytes(raw))
    part = next(item for item in document.parts if (item["type"], item["id"]) == (2, 0))
    ent = part["base"] + struct.unpack_from("<i", raw, part["base"] + 0x58)[0]
    struct.pack_into("<i", raw, ent, -1)
    document = MsbDocument(bytes(raw))
    assert all(entity == -1 or entity == 0 for entity in document._entity_ids())
    row = document.add_placement([2, 0])
    added = next(item for item in document.parts if (item["type"], item["id"]) == (2, 1))
    ent = added["base"] + struct.unpack_from("<i", document.plain, added["base"] + 0x58)[0]
    assert struct.unpack_from("<i", document.plain, ent)[0] == -1
    assert row["partId"] == 1


def test_compose_map_with_added_placement_goes_whole():
    vanilla = build_msb()
    document = MsbDocument(vanilla)
    document.add_placement([2, 0])
    grown = document.export()
    alone = mod_loader.Mod("A", Path("A"), {MAP: grown})
    result = mod_loader.compose({MAP: vanilla}, [alone])
    assert result.files[MAP] == grown


def project(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / MAP).parent.mkdir(parents=True)
    (game / MAP).write_bytes(build_msb())
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def request_json(session, path, payload=None):
    request = Request(session.url.rstrip("/") + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request) as reply:
        return json.load(reply)


def test_service_rows_add_remove(tmp_path):
    game, mod = project(tmp_path)
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                          "LEXEDITOR_MOD_READ_ONLY": "0", "LEXEDITOR_NO_MOD": "0"})
    try:
        session.start()
        row = request_json(session, "/api/rows/add", {"table": "EquipParamGoods", "id": 100})["row"]
        assert row["id"] == 103
        ids = [entry["id"] for entry in request_json(session, "/api/table?tab=consumables")["rows"]]
        assert 103 in ids
        edited = request_json(session, "/api/edit", {"table": "EquipParamGoods", "id": 103,
                                                     "field": "sellValue", "value": 42})
        assert edited["dirtyCount"] >= 1
        removed = request_json(session, "/api/rows/remove", {"table": "EquipParamGoods", "id": 103})
        assert removed["removed"]["id"] == 103
        ids = [entry["id"] for entry in request_json(session, "/api/table?tab=consumables")["rows"]]
        assert 103 not in ids
        with pytest.raises(HTTPError):
            request_json(session, "/api/rows/add", {"table": "EquipParamGoods", "id": 99999})
    finally:
        session.stop()


def test_service_placements_add_remove(tmp_path):
    game, mod = project(tmp_path)
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                          "LEXEDITOR_MOD_READ_ONLY": "0", "LEXEDITOR_NO_MOD": "0"})
    try:
        session.start()
        row = request_json(session, "/api/placements/add",
                           {"map": "m10_00_00_00.msb", "id": "2:0"})["row"]
        assert row["id"] == "2:1"
        ids = [entry["id"] for entry in request_json(session, "/api/table?tab=placements")["rows"]]
        assert "2:1" in ids
        removed = request_json(session, "/api/placements/remove",
                               {"map": "m10_00_00_00.msb", "id": "2:1"})
        assert removed["removed"]["id"] == 1
        with pytest.raises(HTTPError):
            request_json(session, "/api/placements/remove",
                         {"map": "m10_00_00_00.msb", "id": "4:0"})
    finally:
        session.stop()


def test_service_vanilla_refuses_add_remove(tmp_path):
    game, _ = project(tmp_path)
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1"})
    try:
        session.start()
        for path, payload in (("/api/rows/add", {"table": "EquipParamGoods", "id": 100}),
                              ("/api/rows/remove", {"table": "EquipParamGoods", "id": 100}),
                              ("/api/placements/add", {"map": "m10_00_00_00.msb", "id": "2:0"}),
                              ("/api/placements/remove", {"map": "m10_00_00_00.msb", "id": "2:0"})):
            with pytest.raises(HTTPError) as error:
                request_json(session, path, payload)
            assert error.value.code == 403
    finally:
        session.stop()


def test_added_rows_read_as_created():
    document = ItemDocument(make_archive())
    row = document.add_row("EquipParamGoods", 100)
    rows = {row["id"]: row for row in document.list_rows("consumables")}
    assert rows[row["id"]]["created"] is True
    assert rows[100]["created"] is False


def test_add_rows_in_bulk_survive_export_with_padding_before_strings():
    """Shipped tables (SpEffectParam) leave padding between the last row and
    the strings offset; copies must join the data, not follow the padding."""
    _, payload = goods_member()
    size = TABLES["EquipParamGoods"][0]
    view = ParamView(payload)
    pad = 12
    strings = view.strings_offset
    padded = bytearray(payload[:strings] + bytes(pad) + payload[strings:])
    struct.pack_into("<I", padded, 0, strings + pad)
    view = ParamView(bytes(padded))
    copies = [(100 + index % 3, 7000 + index, f"Copy ({7000 + index})") for index in range(500)]
    grown = ParamView(view.copy_rows(copies, size))
    assert len(grown.rows) == len(view.rows) + 500
    offsets = sorted(row.data_offset for row in grown.rows)
    assert all(b - a == size for a, b in zip(offsets, offsets[1:]))
    assert offsets[0] >= 48 + len(grown.rows) * 12
    assert offsets[-1] + size <= grown.strings_offset
    for source_id, new_id, name in copies[:5] + copies[-5:]:
        new = next(row for row in grown.rows if row.row_id == new_id)
        old = next(row for row in view.rows if row.row_id == source_id)
        assert new.name == name
        assert grown.data[new.data_offset:new.data_offset + size] == view.data[old.data_offset:old.data_offset + size]


def test_document_add_rows_batch_exports_and_reopens():
    document = ItemDocument(make_archive())
    rows = document.add_rows("EquipParamGoods", [(100, 6000 + index) for index in range(500)])
    assert [row["id"] for row in rows] == list(range(6000, 6500))
    assert document.dirty_count == 500
    reopened = ItemDocument(document.export())
    assert len(reopened.params["EquipParamGoods"].rows) == 503
    assert reopened._row("EquipParamGoods", 6499)[2] == reopened._row("EquipParamGoods", 100)[2]
    with pytest.raises(FormatError, match="already taken"):
        document.add_rows("EquipParamGoods", [(100, 7000), (100, 7000)])
    assert len(document.params["EquipParamGoods"].rows) == 503
