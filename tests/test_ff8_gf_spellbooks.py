from pathlib import Path
import tempfile
import unittest

from games.ff8 import gf_spellbooks


class GfSpellbookRuntimeTests(unittest.TestCase):
    def sample(self):
        return {
            "schemaVersion": 1,
            "books": [
                {"gfId": 0, "pages": [
                    [{"magicId": 1, "abilityId": None}, {"magicId": 21, "abilityId": 7}],
                    [{"magicId": 50, "abilityId": None}],
                ]},
                {"gfId": 5, "pages": [[{"magicId": 56, "abilityId": 115}]]},
            ],
        }

    def test_runtime_snapshot_round_trips_without_fixed_addresses(self):
        document = gf_spellbooks.validate(self.sample())
        raw = gf_spellbooks.runtime_bytes(document)
        self.assertEqual(len(raw), 8 + 1024 + 16)
        self.assertEqual(raw[:8], b"LXSB\x01\x10\x08\x04")
        self.assertEqual(gf_spellbooks.parse_runtime(raw), document)

    def test_save_writes_json_and_loader_owned_runtime_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            saved = gf_spellbooks.save(root, self.sample())
            runtime = root / gf_spellbooks.RUNTIME_RELATIVE
            self.assertTrue(runtime.is_file())
            self.assertEqual(gf_spellbooks.parse_runtime(runtime.read_bytes()), saved)
            self.assertEqual(gf_spellbooks.load(root), saved)

    def test_empty_runtime_is_valid_native_fallback_snapshot(self):
        empty = {"schemaVersion": 1, "books": []}
        raw = gf_spellbooks.runtime_bytes(empty)
        self.assertEqual(gf_spellbooks.parse_runtime(raw), empty)
        self.assertEqual(raw[-16:], bytes(16))

    def test_runtime_rejects_trailing_slots_and_invalid_ids(self):
        raw = bytearray(gf_spellbooks.runtime_bytes(self.sample()))
        # GF0 declares two pages (8 active slots); slot 9 must remain 0/255.
        offset = 8 + 8 * 2
        raw[offset] = 2
        with self.assertRaises(gf_spellbooks.SpellbookError):
            gf_spellbooks.parse_runtime(bytes(raw))
        raw = bytearray(gf_spellbooks.runtime_bytes(self.sample()))
        raw[8] = 57
        with self.assertRaises(gf_spellbooks.SpellbookError):
            gf_spellbooks.parse_runtime(bytes(raw))

    def test_view_keeps_zero_stock_visible_but_disabled(self):
        pages = gf_spellbooks.project_view(
            self.sample(), 0, {1: 0, 21: 10, 50: 4}, {7},
            {1: True, 21: True, 50: True},
        )
        self.assertEqual(pages[0][0].magic_id, 1)
        self.assertEqual(pages[0][0].amount, 0)
        self.assertFalse(pages[0][0].usable)
        self.assertEqual(pages[0][0].reason, "stock")
        self.assertTrue(pages[0][1].usable)

    def test_duplicate_spell_and_unsafe_ability_fail_closed(self):
        duplicate = self.sample()
        duplicate["books"][0]["pages"][1].append({"magicId": 1, "abilityId": None})
        with self.assertRaises(gf_spellbooks.SpellbookError):
            gf_spellbooks.validate(duplicate)
        invalid = self.sample()
        invalid["books"][0]["pages"][0][0]["abilityId"] = 116
        with self.assertRaises(gf_spellbooks.SpellbookError):
            gf_spellbooks.validate(invalid)


if __name__ == "__main__":
    unittest.main()
