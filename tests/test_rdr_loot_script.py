"""The corpse loot items are readable and writable in the script that holds them.

Red Dead Redemption has no drops table in its data files, so this is the seam.
These cases run against the installed game when it is there, and against a
hand-built script otherwise, so the decoding is checked either way.
"""
from pathlib import Path
import os
import re
import struct
import subprocess
import tempfile
import unittest

from plugins.rdr import loot_script

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "magic-rdr" / "app" / "Rpf6ReadCli.exe"


def _installed_archive() -> Path | None:
    root = os.environ.get("RDR_GAME_ROOT")
    if not root:
        return None
    archive = Path(root) / "game" / "content.rpf"
    return archive if archive.is_file() and TOOL.is_file() else None


class Decoding(unittest.TestCase):
    def _fixture(self):
        """A script shaped like the real one: pushes, calls, and decoy bytes."""
        lookup = 0x5864
        address = struct.pack(">H", lookup)
        # A header, the way the real script has one: a call site cannot begin
        # at offset zero and the reader refuses to look behind the start.
        body = bytearray(bytes(8))
        wanted = [3, 0, 15, 17, 200]
        for item in wanted:
            if item <= loot_script.PUSH_SMALL_MAX:
                body.append(loot_script.PUSH_SMALL + item)
            else:
                body += bytes([loot_script.PUSH_BYTE, item])
            body += bytes([loot_script.CALL]) + address
            body += b"\x00\x11\x22"
        # The same two bytes appearing without a call before them is not a
        # call site, and must not be read as one.
        body += address + b"\x99"
        decompiled = ("var Function_122(int iParam0) //Position: 0x5864 / 22628\n"
                      + "".join(f"ADD_ITEM(Function_122({item}), &x, 1);\n"
                               for item in wanted))
        return bytes(body), decompiled, wanted

    def test_a_decoy_address_is_not_a_call_site(self):
        script, decompiled, wanted = self._fixture()
        self.assertEqual([slot.item for slot in loot_script.verify(script, decompiled)],
                         wanted)

    def test_both_push_forms_decode(self):
        script, decompiled, _ = self._fixture()
        slots = loot_script.verify(script, decompiled)
        self.assertEqual([slot.width for slot in slots], [1, 1, 1, 2, 2])

    def test_an_edit_keeps_the_script_the_same_length(self):
        script, decompiled, _ = self._fixture()
        patched = loot_script.write_slots(script, {0: 9}, decompiled)
        self.assertEqual(len(patched), len(script))
        # verify() compares against the decompiler, which still describes the
        # script as it shipped, so the edited copy is read back directly.
        self.assertEqual(loot_script.read_slots(patched, decompiled)[0].item, 9)

    def test_a_small_push_refuses_a_value_it_cannot_hold(self):
        script, decompiled, _ = self._fixture()
        # Growing the push would move every address after it, and the calls
        # carrying those addresses are not being rewritten.
        with self.assertRaises(ValueError):
            loot_script.write_slots(script, {0: 200}, decompiled)

    def test_a_byte_push_takes_a_large_value(self):
        script, decompiled, _ = self._fixture()
        patched = loot_script.write_slots(script, {4: 42}, decompiled)
        self.assertEqual(loot_script.read_slots(patched, decompiled)[4].item, 42)

    def test_a_script_that_does_not_decode_is_refused(self):
        script, decompiled, _ = self._fixture()
        lying = decompiled + "ADD_ITEM(Function_122(6), &x, 1);\n"
        with self.assertRaises(ValueError):
            loot_script.verify(script, lying)

    def test_the_override_goes_where_the_game_looks(self):
        path = loot_script.override_path(Path(r"C:/RDRMod"))
        self.assertTrue(str(path).endswith("lootcorpsegenericnoanim.wsc"))
        self.assertIn("mod", path.parts)


class InstalledGame(unittest.TestCase):
    def setUp(self):
        self.archive = _installed_archive()
        if self.archive is None:
            self.skipTest("Red Dead Redemption is not installed here")

    def test_the_installed_script_decodes_to_what_the_decompiler_reports(self):
        with tempfile.TemporaryDirectory(prefix="rdr-loot-") as folder:
            work = Path(folder)
            wanted = "*lootcorpsegenericnoanim*"
            subprocess.run([str(TOOL), "unpack", str(self.archive), str(work / "u"),
                            wanted], check=True, capture_output=True, timeout=300)
            subprocess.run([str(TOOL), "decompile", str(self.archive), str(work / "d"),
                            wanted], check=True, capture_output=True, timeout=300)
            script = next((work / "u").rglob("*.wsc")).read_bytes()
            decompiled = next((work / "d").rglob("*.c")).read_text(
                encoding="utf-8", errors="replace")
            slots = loot_script.verify(script, decompiled)
            # Every branch of the LootType switch, and the items it can give.
            self.assertEqual(len(slots), 27)
            self.assertEqual(sorted({slot.item for slot in slots}),
                             [0, 1, 2, 3, 7, 8, 12, 17])

    def test_the_installed_script_survives_a_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="rdr-loot-rt-") as folder:
            work = Path(folder)
            wanted = "*lootcorpsegenericnoanim*"
            subprocess.run([str(TOOL), "unpack", str(self.archive), str(work / "u"),
                            wanted], check=True, capture_output=True, timeout=300)
            subprocess.run([str(TOOL), "decompile", str(self.archive), str(work / "d"),
                            wanted], check=True, capture_output=True, timeout=300)
            script = next((work / "u").rglob("*.wsc")).read_bytes()
            decompiled = next((work / "d").rglob("*.c")).read_text(
                encoding="utf-8", errors="replace")
            before = loot_script.verify(script, decompiled)
            # Give the first branch a different item, then read it back.
            patched = loot_script.write_slots(script, {0: 5}, decompiled)
            self.assertEqual(len(patched), len(script))
            self.assertEqual(sum(1 for a, b in zip(script, patched) if a != b), 1)
            after = loot_script.read_slots(patched, decompiled)
            self.assertEqual(after[0].item, 5)
            self.assertEqual([slot.item for slot in after[1:]],
                             [slot.item for slot in before[1:]])


if __name__ == "__main__":
    unittest.main()
