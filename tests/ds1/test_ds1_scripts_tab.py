"""DS1 Scripts tab: list archives/scripts/states, read one state as plain data.

Uses synthetic ESDs (tests/ds1/esd_fixture.py) wrapped in a synthetic
BND3 + DCX, so no game files are needed. The BND3 writer below mirrors the
shape formats.members reads: BND3 header, member directory, shift_jis
names, then the payloads.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from drb_fixture import make_dcx  # noqa: E402
from esd_fixture import build_esd, make_bnd  # noqa: E402
from plugins.ds1 import scripts  # noqa: E402
from plugins.ds1.esd import Esd, State  # noqa: E402


def make_game(root):
    """A synthetic game folder: two menu archives and two talk archives."""
    menu = root / "menu"
    menu.mkdir(parents=True)
    (menu / "ingame.menuesdbnd.dcx").write_bytes(
        make_dcx(make_bnd({"i02-00.esd": build_esd().to_bytes()})))
    (menu / "common.menuesdbnd.dcx").write_bytes(
        make_dcx(make_bnd({"c00-00.esd": Esd({1: {2: State(2, [], [], [], [])}},
                                            None, 1, True, (0, 0, 0, 0)).to_bytes()})))
    talk = root / "script" / "talk"
    talk.mkdir(parents=True)
    (talk / "t01-00_00_00.talkesdbnd.dcx").write_bytes(
        make_dcx(make_bnd({"t01-00_00_00.esd": build_esd().to_bytes(),
                           "broken.esd": b"\0" * 64})))
    # m14 ships empty; members() refuses it, so it lists as no scripts.
    (talk / "m14_02_00_00.talkesdbnd.dcx").write_bytes(
        make_dcx(make_bnd({})))
    return root


class ListTests(unittest.TestCase):
    def setUp(self):
        scripts.clear_cache()
        self.folder = tempfile.TemporaryDirectory(prefix="lexeditor-ds1-scripts-")
        self.addCleanup(self.folder.cleanup)
        self.game = make_game(Path(self.folder.name))

    def test_menu_scopes_list_every_state(self):
        rows = scripts.list_rows(self.game, "ingame")
        self.assertEqual([row["id"] for row in rows],
                         ["ingame/i02-00.esd/0/0",
                          "ingame/i02-00.esd/5/4",
                          "ingame/i02-00.esd/5/6"])
        first = rows[0]
        self.assertEqual(first["table"], "ScriptState")
        self.assertEqual(first["name"], "i02-00.esd · state 0")
        self.assertEqual(first["values"],
                         {"archive": "ingame", "script": "i02-00.esd",
                          "group": 0, "state": 0})
        common = scripts.list_rows(self.game, "common")
        self.assertEqual([row["id"] for row in common], ["common/c00-00.esd/1/2"])

    def test_talk_scope_skips_empty_and_unreadable_members(self):
        rows = scripts.list_rows(self.game, "talk")
        self.assertEqual([row["id"] for row in rows],
                         ["talk/t01-00_00_00/t01-00_00_00.esd/0/0",
                          "talk/t01-00_00_00/t01-00_00_00.esd/5/4",
                          "talk/t01-00_00_00/t01-00_00_00.esd/5/6"])
        self.assertTrue(all(row["values"]["archive"] == "t01-00_00_00" for row in rows))

    def test_missing_files_list_as_empty(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-scripts-bare-") as bare:
            self.assertEqual(scripts.list_rows(Path(bare), "ingame"), [])
            self.assertEqual(scripts.list_rows(Path(bare), "common"), [])
            self.assertEqual(scripts.list_rows(Path(bare), "talk"), [])

    def test_unknown_scope_and_missing_root_raise(self):
        with self.assertRaises(scripts.ScriptError):
            scripts.list_rows(self.game, "dlc")
        with self.assertRaises(scripts.ScriptError):
            scripts.list_rows(None, "ingame")
        with self.assertRaises(scripts.ScriptError):
            scripts.read_state(None, "ingame/i02-00.esd/0/0")


class ReadTests(unittest.TestCase):
    def setUp(self):
        scripts.clear_cache()
        self.folder = tempfile.TemporaryDirectory(prefix="lexeditor-ds1-scripts-")
        self.addCleanup(self.folder.cleanup)
        self.game = make_game(Path(self.folder.name))

    def test_state_commands_come_back_as_text(self):
        row = scripts.read_state(self.game, "ingame/i02-00.esd/0/0")
        self.assertEqual((row["archive"], row["script"], row["group"], row["state"]),
                         ("ingame", "i02-00.esd", 0, 0))
        self.assertEqual(row["entry"], [{"bank": 1, "id": 3, "args": ['"Ins_X"', "1"]}])
        self.assertEqual(row["exit"], [{"bank": 1, "id": 5, "args": []}])
        self.assertEqual(row["while"],
                         [{"bank": 7, "id": 9,
                           "args": ["i32(1004)", "f32(0.5)", "f64(-2.0)", '"日本"']}])

    def test_state_conditions_come_back_as_a_tree(self):
        row = scripts.read_state(self.game, "ingame/i02-00.esd/0/0")
        plain, nested = row["conditions"]
        self.assertEqual((plain["evaluator"], plain["target"], plain["pass"], plain["sub"]),
                         ("f22() == 1", 0, [], []))
        self.assertEqual((nested["evaluator"], nested["target"]),
                         ("(r0 := f38(2, 0)) == 1...", 0))
        self.assertEqual(nested["pass"], [{"bank": 1, "id": 29, "args": ['"hi"']}])
        (sub,) = nested["sub"]
        self.assertEqual((sub["evaluator"], sub["target"], sub["pass"]),
                         ("r0 != 0", None, [{"bank": 1, "id": 7, "args": []}]))
        (leaf,) = sub["sub"]
        self.assertEqual((leaf["evaluator"], leaf["target"]), ("1", 0))

    def test_talk_state_reads_through_its_archive(self):
        row = scripts.read_state(self.game, "talk/t01-00_00_00/t01-00_00_00.esd/5/6")
        self.assertEqual((row["archive"], row["script"], row["group"], row["state"]),
                         ("t01-00_00_00", "t01-00_00_00.esd", 5, 6))
        (condition,) = row["conditions"]
        self.assertEqual((condition["evaluator"], condition["target"]),
                         ("mstat() == ongoing()", 4))

    def test_unknown_states_raise(self):
        for state_id in ("ingame/missing.esd/0/0",
                         "ingame/i02-00.esd/9/9",
                         "ingame/i02-00.esd/0/x",
                         "talk/t01-00_00_00/missing.esd/0/0",
                         "talk/nope/t01-00_00_00.esd/0/0",
                         "dlc/i02-00.esd/0/0/0",
                         "bogus"):
            with self.subTest(state_id=state_id), self.assertRaises(scripts.ScriptError):
                scripts.read_state(self.game, state_id)


if __name__ == "__main__":
    unittest.main()
