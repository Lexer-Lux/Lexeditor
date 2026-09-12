from __future__ import annotations

import importlib
import unittest

from games.chrono_trigger.event_edit import VARIABLE_OR_UNRESOLVED
from games.chrono_trigger.target_only_ops import TARGET_ONLY_OPCODES


PRODUCTION_MODULES = (
    "games.chrono_trigger.comparisons",
    "games.chrono_trigger.memory_ops",
    "games.chrono_trigger.segment_memory_ops",
    "games.chrono_trigger.bit_ops",
    "games.chrono_trigger.movement_ops",
    "games.chrono_trigger.call_ops",
    "games.chrono_trigger.object_ops",
    "games.chrono_trigger.facing_target_ops",
    "games.chrono_trigger.property_ops",
    "games.chrono_trigger.scene_event_ops",
    "games.chrono_trigger.audio_ops",
    "games.chrono_trigger.misc_ops",
    "games.chrono_trigger.pc_extended_ops",
    "games.chrono_trigger.jump_ops",
)


def public_opcode_sets(module_name: str) -> dict[str, frozenset[int]]:
    module = importlib.import_module(module_name)
    result = {}
    for name, value in vars(module).items():
        if name.startswith("_") or not name.endswith("_OPCODES"):
            continue
        if isinstance(value, frozenset) and all(isinstance(item, int) for item in value):
            result[f"{module_name}:{name}"] = value
    return result


class EditorOpcodeOwnershipTests(unittest.TestCase):
    def test_production_custom_editor_opcode_sets_do_not_overlap(self):
        owner: dict[int, str] = {}
        for module_name in PRODUCTION_MODULES:
            for set_name, opcodes in public_opcode_sets(module_name).items():
                for opcode in opcodes:
                    with self.subTest(opcode=f"0x{opcode:02X}", owner=set_name):
                        self.assertNotIn(
                            opcode,
                            owner,
                            f"0x{opcode:02X} is claimed by both {owner.get(opcode)} and {set_name}",
                        )
                        owner[opcode] = set_name

    def test_dynamic_or_unresolved_boundaries_are_never_owned_by_custom_fixed_editor(self):
        owned = set()
        for module_name in PRODUCTION_MODULES:
            for opcodes in public_opcode_sets(module_name).values():
                owned.update(opcodes)
        self.assertFalse(
            owned & VARIABLE_OR_UNRESOLVED,
            f"dynamic/unresolved opcodes leaked into custom editors: {sorted(owned & VARIABLE_OR_UNRESOLVED)}",
        )

    def test_target_only_research_opcodes_remain_quarantined_from_production_sets(self):
        owned = set()
        for module_name in PRODUCTION_MODULES:
            for opcodes in public_opcode_sets(module_name).values():
                owned.update(opcodes)
        self.assertFalse(
            owned & TARGET_ONLY_OPCODES,
            f"target-only research was promoted without deliberate registry work: {sorted(owned & TARGET_ONLY_OPCODES)}",
        )


if __name__ == "__main__":
    unittest.main()
