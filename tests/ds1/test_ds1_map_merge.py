"""Map files merge by placement field; restructured maps go whole.

Two mods changing different placements, or different fields of one
placement, both apply. Two mods setting the same field to different
values conflict and the later one is used. Synthetic maps only.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from msb_fixture import build_msb
from plugins.ds1 import mod_loader
from plugins.ds1.msb import MAP_DIR, MsbDocument

VANILLA = build_msb()
MAP = MAP_DIR / "m10_00_00_00.msb"
GAME = {MAP: VANILLA}
ENEMY = (2, 0)
PLAYER = (4, 0)


def edited(*edits):
    document = MsbDocument(VANILLA)
    for key, field, value in edits:
        document.edit(key, field, value)
    return document.export()


def mod(name, *maps):
    return mod_loader.Mod(name, Path(name), dict(maps))


def value(payload, key, field):
    row = MsbDocument(payload).read_placement(key)
    return next(item["value"] for item in row["fields"] if item["key"] == field)


def test_no_map_changes_and_single_mod_is_its_own_bytes():
    assert mod_loader.compose(GAME, []).files == {}
    alone = mod("A", (MAP, edited((ENEMY, "posX", 5.5))))
    result = mod_loader.compose(GAME, [alone])
    assert result.files == alone.files and result.conflicts == []


def test_different_placements_and_fields_both_apply():
    a = mod("A", (MAP, edited((ENEMY, "posX", 5.5))))
    b = mod("B", (MAP, edited((ENEMY, "npcId", 120100), (PLAYER, "posZ", 9.25))))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    assert value(result.files[MAP], ENEMY, "posX") == 5.5
    assert value(result.files[MAP], ENEMY, "npcId") == 120100
    assert value(result.files[MAP], PLAYER, "posZ") == 9.25


def test_the_same_field_conflicts_and_the_later_mod_is_used():
    a = mod("A", (MAP, edited((ENEMY, "posX", 5.0))))
    b = mod("B", (MAP, edited((ENEMY, "posX", 9.0))))
    result = mod_loader.compose(GAME, [a, b])
    assert value(result.files[MAP], ENEMY, "posX") == 9.0
    assert [(c.part, c.mods) for c in result.conflicts] == [("m10_00_00_00.msb enemy0, Position X", ["A", "B"])]
    lines = result.by_mod([a, b])
    assert "B changes this too and loads later" in lines["A"][0] and "overrides A" in lines["B"][0]


def test_the_same_value_from_two_mods_is_no_conflict():
    a = mod("A", (MAP, edited((ENEMY, "rotY", 45.0))))
    b = mod("B", (MAP, edited((ENEMY, "rotY", 45.0))))
    assert mod_loader.compose(GAME, [a, b]).conflicts == []


def test_a_restructured_map_is_taken_whole_from_the_last_mod():
    grown = build_msb(parts=(("enemy", 2, 0, 0, 120000), ("enemy", 2, 1, 0, 120100),
                             ("player", 4, 0, 1, None), ("piece", 0, 0, 1, None)))
    b = mod("B", (MAP, edited((ENEMY, "posX", 9.0))))
    a = mod("A", (MAP, grown))
    result = mod_loader.compose(GAME, [b, a])
    assert result.files[MAP] == grown
    assert [(c.part, c.mods) for c in result.conflicts] == [("m10_00_00_00.msb (whole map)", ["B", "A"])]
    foreign = mod("C", (MAP, b"not a map file"))
    result = mod_loader.compose(GAME, [foreign])
    assert result.files[MAP] == b"not a map file" and result.conflicts == []


def test_a_map_missing_from_vanilla_is_taken_whole():
    extra = MAP_DIR / "m99_00_00_00.msb"
    a = mod("A", (extra, edited((ENEMY, "posX", 5.5))))
    result = mod_loader.compose(GAME, [a])
    assert result.files[extra] == a.files[extra] and result.conflicts == []


def test_read_mod_and_vanilla_files_find_maps(tmp_path):
    from plugins.ds1.store import MARKER
    game, folder = tmp_path / "game", tmp_path / "mod"
    (game / MAP_DIR).mkdir(parents=True)
    (game / MAP_DIR / "m10_00_00_00.msb").write_bytes(VANILLA)
    folder.mkdir()
    (folder / MARKER).touch()
    assert mod_loader.read_mod(folder, "empty").files == {}
    (folder / MAP_DIR).mkdir(parents=True)
    (folder / MAP_DIR / "M10_00_00_00.MSB").write_bytes(edited((ENEMY, "posX", 5.5)))
    found = mod_loader.read_mod(folder, "maps")
    assert list(found.files) == [MAP]
    assert mod_loader.vanilla_files(game, frozenset({MAP})) == {MAP: VANILLA}
    for index in range(64):
        (folder / MAP_DIR / f"m98_00_{index:02d}_00.msb").write_bytes(VANILLA)
    try:
        mod_loader.read_mod(folder, "many")
    except ValueError as error:
        assert "too many map files" in str(error)
    else:
        raise AssertionError("Expected too many map files to fail")
