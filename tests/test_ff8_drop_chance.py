"""Regression coverage for the FF8 Drop Chance / Rare Item tweak."""
import io
import unittest

from games.ff8 import drop_chance


class DropChanceTests(unittest.TestCase):
    def test_all_weight_sets_total_256(self):
        for enabled in (False, True):
            for rare in (False, True):
                self.assertEqual(sum(drop_chance.weights(enabled, rare)), 256)

    def test_vanilla_normal_boundaries(self):
        expected = ((0, 0), (177, 0), (178, 1), (228, 1),
                    (229, 2), (243, 2), (244, 3), (255, 3))
        for roll, slot in expected:
            self.assertEqual(drop_chance.select_slot(
                roll, enabled=False, rare_item=False), slot)

    def test_vanilla_rare_keeps_slot_four_unreachable(self):
        expected = ((0, 0), (127, 0), (128, 1), (241, 1),
                    (242, 2), (255, 2))
        for roll, slot in expected:
            self.assertEqual(drop_chance.select_slot(
                roll, enabled=False, rare_item=True), slot)
        self.assertNotIn(3, {
            drop_chance.select_slot(roll, enabled=False, rare_item=True)
            for roll in range(256)
        })

    def test_tweak_normal_boundaries(self):
        expected = ((0, 0), (136, 0), (137, 1), (204, 1),
                    (205, 2), (238, 2), (239, 3), (255, 3))
        for roll, slot in expected:
            self.assertEqual(drop_chance.select_slot(
                roll, enabled=True, rare_item=False), slot)

    def test_tweak_rare_boundaries_and_slot_four(self):
        expected = ((0, 0), (93, 0), (94, 1), (163, 1),
                    (164, 2), (216, 2), (217, 3), (255, 3))
        for roll, slot in expected:
            self.assertEqual(drop_chance.select_slot(
                roll, enabled=True, rare_item=True), slot)
        counts = [0, 0, 0, 0]
        for roll in range(256):
            counts[drop_chance.select_slot(
                roll, enabled=True, rare_item=True)] += 1
        self.assertEqual(tuple(counts), drop_chance.TWEAK_RARE_WEIGHTS)

    @staticmethod
    def _fake_function() -> bytes:
        # Six CMP EAX,imm32 instructions with filler between them.
        blob = bytearray(b"\x90" * 0x100)
        cursor = 8
        for value in (178, 229, 244, 128, 242, 261):
            encoded = b"\x3D" + value.to_bytes(4, "little") + b"\x72\x02"
            blob[cursor:cursor + len(encoded)] = encoded
            cursor += 13
        return bytes(blob)

    def test_discovery_finds_both_selector_functions(self):
        size = drop_chance.MUG_END - drop_chance.IMAGE_BASE
        image = bytearray(b"\0" * size)
        fake = self._fake_function()
        drop_offset = drop_chance.DROP_START - drop_chance.IMAGE_BASE
        mug_offset = drop_chance.MUG_START - drop_chance.IMAGE_BASE
        image[drop_offset:drop_offset + len(fake)] = fake
        image[mug_offset:mug_offset + len(fake)] = fake
        patches = drop_chance.discover(io.BytesIO(image))
        self.assertEqual(len(patches), 12)
        self.assertEqual({patch.function for patch in patches}, {
            "Battle_RollDropItem", "Battle_RollMugItem"})
        self.assertEqual({patch.original for patch in patches},
                         {178, 229, 244, 128, 242, 261})

    def test_discovery_rejects_duplicate_threshold_operand(self):
        fake = bytearray(self._fake_function())
        fake[0xE0:0xE7] = b"\x3D" + (178).to_bytes(4, "little") + b"\x72\x02"
        with self.assertRaisesRegex(ValueError, r"expected one CMP immediate 178, found 2"):
            drop_chance._discover_function(bytes(fake), 0x1000, 0x1100, "fake")

    def test_hext_off_is_byte_for_byte_vanilla(self):
        self.assertEqual(drop_chance.build_hext(False), "")

    def test_hext_patches_all_discovered_operands(self):
        plan = []
        address = 0x500000
        for function in ("Battle_RollDropItem", "Battle_RollMugItem"):
            for original, replacement in drop_chance._THRESHOLD_REPLACEMENTS.items():
                plan.append(drop_chance.ThresholdPatch(
                    function, address, original, replacement))
                address += 4
        text = drop_chance.build_hext(True, tuple(plan))
        self.assertEqual(sum(" = " in line for line in text.splitlines()), 12)
        self.assertIn("Normal 137/68/34/17", text)
        self.assertIn("Rare Item 94/70/53/39", text)


if __name__ == "__main__":
    unittest.main()
