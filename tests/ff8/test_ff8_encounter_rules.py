"""Hermetic coverage for the FF8 region-and-ground encounter rules.

The Encounters tab's Rules page edits one value per stored rule: the encounter
group a (region, ground) pair selects. This builds a synthetic wmsetus.obj in
memory - no game install - with three rules and three groups, and pins the
behaviour the screen depends on:

  * parsing exposes every stored rule with its region, ground and group;
  * re-aiming a rule writes only that rule's two group bytes and leaves the
    rest of the archive byte-identical;
  * the number of rules is fixed: the writer refuses an edit for a rule index
    the file does not hold, which is why the table offers no way to add one;
  * a rule pointing at a group that does not exist is refused, both on the way
    in (parse) and on the way out (save);
  * two rules may store the same pair, so the screen has to report a clash
    rather than assume the data is unambiguous.
"""
import struct
import tempfile
import unittest
from pathlib import Path

from plugins.ff8 import paths, world_map

# (region, ground, group). The last two share a pair on purpose.
RULES = [(1, 0, 0), (2, 3, 2), (2, 3, 1)]
GROUPS = [[10, 11, 12, 13, 14, 15, 16, 17],
          [20, 21, 22, 23, 24, 25, 26, 27],
          [30, 31, 32, 33, 34, 35, 36, 37]]


def _synthetic_wmset(rules=RULES, groups=GROUPS):
    pointers = [0] * world_map.SECTION_COUNT
    cursor = world_map.SECTION_COUNT * 4
    pointers[0] = cursor
    section1 = struct.pack("<I", 0)  # OpenVIII: global-file end marker.
    for region, ground, group in rules:
        section1 += struct.pack("<BBH", region, ground, group)
    section1 += struct.pack("<I", 0)  # terminator
    cursor += len(section1)
    pointers[1] = cursor
    section2 = bytes(world_map.REGION_COUNT)
    cursor += len(section2)
    pointers[2] = cursor
    pointers[3] = cursor
    section4 = b"".join(struct.pack("<8H", *group) for group in groups)
    section4 += struct.pack("<I", 0)  # terminator
    cursor += len(section4)
    pointers[4] = cursor
    pointers[5] = pointers[6] = pointers[7] = pointers[8] = cursor
    field_returns = struct.pack("<I", 0)
    cursor += len(field_returns)
    for index in range(9, 32):
        pointers[index] = cursor
    pointers[32] = cursor
    sky = struct.pack("<II", 8, 0) + bytes(52)
    cursor += len(sky)
    pointers[33] = cursor
    pointers[34] = cursor
    draw = bytearray(world_map.DRAW_HEADER_SIZE) + bytes(
        world_map.DRAW_POINT_COUNT * world_map.DRAW_RECORD_SIZE)
    cursor += len(draw)
    for index in range(35, world_map.SECTION_COUNT):
        pointers[index] = cursor
    return (struct.pack(f"<{world_map.SECTION_COUNT}I", *pointers)
            + section1 + section2 + section4 + field_returns + sky + bytes(draw)
            + b"\0\0\0\0")


def _rule_offset(index):
    """Where rule `index` sits: section 1, past the four-byte end marker."""
    return world_map.SECTION_COUNT * 4 + 4 + index * 4


class EncounterRuleTests(unittest.TestCase):
    def test_parse_exposes_every_rule_and_group(self):
        parsed = world_map.parse(_synthetic_wmset())
        self.assertEqual(
            [(row["regionId"], row["groundId"], row["encounterGroup"])
             for row in parsed["helpers"]], RULES)
        self.assertEqual([row["encounters"] for row in parsed["groups"]], GROUPS)
        # Two rules claim region 2 with ground 3. The reader keeps both, so
        # the editor is the thing that has to say the pair is ambiguous.
        pairs = [(row["regionId"], row["groundId"]) for row in parsed["helpers"]]
        self.assertEqual(pairs.count((2, 3)), 2)

    def _save(self, raw, edits):
        with tempfile.TemporaryDirectory(prefix="ff8-encounter-rules-") as temp:
            source = Path(temp) / "wmsetus.obj"
            source.write_bytes(raw)
            original_source, original_direct = world_map.source_path, paths.DIRECT_ROOT
            world_map.source_path = lambda dataset="current": source
            paths.DIRECT_ROOT = Path(temp) / "direct"
            try:
                result = world_map.save(edits)
                written = (paths.DIRECT_ROOT / world_map.DIRECT_RELATIVE).read_bytes()
            finally:
                world_map.source_path = original_source
                paths.DIRECT_ROOT = original_direct
        return result, written

    def test_reaiming_a_rule_touches_only_its_group_bytes(self):
        raw = _synthetic_wmset()
        result, written = self._save(raw, [
            {"kind": "helper", "id": 1, "regionId": 2, "groundId": 3, "encounterGroup": 0}])
        self.assertEqual(result["saved"], 1)
        self.assertEqual(len(written), len(raw))
        parsed = world_map.parse(written)
        self.assertEqual(parsed["helpers"][1]["encounterGroup"], 0)
        self.assertEqual(len(parsed["helpers"]), len(RULES))
        changed = [index for index, byte in enumerate(raw) if written[index] != byte]
        # The group is the third and fourth byte of the record.
        self.assertEqual(changed, [_rule_offset(1) + 2])

    def test_the_rule_count_is_fixed(self):
        raw = _synthetic_wmset()
        # There is no index 3: the screen cannot offer to add a rule because
        # section 1 has no room reserved for one.
        with self.assertRaises(ValueError):
            self._save(raw, [{"kind": "helper", "id": len(RULES), "regionId": 9,
                              "groundId": 9, "encounterGroup": 0}])
        # A save with no rule edits leaves the rule bytes exactly as they were.
        _result, written = self._save(raw, [
            {"kind": "region", "id": 0, "regionId": 4}])
        start = _rule_offset(0)
        self.assertEqual(written[start:start + len(RULES) * 4],
                         raw[start:start + len(RULES) * 4])

    def test_a_rule_cannot_point_at_a_missing_group(self):
        raw = _synthetic_wmset()
        with self.assertRaises(ValueError):
            self._save(raw, [{"kind": "helper", "id": 0, "regionId": 1,
                              "groundId": 0, "encounterGroup": len(GROUPS)}])
        # The same rule is refused on the way in, so a hand-edited archive
        # cannot present the editor with an unreachable group either.
        with self.assertRaises(ValueError):
            world_map.parse(_synthetic_wmset(rules=[(1, 0, len(GROUPS))]))


if __name__ == "__main__":
    unittest.main()
