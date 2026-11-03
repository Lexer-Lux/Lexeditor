"""Developer soapstone message reading, editing, adding and removal on synthetic MSBs.

The events overlap the way the installed maps do: a chained event's tail
is its follower's header, so each message carries only its two owned data
words and the run ends on a chainless terminal.
"""
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from msb_fixture import build_msb
from plugins.ds1.msb import CHAIN_PREFIX, MESSAGE_EVENT, MESSAGE_TEXT_BANK, MsbDocument, MsbError

PARTS = (("enemy", 2, 0, 0, 120000), ("player", 4, 0, 1, None),
         ("piece", 0, 0, 1, None), ("chest", 1, 0, 1, None),
         ("zone", 5, 0, 1, None))
POINTS = (("pt0", (1.0, 2.0, 3.0)), ("pt1", (4.0, 5.0, 6.0)))
BANK = MESSAGE_TEXT_BANK


def _ahead(name):
    encoded = name.encode("shift_jis") + b"\0"
    padded = encoded + bytes(-len(encoded) % 4)
    ahead = 28 + len(padded)
    return ahead, ahead + 16


def _msg(name, seq, point, stored=BANK + 1000, unknown=1, part=2, area=4, flag=-1):
    return (name, MESSAGE_EVENT, seq, part, (area, point, flag, 0),
            struct.pack("<2i", stored, unknown))


def _objact(name="oa0", seq=0):
    return (name, 7, seq, 2, (4, 0, -1, 0), struct.pack("<4i", 1, 2, 3, 4))


def _treasure(name="tr0", seq=0):
    return (name, 4, seq, 2, (4, 0, -1, 0), bytes(52))


def _tail(name="end0", seq=0):
    return (name, 11, seq, 2, (4, 0, -1, 0), bytes(32))


def build_messages(nmsg=2, with_treasure=False, points=POINTS, parts=PARTS):
    events = [_treasure()] if with_treasure else []
    for i in range(nmsg):
        events.append(_msg("msg%d" % i, i, 0, stored=BANK + 1000 + i))
    events.append(_objact())
    events.append(_tail())
    return build_msb(parts=parts, points=points, events=tuple(events))


def chain_of(doc):
    """(nextPart, nextType, ordinal) per event in file order; None when chainless."""
    out = []
    for event in doc.events:
        slots = MsbDocument._chain_slots(event["type"], event["bhead"])
        if slots is None:
            out.append(None)
            continue
        prefix = CHAIN_PREFIX[event["type"]]
        out.append((struct.unpack_from("<i", doc.plain, slots[0])[0],
                    struct.unpack_from("<i", doc.plain, slots[1])[0],
                    struct.unpack_from("<i", doc.plain, event["bhead"] + 4 * (prefix + 3))[0]))
    return out


def assert_chain_coherent(doc):
    """Directory order is physical order; every chained tail is its
    follower's header, so next and ordinal read the follower's words."""
    assert [e["base"] for e in doc.events] == sorted(e["base"] for e in doc.events)
    chain = chain_of(doc)
    for pos, event in enumerate(doc.events):
        if chain[pos] is None:
            continue
        assert pos + 1 < len(doc.events)
        follower = doc.events[pos + 1]
        assert chain[pos] == (follower["part"], follower["type"], follower["seq"])
        prefix = CHAIN_PREFIX[event["type"]]
        assert event["bhead"] + 4 * prefix == follower["base"]


def test_messages_listed_with_text_point_and_links():
    doc = MsbDocument(build_messages())
    messages = doc.messages()
    assert [(m["seq"], m["textId"], m["storedId"]) for m in messages] == [(0, 1000, BANK + 1000),
                                                                         (1, 1001, BANK + 1001)]
    first = messages[0]
    assert (first["key"], first["name"], first["pointName"]) == ("message:0", "msg0", "pt0")
    assert (first["partName"], first["areaName"], first["flag"]) == ("piece0", "zone0", -1)
    assert first["pos"] == (1.0, 2.0, 3.0)
    assert "oa0" in first["sharers"]
    assert [m["point"] for m in messages] == [0, 0]
    assert_chain_coherent(doc)


def test_message_without_marker_hides_and_offers_no_position():
    raw = build_msb(parts=PARTS, points=POINTS, events=(_msg("hid0", 0, -1), _tail()))
    doc = MsbDocument(raw)
    [hidden] = doc.messages()
    assert (hidden["pos"], hidden["pointName"], hidden["point"]) == (None, None, -1)
    assert hidden["sharers"] == []
    row = doc.read_message(("message", 0))
    assert [f["key"] for f in row["fields"]] == ["text", "point", "flag"]
    assert (row["kind"], row["textId"], row["point"]) == ("Message", 1000, None)


def test_read_message_fields_expose_text_point_flag_and_shared_spot():
    doc = MsbDocument(build_messages())
    row = doc.read_message(("message", 1))
    assert [f["key"] for f in row["fields"]] == ["text", "point", "flag", "posX", "posY", "posZ"]
    by_key = {f["key"]: f for f in row["fields"]}
    assert by_key["text"]["value"] == 1001 and by_key["text"]["vanilla"] == 1001
    assert by_key["point"]["enum"] == {"0": "pt0", "1": "pt1", "-1": "None (hidden)"}
    assert by_key["flag"]["value"] == -1
    assert (by_key["posX"]["value"], by_key["posY"]["value"]) == (1.0, 2.0)
    assert "oa0" in by_key["posX"]["description"]
    assert (row["part"], row["areaPart"]) == ("piece0", "zone0")
    listed = doc.read_message(["message", 1])
    assert listed["key"] == "message:1"


def test_unknown_message_key_rejected():
    doc = MsbDocument(build_messages())
    with pytest.raises(MsbError):
        doc.read_message(("message", 99))
    with pytest.raises(MsbError):
        doc.edit_message(("message", 99), "text", 1000)


def test_edit_message_roundtrip_exact_bytes_and_revert():
    raw = build_messages()
    doc = MsbDocument(raw)
    doc.edit_message(("message", 0), "text", 2000)
    doc.edit_message(("message", 0), "flag", 555)
    doc.edit_message(("message", 0), "point", 1)
    doc.edit_message(("message", 0), "posX", 10.5)
    assert doc.message_modified(("message", 0)) and not doc.message_modified(("message", 1))
    assert doc.dirty_count == 4
    changed = doc.export()
    diff = [i for i, (a, b) in enumerate(zip(raw, changed)) if a != b]
    assert 0 < len(diff) <= 16
    back = MsbDocument(changed)
    assert back.read_message(("message", 0))["textId"] == 2000
    assert [m["point"] for m in back.messages()] == [1, 0]
    doc.edit_message(("message", 0), "text", 1000)
    doc.edit_message(("message", 0), "flag", -1)
    doc.edit_message(("message", 0), "posX", 4.0)
    doc.edit_message(("message", 0), "point", 0)
    assert doc.export() == raw and doc.dirty_count == 0
    assert not doc.message_modified(("message", 0))


def test_edit_flag_reads_back_before_any_save():
    doc = MsbDocument(build_messages())
    row = doc.edit_message(("message", 1), "flag", 555)
    fields = {f["key"]: f["value"] for f in row["fields"]}
    assert fields["flag"] == 555
    assert doc.messages()[1]["flag"] == 555


def test_edit_message_validation_and_protected_fields():
    doc = MsbDocument(build_messages())
    for bad in (-1, True, 1.5, 2 ** 31 - BANK):
        with pytest.raises(MsbError):
            doc.edit_message(("message", 0), "text", bad)
    for bad in ("1", True, None, 2 ** 31, -(2 ** 31) - 1):
        with pytest.raises(MsbError):
            doc.edit_message(("message", 0), "flag", bad)
    for bad in (2, -2, True, 1.5):
        with pytest.raises(MsbError):
            doc.edit_message(("message", 0), "point", bad)
    for bad in (float("nan"), float("inf"), "1.5", True, None):
        with pytest.raises(MsbError):
            doc.edit_message(("message", 0), "posX", bad)
    for key in ("name", "preset", "area", "part", "unknown"):
        with pytest.raises(MsbError):
            doc.edit_message(("message", 0), key, 0)
    hidden = MsbDocument(build_msb(parts=PARTS, points=POINTS,
                                   events=(_msg("hid0", 0, -1), _tail())))
    with pytest.raises(MsbError):
        hidden.edit_message(("message", 0), "posX", 1.0)


def test_messages_sharing_a_marker_move_together():
    doc = MsbDocument(build_messages())
    doc.edit_message(("message", 0), "posY", 25.0)
    assert [m["pos"] for m in doc.messages()] == [(1.0, 25.0, 3.0), (1.0, 25.0, 3.0)]


def test_add_message_duplicates_with_fresh_identity():
    doc = MsbDocument(build_messages())
    row = doc.add_message(("message", 0))
    assert (row["key"], row["textId"], row["point"], row["part"]) == ("message:2", 1000, "pt0", "piece0")
    assert [m["seq"] for m in doc.messages()] == [0, 1, 2]
    copy = doc.messages()[2]
    assert (copy["point"], copy["part"], copy["area"], copy["flag"]) == (0, 2, 4, -1)
    assert copy["pos"] == (1.0, 2.0, 3.0)
    assert copy["name"] != "msg0"
    assert doc.message_modified(("message", 2)) and ("message", 2) in doc.added
    assert_chain_coherent(doc)


def test_add_message_files_before_its_follower_on_disk():
    doc = MsbDocument(build_messages())
    doc.add_message(("message", 0))
    assert [e["name"] for e in doc.events] == ["msg0", "msg1", "msg0_2", "oa0", "end0"]
    back = MsbDocument(doc.export())
    assert [e["name"] for e in back.events] == ["msg0", "msg1", "msg0_2", "oa0", "end0"]
    assert [(m["seq"], m["textId"]) for m in back.messages()] == [(0, 1000), (1, 1001), (2, 1000)]
    assert_chain_coherent(back)


def test_add_message_twice_then_reload_keeps_unique_identities():
    doc = MsbDocument(build_messages())
    doc.add_message(("message", 0))
    doc.add_message(("message", 1))
    assert [m["seq"] for m in doc.messages()] == [0, 1, 2, 3]
    back = MsbDocument(doc.export())
    assert [e["name"] for e in back.events] == [e["name"] for e in doc.events]
    assert [m["seq"] for m in back.messages()] == [0, 1, 2, 3]
    assert_chain_coherent(back)
    third = MsbDocument(back.export())
    third.add_message(("message", 3))
    assert [m["seq"] for m in MsbDocument(third.export()).messages()] == [0, 1, 2, 3, 4]


def test_add_message_needs_a_follower_and_changes_nothing():
    raw = build_msb(parts=PARTS, points=POINTS, events=(_msg("msg0", 0, 0),))
    doc = MsbDocument(raw)
    with pytest.raises(MsbError):
        doc.add_message(("message", 0))
    assert len(doc.events) == 1 and doc.export() == raw


def test_create_message_from_scratch_takes_a_fresh_marker():
    doc = MsbDocument(build_messages())
    row = doc.create_message(3000, [9.0, 8.0, 7.0])
    assert (row["key"], row["textId"]) == ("message:2", 3000)
    [created] = [m for m in doc.messages() if m["seq"] == 2]
    assert (created["point"], created["flag"], created["part"]) == (2, -1, 2)
    assert created["pos"] == (9.0, 8.0, 7.0)
    point = doc.points[2]
    assert (point["name"], point["index"], point["type"]) == ("MessagePoint", 2, 0)
    event = doc._messages[(MESSAGE_EVENT, 2)]
    assert struct.unpack_from("<i", doc.plain, event["bhead"] + 4)[0] == 0
    back = MsbDocument(doc.export())
    assert [(p["name"], p["index"]) for p in back.points] == [("pt0", 0), ("pt1", 1),
                                                              ("MessagePoint", 2)]
    assert [(m["seq"], m["point"], m["textId"]) for m in back.messages()] == [(0, 0, 1000),
                                                                              (1, 0, 1001),
                                                                              (2, 2, 3000)]
    assert_chain_coherent(back)


def test_create_message_beside_chainless_treasure_takes_no_area():
    raw = build_msb(parts=PARTS, points=POINTS, events=(_treasure(), _objact(), _tail()))
    doc = MsbDocument(raw)
    row = doc.create_message(3000, [1.0, 2.0, 3.0])
    assert row["key"] == "message:0"
    [created] = doc.messages()
    assert created["area"] == -1 and created["areaName"] is None
    assert [e["name"] for e in MsbDocument(doc.export()).events] == ["tr0", row["name"], "oa0", "end0"]
    assert_chain_coherent(MsbDocument(doc.export()))


def test_create_message_validation():
    doc = MsbDocument(build_messages())
    for bad in (-1, True, 1.5, 2 ** 31 - BANK):
        with pytest.raises(MsbError):
            doc.create_message(bad, [0.0, 0.0, 0.0])
    for bad in ([0.0, 0.0], [0.0, 0.0, float("nan")], ["x", 0.0, 0.0], None):
        with pytest.raises(MsbError):
            doc.create_message(3000, bad)
    bare = MsbDocument(build_msb(parts=(("enemy", 2, 0, 0, 120000), ("player", 4, 0, 1, None)),
                                   points=POINTS, events=(_msg("msg0", 0, 0), _tail())))
    with pytest.raises(MsbError):
        bare.create_message(3000, [0.0, 0.0, 0.0])


def test_create_message_without_follower_adds_no_marker():
    raw = build_msb(parts=PARTS, points=POINTS, events=(_msg("msg0", 0, 0),))
    doc = MsbDocument(raw)
    with pytest.raises(MsbError):
        doc.create_message(3000, [0.0, 0.0, 0.0])
    assert len(doc.points) == 2 and doc.export() == raw


def test_remove_message_joins_the_chain_and_renumbers():
    raw = build_messages(nmsg=3)
    doc = MsbDocument(raw)
    # A distinct anchor on the last message proves the skip lands on it, not its name.
    struct.pack_into("<i", doc.plain, doc.events[2]["base"] + 4, 3)
    doc.events[2]["part"] = 3
    gone = doc.remove_message(("message", 1))
    assert gone == {"type": MESSAGE_EVENT, "id": 1, "name": "msg1"}
    assert [m["seq"] for m in doc.messages()] == [0, 2]
    assert chain_of(doc)[0][:2] == (3, MESSAGE_EVENT)
    assert doc.removed == [{"type": MESSAGE_EVENT, "id": 1, "name": "msg1", "kind": "Message"}]
    assert doc.dirty_count == 1
    with pytest.raises(MsbError):
        doc.read_message(("message", 1))
    back = MsbDocument(doc.export())
    assert [m["seq"] for m in back.messages()] == [0, 2]
    assert [e["name"] for e in back.events] == ["msg0", "msg2", "oa0", "end0"]
    assert_chain_coherent(back)
    assert back.export() != raw


def test_remove_message_beside_chainless_treasure_leaves_it_alone():
    doc = MsbDocument(build_messages(with_treasure=True))
    treasure = next(e for e in doc.events if e["type"] == 4)
    follower_base = doc.events[doc.events.index(treasure) + 1]["base"]
    before = bytes(doc.plain[treasure["base"]:follower_base])
    doc.remove_message(("message", 0))
    span = slice(treasure["base"], treasure["base"] + len(before))
    assert bytes(doc.plain[span]) == before
    back = MsbDocument(doc.export())
    assert [e["name"] for e in back.events] == ["tr0", "msg1", "oa0", "end0"]
    assert_chain_coherent(back)


def test_remove_message_filing_last_is_refused_cleanly():
    raw = build_msb(parts=PARTS, points=POINTS, events=(_msg("msg0", 0, 0),))
    doc = MsbDocument(raw)
    with pytest.raises(MsbError):
        doc.remove_message(("message", 0))
    assert len(doc.events) == 1 and doc.export() == raw


def test_remove_then_add_keeps_the_map_sound():
    doc = MsbDocument(build_messages())
    doc.remove_message(("message", 1))
    doc.add_message(("message", 0))
    assert [m["seq"] for m in doc.messages()] == [0, 1]
    back = MsbDocument(doc.export())
    assert [m["seq"] for m in back.messages()] == [0, 1]
    assert [(m["seq"], m["name"]) for m in back.messages()] == [(0, "msg0"), (1, "msg0_1")]
    assert_chain_coherent(back)


def test_message_merge_units_cover_text_point_flag_and_spot():
    doc = MsbDocument(build_messages())
    units = [unit for unit in doc.merge_units() if unit[0] == ("message", 0)]
    assert {unit[1] for unit in units} == {"text", "point", "flag"}
    event = doc._messages[(MESSAGE_EVENT, 0)]
    region_key = ('region', doc.points[event['point']]['index'])
    region_units = [unit for unit in doc.merge_units() if unit[0] == region_key]
    assert {'posX', 'posY', 'posZ'} <= {unit[1] for unit in region_units}
    spans = [(unit[2], unit[3]) for unit in doc.merge_units()]
    assert len(spans) == len(set(spans))
    starts = {unit[1]: unit[2] for unit in units}
    assert starts["text"] == event["bhead"]
    assert (starts["point"], starts["flag"]) == (event["ahead"] + 4, event["ahead"] + 8)
    assert all(unit[3] == 4 for unit in units)


def test_noop_export_preserves_message_bytes():
    raw = build_messages(with_treasure=True)
    assert MsbDocument(raw).export() == raw


def test_duplicate_message_identity_rejected():
    raw = build_msb(parts=PARTS, points=POINTS,
                    events=(_msg("msg0", 0, 0), _msg("msg0b", 0, 0), _tail()))
    with pytest.raises(MsbError):
        MsbDocument(raw)


def test_loader_tolerates_legacy_non_overlapping_tails():
    ahead, bhead = _ahead("msg0")
    structb = struct.pack("<8i", BANK + 1000, 1, 28, 2, 7, 0, ahead, bhead)
    raw = build_msb(parts=PARTS, points=POINTS,
                    events=(("msg0", MESSAGE_EVENT, 0, 2, (4, 0, -1, 0), structb), _tail()))
    doc = MsbDocument(raw)
    assert doc.messages()[0]["textId"] == 1000
    doc.edit_message(("message", 0), "text", 2000)
    assert MsbDocument(doc.export()).messages()[0]["textId"] == 2000
    doc.add_message(("message", 0))
    assert [m["seq"] for m in MsbDocument(doc.export()).messages()] == [0, 1]
