"""Native branches must target a byte inside their own declared island."""
import copy
import unittest

from plugins.ds1 import exe_patches


class BranchTargetBoundsTests(unittest.TestCase):
    def descriptor(self):
        return {
            "version": 1,
            "islands": [{"name": "target", "code": "9090c3"},
                        {"name": "larger-neighbor", "code": "90" * 32}],
            "hooks": [{"rva": 0x1000, "original": "9090909090",
                       "branch": {"opcode": "E8", "island": "target", "offset": 0}}],
        }

    def test_start_last_byte_and_default_offset_are_accepted(self):
        for offset in (None, 0, 2):
            with self.subTest(offset=offset):
                raw = self.descriptor()
                if offset is None:
                    del raw["hooks"][0]["branch"]["offset"]
                else:
                    raw["hooks"][0]["branch"]["offset"] = offset
                spec = exe_patches.validate(raw, "Example")
                self.assertEqual(spec["hooks"][0]["replacement"][-1], offset or 0)

    def test_end_and_outside_offsets_are_refused_for_both_opcodes(self):
        for opcode in ("E8", "E9"):
            for offset in (3, 4, 31, 0xFFFFFFFF, -1, True, 1.5, "1"):
                with self.subTest(opcode=opcode, offset=offset):
                    raw = self.descriptor()
                    raw["hooks"][0]["branch"].update(opcode=opcode, offset=offset)
                    with self.assertRaisesRegex(exe_patches.PatchError, "branch offset"):
                        exe_patches.validate(raw, "Example")

    def test_bounds_belong_to_the_named_island_not_the_largest(self):
        raw = self.descriptor()
        raw["hooks"][0]["branch"]["offset"] = 31
        with self.assertRaises(exe_patches.PatchError):
            exe_patches.validate(raw, "Example")
        raw["hooks"][0]["branch"]["island"] = "larger-neighbor"
        self.assertEqual(exe_patches.validate(raw, "Example")["hooks"][0]["replacement"][-1], 31)

    def test_validation_does_not_mutate_the_input(self):
        raw = self.descriptor()
        original = copy.deepcopy(raw)
        exe_patches.validate(raw, "Example")
        self.assertEqual(raw, original)


if __name__ == "__main__":
    unittest.main()
