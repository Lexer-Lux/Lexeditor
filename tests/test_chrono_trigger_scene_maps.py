from __future__ import annotations

import unittest

from games.chrono_trigger.scene_maps import parse_scene_map


def _map(prop: bytes, repeat: int = 0, *, layer3=False) -> bytes:
    # All three size nibbles 0 => 16x16 map tiles. L3 flag is bit 7.
    header = bytes([0x00, 0x80 if layer3 else 0x00, 0x00, 0x00, 0x03, 0x11])
    l1 = bytes([1]) * (16 * 16)
    l2 = bytes([2]) * (16 * 16)
    l3 = bytes([3]) * (16 * 16) if layer3 else b""
    return header + l1 + l2 + l3 + prop + bytes([repeat])


class SceneMapTests(unittest.TestCase):
    def test_decodes_dimensions_layers_and_rle_properties(self):
        # 0x84 = RLE flag + collision index 1 (Full); repeat 0 means 256.
        parsed = parse_scene_map(_map(bytes([0x84, 0x00, 0x00])))
        self.assertEqual(parsed["sceneWidth"], 16)
        self.assertEqual(parsed["sceneHeight"], 16)
        self.assertEqual(parsed["layers"]["layer1"]["tiles"], [1] * 256)
        self.assertEqual(parsed["layers"]["layer2"]["tiles"], [2] * 256)
        self.assertFalse(parsed["layers"]["layer3"]["enabled"])
        self.assertEqual(parsed["propertyStats"]["decodedBeforeNormalize"], 256)
        self.assertEqual(parsed["collisionCounts"], {"Full": 256})

    def test_layer3_payload_is_present_only_when_enabled(self):
        parsed = parse_scene_map(_map(bytes([0x80, 0x00, 0x00]), layer3=True))
        self.assertTrue(parsed["header"]["layer3Enabled"])
        self.assertEqual(parsed["layers"]["layer3"]["tiles"], [3] * 256)

    def test_tile_add_flags_promote_effective_tile_bank(self):
        parsed = parse_scene_map(_map(bytes([0x83, 0x00, 0x00])))
        self.assertEqual(parsed["layers"]["layer1"]["tiles"][0], 257)
        self.assertEqual(parsed["layers"]["layer2"]["tiles"][0], 258)

    def test_property_stream_can_pad_short_decoded_grid(self):
        header = bytes([0, 0, 0, 0, 0, 0])
        raw = header + bytes(256) + bytes(256) + bytes([0x00, 0x00, 0x00])
        parsed = parse_scene_map(raw)
        self.assertEqual(parsed["propertyStats"]["decodedBeforeNormalize"], 1)
        self.assertEqual(parsed["propertyStats"]["padded"], 255)
        self.assertEqual(len(parsed["properties"]), 256)

    def test_truncated_tile_array_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_scene_map(bytes([0, 0, 0, 0, 0, 0]) + bytes(100))

    def test_rle_record_requires_repeat_byte(self):
        header = bytes([0, 0, 0, 0, 0, 0])
        raw = header + bytes(256) + bytes(256) + bytes([0x80, 0, 0])
        with self.assertRaises(ValueError):
            parse_scene_map(raw)


if __name__ == "__main__":
    unittest.main()
