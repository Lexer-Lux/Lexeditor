from __future__ import annotations

import struct
import unittest

from games.chrono_trigger.scene_animations import (
    load_scene_chip_animations,
    parse_scene_chip_animations,
)


class FakeStore:
    def __init__(self, resources: dict[str, bytes]):
        self.resources = resources

    def read(self, path: str, source: str = "mine"):
        if path not in self.resources:
            raise KeyError(path)
        return self.resources[path], "archive"

    def exists(self, path: str, source: str = "mine") -> bool:
        return path in self.resources

    def scene_entries(self):
        return [(0, "Game/field/Mapinfo/mapinfo_0.dat")]


def _descriptor() -> bytes:
    # 2 animations.
    # A0: dest chip 2, two frames. Upper duration nibbles 0x10/0x80 map
    # to 16/4 ticks while low nibbles remain uninterpreted raw data.
    data = bytearray([2])
    data.extend([2])
    data.extend(struct.pack("<H", 2 * 32))
    data.extend([0x12, 0x83])
    data.extend(struct.pack("<HH", 0 * 32, 4 * 32))
    # A1: dest chip 5, one eight-tick frame sourced from chip 1.
    data.extend([1])
    data.extend(struct.pack("<H", 5 * 32))
    data.extend([0x40])
    data.extend(struct.pack("<H", 1 * 32))
    return bytes(data)


def _scene() -> bytes:
    raw = bytearray(24)
    struct.pack_into("<H", raw, 2, 7)   # BGSetTable
    struct.pack_into("<H", raw, 14, 9)  # BGAnime index
    return bytes(raw)


class SceneAnimationTests(unittest.TestCase):
    def test_decodes_pc_animation_count_offsets_and_duration_nibbles(self):
        parsed = parse_scene_chip_animations(_descriptor(), source_chip_count=8)
        self.assertEqual(parsed["declaredAnimationCount"], 2)
        self.assertEqual(parsed["decodedAnimationCount"], 2)
        first = parsed["animations"][0]
        self.assertEqual(first["destinationChipRange"], [2, 5])
        self.assertEqual(first["frames"][0]["durationTicks"], 16)
        self.assertEqual(first["frames"][0]["durationLowerNibble"], 2)
        self.assertEqual(first["frames"][1]["durationTicks"], 4)
        self.assertEqual(first["frames"][1]["durationLowerNibble"], 3)
        self.assertEqual(first["frames"][1]["sourceChipRange"], [4, 7])
        self.assertTrue(first["frames"][1]["sourceRangeValid"])
        self.assertFalse(parsed["playbackEmulated"])

    def test_unknown_duration_upper_nibble_is_preserved_without_guessing(self):
        raw = bytearray([1, 1])
        raw.extend(struct.pack("<H", 0))
        raw.append(0x31)
        raw.extend(struct.pack("<H", 0))
        parsed = parse_scene_chip_animations(bytes(raw))
        frame = parsed["animations"][0]["frames"][0]
        self.assertIsNone(frame["durationTicks"])
        self.assertEqual(frame["durationUpperNibble"], 0x30)
        self.assertEqual(parsed["unknownDurationFrames"], 1)

    def test_declared_animation_truncation_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "destination offset"):
            parse_scene_chip_animations(bytes([2, 1]))

    def test_terminator_before_declared_count_is_reported_not_guessed(self):
        parsed = parse_scene_chip_animations(bytes([2, 0]))
        self.assertEqual(parsed["decodedAnimationCount"], 0)
        self.assertTrue(parsed["terminatedBeforeDeclaredCount"])
        self.assertEqual(parsed["terminator"]["marker"], 0)

    def test_loads_scene_reference_and_bgset_animation_slot(self):
        # One 128x64 packed cg sheet -> 128 chips after nibble unpacking.
        cg = b"CG00" + bytes(128 * 64 // 2)
        store = FakeStore({
            "Game/field/Mapinfo/mapinfo_0.dat": _scene(),
            "Game/field/BGSetTable/bgsettable_7.dat": bytes([0xFF] * 6 + [11, 0xFF]),
            "Game/field/map_bin/cg11.bin": cg,
            "Game/field/BGAnime/bganimeinfo_9.dat": _descriptor(),
        })
        payload = load_scene_chip_animations(store, 0)
        self.assertTrue(payload["present"])
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["animationIndex"], 9)
        self.assertEqual(payload["sourceSheet"]["chipset"], 11)
        self.assertEqual(payload["sourceSheet"]["chipCount"], 128)
        self.assertEqual(payload["decodedAnimationCount"], 2)
        self.assertFalse(payload["playbackEmulated"])

    def test_missing_descriptor_is_reported_without_breaking_scene_inspection(self):
        store = FakeStore({
            "Game/field/Mapinfo/mapinfo_0.dat": _scene(),
            "Game/field/BGSetTable/bgsettable_7.dat": bytes([0xFF] * 8),
        })
        payload = load_scene_chip_animations(store, 0)
        self.assertFalse(payload["present"])
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["animations"], [])


if __name__ == "__main__":
    unittest.main()
