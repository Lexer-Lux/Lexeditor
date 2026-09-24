"""Regression checks for the RDR1 STRTBL codec.

Synthetic fixtures prove byte-for-byte no-op round trips and relocation after
text growth without shipping Rockstar data.  When RDR_GAME_ROOT is available,
the installed PC global string table is also extracted and parsed read-only.
"""

from pathlib import Path
import os
import struct
import subprocess
import tempfile
import unittest

from plugins.rdr import string_tables


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "magic-rdr" / "app" / "Rpf6ReadCli.exe"


def _entry(identifier: str, text: str, *, suffix: bytes | None = None) -> bytes:
    entry_hash = string_tables.joaat(identifier)
    glyph = struct.pack("<I6B", entry_hash, 1, 2, 3, 4, 5, 6)
    encoded = (text + "\0").encode("utf-16le")
    layout = suffix or struct.pack("<ffBB", 1.25, 0.75, 7, 8)
    return glyph + struct.pack("<i", len(encoded) // 2) + encoded + layout


def _block(entries: list[tuple[str, str]], trailing: bytes = b"") -> bytes:
    return (
        struct.pack("<I", len(entries))
        + b"".join(_entry(identifier, text) for identifier, text in entries)
        + trailing
    )


def fixture() -> bytes:
    identifiers = ["HELLO", "GOODBYE"]
    prefix = bytearray(struct.pack("<i", 11) + bytes(44))
    prefix += struct.pack("<Ii", 256, len(identifiers))
    for identifier in identifiers:
        encoded = identifier.encode("ascii")
        prefix += struct.pack("<I", len(encoded)) + encoded + b"\0"
    first = _block([("HELLO", "Hello"), ("GOODBYE", "Goodbye")], b"\xAA\xBB")
    second = _block([("HELLO", "Hola"), ("GOODBYE", "Adiós")])
    first_offset = len(prefix)
    second_offset = first_offset + len(first)
    positions = [first_offset] + [0] * 8 + [second_offset, second_offset]
    for index, offset in enumerate(positions):
        struct.pack_into("<I", prefix, 4 + index * 4, offset)
    return bytes(prefix) + first + second


class StringTableCodec(unittest.TestCase):
    def test_noop_roundtrip_is_byte_identical(self):
        source = fixture()
        table = string_tables.parse(source)
        self.assertEqual(string_tables.serialize(table, {}), source)
        self.assertEqual(table.identifiers, ("HELLO", "GOODBYE"))

    def test_text_growth_relocates_later_blocks_and_preserves_shared_language(self):
        source = fixture()
        table = string_tables.parse(source)
        original_second = table.positions[9]
        edited, changed = string_tables.apply_text_edits(source, [{
            "languageIndex": 0,
            "entryIndex": 0,
            "expectedHash": f"0x{string_tables.joaat('HELLO'):08X}",
            "expectedText": "Hello",
            "value": "Hello from New Austin",
        }])
        self.assertEqual(changed, 1)
        reparsed = string_tables.parse(edited)
        self.assertGreater(reparsed.positions[9], original_second)
        self.assertEqual(reparsed.positions[9], reparsed.positions[10])
        self.assertEqual(reparsed.blocks[reparsed.positions[0]].entries[0].text,
                         "Hello from New Austin")
        self.assertEqual(reparsed.blocks[reparsed.positions[9]].entries[0].text, "Hola")
        self.assertTrue(
            reparsed.blocks[reparsed.positions[0]].trailing.endswith(b"\xAA\xBB")
        )

    def test_shared_language_block_is_one_ui_record_set(self):
        rows = string_tables.rows(string_tables.parse(fixture()))
        spanish = [row for row in rows if row["languageIndex"] == 9]
        self.assertEqual(len(spanish), 2)
        self.assertEqual(spanish[0]["languageIndexes"], [9, 10])
        self.assertTrue(spanish[0]["sharedLanguageBlock"])
        self.assertEqual(spanish[0]["identifier"], "HELLO")

    def test_stale_hash_or_text_is_refused(self):
        source = fixture()
        base = {
            "languageIndex": 0,
            "entryIndex": 0,
            "expectedHash": f"0x{string_tables.joaat('HELLO'):08X}",
            "expectedText": "Hello",
            "value": "Changed",
        }
        with self.assertRaisesRegex(ValueError, "identity changed"):
            string_tables.apply_text_edits(source, [{**base, "expectedHash": "0x00000000"}])
        with self.assertRaisesRegex(ValueError, "text changed"):
            string_tables.apply_text_edits(source, [{**base, "expectedText": "Old"}])

    def test_utf16_unit_count_handles_non_bmp_characters(self):
        source = fixture()
        edit = {
            "languageIndex": 0,
            "entryIndex": 0,
            "expectedHash": f"0x{string_tables.joaat('HELLO'):08X}",
            "expectedText": "Hello",
            "value": "Horse 🐎",
        }
        encoded, changed = string_tables.apply_text_edits(source, [edit])
        self.assertEqual(changed, 1)
        reparsed = string_tables.parse(encoded)
        self.assertEqual(reparsed.blocks[reparsed.positions[0]].entries[0].text, "Horse 🐎")


class InstalledGame(unittest.TestCase):
    def setUp(self):
        root = os.environ.get("RDR_GAME_ROOT")
        archive = Path(root) / "game" / "tune_d11generic.rpf" if root else None
        if not archive or not archive.is_file() or not TOOL.is_file():
            self.skipTest("Red Dead Redemption is not installed here")
        self.archive = archive

    def test_installed_global_table_parses_and_noop_roundtrips(self):
        with tempfile.TemporaryDirectory(prefix="rdr-strtbl-") as folder:
            subprocess.run(
                [str(TOOL), "extract", str(self.archive), folder, "*global.strtbl"],
                check=True, capture_output=True, timeout=120,
            )
            target = next(Path(folder).rglob("global.strtbl"))
            source = target.read_bytes()
            table = string_tables.parse(source)
            self.assertGreater(len(table.identifiers), 0)
            self.assertGreater(len(string_tables.rows(table)), 0)
            self.assertEqual(string_tables.serialize(table, {}), source)


if __name__ == "__main__":
    unittest.main()
