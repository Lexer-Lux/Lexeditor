"""Read and write the item enums in RDR1's corpse loot script.

There is no drops table in Red Dead Redemption's data files. Every XML in
content.rpf was searched and none of them holds one: what a body yields is a
switch on a LootType decorator compiled into Function_90 of
content/release64/scripting/gringo/commonscripts/lootcorpsegenericnoanim.wsc,
and each branch calls the item-name lookup with a constant.

That constant is editable without a script compiler. The decompiler reports
every function's bytecode offset, so the lookup's address is known; a call
carries that address as its operand, so the calls can be found by searching for
the address rather than by knowing the whole instruction set, and the push
immediately before each call is the item the branch hands over.

Three opcodes are all this needs, and each was confirmed against the
decompiled source rather than assumed:

    0x52 <big-endian 16-bit address>   call
    0x8B + n                           push n, for n from 0 to 15
    0x25 <byte>                        push a byte

Decoding the script's twenty-seven call sites this way reproduces the
decompiler's argument list exactly, which is what `verify()` re-checks.

The game already loads loose overrides by archive path for files that are not
XML, so a patched copy written under the project's mod folder is picked up
without rebuilding the archive.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct

# Where the script lives inside content.rpf, and therefore where an override
# goes inside the mod folder.
ARCHIVE_PATH = (
    "content/release64/scripting/gringo/commonscripts/lootcorpsegenericnoanim.wsc"
)

CALL = 0x52
PUSH_BYTE = 0x25
PUSH_SMALL = 0x8B          # 0x8B + n pushes n
PUSH_SMALL_MAX = 15
MAX_ITEM = 0xFF


@dataclass(frozen=True)
class Slot:
    """One `push item; call the item lookup` pair in the script."""

    offset: int      # where the push begins
    width: int       # 1 for a small push, 2 for a byte push
    item: int        # the item enum this branch hands over


def _lookup_offset(decompiled: str) -> int:
    """The bytecode address of the item-name lookup, from the decompiler."""
    for match in re.finditer(
        r"(\w+)\s+(Function_\d+)\([^)]*\)\s*//Position: (0x[0-9A-Fa-f]+)", decompiled
    ):
        if match.group(2) == "Function_122":
            return int(match.group(3), 16)
    raise ValueError("The decompiled script does not name the item-name lookup")


def read_slots(script: bytes, decompiled: str) -> list[Slot]:
    """Every item enum the script hands to the lookup, in bytecode order."""
    address = struct.pack(">H", _lookup_offset(decompiled))
    slots: list[Slot] = []
    for match in re.finditer(re.escape(address), script):
        call = match.start()
        if call < 3 or script[call - 1] != CALL:
            continue
        opcode = script[call - 2]
        if PUSH_SMALL <= opcode <= PUSH_SMALL + PUSH_SMALL_MAX:
            slots.append(Slot(call - 2, 1, opcode - PUSH_SMALL))
        elif script[call - 3] == PUSH_BYTE:
            slots.append(Slot(call - 3, 2, opcode))
    return slots


def decompiled_items(decompiled: str) -> list[int]:
    """What the decompiler says those arguments are. The oracle for read_slots."""
    return [int(match.group(1))
            for match in re.finditer(r"Function_122\((\d+)\)", decompiled)]


def verify(script: bytes, decompiled: str) -> list[Slot]:
    """Read the slots and refuse to hand them back unless they agree.

    A mismatch means the opcodes above no longer describe this script - a
    different game build, or a file that is still resource-packed. Editing on a
    guess would write a byte into the middle of an unrelated instruction.
    """
    slots = read_slots(script, decompiled)
    expected = decompiled_items(decompiled)
    found = [slot.item for slot in slots]
    if found != expected:
        raise ValueError(
            "The loot script does not decode as expected: "
            f"{len(found)} call sites reading {found[:8]}, "
            f"but the decompiler reports {len(expected)} reading {expected[:8]}"
        )
    return slots


def write_slots(script: bytes, changes: dict[int, int], decompiled: str) -> bytes:
    """Return the script with the named slots handing over different items.

    `changes` maps a slot's index in `verify()` order to its new item enum. The
    edit is in place and never changes the script's length: a push that has to
    grow from a small push to a byte push would move every address after it,
    and the calls that carry those addresses are not being rewritten, so a
    value a small push cannot hold is refused instead.
    """
    slots = verify(script, decompiled)
    patched = bytearray(script)
    for index, item in changes.items():
        if not 0 <= int(index) < len(slots):
            raise IndexError(f"No loot slot {index}; the script has {len(slots)}")
        value = int(item)
        if not 0 <= value <= MAX_ITEM:
            raise ValueError(f"Item enum {value} is outside 0 to {MAX_ITEM}")
        slot = slots[index]
        if slot.width == 1:
            if value > PUSH_SMALL_MAX:
                raise ValueError(
                    f"Slot {index} is a small push and cannot hold {value}; "
                    f"small pushes carry 0 to {PUSH_SMALL_MAX}"
                )
            patched[slot.offset] = PUSH_SMALL + value
        else:
            patched[slot.offset] = PUSH_BYTE
            patched[slot.offset + 1] = value
    if len(patched) != len(script):
        raise AssertionError("A loot edit changed the script's length")
    return bytes(patched)


def override_path(mod_root: Path) -> Path:
    """Where a patched script goes so the game loads it instead."""
    return Path(mod_root) / "mod" / Path(ARCHIVE_PATH)
