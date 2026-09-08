"""Hermetic tests for RDR2 inventory-artwork coverage and DLC fallback."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.rdr2 import inventory_icons as icons


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "games" / "rdr2" / "assets"


class InstalledItemviewerTests(unittest.TestCase):
    def test_only_proven_dlc_treasure_ids_are_eligible(self):
        self.assertEqual(icons._DLC_ARCHIVE.as_posix(), "x64/dlcpacks/dlc_content_extra/dlc.rpf")
        self.assertEqual(icons._DLC_ENTRY, "x64/textures/ui/ui_itemviewer.ytd")
        self.assertEqual(icons.DLC_TREASURE_MAP_IDS, {
            "treasure_map_c5_m1", "treasure_map_c5_m2", "treasure_map_c5_m3",
            "treasure_map_c6_m1", "treasure_map_c6_m2", "treasure_map_c6_m3",
            "treasure_map_c6_m4",
        })
        self.assertIsNone(icons.resolve_inventory_icon("UI_NOTE_DINO_01"))
        self.assertIsNone(icons.resolve_inventory_icon("../treasure_map_c5_m1"))
        self.assertIsNone(icons.resolve_inventory_icon("treasure_map_c5_m1/../../x"))

    def test_historical_static_atlas_and_document_classification(self):
        # ITEM_TEXTURES is maintained independently and can legitimately gain or
        # lose checked-in overrides. This regression owns UI_ITEMVIEWER's
        # document/DLC accounting, so do not pin an unrelated physical-file
        # count that changes when other inventory-artwork work lands on master.
        item_textures = list((ASSETS / "dictionary_icons" / "item_textures").glob("*.png"))
        itemviewer = list((ASSETS / "dictionary_icons" / "ui_itemviewer").glob("*.png"))
        self.assertTrue(item_textures)
        self.assertEqual(len(itemviewer), 235)
        # Abigail's letters are script-driven narrative documents, not a proven
        # UI_ITEMVIEWER texture. Keep unknown aliases missing rather than
        # fabricating static art; exercise non-static classification with a
        # catalog-backed document handle instead.
        self.assertEqual(
            icons.classify_ui_itemviewer_reference("UI_LETTER_ABIGAIL", ASSETS),
            "missing",
        )
        self.assertEqual(
            icons.classify_ui_itemviewer_reference("UI_LETTER_MAYOR_PERM", ASSETS),
            "non-static",
        )

    def test_all_residual_raw_values_are_source_classified(self):
        # 41 raw catalog values remain after the 235 static atlas images and the
        # seven C5/C6 installed-game fallbacks. Two values contain alternatives,
        # producing 42 unique attempted texture IDs.
        self.assertEqual(len(icons.NON_STATIC_UI_ITEMVIEWER_RAW_VALUES), 41)
        self.assertEqual(len(icons.NON_STATIC_UI_ITEMVIEWER_IDS), 42)
        self.assertEqual(
            {icons.classify_ui_itemviewer_reference(raw, ASSETS)
             for raw in icons.NON_STATIC_UI_ITEMVIEWER_RAW_VALUES},
            {"non-static"},
        )
        for texture_id in icons.DLC_TREASURE_MAP_IDS:
            self.assertEqual(
                icons.classify_ui_itemviewer_reference(texture_id, ASSETS),
                "installed-game",
            )
        self.assertEqual(
            icons.classify_ui_itemviewer_reference("UI_DOES_NOT_EXIST", ASSETS),
            "missing",
        )
        # Historical UI_ITEMVIEWER accounting: 235 static raw values + seven
        # installed-DLC raw values + 41 source-proven non-static raw values.
        self.assertEqual(235 + len(icons.DLC_TREASURE_MAP_IDS)
                         + len(icons.NON_STATIC_UI_ITEMVIEWER_RAW_VALUES), 283)

    def test_existing_private_cache_does_not_run_extractor(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / icons._DLC_ARCHIVE
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"fixture")
            cache = root / "cache"
            target = cache / "generation" / "treasure_map_c5_m1.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"png")
            with patch.object(icons, "GAME_ROOT", root), \
                    patch.object(icons, "_CACHE_ROOT", cache), \
                    patch.object(icons, "_archive_generation", return_value="generation"), \
                    patch.object(icons, "_load_dictionary", side_effect=AssertionError("extractor ran")):
                self.assertEqual(icons.resolve_inventory_icon("TREASURE_MAP_C5_M1"), target)

    def test_decoded_rsc8_is_rewrapped_as_standard_raw_deflate(self):
        virtual = bytes(range(32))
        physical = bytes(range(16))
        # RpfCli's decoded-resource header encodes compressor None as stored 31.
        decoded = struct.pack(
            "<IIII", icons._RSC8_MAGIC, 2 | (31 << 8), len(virtual), len(physical)
        ) + virtual + physical
        normalized = icons._normalize_decoded_rsc8(decoded)
        magic, version, virtual_flags, physical_flags = struct.unpack_from("<IIII", normalized, 0)
        self.assertEqual(magic, icons._RSC8_MAGIC)
        self.assertEqual(((version >> 8) & 0x1F) + 1, 1)  # deflate
        self.assertEqual((virtual_flags, physical_flags), (32, 16))
        self.assertEqual(
            zlib.decompress(normalized[16:], -zlib.MAX_WBITS),
            virtual + physical,
        )

    def test_server_falls_back_only_after_a_local_ui_itemviewer_miss(self):
        source = (ROOT / "games/rdr2/server.py").read_text(encoding="utf-8")
        self.assertIn("_resolve_inventory_icon(relative.stem)", source)
        self.assertIn('relative.parts[:2] == ("dictionary_icons", "ui_itemviewer")', source)
        self.assertIn("if not asset.is_file():", source)

    def test_decoded_rsc8_rejects_truncated_payload(self):
        decoded = struct.pack("<IIII", icons._RSC8_MAGIC, 2 | (31 << 8), 32, 16) + b"short"
        with self.assertRaisesRegex(ValueError, "truncated"):
            icons._normalize_decoded_rsc8(decoded)


if __name__ == "__main__":
    unittest.main()
