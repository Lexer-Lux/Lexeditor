"""Summon states its own eligibility before any menu hook exists.

Monogamy gives each character one GF. A character with none has nothing to
summon, and choosing the slot does nothing, which reads as a bug rather than a
rule. The rule and the sentence it shows are settled here the way Draw's were,
so the menu hook has something verified to implement.
"""
import os
from pathlib import Path
import unittest

from plugins.ff8 import battle_issue_54 as battle


class SummonEligibility(unittest.TestCase):
    def test_a_character_with_no_gf_cannot_summon(self):
        self.assertFalse(battle.summon_command_available(junctioned_gf_count=0))

    def test_one_junctioned_gf_is_enough(self):
        self.assertTrue(battle.summon_command_available(junctioned_gf_count=1))

    def test_monogamy_is_not_assumed(self):
        # Monogamy is a separate tweak. Summon asks whether there is a GF, not
        # whether there is exactly one, so the rule holds with it off.
        self.assertTrue(battle.summon_command_available(junctioned_gf_count=3))

    def test_a_negative_count_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            battle.summon_command_available(junctioned_gf_count=-1)

    def test_the_grey_slot_says_why(self):
        reason = battle.summon_unavailable_reason(junctioned_gf_count=0)
        self.assertIn("No GF is junctioned", reason)
        # It says what to do about it, not only what is wrong.
        self.assertIn("Junction", reason)

    def test_a_usable_slot_says_nothing(self):
        self.assertEqual(battle.summon_unavailable_reason(junctioned_gf_count=1), "")

    def test_summon_is_no_longer_a_blocker(self):
        # It was one while the rule existed and the hook did not. The gate now
        # rides the two menu sites the Draw work already owns, so what remains
        # blocked is GF Magic and nothing else.
        self.assertFalse(any("Summon" in blocker for blocker in battle.BLOCKERS))
        self.assertTrue(any("GF Magic" in blocker for blocker in battle.BLOCKERS))


if __name__ == "__main__":
    unittest.main()


class DisabledCommandMechanism(unittest.TestCase):
    """FF8 already greys a command and refuses it. Summon needs that flag, not a hook."""

    def _executable(self):
        root = os.environ.get("LEXEDITOR_FF8_ROOT")
        if not root:
            self.skipTest("Final Fantasy VIII is not installed here")
        path = Path(root) / "FF8_EN.exe"
        if not path.is_file():
            self.skipTest("FF8_EN.exe is not where the installation says it is")
        return path.read_bytes()

    def test_the_disabled_flag_is_read_and_branched_on(self):
        image = self._executable()
        # Virtual address to file offset for this build's .text section.
        offset = lambda va: 0x1000 + (va - 0x401000)
        for address, expected in battle.COMMAND_DISABLED_SITES.items():
            actual = image[offset(address):offset(address) + len(expected)]
            self.assertEqual(actual, expected, f"{address:08X}")

    def test_the_flag_is_bit_one_of_the_entry_flags(self):
        # test cl, 2 on the select side and test bl, 2 on the render side.
        self.assertEqual(battle.COMMAND_FLAG_DISABLED, 0x02)
        self.assertEqual(battle.COMMAND_FLAGS_OFFSET, 3)
        self.assertIn(battle.COMMAND_FLAG_DISABLED,
                      battle.COMMAND_DISABLED_SITES[0x004BC7BB])

    def test_the_refusal_already_makes_a_noise(self):
        # push 5 into the sound call, so a greyed command is not silent.
        self.assertEqual(battle.COMMAND_DENIED_SOUND, 5)
        self.assertEqual(battle.COMMAND_DISABLED_SITES[0x004BCA45],
                         bytes([0x6A, battle.COMMAND_DENIED_SOUND]))

    def test_the_entry_layout_is_read_from_the_executable(self):
        image = self._executable()
        offset = lambda va: 0x1000 + (va - 0x401000)
        for address, expected in battle.COMMAND_ENTRY_SITES.items():
            actual = image[offset(address):offset(address) + len(expected)]
            self.assertEqual(actual, expected, f"{address:08X}")

    def test_the_entry_pointer_is_the_one_the_renderer_loads(self):
        # 8B 1D <dword> is mov ebx, [address]; the dword is the entry pointer.
        load = battle.COMMAND_ENTRY_SITES[0x004BCEE9]
        self.assertEqual(load[:2], bytes([0x8B, 0x1D]))
        self.assertEqual(int.from_bytes(load[2:6], "little"),
                         battle.COMMAND_ENTRY_POINTER)

    def test_the_menu_state_table_is_recorded_as_not_the_command_list(self):
        # It dispatches on a state byte, not on a command, and reading it as a
        # command table is the wrong turn this note exists to prevent.
        self.assertEqual(battle.BATTLE_MENU_STATE_TABLE, 0x004BC704)
        self.assertNotEqual(battle.BATTLE_MENU_STATE_TABLE,
                            battle.COMMAND_ENTRY_POINTER)


class CommandFlags(unittest.TestCase):
    """Only Summon's disabled bit, and only when the character has no GF."""

    def test_summon_is_disabled_without_a_gf(self):
        self.assertEqual(
            battle.command_flags(command_id=battle.GF_COMMAND_ID, flags=0,
                                 junctioned_gf_count=0),
            battle.COMMAND_FLAG_DISABLED)

    def test_junctioning_one_during_a_battle_takes_the_greying_off(self):
        self.assertEqual(
            battle.command_flags(command_id=battle.GF_COMMAND_ID,
                                 flags=battle.COMMAND_FLAG_DISABLED,
                                 junctioned_gf_count=1), 0)

    def test_every_other_flag_in_the_byte_belongs_to_the_game(self):
        for count in (0, 1):
            result = battle.command_flags(command_id=battle.GF_COMMAND_ID,
                                          flags=0xFD, junctioned_gf_count=count)
            self.assertEqual(result & ~battle.COMMAND_FLAG_DISABLED, 0xFD & ~battle.COMMAND_FLAG_DISABLED)

    def test_no_other_command_is_touched(self):
        for command in (1, 2, 4, 5, 6, 7):
            for flags in (0, battle.COMMAND_FLAG_DISABLED, 0xFF):
                self.assertEqual(
                    battle.command_flags(command_id=command, flags=flags,
                                         junctioned_gf_count=0), flags)


class SummonGate(unittest.TestCase):
    """The machine code that greys Summon, checked without running the game."""

    def _disassemble(self, payload, address):
        try:
            from capstone import Cs, CS_ARCH_X86, CS_MODE_32
        except ImportError:  # pragma: no cover - capstone is a dev dependency
            self.skipTest("capstone is not installed here")
        engine = Cs(CS_ARCH_X86, CS_MODE_32)
        return [f"{i.mnemonic} {i.op_str}".strip() for i in engine.disasm(payload, address)]

    def test_the_gate_reads_the_acting_character_and_its_junctioned_gfs(self):
        listing = self._disassemble(battle._summon_gate_payload(), battle.SUMMON_GATE_CAVE)
        text = "\n".join(listing)
        self.assertIn(f"movzx eax, byte ptr [{battle.ACTIVE_BATTLE_ACTOR:#x}]", text)
        self.assertIn(f"imul eax, eax, {battle.BATTLE_ACTOR_STRIDE:#x}", text)
        character = battle.BATTLE_ACTOR_BASE + battle.BATTLE_ACTOR_CHARACTER_ID
        self.assertIn(f"movzx eax, byte ptr [eax + {character:#x}]", text)
        self.assertIn(f"imul eax, eax, {battle.SAVEMAP_CHARACTER_STRIDE:#x}", text)
        mask = battle.SAVEMAP_CHARACTER_BASE + battle.GF_MASK_OFFSET
        self.assertIn(f"movzx eax, word ptr [eax + {mask:#x}]", text)

    def test_the_gate_gives_every_register_back(self):
        listing = self._disassemble(battle._summon_gate_payload(), battle.SUMMON_GATE_CAVE)
        pushes = [line.split()[1] for line in listing if line.startswith("push ")]
        pops = [line.split()[1] for line in listing if line.startswith("pop ")]
        self.assertEqual(pushes, list(reversed(pops)))
        self.assertNotIn("eax", pushes, "EAX is the answer, not something to restore")
        self.assertEqual(listing[-1], "ret")

    def test_an_unrecognizable_actor_leaves_the_command_alone(self):
        # Both bounds checks jump to the same answer: available. A gate that
        # greyed a command because it could not identify the character would
        # be worse than no gate.
        listing = self._disassemble(battle._summon_gate_payload(), battle.SUMMON_GATE_CAVE)
        aboves = [line for line in listing if line.startswith("ja ")]
        self.assertEqual(len(aboves), 2)
        self.assertEqual(len(set(aboves)), 1, "both bounds checks answer the same way")
        self.assertIn("mov eax, 1", listing)

    def test_the_render_path_saves_what_the_displaced_code_needs(self):
        listing = self._disassemble(
            battle._draw_render_payload(draw_once=False, summon_gate=True),
            battle.DRAW_RENDER_CAVE)
        text = "\n".join(listing)
        # EAX carries the sprite state the displaced instruction reads at +0x34.
        self.assertLess(text.index("push eax"), text.index("call"))
        self.assertLess(text.index("pop eax"), text.index("movsx esi, word ptr [eax + 0x34]"))
        self.assertIn("or bl, 2", listing)

    def test_the_select_path_raises_the_flag_that_says_why(self):
        listing = self._disassemble(
            battle._draw_select_payload(draw_once=False, summon_gate=True),
            battle.DRAW_SELECT_CAVE)
        text = "\n".join(listing)
        self.assertIn(f"mov byte ptr [{battle.SUMMON_REFUSED_FLAG:#x}], 1", text)
        # And then hands the press to FF8's own refusal, which makes the noise.
        self.assertIn(f"jmp {battle.COMMAND_SELECT_DISABLED_BRANCH:#x}", text)

    def test_both_paths_branch_on_the_gf_command_and_nothing_else(self):
        select = self._disassemble(
            battle._draw_select_payload(draw_once=False, summon_gate=True),
            battle.DRAW_SELECT_CAVE)
        render = self._disassemble(
            battle._draw_render_payload(draw_once=False, summon_gate=True),
            battle.DRAW_RENDER_CAVE)
        self.assertIn(f"cmp byte ptr [ebx], {battle.GF_COMMAND_ID}", select)
        self.assertIn(f"cmp byte ptr [ecx], {battle.GF_COMMAND_ID}", render)

    def test_the_gate_is_absent_when_it_is_not_asked_for(self):
        self.assertEqual(battle.build_command_eligibility_patch(
            draw_once=False, summon_gate=False), "")
        patch = battle.build_command_eligibility_patch(draw_once=True, summon_gate=False)
        self.assertNotIn(f"{battle.SUMMON_GATE_CAVE:X}:", patch)

    def test_the_gate_fits_between_the_caves_around_it(self):
        gate = battle._summon_gate_payload()
        render = battle._draw_render_payload(summon_gate=True)
        self.assertLessEqual(battle.DRAW_RENDER_CAVE + len(render), battle.SUMMON_GATE_CAVE)
        self.assertLessEqual(battle.SUMMON_GATE_CAVE + len(gate), battle.SUMMON_REFUSED_FLAG)
        self.assertLessEqual(battle.SUMMON_REFUSED_FLAG + 4, 0x0279F600)


class CommandIdentity(unittest.TestCase):
    def _kernel(self):
        root = os.environ.get("LEXEDITOR_FF8_DATA_ROOT")
        if not root:
            self.skipTest("Final Fantasy VIII data has not been prepared here")
        path = Path(root) / "baseline" / "en" / "main" / "kernel.bin"
        if not path.is_file():
            self.skipTest("kernel.bin is not in the prepared data")
        return path.read_bytes()

    def test_gf_is_the_third_battle_command_in_the_kernel(self):
        import struct
        data = self._kernel()
        offsets = [struct.unpack_from("<I", data, 4 + 4 * i)[0]
                   for i in range(struct.unpack_from("<I", data, 0)[0])]
        commands = offsets[battle.KERNEL_COMMAND_SECTION]
        text = offsets[battle.KERNEL_COMMAND_TEXT_SECTION]
        pointer = struct.unpack_from(
            "<H", data, commands + battle.GF_COMMAND_ID * battle.KERNEL_COMMAND_STRIDE)[0]
        raw = data[text + pointer:data.index(b"\x00", text + pointer)]
        # 'A' sits at 0x45 in FF8's font table.
        name = "".join(chr(ord("A") + b - 0x45) for b in raw)
        self.assertEqual(name, "GF")
