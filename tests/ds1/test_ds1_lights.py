"""Map light reading, editing and byte preservation on synthetic MSBs.

A light is a type-0 event: its position rides a shared map point, and one
preset word picks the game's built-in look. Effects often share the point,
so moving a light moves its flame along.
"""
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from msb_fixture import build_msb
from plugins.ds1.msb import MsbDocument, MsbError


def light_msb():
    return build_msb(points=(("pt0", (1.0, 2.0, 3.0)), ("pt1", (4.0, 5.0, 6.0))),
                     events=(("lamp0", 0, 0, 3, (2, 0, -1, 0), struct.pack("<i", 8)),
                             ("lamp1", 0, 1, 3, (2, 1, -1, 0), struct.pack("<i", 15)),
                             ("flame0", 2, 0, 3, (2, 0, -1, 0), struct.pack("<i", 0))))


def test_lights_listed_with_point_positions_and_sharers():
    doc = MsbDocument(light_msb())
    lights = doc.lights()
    assert [(light["seq"], light["name"], light["preset"]) for light in lights] == [
        (0, "lamp0", 8), (1, "lamp1", 15)]
    assert lights[0]["pos"] == (1.0, 2.0, 3.0)
    # The header's fourth word identifies the event, not an attached part.
    assert lights[0]["part"] == "piece0" and lights[0]["areaPart"] == "piece0"
    assert lights[0]["sharers"] == [{"type": 2, "kind": "SFX", "name": "flame0"}]
    assert lights[1]["sharers"] == []
    fields = doc.read_light(("light", 0))["fields"]
    assert [field["key"] for field in fields] == ["posX", "posY", "posZ", "preset"]
    assert fields[0]["value"] == 1.0 and fields[3]["value"] == 8
    assert "flame0" in fields[0]["description"]


def test_edit_roundtrip_exact_byte_boundary_and_revert():
    raw = light_msb()
    doc = MsbDocument(raw)
    doc.edit_light(("light", 0), "posX", 10.5)
    doc.edit_light(("light", 0), "preset", 25)
    assert doc.dirty_count == 2
    assert doc.light_modified(("light", 0))
    assert not doc.light_modified(("light", 1))
    changed = doc.export()
    diff = [i for i, (a, b) in enumerate(zip(raw, changed)) if a != b]
    assert 0 < len(diff) <= 8
    assert MsbDocument(changed).read_light(("light", 0))["fields"][3]["value"] == 25
    doc.edit_light(("light", 0), "posX", 1.0)
    doc.edit_light(("light", 0), "preset", 8)
    assert doc.export() == raw and doc.dirty_count == 0
    assert not doc.light_modified(("light", 0))


def test_light_validation_and_protected_fields():
    doc = MsbDocument(light_msb())
    with pytest.raises(MsbError):
        doc.edit_light(("light", 0), "posX", float("nan"))
    with pytest.raises(MsbError):
        doc.edit_light(("light", 0), "preset", 1.5)
    with pytest.raises(MsbError):
        doc.edit_light(("light", 0), "flag", 0)
    with pytest.raises(MsbError):
        doc.read_light(("light", 9))
    assert doc.export() == light_msb() and doc.dirty_count == 0


def test_broken_points_and_duplicate_events_rejected():
    raw = build_msb(points=(("pt0", (1.0, 2.0, 3.0)),))
    broken = bytearray(raw)
    struct.pack_into("<i", broken, raw.index(b"pt0\0") - 60, 44)
    with pytest.raises(MsbError):
        MsbDocument(bytes(broken))
    with pytest.raises(MsbError):
        MsbDocument(build_msb(points=(("pt0", (1.0, 2.0, 3.0)),),
                              events=(("lamp0", 0, 0, 3, (2, 0, -1, 0), struct.pack("<i", 8)),
                                      ("lamp1", 0, 0, 3, (2, 0, -1, 0), struct.pack("<i", 8)))))
