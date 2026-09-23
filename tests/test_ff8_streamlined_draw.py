"""Regression coverage for the FF8 Streamlined Draw tweak."""
import unittest

from plugins.ff8 import streamlined_draw as draw


class StreamlinedDrawTests(unittest.TestCase):
    def test_disabled_is_vanilla(self):
        self.assertEqual(draw.build_hext(False), "")

    def test_enabled_requires_boolean(self):
        for bad in (1, "yes", None):
            with self.assertRaises(ValueError):
                draw.build_hext(bad)

    def test_stock_limit_bounds(self):
        for bad in (0, 256, -1, "lots", 10.5, True):
            with self.assertRaises(ValueError):
                draw.build_hext(True, bad)
        self.assertIn("7A17F0", draw.build_hext(True, 100))

    def test_drawable_stock_truth_table(self):
        self.assertFalse(draw.enemy_has_drawable_stock([0, 0, 0, 0], {}))
        self.assertTrue(draw.enemy_has_drawable_stock([1, 0, 0, 0], {}))
        self.assertTrue(draw.enemy_has_drawable_stock([1, 2, 3, 4], {1: 100}))
        self.assertFalse(draw.enemy_has_drawable_stock([1, 0, 0, 0], {1: 100}))
        self.assertFalse(draw.enemy_has_drawable_stock([0x40, 0, 0, 0], {}))
        with self.assertRaises(ValueError):
            draw.enemy_has_drawable_stock([1, 0, 0], {})

    def test_mask_keeps_only_enemies_with_stock(self):
        spells = {3: [1, 0, 0, 0], 4: [0, 0, 0, 0], 5: [2, 0, 0, 0]}
        mask = (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6)
        self.assertEqual(draw.filter_draw_target_mask(mask, spells, {}),
                         (1 << 3) | (1 << 5))
        self.assertEqual(draw.filter_draw_target_mask(mask, spells, {1: 100, 2: 100}), 0)

    def test_hext_names_both_native_hooks(self):
        text = draw.build_hext(True)
        self.assertIn(f"{draw.SPELL_COUNT_HOOK:X}", text)
        self.assertIn(f"{draw.MODE_LIST_HOOK:X}", text)
        self.assertIn(f"{draw.SPELL_COUNT_CAVE:X}", text)
        self.assertIn(f"{draw.MODE_LIST_CAVE:X}", text)
        self.assertIn(f"{draw.STOCK_FILTER_CAVE:X}", text)

    def test_hext_never_touches_shared_draw_hooks(self):
        text = draw.build_hext(True)
        for hook in draw.SHARED_DRAW_HOOKS:
            self.assertNotIn(f"{hook:X}", text)
