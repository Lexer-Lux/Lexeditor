"""Hermetic tests for RDR2 installed-game inventory artwork fallback."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.rdr2 import inventory_icons as icons


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

    def test_decoded_rsc8_rejects_truncated_payload(self):
        decoded = struct.pack("<IIII", icons._RSC8_MAGIC, 2 | (31 << 8), 32, 16) + b"short"
        with self.assertRaisesRegex(ValueError, "truncated"):
            icons._normalize_decoded_rsc8(decoded)


if __name__ == "__main__":
    unittest.main()
