"""TAE event editing on a synthetic file (see tae_fixture.py)."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tae_fixture import build_tae
from plugins.ds1.tae import EVENT_TYPES, TaeDocument, TaeError, _display_name


def test_lists_anims_and_events():
    doc = TaeDocument(build_tae(), "a87.tae")
    anims = doc.list_anims()
    assert [(anim["id"], anim["name"], anim["events"]) for anim in anims] == [
        (3300, "a87_3300.HKX", 4), (3301, "animation 3301", 0)]
    events = doc.list_events(0)
    assert [(event["type"], event["label"]) for event in events] == [
        (1, "Attack"), (66, "Add effect"), (999, "Unknown event 999"), (16, "Unknown event 16")]
    assert [(event["start"], event["end"]) for event in events] == [
        (0.0, 0.5), (0.0, 1.0), (1.5, 1.5), (0.5, 1.0)]


def test_control_character_anim_names_fall_back_to_ids():
    assert _display_name("a00_0000.hkx", 30) == "a00_0000.hkx"
    assert _display_name("", 30) == "animation 30"
    assert _display_name("\x01", 30) == "animation 30"
    assert _display_name("  ", 30) == "animation 30"
    raw = bytearray(build_tae())
    garbage_at = len(raw)
    raw += b"\x01\x00\x00\x00"
    # Anim 3301's name offset sits 16 bytes before the original end of file.
    struct.pack_into("<I", raw, garbage_at - 16, garbage_at)
    struct.pack_into("<I", raw, 12, len(raw))
    names = [anim["name"] for anim in TaeDocument(bytes(raw), "a87.tae").list_anims()]
    assert names == ["a87_3300.HKX", "animation 3301"]


def test_reads_event_fields_with_vanilla_and_sharing():
    doc = TaeDocument(build_tae())
    row = doc.read_event(0, 0)
    assert (row["anim"], row["type"], row["label"]) == (3300, 1, "Attack")
    by_key = {field["key"]: field for field in row["fields"]}
    assert [field["key"] for field in row["fields"]] == ["start", "end", "attackType",
                                                         "attackIndex", "judge"]
    assert by_key["attackIndex"]["value"] == 2 and by_key["judge"]["vanilla"] == 100
    assert by_key["start"]["vanilla"] == 0.0 and by_key["start"]["shared"] == 1
    assert "1 other event shares this timestamp" in by_key["start"]["description"]
    assert by_key["end"]["shared"] == 1
    required = {"key", "label", "description", "group", "dtype", "value", "type",
                "minimum", "maximum", "enum", "editable", "vanilla", "sliderMin", "sliderMax"}
    assert all(required <= set(field) for field in row["fields"])
    assert by_key["attackType"]["dtype"] == "s32" and by_key["start"]["dtype"] == "f32"
    # Unknown and empty events expose timing only.
    assert [field["key"] for field in doc.read_event(0, 2)["fields"]] == ["start", "end"]
    assert [field["key"] for field in doc.read_event(0, 3)["fields"]] == ["start", "end"]


def test_shared_timestamp_edit_moves_every_sharer():
    doc = TaeDocument(build_tae())
    original = doc.export()
    doc.edit(0, 0, "start", 0.25)
    assert doc.read_event(0, 1)["fields"][0]["value"] == pytest.approx(0.25)
    assert doc.dirty_count == 2
    changed = doc.export()
    assert len(changed) == len(original)
    diffs = [index for index in range(len(original)) if changed[index] != original[index]]
    assert 1 <= len(diffs) <= 4 and max(diffs) - min(diffs) < 4
    doc.edit(0, 1, "start", 0.0)
    assert doc.dirty_count == 0 and doc.export() == original


def test_param_edits_stay_within_their_bytes():
    doc = TaeDocument(build_tae())
    original = doc.export()
    doc.edit(0, 0, "attackType", 62)
    doc.edit(0, 0, "judge", 300)
    doc.edit(0, 1, "effect", 39, speffect_ids={31, 39})
    assert doc.dirty_count == 3
    changed = doc.export()
    assert len(changed) == len(original)
    assert changed != original
    doc.edit(0, 0, "attackType", 0)
    doc.edit(0, 0, "judge", 100)
    doc.edit(0, 1, "effect", 31, speffect_ids={31, 39})
    assert doc.dirty_count == 0 and doc.export() == original


def test_rejects_bad_values_and_protected_fields():
    doc = TaeDocument(build_tae())
    with pytest.raises(TaeError):
        doc.edit(0, 0, "attackType", 99)
    with pytest.raises(TaeError):
        doc.edit(0, 1, "effect", 7, speffect_ids={31, 39})
    # A pre-existing unknown effect survives a revert to itself.
    assert doc.edit(0, 1, "effect", 31, speffect_ids=set())["fields"][2]["value"] == 31
    for field, value in (("start", float("nan")), ("end", "soon"), ("judge", 1.5),
                         ("judge", True), ("attackIndex", 2 ** 31)):
        with pytest.raises(TaeError):
            doc.edit(0, 0, field, value)
    with pytest.raises(TaeError):
        doc.edit(0, 2, "whatever", 0)
    with pytest.raises(TaeError):
        doc.edit(0, 3, "flag", 0)
    with pytest.raises(TaeError):
        doc.edit(0, 9, "start", 0.0)
    with pytest.raises(TaeError):
        doc.edit(9, 0, "start", 0.0)
    assert doc.dirty_count == 0 and doc.export() == build_tae()


def test_noop_export_is_byte_identical():
    raw = build_tae()
    assert TaeDocument(raw).export() == raw


def test_every_table_entry_fits_a_real_size():
    sizes = {etype: spec[0] for etype, spec in EVENT_TYPES.items()}
    assert all(size % 4 == 0 and size >= 12 for size in sizes.values())
    assert min(sizes) >= 0 and len(sizes) == len(EVENT_TYPES)


def test_malformed_files_rejected():
    raw = build_tae()
    cases = [
        (b"XAE " + raw[4:], "magic"),
        (raw[:8] + struct.pack("<I", 0x1000D) + raw[12:], "version"),
        (raw[:12] + struct.pack("<I", len(raw) + 1) + raw[16:], "length"),
        (raw[:96] + struct.pack("<I", 0x80) + raw[100:], "header const"),
        (raw[:100] + struct.pack("<I", 999) + raw[104:], "count"),
        (raw[:-4], "truncated"),
    ]
    for blob, _why in cases:
        with pytest.raises(TaeError):
            TaeDocument(bytes(blob))
    broken = bytearray(raw)
    anims_off = struct.unpack_from("<I", raw, 88)[0]
    _aid, anim_off = struct.unpack_from("<2I", raw, anims_off)
    _ev_n, ev_off = struct.unpack_from("<2I", raw, anim_off)
    _s, _e, data_off = struct.unpack_from("<3I", raw, ev_off)
    broken[data_off + 4:data_off + 8] = struct.pack("<I", data_off + 12)
    with pytest.raises(TaeError):
        TaeDocument(bytes(broken))
