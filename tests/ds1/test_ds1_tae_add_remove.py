"""TAE add/remove events: relocation, validation, dirty tracking, saving."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tae_fixture import build_anibnd, build_tae
from plugins.ds1.formats import inflate, members
from plugins.ds1.store import MARKER
from plugins.ds1.tae import TaeDocument, TaeError
from plugins.ds1.tae_store import CHR_DIR, TaeStore

BINDER = "c1200.anibnd.dcx"
TAE = "a87.tae"


def test_add_appends_a_reparseable_event_and_preserves_the_prefix():
    raw = build_tae()
    doc = TaeDocument(raw)
    entry_off = doc.anims[0]["offset"]
    index = doc.add_event(0, 66, 0.25, 0.75, {"effect": 31})
    assert index == 4
    row = doc.read_event(0, index)
    assert row["vanillaIndex"] is None
    assert [(field["key"], field["value"], field["vanilla"]) for field in row["fields"]] == [
        ("start", pytest.approx(0.25), None), ("end", pytest.approx(0.75), None), ("effect", 31, None)]
    assert doc.dirty_count == 3
    out = doc.export()
    assert len(out) > len(raw) and struct.unpack_from("<I", out, 12)[0] == len(out)
    # Only the size field and the one animation entry change below the append point.
    assert out[:12] == raw[:12] and out[16:entry_off] == raw[16:entry_off]
    assert out[entry_off + 28:len(raw)] == raw[entry_off + 28:]
    fresh = TaeDocument(out)
    assert [event["type"] for event in fresh.list_events(0)] == [1, 66, 999, 16, 66]
    assert fresh.read_event(0, 4)["fields"][-1]["value"] == 31
    assert fresh.list_events(1) == []


def test_add_validates_type_fields_and_timing():
    doc = TaeDocument(build_tae())
    with pytest.raises(TaeError, match="documented"):
        doc.add_event(0, 999, 0.0, 1.0)
    with pytest.raises(TaeError, match="documented"):
        doc.add_event(0, "66", 0.0, 1.0)
    with pytest.raises(TaeError, match="Unknown event field"):
        doc.add_event(0, 66, 0.0, 1.0, {"nope": 1})
    with pytest.raises(TaeError, match="whole number"):
        doc.add_event(0, 66, 0.0, 1.0, {"effect": 1.5})
    with pytest.raises(TaeError, match="finite number of seconds"):
        doc.add_event(0, 66, float("nan"), 1.0)
    with pytest.raises(TaeError, match="documented attack type"):
        doc.add_event(0, 1, 0.0, 1.0, {"attackType": 5, "attackIndex": 0, "judge": 0})
    with pytest.raises(TaeError, match="effect the game knows"):
        doc.add_event(0, 66, 0.0, 1.0, {"effect": 404}, speffect_ids={31, 39})
    assert doc.dirty_count == 0 and doc.export() == build_tae()


def test_add_defaults_params_to_zero_and_edits_after():
    doc = TaeDocument(build_tae())
    index = doc.add_event(0, 1, 0.0, 1.0)
    row = doc.read_event(0, index)
    assert [(field["key"], field["value"]) for field in row["fields"]] == [
        ("start", pytest.approx(0.0)), ("end", pytest.approx(1.0)),
        ("attackType", 0), ("attackIndex", 0), ("judge", 0)]
    doc.edit(0, index, "attackIndex", 3)
    assert doc.read_event(0, index)["fields"][3]["value"] == 3
    assert TaeDocument(doc.export()).read_event(0, index)["fields"][3]["value"] == 3


def test_remove_middle_shifts_indices_and_keeps_vanilla_links():
    doc = TaeDocument(build_tae())
    doc.add_event(0, 66, 0.0, 1.0, {"effect": 31})
    doc.remove_event(0, 1)
    assert [event["type"] for event in doc.list_events(0)] == [1, 999, 16, 66]
    assert [doc.read_event(0, number)["vanillaIndex"] for number in range(4)] == [0, 2, 3, None]
    assert [(gone["event"], gone["label"]) for gone in doc.removed] == [(1, "Add effect")]
    assert (0, 3, "effect") in doc.dirty and not [entry for entry in doc.dirty if entry[1] == 4]
    assert doc.dirty_count == len(doc.dirty) + 1
    fresh = TaeDocument(doc.export())
    assert [event["type"] for event in fresh.list_events(0)] == [1, 999, 16, 66]


def test_remove_empties_an_anim_and_add_brings_events_back():
    doc = TaeDocument(build_tae())
    for _number in range(4):
        doc.remove_event(0, 0)
    assert doc.list_events(0) == []
    assert len(doc.removed) == 4
    fresh = TaeDocument(doc.export())
    assert fresh.list_events(0) == []
    fresh.add_event(0, 128, 0.0, 2.0, {"soundType": 1, "soundId": 7})
    assert [event["label"] for event in fresh.list_events(0)] == ["Play sound"]
    assert TaeDocument(fresh.export()).list_events(0)[0]["type"] == 128


def test_remove_saved_added_event_leaves_a_tombstone():
    doc = TaeDocument(build_tae())
    index = doc.add_event(0, 66, 0.0, 1.0)
    reopened = TaeDocument(doc.export())
    assert reopened.dirty_count == 0
    reopened.remove_event(0, index)
    assert reopened.dirty_count == 1
    assert [(gone["event"], gone["label"]) for gone in reopened.removed] == [(4, "Add effect")]
    assert [event["type"] for event in TaeDocument(reopened.export()).list_events(0)] == [1, 66, 999, 16]


def test_add_then_remove_cancels_without_a_tombstone():
    doc = TaeDocument(build_tae())
    index = doc.add_event(0, 66, 0.0, 1.0)
    doc.remove_event(0, index)
    assert doc.dirty_count == 0 and doc.removed == []
    assert [event["type"] for event in doc.list_events(0)] == [1, 66, 999, 16]


def setup(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / CHR_DIR).mkdir(parents=True)
    (game / CHR_DIR / BINDER).write_bytes(build_anibnd({TAE: build_tae()}))
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod, TaeStore(game, mod, False, None)


def test_store_add_remove_save_pack_and_reopen(tmp_path):
    game, mod, store = setup(tmp_path)
    row = store.add_event(BINDER, TAE, 0, 128, 0.25, 0.75, {"soundType": 1, "soundId": 7})
    assert row["id"] == f"ev:{TAE}|0|4" and row["type"] == 128
    assert len(store.list_events(BINDER, TAE, 0)) == 5
    store.save()
    output = mod / CHR_DIR / BINDER
    assert output.is_file()
    member = members(inflate(output.read_bytes()))[TAE]
    assert len(TaeDocument(build_tae()).export()) != member.size
    fresh = TaeStore(game, mod, False, None)
    assert len(fresh.list_events(BINDER, TAE, 0)) == 5
    assert fresh.dirty_count == 0
    events = fresh.remove_event(BINDER, f"ev:{TAE}|0|0")
    assert [event["values"]["type"] for event in events] == [66, 999, 16, 128]
    labels = [change["label"] for change in fresh.pending_changes()]
    assert f"{BINDER} {TAE} a87_3300.HKX event 0, Attack (removed)" in labels
    fresh.save()
    reopened = TaeStore(game, mod, False, None)
    assert [event["values"]["type"] for event in reopened.list_events(BINDER, TAE, 0)] == [66, 999, 16, 128]


def test_store_vanilla_overlay_follows_removed_events(tmp_path):
    _game, _mod, store = setup(tmp_path)
    store.remove_event(BINDER, f"ev:{TAE}|0|0")
    row = store.read(BINDER, f"ev:{TAE}|0|1")
    assert row["type"] == 999
    assert next(item["vanilla"] for item in row["fields"] if item["key"] == "start") == 1.5


def test_store_remove_saved_added_event_saves(tmp_path):
    game, mod, store = setup(tmp_path)
    row = store.add_event(BINDER, TAE, 0, 128, 0.0, 1.0)
    store.save()
    assert store.dirty_count == 0
    rested = TaeStore(game, mod, False, None)
    assert len(rested.list_events(BINDER, TAE, 0)) == 5
    rested.remove_event(BINDER, row["id"])
    assert rested.dirty_count == 1
    assert any("removed" in change["label"] for change in rested.pending_changes())
    rested.save()
    reopened = TaeStore(game, mod, False, None)
    assert [event["values"]["type"] for event in reopened.list_events(BINDER, TAE, 0)] == [1, 66, 999, 16]


def test_store_add_then_remove_writes_nothing(tmp_path):
    game, mod, store = setup(tmp_path)
    row = store.add_event(BINDER, TAE, 0, 128, 0.0, 1.0)
    store.remove_event(BINDER, row["id"])
    assert store.dirty_count == 0
    store.save()
    assert not (mod / CHR_DIR / BINDER).exists()
    assert (game / CHR_DIR / BINDER).read_bytes() == build_anibnd({TAE: build_tae()})
