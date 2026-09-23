"""Independent GF spellbook core tests. Does not claim native integration."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import gf_spellbooks as s


def document():
    return {"schemaVersion": 1, "books": [
        {"gfId": 0, "pages": [[{"magicId": 7, "abilityId": None}, {"magicId": 1, "abilityId": 20}], [], [{"magicId": 4, "abilityId": None}]]},
        {"gfId": 1, "pages": [[{"magicId": 7, "abilityId": 21}]]},
    ]}


class SpellbookTests(unittest.TestCase):
    def test_order_pages_and_zero_stock_never_filtered(self):
        view = s.project_view(document(), 0, {1: 150}, (), {1: True, 4: True, 7: True})
        self.assertEqual([[x.magic_id for x in page] for page in view], [[7, 1], [], [4]])
        self.assertEqual((view[0][0].amount, view[0][0].usable, view[0][0].reason), (0, False, "stock"))
        self.assertEqual((view[0][1].amount, view[0][1].usable, view[0][1].reason), (150, False, "ability"))
        self.assertEqual((view[2][0].page, view[2][0].index), (2, 0))

    def test_gate_requires_both_stock_and_learned_ability(self):
        for stock, learned, expected in ((0, (), False), (1, (), False), (0, (20,), False), (1, (20,), True)):
            with self.subTest(stock=stock, learned=learned):
                view = s.project_view(document(), 0, {1: stock}, learned, {1: True})
                self.assertEqual(view[0][1].usable, expected)
        self.assertFalse(s.project_view(document(), 1, {7: 1}, (20,), {7: True})[0][0].usable)

    def test_native_restrictions_fail_closed(self):
        for native in ({}, {1: False}):
            self.assertEqual(s.project_view(document(), 0, {1: 5}, (20,), native)[0][1].reason, "native")

    def test_missing_gf_and_unconfigured_gf_have_no_borrowed_book(self):
        for gf in (None, 15):
            self.assertEqual(s.project_view(document(), gf, {7: 10}, (), {7: True}), [])
            with self.assertRaises(s.SpellbookError):
                s.debit_selection(document(), gf, 0, 0, 7, {7: 10}, (), {7: True})

    def test_duplicate_and_unknown_values_rejected(self):
        doc = document()
        doc["books"][0]["pages"][2].append({"magicId": 7, "abilityId": None})
        with self.assertRaises(s.SpellbookError): s.validate(doc)
        doc = document(); doc["books"].append(copy.deepcopy(doc["books"][0]))
        with self.assertRaises(s.SpellbookError): s.validate(doc)
        for field, value in (("magicId", 0), ("magicId", 57), ("magicId", True), ("magicId", "7"), ("abilityId", 0), ("abilityId", 116), ("abilityId", True)):
            doc = document(); doc["books"][0]["pages"][0][0][field] = value
            with self.assertRaises(s.SpellbookError): s.validate(doc)
        for gf in (-1, 16, True):
            doc = document(); doc["books"][0]["gfId"] = gf
            with self.assertRaises(s.SpellbookError): s.validate(doc)

    def test_debit_is_by_id_not_display_position_and_preserves_inputs(self):
        stock = {4: 255, 1: 150, 7: 2}
        before = copy.deepcopy(stock)
        after = s.debit_selection(document(), 0, 0, 0, 7, stock, (), {7: True})
        self.assertEqual(after, {4: 255, 1: 150, 7: 1})
        self.assertEqual(stock, before)
        after = s.debit_selection(document(), 0, 2, 0, 4, stock, (), {4: True}, amount=3)
        self.assertEqual(after, {4: 252, 1: 150, 7: 2})
        self.assertEqual(s.debit_selection(document(), 0, 0, 0, 7, {7: 1}, (), {7: True}), {7: 0})

    def test_selection_rechecks_stock_gate_native_and_stale_index(self):
        for stock, learned, native in (({1: 0}, (20,), {1: True}), ({1: 1}, (), {1: True}), ({1: 1}, (20,), {1: False})):
            with self.assertRaises(s.SpellbookError):
                s.debit_selection(document(), 0, 0, 1, 1, stock, learned, native)
        with self.assertRaises(s.SpellbookError):
            s.debit_selection(document(), 0, 0, 0, 4, {4: 10, 7: 10}, (), {4: True, 7: True})
        for page, index in ((-1, 0), (0, -1), (3, 0), (1, 0)):
            with self.assertRaises(s.SpellbookError):
                s.debit_selection(document(), 0, page, index, 7, {7: 10}, (), {7: True})

    def test_reservations_prevent_double_spend(self):
        self.assertEqual(s.project_view(document(), 0, {7: 2}, (), {7: True}, {7: 2})[0][0].reason, "reserved")
        with self.assertRaises(s.SpellbookError):
            s.debit_selection(document(), 0, 0, 0, 7, {7: 2}, (), {7: True}, amount=2, reserved={7: 1})
        self.assertEqual(s.debit_selection(document(), 0, 0, 0, 7, {7: 2}, (), {7: True}, reserved={7: 1}), {7: 1})

    def test_persistence_is_validated_atomic_and_does_not_touch_runtime(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            self.assertEqual(s.load(root), {"schemaVersion": 1, "books": []})
            original = document()
            s.save(root, original)
            self.assertEqual(s.load(root), original)
            self.assertEqual([p.name for p in root.iterdir()], [s.FILE_NAME])
            data = (root / s.FILE_NAME).read_bytes()
            invalid = document(); invalid["schemaVersion"] = 2
            with self.assertRaises(s.SpellbookError): s.save(root, invalid)
            self.assertEqual((root / s.FILE_NAME).read_bytes(), data)
            with patch.object(s.os, "replace", side_effect=OSError("denied")):
                with self.assertRaises(OSError): s.save(root, {"schemaVersion": 1, "books": []})
            self.assertEqual((root / s.FILE_NAME).read_bytes(), data)
            self.assertEqual([p.name for p in root.iterdir()], [s.FILE_NAME])
            (root / s.FILE_NAME).write_text("{broken", encoding="utf-8")
            with self.assertRaises(s.SpellbookError): s.load(root)


if __name__ == "__main__":
    unittest.main()
