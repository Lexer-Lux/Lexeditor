"""Animation binder overlay: vanilla or saved edits, names linked, stale-safe."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from msb_fixture import build_msb
from tae_fixture import build_anibnd, build_tae
from plugins.ds1.store import MARKER
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.tae import TaeError
from plugins.ds1.tae_store import CHR_DIR, TaeStore

BINDER = "c1200.anibnd.dcx"
TAE = "a87.tae"


class _Params:
    """Minimal item-store double: NpcParam and SpEffectParam rows."""

    def __init__(self, npcs=None, effects=None):
        self._tables = {
            "NpcParam": [SimpleNamespace(row_id=row_id) for row_id in (npcs or {})],
            "SpEffectParam": [SimpleNamespace(row_id=row_id) for row_id in (effects or {})],
        }
        self._names = {"NpcParam": dict(npcs or {}), "SpEffectParam": dict(effects or {})}

    def get(self):
        return self

    @property
    def params(self):
        return {table: SimpleNamespace(rows=rows) for table, rows in self._tables.items()}

    def display_name(self, table, row_id, _row):
        return self._names[table][row_id]


def setup(tmp_path, binder=BINDER, items=None, maps=True):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / CHR_DIR).mkdir(parents=True)
    (game / CHR_DIR / binder).write_bytes(build_anibnd({TAE: build_tae()}))
    if maps:
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / "m10_00_00_00.msb").write_bytes(build_msb())
    mod.mkdir()
    (mod / MARKER).touch()
    if items is None:
        items = _Params(npcs={120000: "Hollow Soldier"}, effects={31: "Poison", 39: "Toxic"})
    return game, mod, TaeStore(game, mod, False, items)


def test_lists_chars_anims_and_events(tmp_path):
    _game, _mod, store = setup(tmp_path)
    chars = store.list_chars()
    assert [(row["id"], row["name"]) for row in chars] == [(f"char:{BINDER}", "Hollow Soldier")]
    anims = store.list_anims(BINDER)
    assert [(row["name"], row["values"]["animId"], row["values"]["events"]) for row in anims] == [
        ("a87_3300.HKX", 3300, 4), ("animation 3301", 3301, 0)]
    events = store.list_events(BINDER, TAE, 0)
    assert [row["values"]["label"] for row in events] == [
        "Attack", "Add effect", "Unknown event 999", "Unknown event 16"]
    assert events[0]["id"] == f"ev:{TAE}|0|0" and events[0]["table"] == BINDER


def test_read_returns_selects_and_vanilla_values(tmp_path):
    _game, _mod, store = setup(tmp_path)
    row = store.read(BINDER, f"{TAE}|0|0")
    assert (row["id"], row["table"], row["tae"]) == (f"ev:{TAE}|0|0", BINDER, TAE)
    attack = next(item for item in row["fields"] if item["key"] == "attackType")
    assert attack["type"] == "enum" and attack["enum"]["62"] == "Plunging attack"
    effect = next(item for item in store.read(BINDER, f"{TAE}|0|1")["fields"] if item["key"] == "effect")
    assert effect["type"] == "enum" and effect["enum"]["31"] == "Poison"
    assert effect["vanilla"] == 31
    start = next(item for item in row["fields"] if item["key"] == "start")
    assert (start["value"], start["vanilla"]) == (0.0, 0.0)


def test_edit_save_reload_and_discard_round_trip(tmp_path):
    game, mod, store = setup(tmp_path)
    store.edit(BINDER, f"{TAE}|0|0", "start", 0.25)
    store.edit(BINDER, f"{TAE}|0|1", "effect", 39)
    assert store.dirty_count == 3
    changes = store.pending_changes()
    assert len(changes) == 3 and all(change["label"].startswith(BINDER) for change in changes)
    assert any(change["after"] == "Toxic" for change in changes)
    store.save()
    assert store.dirty_count == 0
    assert (mod / CHR_DIR / BINDER).is_file()
    fresh = TaeStore(game, mod, False, _Params(effects={31: "Poison", 39: "Toxic"}))
    row = fresh.read(BINDER, f"{TAE}|0|0")
    assert next(item for item in row["fields"] if item["key"] == "start")["value"] == pytest.approx(0.25)
    assert next(item for item in fresh.read(BINDER, f"{TAE}|0|1")["fields"]
                if item["key"] == "effect")["value"] == 39
    fresh.edit(BINDER, f"{TAE}|0|0", "start", 0.0)
    fresh.discard()
    assert fresh.dirty_count == 0
    assert next(item for item in fresh.read(BINDER, f"{TAE}|0|0")["fields"]
                if item["key"] == "start")["value"] == pytest.approx(0.25)


def test_stale_project_and_live_files_refuse_save(tmp_path):
    game, mod, store = setup(tmp_path)
    store.edit(BINDER, f"{TAE}|0|0", "start", 0.25)
    (mod / CHR_DIR).mkdir(parents=True)
    (mod / CHR_DIR / BINDER).write_bytes(build_anibnd({TAE: build_tae()}))
    with pytest.raises(ValueError, match="outside Lexeditor"):
        store.save()
    _game, _mod, live = setup(tmp_path / "live")
    live.edit(BINDER, f"{TAE}|0|0", "start", 0.25)
    doc = live.get(BINDER)
    (live.game_root / CHR_DIR / BINDER).write_bytes(doc["raw"] + b"!")
    with pytest.raises(ValueError, match="outside Lexeditor"):
        live.save()


def test_read_only_unknown_and_unreadable_targets_fail_closed(tmp_path):
    game, mod, _store = setup(tmp_path)
    frozen = TaeStore(game, mod, True, _Params())
    with pytest.raises(PermissionError):
        frozen.edit(BINDER, f"{TAE}|0|0", "start", 0.25)
    store = TaeStore(game, mod, False, _Params(effects={31: "Poison"}))
    with pytest.raises(TaeError):
        store.read("c0001.anibnd.dcx", f"{TAE}|0|0")
    with pytest.raises(TaeError):
        store.read(BINDER, "nope")
    with pytest.raises(TaeError):
        store.edit(BINDER, f"{TAE}|0|1", "effect", 999)
    (game / CHR_DIR / "c0001.anibnd.dcx").write_bytes(b"not a binder")
    assert [row["id"] for row in store.list_chars()] == [f"char:{BINDER}"]
    with pytest.raises(TaeError):
        store.read("c0001.anibnd.dcx", f"{TAE}|0|0")


def test_list_rows_mark_modified_after_edit(tmp_path):
    _game, _mod, store = setup(tmp_path)
    assert all(not row.get("modified") for row in store.list_chars())
    assert all(not row.get("modified") for row in store.list_anims(BINDER))
    assert all(not row.get("modified") for row in store.list_events(BINDER, TAE, 0))
    store.get(BINDER)["taes"][TAE].edit(0, 0, "start", 0.25)
    assert [row.get("modified") for row in store.list_chars()] == [True]
    anims = {row["id"]: row.get("modified") for row in store.list_anims(BINDER)}
    assert anims[f"anim:{TAE}|0"] is True
    assert all(value is not True for key, value in anims.items() if key != f"anim:{TAE}|0")
    events = {row["id"]: row.get("modified") for row in store.list_events(BINDER, TAE, 0)}
    assert events[f"ev:{TAE}|0|0"] is True
    # ev1 shares ev0's start slot, so its timestamp changed too; the rest did not.
    assert events[f"ev:{TAE}|0|1"] is True
    assert all(value is not True for key, value in events.items()
               if key not in (f"ev:{TAE}|0|0", f"ev:{TAE}|0|1"))
