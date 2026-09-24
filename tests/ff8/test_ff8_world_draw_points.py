"""Hermetic coverage for FF8 world Draw Point parsing and editing (#84).

Builds a synthetic wmsetus.obj in memory (no game install): 48 ascending
section pointers, an empty helper/group/field-return/sky layout, and a full
section-34 table of 128 position records. Pins that parsing exposes every
record, that edits move only the three proved bytes (the fourth padding byte
and every other record stay byte-identical), and that out-of-range or
duplicated edits fail instead of corrupting the archive.
"""
import struct
import unittest

from plugins.ff8 import world_map


def _synthetic_wmset(padding=0xA5):
    pointers = [0] * world_map.SECTION_COUNT
    cursor = world_map.SECTION_COUNT * 4
    # Section 1: end marker plus an all-zero helper terminator.
    pointers[0] = cursor
    section1 = struct.pack("<II", 0, 0)
    cursor += len(section1)
    # Section 2: 768 region bytes.
    pointers[1] = cursor
    section2 = bytes(world_map.REGION_COUNT)
    cursor += len(section2)
    pointers[2] = cursor
    # Section 4: one all-zero group terminator, so no encounter groups.
    pointers[3] = cursor
    section4 = struct.pack("<I", 0)
    cursor += len(section4)
    pointers[4] = cursor
    pointers[5] = pointers[6] = pointers[7] = pointers[8] = cursor
    # Field-return section (0-based section 8): footer only, zero records.
    field_returns = struct.pack("<I", 0)
    cursor += len(field_returns)
    for index in range(9, 32):
        pointers[index] = cursor
    # Sky section (0-based section 32): pointer table [record-at-8,
    # terminator] plus one record.
    pointers[32] = cursor
    sky = struct.pack("<II", 8, 0) + bytes(52)
    cursor += len(sky)
    pointers[33] = cursor
    # Draw section (0-based section 34): 0x2C header plus 128 records with
    # distinct padding. The section between sky and draw stays empty.
    pointers[34] = cursor
    draw = bytearray(world_map.DRAW_HEADER_SIZE)
    for index in range(world_map.DRAW_POINT_COUNT):
        draw += struct.pack("<BBBB", index, (3 * index) % 256,
                            index % 251, (padding + index) % 256)
    cursor += len(draw)
    for index in range(35, world_map.SECTION_COUNT):
        pointers[index] = cursor
    raw = (struct.pack(f"<{world_map.SECTION_COUNT}I", *pointers)
           + section1 + section2 + section4 + field_returns + sky + bytes(draw)
           + b"\0\0\0\0")
    return bytes(raw)


class WorldDrawPointTests(unittest.TestCase):
    def test_parse_exposes_all_records(self):
        parsed = world_map.parse(_synthetic_wmset())
        self.assertEqual(len(parsed["drawPoints"]), 128)
        first, last = parsed["drawPoints"][0], parsed["drawPoints"][127]
        self.assertEqual((first["id"], first["drawId"], first["x"],
                          first["y"], first["subId"]), (0, 129, 0, 0, 0))
        self.assertEqual((last["id"], last["drawId"]), (127, 256))

    def test_edit_moves_point_and_preserves_padding(self):
        raw = _synthetic_wmset()
        changed = world_map.apply_draw_point_edits(
            raw, [{"id": 10, "x": 200, "y": 44, "subId": 7}])
        parsed = world_map.parse(bytes(changed))
        point = parsed["drawPoints"][10]
        self.assertEqual((point["x"], point["y"], point["subId"]),
                         (200, 44, 7))
        self.assertEqual(point["padding"], (0xA5 + 10) % 256)
        # Every other byte in the archive is untouched.
        offset = (world_map.SECTION_COUNT * 4 + 8 + world_map.REGION_COUNT
                  + 4 + 4 + 8 + 52 + world_map.DRAW_HEADER_SIZE + 10 * 4)
        for index, byte in enumerate(raw):
            if offset <= index < offset + 3:
                continue
            self.assertEqual(changed[index], byte, f"byte {index} changed")

    def test_edit_rejects_bad_and_duplicate_edits(self):
        raw = _synthetic_wmset()
        with self.assertRaises(ValueError):
            world_map.apply_draw_point_edits(
                raw, [{"id": 128, "x": 0, "y": 0, "subId": 0}])
        with self.assertRaises(ValueError):
            world_map.apply_draw_point_edits(
                raw, [{"id": 0, "x": 256, "y": 0, "subId": 0}])
        with self.assertRaises(ValueError):
            world_map.apply_draw_point_edits(raw, [
                {"id": 5, "x": 1, "y": 1, "subId": 1},
                {"id": 5, "x": 2, "y": 2, "subId": 2},
            ])
        # Failed edits leave the archive untouched.
        self.assertEqual(bytes(world_map.apply_draw_point_edits(raw, [])),
                         raw)


if __name__ == "__main__":
    unittest.main()
