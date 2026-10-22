"""DS1 menu scripts: a tweak adds commands after an anchor in an ESD member.

Uses synthetic ESDs wrapped in a synthetic BND3 + DCX, so no game files are
needed. The anchor and the new command mirror the real equipment-list case:
1:15 ("Ins_button4_item_select", "icon", "FrpgMenuDlgObjEquipListItem")
gains 1:29 ("Ins_I02-02", "button5_0", ...) right after it.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from drb_fixture import make_dcx  # noqa: E402
from plugins.ds1 import esd, formats, menu_scripts  # noqa: E402
from plugins.ds1.esd import Command, Condition, Esd, State, assemble, disassemble, parse  # noqa: E402

ANCHOR = {"bank": 1, "id": 15,
          "args": ['"Ins_button4_item_select"', '"icon"', '"FrpgMenuDlgObjEquipListItem"']}
NEW = {"bank": 1, "id": 29,
       "args": ['"Ins_I02-02"', '"button5_0"', '"button_item_select"',
                '"Ins_button5_item_select"', '"FrpgMenuDlgEquipListIcon"']}


def command(spec):
    return Command(spec["bank"], spec["id"], [assemble(arg) for arg in spec["args"]])


def fresh(spec):
    return {"bank": spec["bank"], "id": spec["id"], "args": list(spec["args"])}


def build_script(where="pass"):
    """One group, two states; the anchor sits in one command list only."""
    entry = [Command(1, 3, [assemble('"Ins_X"')])]
    gone = [Command(1, 5, [])]
    ticking = [Command(7, 9, [assemble("i32(1004)")])]
    passes = [Command(1, 20, [])]
    subs = [Command(1, 7, [])]
    if where == "pass":
        passes.insert(0, command(ANCHOR))
    else:
        {"sub": subs, "entry": entry, "exit": gone, "while": ticking}[where].append(command(ANCHOR))
    condition = Condition(0, assemble("f22() == 1"), passes,
                          [Condition(None, assemble("r0 != 0"), subs)])
    first = State(0, entry, gone, ticking, [condition])
    return Esd({0: {0: first, 1: State(1, [], [], [], [])}}, None, 1, True, (0, 0, 0, 0))


def make_bnd(members):
    """A synthetic BND3: {base name: payload}, stored like the game ships them."""
    entries = sorted(members.items())
    encoded = [("N:/FRPG/data/MENU/" + name).encode("shift_jis") + b"\0" for name, _ in entries]
    directory_end = 32 + len(entries) * 24
    names_end = directory_end + sum(map(len, encoded))
    plain = bytearray(names_end)
    plain[:4] = b"BND3"
    plain[4:12] = b"TEST0000"
    plain[12] = 0x74
    struct.pack_into("<II", plain, 16, len(entries), names_end)
    name_offset = directory_end
    for raw in encoded:
        plain[name_offset:name_offset + len(raw)] = raw
        name_offset += len(raw)
    while len(plain) % 16:
        plain.append(0)
    name_offset = directory_end
    for index, ((name, payload), raw) in enumerate(zip(entries, encoded)):
        if payload:
            while len(plain) % 16:
                plain.append(0)
        struct.pack_into("<6I", plain, 32 + index * 24, 0x40, len(payload), len(plain),
                         index, name_offset, len(payload))
        name_offset += len(raw)
        plain.extend(payload)
    return bytes(plain)


def archive(scripts):
    return make_dcx(make_bnd(scripts))


def payload(dcx, name):
    plain = formats.inflate(dcx)
    entry = formats.members(plain)[name]
    return bytes(plain[entry.offset:entry.offset + entry.size])


def script(after=None, commands=None, member="i02-00.esd", archive_name="ingame"):
    return {"version": 1, "changes": [
        {"archive": archive_name, "script": member, "after": fresh(after or ANCHOR),
         "commands": [fresh(item) for item in commands or [NEW]]}]}


def passes_of(data, member="i02-00.esd"):
    return parse(payload(data, member)).state_groups[0][0].conditions[0].pass_commands


class ValidateTests(unittest.TestCase):
    def test_a_good_patch_keeps_its_owner_and_assembled_args(self):
        validated = menu_scripts.validate(script(), "Details")
        self.assertEqual(validated["owner"], "Details")
        change = validated["changes"][0]
        self.assertEqual((change["archive"], change["script"]), ("ingame", "i02-00.esd"))
        self.assertEqual(change["after"]["arg_bytes"], [assemble(arg) for arg in ANCHOR["args"]])
        self.assertEqual(change["commands"][0]["arg_bytes"], [assemble(arg) for arg in NEW["args"]])

    def test_patch_descriptions_are_strict(self):
        good_after = fresh(ANCHOR)
        good_command = fresh(NEW)
        bad = [
            None, {}, {"version": 2, "changes": []}, {"version": 1},
            {"version": 1, "changes": [], "extra": 1}, {"version": 1, "changes": []},
            {"version": 1, "changes": [{"archive": "ingame", "script": "i02-00.esd",
                                        "after": good_after, "commands": []}]},
            {"version": 1, "changes": [{"archive": "dlc", "script": "i02-00.esd",
                                        "after": good_after, "commands": [good_command]}]},
            {"version": 1, "changes": [{"archive": "ingame", "script": "",
                                        "after": good_after, "commands": [good_command]}]},
            {"version": 1, "changes": [{"archive": "ingame", "script": "i02-00.esd",
                                        "after": {**good_after, "bank": 2}, "commands": [good_command]}]},
            {"version": 1, "changes": [{"archive": "ingame", "script": "i02-00.esd",
                                        "after": {**good_after, "id": -1}, "commands": [good_command]}]},
            {"version": 1, "changes": [{"archive": "ingame", "script": "i02-00.esd",
                                        "after": {**good_after, "args": "x"}, "commands": [good_command]}]},
            {"version": 1, "changes": [{"archive": "ingame", "script": "i02-00.esd",
                                        "after": good_after,
                                        "commands": [{**good_command, "args": ['"unterminated']}]}]},
            {"version": 1, "changes": [{"archive": "ingame", "script": "i02-00.esd",
                                        "after": good_after, "commands": [good_command], "when": 1}]},
        ]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(menu_scripts.ScriptError):
                menu_scripts.validate(item, "Mod")
        self.assertIsInstance(menu_scripts.ScriptError("x"), ValueError)

    def test_a_patch_with_no_args_matches_a_command_with_none(self):
        validated = menu_scripts.validate(
            script(after={"bank": 1, "id": 20, "args": []}), "Details")
        self.assertEqual(validated["changes"][0]["after"]["arg_bytes"], [])


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.original = archive({"i02-00.esd": build_script().to_bytes(),
                                 "other.esd": build_script(where="entry").to_bytes(),
                                 "empty.esd": b""})

    def test_insertion_lands_right_after_the_anchor_in_pass_commands(self):
        result = menu_scripts.compose(self.original, [menu_scripts.validate(script(), "Details")],
                                      "ingame")
        self.assertEqual([(item.bank, item.id) for item in passes_of(result)],
                         [(1, 15), (1, 29), (1, 20)])
        self.assertEqual([disassemble(arg) for arg in passes_of(result)[1].args], NEW["args"])
        # The rebuilt script still parses, and the archive framing survives.
        self.assertEqual(parse(payload(result, "i02-00.esd")).to_bytes(),
                         payload(result, "i02-00.esd"))

    def test_anchors_match_in_every_list_at_any_depth(self):
        for where, grab in (("entry", lambda parsed: parsed.state_groups[0][0].entry_commands),
                            ("exit", lambda parsed: parsed.state_groups[0][0].exit_commands),
                            ("while", lambda parsed: parsed.state_groups[0][0].while_commands),
                            ("sub", lambda parsed: (parsed.state_groups[0][0].conditions[0]
                                                   .subconditions[0].pass_commands))):
            with self.subTest(where=where):
                source = archive({"only.esd": build_script(where=where).to_bytes()})
                member = "only.esd"
                result = menu_scripts.compose(
                    source, [menu_scripts.validate(script(member=member), "Details")], "ingame")
                found = grab(parse(payload(result, member)))
                self.assertEqual([(item.bank, item.id) for item in found
                                  if (item.bank, item.id) in ((1, 15), (1, 29))], [(1, 15), (1, 29)])

    def test_two_specs_apply_in_order_and_anchor_on_added_commands(self):
        first = menu_scripts.validate(script(), "One")
        third = {"bank": 1, "id": 30, "args": ['"extra"']}
        second = menu_scripts.validate(script(after=fresh({**NEW}), commands=[third]), "Two")
        result = menu_scripts.compose(self.original, [first, second], "ingame")
        self.assertEqual([(item.bank, item.id) for item in passes_of(result)],
                         [(1, 15), (1, 29), (1, 30), (1, 20)])

    def test_a_missing_or_ambiguous_anchor_is_refused_naming_the_mod(self):
        missing = menu_scripts.validate(
            script(after={"bank": 1, "id": 999, "args": []}), "Missing")
        with self.assertRaisesRegex(menu_scripts.ScriptError, "Missing"):
            menu_scripts.compose(self.original, [missing], "ingame")
        both = build_script()
        both.state_groups[0][0].entry_commands.append(
            Command(ANCHOR["bank"], ANCHOR["id"], [assemble(arg) for arg in ANCHOR["args"]]))
        source = archive({"dup.esd": both.to_bytes()})
        clash = menu_scripts.validate(script(member="dup.esd"), "Clash")
        with self.assertRaisesRegex(menu_scripts.ScriptError, "Clash.*2 commands"):
            menu_scripts.compose(source, [clash], "ingame")

    def test_a_missing_member_is_refused_naming_the_mod(self):
        bad = menu_scripts.validate(script(member="missing.esd"), "Lost")
        with self.assertRaisesRegex(menu_scripts.ScriptError, "Lost.*missing.esd"):
            menu_scripts.compose(self.original, [bad], "ingame")

    def test_untouched_members_stay_byte_identical(self):
        result = menu_scripts.compose(self.original, [menu_scripts.validate(script(), "Details")],
                                      "ingame")
        for name in ("other.esd", "empty.esd"):
            self.assertEqual(payload(result, name), payload(self.original, name))
        self.assertEqual(sorted(formats.members(formats.inflate(result))),
                         ["empty.esd", "i02-00.esd", "other.esd"])

    def test_no_applicable_changes_returns_the_original_bytes(self):
        self.assertIs(menu_scripts.compose(self.original, [], "ingame"), self.original)
        other = menu_scripts.validate(script(archive_name="common"), "Details")
        self.assertIs(menu_scripts.compose(self.original, [other], "ingame"), self.original)
        with self.assertRaises(menu_scripts.ScriptError):
            menu_scripts.compose(self.original, [], "dlc")


class VanillaTests(unittest.TestCase):
    def test_relative_names_both_archives(self):
        self.assertEqual(menu_scripts.RELATIVE["ingame"].as_posix(), "menu/ingame.menuesdbnd.dcx")
        self.assertEqual(menu_scripts.RELATIVE["common"].as_posix(), "menu/common.menuesdbnd.dcx")

    def test_synthetic_data_is_not_vanilla_and_unknown_archives_refused(self):
        self.assertFalse(menu_scripts.is_vanilla(b"x", "ingame"))
        self.assertFalse(menu_scripts.is_vanilla(b"x", "common"))
        with self.assertRaises(menu_scripts.ScriptError):
            menu_scripts.is_vanilla(b"x", "dlc")


if __name__ == "__main__":
    unittest.main()
