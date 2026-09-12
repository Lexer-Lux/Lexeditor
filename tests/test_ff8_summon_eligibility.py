"""Summon states its own eligibility before any menu hook exists.

Monogamy gives each character one GF. A character with none has nothing to
summon, and choosing the slot does nothing, which reads as a bug rather than a
rule. The rule and the sentence it shows are settled here the way Draw's were,
so the menu hook has something verified to implement.
"""
import os
from pathlib import Path
import unittest

from games.ff8 import battle_issue_54 as battle


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

    def test_the_missing_addresses_are_declared_rather_than_guessed(self):
        # The grouped feature stays fail-closed until the GF slot's render and
        # select addresses are verified against the running game.
        self.assertTrue(any("Greying Summon" in blocker for blocker in battle.BLOCKERS))


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
