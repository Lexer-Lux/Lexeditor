"""Enemy AI branch safety with small, synthetic DAT files; no game install needed."""
from copy import deepcopy
import struct
import unittest

from games.ff8 import enemy_ai


def dat(first=b"\x23\x01\x00\x00"):
    blocks = [first, b"\0" * 4, b"\0" * 4, b"\0" * 4, b"\0" * 4]
    starts, cursor = [], 20
    for block in blocks:
        starts.append(cursor)
        cursor += len(block)
    text_offset = 16 + cursor
    section = struct.pack("<4I", 3, 16, text_offset, text_offset + 4)
    section += struct.pack("<5I", *starts) + b"".join(blocks)
    section += b"\0\0\0\0TEXT"  # offset table and opaque battle text
    return struct.pack("<4I", 2, 16, 20, 20 + len(section)) + b"KEEP" + section


class EnemyAiBranchTests(unittest.TestCase):
    def test_every_new_instruction_has_valid_default_operands(self):
        for template in enemy_ai.opcode_catalog():
            with self.subTest(opcode=template["opcode"]):
                if any(value["type"] in {"skip16", "jump16"} for value in template["operands"]):
                    template["targetKey"] = "end"
                enemy_ai._compile_script({"instructions": [template]})

    def test_end_target_round_trips_through_source_and_structure(self):
        raw = dat()
        parsed = enemy_ai.read(raw)
        script = parsed["scripts"][0]
        self.assertIn("jump16=@END", script["source"])
        self.assertEqual(script["instructions"][0]["targetKey"], "end")
        sources = [row["source"] for row in parsed["scripts"]]
        compiled = enemy_ai.compile_sources(sources)
        self.assertEqual(enemy_ai.rebuild_scripts(raw, compiled), (raw, 0))
        self.assertEqual(enemy_ai.rebuild_scripts(raw, parsed["scripts"]), (raw, 0))

    def test_end_target_moves_when_instruction_is_inserted(self):
        raw = dat()
        scripts = enemy_ai.read(raw)["scripts"]
        scripts[0]["instructions"].insert(1, {
            "key": "added", "opcode": 13, "operands": [7], "editable": True})
        rebuilt, changed = enemy_ai.rebuild_scripts(raw, scripts)
        reread = enemy_ai.read(rebuilt)["scripts"][0]
        self.assertEqual(changed, 1)
        self.assertEqual(reread["instructions"][0]["targetOffset"], reread["size"])
        self.assertTrue(rebuilt.endswith(b"\0\0\0\0TEXT"))
        self.assertEqual(rebuilt[16:20], b"KEEP")

    def test_invalid_branch_is_readable_without_invalid_source(self):
        for branch in (b"\x23\xfe\xff\0", b"\x23\x64\0\0"):
            with self.subTest(branch=branch):
                raw = dat(branch)
                parsed = enemy_ai.read(raw)
                self.assertFalse(parsed["scripts"][0]["instructions"][0]["targetValid"])
                self.assertIsNone(parsed["scripts"][0]["source"])
                with self.assertRaisesRegex(ValueError, "branch"):
                    enemy_ai.rebuild_scripts(raw, parsed["scripts"])

    def test_operand_edit_rejects_unaligned_and_outside_branch(self):
        raw = dat()
        for value in (-2, 100, 1.5, "1.5", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                enemy_ai.apply_edits(raw, [{"script": 0, "offset": 0,
                                           "operand": 0, "value": value}])
        changed, count = enemy_ai.apply_edits(raw, [{"script": 0, "offset": 0,
                                                     "operand": 0, "value": -3}])
        self.assertEqual(count, 1)
        self.assertEqual(enemy_ai.read(changed)["scripts"][0]["instructions"][0]["targetOffset"], 0)

    def test_structural_numeric_branches_receive_same_validation(self):
        raw = dat()
        scripts = enemy_ai.read(raw)["scripts"]
        for value in (-2, 100, 1.5):
            candidate = deepcopy(scripts)
            row = candidate[0]["instructions"][0]
            row.pop("targetKey")
            row["operands"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                enemy_ai.rebuild_scripts(raw, candidate)

    def test_forward_if_to_end_and_backward_jump(self):
        source = "A: IF[2] subject=0 subject_param=0 comparator=0 value16=0 skip16=@END\nB: JUMP[35] jump16=@A\nC: STOP[0]"
        script = enemy_ai.parse_script(source)
        code = enemy_ai._compile_script(script)
        parsed = enemy_ai.read(dat(code))["scripts"][0]
        self.assertEqual(parsed["instructions"][0]["targetLabel"], "END")
        self.assertEqual(parsed["instructions"][1]["targetOffset"], 0)


if __name__ == "__main__":
    unittest.main()
