from __future__ import annotations

import struct
import unittest

from games.chrono_trigger.scene_maps import load_scene_map


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


def _fixture() -> FakeStore:
    scene = bytearray(24)
    struct.pack_into("<H", scene, 2, 1)   # BGSetTable
    struct.pack_into("<H", scene, 12, 2)  # MapTable
    struct.pack_into("<H", scene, 14, 3)  # BGAnime

    # 16x16 L1/L2, no L3. main L1/L2, sub L3, effects L1 + sprites + half.
    map_table = bytes([0, 0, 0, 0, 0x43, 0x51]) + bytes(256) + bytes(256) + bytes([0x80, 0, 0, 0])
    # One animation: 4-chip destination at chip 2; one frame from source chip 4 for 16 ticks.
    animation = bytes([1, 1]) + struct.pack("<H", 2 * 32) + bytes([0x10]) + struct.pack("<H", 4 * 32)
    cg = b"CG00" + bytes(128 * 64 // 2)
    return FakeStore({
        "Game/field/Mapinfo/mapinfo_0.dat": bytes(scene),
        "Game/field/MapTable/MapTable_0002.dat": map_table,
        "Game/field/PrioMap/PrioMap2.dat": bytes([3, 1, 2, 2]),
        "Game/field/BGSetTable/bgsettable_1.dat": bytes([0xFF] * 6 + [5, 0xFF]),
        "Game/field/map_bin/cg5.bin": cg,
        "Game/field/BGAnime/bganimeinfo_3.dat": animation,
    })


class SceneDiagnosticsIntegrationTests(unittest.TestCase):
    def test_scene_map_combines_pc_map_animation_and_raw_priority_diagnostics(self):
        payload = load_scene_map(_fixture(), 0)
        self.assertEqual(payload["layerPriorities"], [3, 1, 2, 2])
        self.assertFalse(payload["prioritySemanticsKnown"])
        self.assertEqual(payload["priorityPath"], "Game/field/PrioMap/PrioMap2.dat")

        screen = payload["compositionBits"]["screen"]
        effects = payload["compositionBits"]["effects"]
        self.assertTrue(screen["main"]["layer1"])
        self.assertTrue(screen["main"]["layer2"])
        self.assertTrue(screen["sub"]["layer3"])
        self.assertTrue(effects["targets"]["layer1"])
        self.assertTrue(effects["targets"]["sprites"])
        self.assertTrue(effects["halfIntensity"])

        animations = payload["chipAnimations"]
        self.assertTrue(animations["present"])
        self.assertTrue(animations["valid"])
        self.assertEqual(animations["decodedAnimationCount"], 1)
        self.assertEqual(animations["animations"][0]["destinationChipRange"], [2, 5])
        self.assertEqual(animations["animations"][0]["frames"][0]["sourceChipRange"], [4, 7])
        self.assertEqual(animations["animations"][0]["frames"][0]["durationTicks"], 16)
        self.assertFalse(animations["playbackEmulated"])


if __name__ == "__main__":
    unittest.main()
