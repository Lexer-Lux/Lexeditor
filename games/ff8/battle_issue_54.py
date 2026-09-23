"""FF8 battle mechanics for Lexeditor issue #54.

The Draw fragment is complete for the supported English 2013 Steam build. It
keeps FFNx's existing Draw wrapper, filters battle-enemy actor bits 3 through
6, and stores only a battle-local mask in the assigned Hext cave. Switch,
Shoot, and the supported fixed commands are separate verified components. GF
Magic pages remain blocked on a missing GF-to-spell definition.
"""

from __future__ import annotations


DEFAULT_SHOTS_PER_ATB = 1
MIN_SHOTS_PER_ATB = 1
MAX_SHOTS_PER_ATB = 10

DRAW_STRENGTH = "vanilla"
DRAW_SCOPE = "enemy instance in the current battle"
DEFAULT_DRAW_ONCE_PER_ENEMY = False
# On by default: a Summon slot that does nothing and never says why is the bug
# this fixes, not a taste a player opts into.
DEFAULT_SUMMON_GATE = True

DRAW_COMMAND_ID = 6
CARD_COMMAND_ID = 25
QUISTIS_CHARACTER_ID = 3
FIRST_ENEMY_ACTOR = 3
LAST_ENEMY_ACTOR = 6
ENEMY_ACTOR_MASK = 0x0078

BATTLE_ENTER_HOOK = 0x0047CE10
BATTLE_ENTER_ORIGINAL = bytes.fromhex("56 57 33 F6 B9 D1 04 00 00")
BATTLE_EXIT_HOOK = 0x0047D194
BATTLE_EXIT_ORIGINAL = bytes.fromhex("8D 44 24 08 56")
DRAW_RESULT_HOOK = 0x0048D559
DRAW_CAPTURE_HOOK = 0x0048D54D
DRAW_CAPTURE_ORIGINAL = bytes.fromhex("56 52 8B 54 24 30")
DRAW_RESULT_ORIGINAL = bytes.fromhex("83 C4 0C 88 44 24 3C")
DRAW_SELECT_HOOK = 0x004BC7B5
DRAW_SELECT_ORIGINAL = bytes.fromhex("8A 4B 03 83 C4 10 F6 C1 02")
DRAW_TARGET_MASK_HOOK = 0x004BC81A
DRAW_TARGET_MASK_ORIGINAL = bytes.fromhex("66 8B F8 83 C4 04")
DRAW_RENDER_HOOK = 0x004BCB3B
DRAW_RENDER_ORIGINAL = bytes.fromhex("8A 59 03 56 0F BF 70 34")

DRAW_SELECT_ENABLED = 0x004BC7C4
DRAW_SELECT_DISABLED = 0x004BCA45
DRAW_TARGET_MASK_RETURN = 0x004BC820
DRAW_RENDER_RETURN = 0x004BCB43

ACTIVE_BATTLE_ACTOR = 0x01D76844
BATTLE_ACTOR_BASE = 0x01CFF000
BATTLE_ACTOR_STRIDE = 0x1D0
BATTLE_ACTOR_CHARACTER_ID = 0x1C3
TARGETABLE_ENEMY_MASK = 0x01D750BE

DRAW_ENTER_CAVE = 0x0279F040
DRAW_EXIT_CAVE = 0x0279F060
DRAW_RESULT_CAVE = 0x0279F080
DRAW_CAPTURE_CAVE = 0x0279F0C0
DRAW_CAPTURED_TARGET = 0x0279F2F4
DRAW_TARGET_MASK_CAVE = 0x0279F0E0
DRAW_SELECT_CAVE = 0x0279F140
DRAW_RENDER_CAVE = 0x0279F300
DRAW_STATE = 0x0279F2F0
CARD_FILTER_CAVE = 0x027A1380
# Free space between the render cave and the fixed-command menu's block.
SUMMON_GATE_CAVE = 0x0279F400
# One byte the gate raises when it refuses Summon, and the native driver lowers
# after it has said why. A refusal that only plays the denied sound is what
# made the greyed slot look broken in the first place.
SUMMON_REFUSED_FLAG = 0x0279F4F0

# Where a character's junctioned GFs live. Verified by the Single GF patch,
# which normalizes this same mask on field and world-map entry.
from .single_gf import (  # noqa: E402  (kept beside the addresses it explains)
    GF_MASK_OFFSET, SAVEMAP_CHARACTER_BASE, SAVEMAP_CHARACTER_STRIDE,
)
CHARACTER_COUNT = 8
LAST_PARTY_ACTOR = 2

BLOCKERS = (
    "GF Magic still needs the verified Magic-list builder and a defined GF-to-spell map.",
)


class _MachineCode:
    """Small label-aware encoder for the guarded near branches used here."""

    def __init__(self, address: int):
        self.address = int(address)
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    def add(self, data: bytes) -> None:
        self.data.extend(data)

    def label(self, name: str) -> None:
        self.labels[name] = len(self.data)

    def jump(self, opcode: bytes, label: str) -> None:
        self.data.extend(opcode)
        self.fixups.append((len(self.data), label))
        self.data.extend(b"\x00\x00\x00\x00")

    def finish(self) -> bytes:
        for position, label in self.fixups:
            target = self.address + self.labels[label]
            source_after = self.address + position + 4
            self.data[position:position + 4] = int(target - source_after).to_bytes(
                4, "little", signed=True,
            )
        return bytes(self.data)


def _near_jump(source: int, target: int) -> bytes:
    return b"\xE9" + int(target - (source + 5)).to_bytes(4, "little", signed=True)


def _near_call(source: int, target: int) -> bytes:
    return b"\xE8" + int(target - (source + 5)).to_bytes(4, "little", signed=True)


def _absolute_jump(code: _MachineCode, target: int) -> None:
    source = code.address + len(code.data)
    code.add(_near_jump(source, target))


def _active_quistis_guard(code: _MachineCode, fail: str) -> None:
    code.add(b"\x0F\xB6\x15" + ACTIVE_BATTLE_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("80 FA 0A"))
    code.jump(bytes.fromhex("0F 87"), fail)
    code.add(bytes.fromhex("69 D2 D0 01 00 00"))
    character = BATTLE_ACTOR_BASE + BATTLE_ACTOR_CHARACTER_ID
    code.add(b"\x80\xBA" + character.to_bytes(4, "little") + bytes((QUISTIS_CHARACTER_ID,)))
    code.jump(bytes.fromhex("0F 85"), fail)


def _battle_enter_payload() -> bytes:
    code = _MachineCode(DRAW_ENTER_CAVE)
    code.add(b"\xC7\x05" + DRAW_STATE.to_bytes(4, "little") + b"\x00\x00\x00\x00")
    code.add(BATTLE_ENTER_ORIGINAL)
    _absolute_jump(code, BATTLE_ENTER_HOOK + len(BATTLE_ENTER_ORIGINAL))
    return code.finish()


def _battle_exit_payload() -> bytes:
    code = _MachineCode(DRAW_EXIT_CAVE)
    code.add(b"\xC7\x05" + DRAW_STATE.to_bytes(4, "little") + b"\x00\x00\x00\x00")
    code.add(BATTLE_EXIT_ORIGINAL)
    _absolute_jump(code, BATTLE_EXIT_HOOK + len(BATTLE_EXIT_ORIGINAL))
    return code.finish()


def _draw_result_payload() -> bytes:
    code = _MachineCode(DRAW_RESULT_CAVE)
    code.add(bytes.fromhex("84 C0"))        # zero means no Draw occurred
    code.jump(bytes.fromhex("0F 84"), "replay")
    # Native Draw amount overwrites its second argument with enemy level.
    # Read the actor captured before that call, not its mutated stack slot.
    code.add(b"\x8B\x0D" + DRAW_CAPTURED_TARGET.to_bytes(4, "little"))
    code.add(bytes.fromhex("83 F9 03"))
    code.jump(bytes.fromhex("0F 82"), "replay")
    code.add(bytes.fromhex("83 F9 06"))
    code.jump(bytes.fromhex("0F 87"), "replay")
    code.add(b"\x0F\xAB\x0D" + DRAW_STATE.to_bytes(4, "little"))
    code.label("replay")
    code.add(DRAW_RESULT_ORIGINAL)
    _absolute_jump(code, DRAW_RESULT_HOOK + len(DRAW_RESULT_ORIGINAL))
    return code.finish()


def _draw_capture_payload() -> bytes:
    code = _MachineCode(DRAW_CAPTURE_CAVE)
    code.add(b"\x89\x15" + DRAW_CAPTURED_TARGET.to_bytes(4, "little"))
    code.add(DRAW_CAPTURE_ORIGINAL)
    _absolute_jump(code, DRAW_CAPTURE_HOOK + len(DRAW_CAPTURE_ORIGINAL))
    return code.finish()


def _summon_gate_payload() -> bytes:
    """Answer, in AL, whether the acting character has a GF to summon.

    Reads the acting battle actor, its character id, and that character's
    junctioned-GF mask in the savemap. Everything but EAX is preserved, because
    both callers still need the registers the menu code left them.

    Anything unexpected - an actor that is not one of the three party slots, a
    character id outside the eight - answers "available". A gate that greys a
    command because it could not identify the character would be worse than no
    gate at all.
    """
    code = _MachineCode(SUMMON_GATE_CAVE)
    code.add(bytes.fromhex("53 51 52"))                     # push ebx, ecx, edx
    code.add(b"\x0F\xB6\x05" + ACTIVE_BATTLE_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("3C") + bytes((LAST_PARTY_ACTOR,)))
    code.jump(bytes.fromhex("0F 87"), "available")          # ja available
    code.add(bytes.fromhex("69 C0") + BATTLE_ACTOR_STRIDE.to_bytes(4, "little"))
    character = BATTLE_ACTOR_BASE + BATTLE_ACTOR_CHARACTER_ID
    code.add(b"\x0F\xB6\x80" + character.to_bytes(4, "little"))
    code.add(bytes.fromhex("3C") + bytes((CHARACTER_COUNT - 1,)))
    code.jump(bytes.fromhex("0F 87"), "available")
    code.add(bytes.fromhex("69 C0") + SAVEMAP_CHARACTER_STRIDE.to_bytes(4, "little"))
    mask = SAVEMAP_CHARACTER_BASE + GF_MASK_OFFSET
    code.add(b"\x0F\xB7\x80" + mask.to_bytes(4, "little"))
    code.add(bytes.fromhex("85 C0"))                        # test eax, eax
    code.add(bytes.fromhex("0F 95 C0"))                     # setne al
    code.add(bytes.fromhex("0F B6 C0"))                     # movzx eax, al
    code.jump(bytes.fromhex("E9"), "done")
    code.label("available")
    code.add(bytes.fromhex("B8 01 00 00 00"))               # mov eax, 1
    code.label("done")
    code.add(bytes.fromhex("5A 59 5B C3"))                  # pop edx, ecx, ebx; ret
    return code.finish()


def _card_filter_payload() -> bytes:
    """Filter EAX's actor mask to enemies that have a Card result."""
    code = _MachineCode(CARD_FILTER_CAVE)
    code.add(bytes.fromhex("53 51 52 56 57"))  # preserve EBX, ECX, EDX, ESI, EDI
    code.add(bytes.fromhex("89 C7 BE 03 00 00 00"))  # EDI=mask, ESI=actor 3
    code.label("loop")
    code.add(bytes.fromhex("0F A3 F7"))  # bt edi, esi
    code.jump(bytes.fromhex("0F 83"), "next")
    code.add(bytes.fromhex("69 CE D0 00 00 00"))  # ecx = actor * 0xD0
    code.add(bytes.fromhex("8B 91 10 7B D2 01 85 D2"))
    code.jump(bytes.fromhex("0F 84"), "remove")
    code.add(bytes.fromhex("8B 12 85 D2"))
    code.jump(bytes.fromhex("0F 84"), "remove")
    code.add(bytes.fromhex("80 BA F9 00 00 00 FF"))
    code.jump(bytes.fromhex("0F 85"), "next")
    code.add(bytes.fromhex("80 BA FA 00 00 00 FF"))
    code.jump(bytes.fromhex("0F 85"), "next")
    code.label("remove")
    code.add(bytes.fromhex("0F B3 F7"))  # btr edi, esi
    code.label("next")
    code.add(bytes.fromhex("46 83 FE 07"))
    code.jump(bytes.fromhex("0F 8C"), "loop")
    code.add(bytes.fromhex("89 F8 5F 5E 5A 59 5B C3"))
    return code.finish()


def _draw_target_mask_payload(*, draw_once: bool = True,
                              better_card: bool = False,
                              streamlined_draw: bool = False) -> bytes:
    code = _MachineCode(DRAW_TARGET_MASK_CAVE)
    code.add(bytes.fromhex("66 8B F8 83 C4 04 50"))
    # After the displaced stack cleanup and our saved EAX, the descriptor
    # argument from 4BC770 is at ESP+0x20.
    if draw_once or streamlined_draw:
        code.add(bytes.fromhex("8B 4C 24 20 80 39 06"))
        code.jump(bytes.fromhex("0F 85"), "replay")
    if streamlined_draw:
        code.add(bytes.fromhex("89 F8"))
        source = code.address + len(code.data)
        from . import streamlined_draw as streamlined
        code.add(_near_call(source, streamlined.STOCK_FILTER_CAVE))
        code.add(bytes.fromhex("89 C7"))
    if draw_once:
        code.add(b"\x8B\x0D" + DRAW_STATE.to_bytes(4, "little"))
        code.add(bytes.fromhex("F7 D1 23 F9"))
    code.label("replay")
    if better_card:
        code.add(bytes.fromhex("8B 4C 24 20 80 39 19"))
        code.jump(bytes.fromhex("0F 85"), "restore")
        code.add(bytes.fromhex("89 F8"))
        source = code.address + len(code.data)
        code.add(_near_call(source, CARD_FILTER_CAVE))
        code.add(bytes.fromhex("89 C7"))
    code.label("restore")
    code.add(bytes.fromhex("58"))
    _absolute_jump(code, DRAW_TARGET_MASK_RETURN)
    return code.finish()


def _draw_select_payload(*, draw_once: bool = True,
                         better_card: bool = False,
                         streamlined_draw: bool = False,
                         summon_gate: bool = False) -> bytes:
    code = _MachineCode(DRAW_SELECT_CAVE)
    code.add(DRAW_SELECT_ORIGINAL)
    code.jump(bytes.fromhex("0F 85"), "disabled")
    if summon_gate:
        # EAX is dead here: the enabled branch reloads it from the entry. CL
        # is not, so the gate leaves it alone.
        code.add(bytes.fromhex("80 3B") + bytes((GF_COMMAND_ID,)))
        code.jump(bytes.fromhex("0F 85"), "not_summon")
        source = code.address + len(code.data)
        code.add(_near_call(source, SUMMON_GATE_CAVE))
        code.add(bytes.fromhex("84 C0"))
        code.jump(bytes.fromhex("0F 85"), "enabled")
        # Refused. Raise the flag so the reason can be said, then let FF8's own
        # disabled branch play the denied sound and swallow the press.
        code.add(b"\xC6\x05" + SUMMON_REFUSED_FLAG.to_bytes(4, "little") + b"\x01")
        code.jump(bytes.fromhex("E9"), "disabled")
        code.label("not_summon")
    if draw_once or streamlined_draw:
        code.add(bytes.fromhex("8B 44 24 14 80 38 06"))
        code.jump(bytes.fromhex("0F 85"), "card")
        code.add(b"\x0F\xB7\x05" + TARGETABLE_ENEMY_MASK.to_bytes(4, "little"))
        code.add(bytes.fromhex("83 E0 78"))
        if streamlined_draw:
            source = code.address + len(code.data)
            from . import streamlined_draw as streamlined
            code.add(_near_call(source, streamlined.STOCK_FILTER_CAVE))
    if draw_once:
        code.add(b"\x8B\x15" + DRAW_STATE.to_bytes(4, "little"))
        code.add(bytes.fromhex("F7 D2 23 C2 85 C0"))
    if draw_once or streamlined_draw:
        if not draw_once:
            code.add(bytes.fromhex("85 C0"))
        code.jump(bytes.fromhex("0F 84"), "disabled")
        code.jump(bytes.fromhex("E9"), "enabled")
    code.label("card")
    if better_card:
        code.add(bytes.fromhex("8B 44 24 14 80 38 19"))
        code.jump(bytes.fromhex("0F 85"), "enabled")
        code.add(b"\x0F\xB7\x05" + TARGETABLE_ENEMY_MASK.to_bytes(4, "little"))
        code.add(bytes.fromhex("83 E0 78"))
        source = code.address + len(code.data)
        code.add(_near_call(source, CARD_FILTER_CAVE))
        code.add(bytes.fromhex("85 C0"))
        code.jump(bytes.fromhex("0F 84"), "disabled")
    code.label("enabled")
    _absolute_jump(code, DRAW_SELECT_ENABLED)
    code.label("disabled")
    _absolute_jump(code, DRAW_SELECT_DISABLED)
    return code.finish()


def _draw_render_payload(*, draw_once: bool = True,
                         better_card: bool = False,
                         streamlined_draw: bool = False,
                         summon_gate: bool = False) -> bytes:
    code = _MachineCode(DRAW_RENDER_CAVE)
    code.add(bytes.fromhex("8A 59 03"))
    if summon_gate:
        # EAX holds the sprite state the displaced code reads at +0x34, so it
        # is saved across the gate. Setting bit 1 is all the greying takes:
        # FF8 draws any command with that bit in colour index zero.
        code.add(bytes.fromhex("80 39") + bytes((GF_COMMAND_ID,)))
        code.jump(bytes.fromhex("0F 85"), "not_summon_render")
        code.add(bytes.fromhex("50"))
        source = code.address + len(code.data)
        code.add(_near_call(source, SUMMON_GATE_CAVE))
        code.add(bytes.fromhex("84 C0"))
        code.jump(bytes.fromhex("0F 85"), "summon_restore")
        code.add(bytes.fromhex("80 CB 02"))
        code.label("summon_restore")
        code.add(bytes.fromhex("58"))
        code.label("not_summon_render")
    if draw_once or streamlined_draw:
        code.add(bytes.fromhex("80 39 06"))
        code.jump(bytes.fromhex("0F 85"), "card")
        code.add(bytes.fromhex("50"))
        code.add(b"\x0F\xB7\x05" + TARGETABLE_ENEMY_MASK.to_bytes(4, "little"))
        code.add(bytes.fromhex("83 E0 78"))
        if streamlined_draw:
            source = code.address + len(code.data)
            from . import streamlined_draw as streamlined
            code.add(_near_call(source, streamlined.STOCK_FILTER_CAVE))
    if draw_once:
        code.add(b"\x8B\x2D" + DRAW_STATE.to_bytes(4, "little"))
        code.add(bytes.fromhex("F7 D5 23 C5"))
    if draw_once or streamlined_draw:
        code.add(bytes.fromhex("85 C0"))
        code.jump(bytes.fromhex("0F 85"), "draw_restore")
        code.add(bytes.fromhex("80 CB 02"))
        code.label("draw_restore")
        code.add(bytes.fromhex("58"))
        code.jump(bytes.fromhex("E9"), "replay")
    code.label("card")
    if better_card:
        code.add(bytes.fromhex("80 39 19"))
        code.jump(bytes.fromhex("0F 85"), "replay")
        code.add(bytes.fromhex("50"))  # preserve UI pointer used by displaced code
        code.add(b"\x0F\xB7\x05" + TARGETABLE_ENEMY_MASK.to_bytes(4, "little"))
        code.add(bytes.fromhex("83 E0 78"))
        source = code.address + len(code.data)
        code.add(_near_call(source, CARD_FILTER_CAVE))
        code.add(bytes.fromhex("85 C0"))
        code.jump(bytes.fromhex("0F 85"), "card_restore")
        code.add(bytes.fromhex("80 CB 02"))
        code.label("card_restore")
        code.add(bytes.fromhex("58"))
    code.label("replay")
    code.add(bytes.fromhex("56 0F BF 70 34"))
    _absolute_jump(code, DRAW_RENDER_RETURN)
    return code.finish()


def shots_per_atb(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Shots per ATB must be a whole number from 1 to 10")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Shots per ATB must be a whole number from 1 to 10") from error
    if str(value).strip() not in {str(result), f"{result}.0"}:
        raise ValueError("Shots per ATB must be a whole number from 1 to 10")
    if not MIN_SHOTS_PER_ATB <= result <= MAX_SHOTS_PER_ATB:
        raise ValueError("Shots per ATB must be from 1 to 10")
    return result


def draw_target_eligible(*, drawn_enemy_slots: set[int], enemy_slot: int) -> bool:
    """State the required battle-local Draw eligibility rule."""
    if not 0 <= int(enemy_slot) < 4:
        raise ValueError("Enemy slot must be from 0 to 3")
    return int(enemy_slot) not in drawn_enemy_slots


def draw_command_available(*, drawn_enemy_slots: set[int],
                           targetable_enemy_slots: set[int]) -> bool:
    """Draw is grey only when no current target remains eligible."""
    return any(slot not in drawn_enemy_slots for slot in targetable_enemy_slots)


# The Summon slot in the fixed command menu. Monogamy gives each character one
# GF, so a character with none has nothing to summon and the slot does nothing
# when it is chosen. It reads as a bug rather than as a rule, which is why the
# slot states its own eligibility here the same way Draw does above: the rule
# and its wording are settled and testable before any menu hook exists.
SUMMON_UNAVAILABLE_REASON = (
    "No GF is junctioned to this character. Junction one on the Junction "
    "screen to use Summon."
)


# How FF8 already greys a battle command, found by disassembling FF8_EN.exe
# rather than by adding hooks of our own. Each command entry carries a flags
# byte at +3, and bit 1 means "disabled":
#
#   select  004BC7B5  8A 4B 03        mov cl, [ebx+3]
#           004BC7BB  F6 C1 02        test cl, 2
#           004BC7BE  0F 85 ...       jne 004BCA45
#           004BCA45  6A 05 E8 ...    push 5; call 004A9780   (denied sound)
#                                     then xor eax,eax; ret   (selection refused)
#
#   render  004BCB66  F6 C3 02        test bl, 2
#           004BCB69  74 02           je  004BCB6D
#           004BCB6B  33 C9           xor ecx, ecx            (colour index 0)
#                                     ecx is the last argument to the text
#                                     renderer at 004A7250
#
# So greying Summon needs no render or select hook at all: both behaviours the
# request asks for - drawn greyed, and refusing the press with a noise - are
# what the game does for any command whose flag is set. What is left is setting
# that bit on the GF entry when the acting character has no junctioned GF, and
# putting our own sentence on the refusal instead of only the sound.
COMMAND_FLAGS_OFFSET = 3
COMMAND_FLAG_DISABLED = 0x02

COMMAND_DISABLED_SITES = {
    # address: the bytes that must still be there for the reading above to hold
    0x004BC7B5: bytes.fromhex("8A 4B 03"),
    0x004BC7BB: bytes.fromhex("F6 C1 02"),
    0x004BCA45: bytes.fromhex("6A 05"),
    0x004BCB66: bytes.fromhex("F6 C3 02 74 02 33 C9"),
}
COMMAND_DENIED_SOUND = 5
COMMAND_TEXT_RENDERER = 0x004A7250
COMMAND_SELECT_DISABLED_BRANCH = 0x004BCA45

# The entry itself. The renderer's caller loads the current command from a
# pointer in memory, reads its id from the first byte, and asks the name
# lookup for a string:
#
#   004BCEE9  8B 1D 38 68 D7 01   mov ebx, [1D76838]      the entry
#   004BCEFC  8A 03               mov al, [ebx]           its id
#   004BCEFE  50 E8 ...           push eax; call 0047EBD0 its name
#
# and the select path refuses id zero as well as the disabled flag:
#
#   004BC7C4  8A 03 84 C0         mov al, [ebx]; test al, al
#
# So an entry is: id at +0, flags at +3, and bit 1 of those flags is what
# greys it and refuses the press.
COMMAND_ENTRY_POINTER = 0x01D76838
COMMAND_ID_OFFSET = 0
COMMAND_NAME_LOOKUP = 0x0047EBD0
COMMAND_ENTRY_SITES = {
    0x004BCEE9: bytes.fromhex("8B 1D 38 68 D7 01"),
    0x004BCEFC: bytes.fromhex("8A 03"),
    0x004BC7C4: bytes.fromhex("8A 03 84 C0"),
}

# Which command is Summon. The name lookup indexes an eight-byte table and
# reads a word at +0 for the name string; that table is kernel.bin's battle
# command section loaded into memory, so a command's runtime id is its index
# there and the names can be read without the game running. Reading the
# installed kernel gives: 1 Attack, 2 Magic, 3 GF, 4 Item, 5 Renzokuken,
# 6 Draw, 7 Devour. Summon is the GF command.
GF_COMMAND_ID = 3
KERNEL_COMMAND_SECTION = 0        # section 1, the first offset in kernel.bin
KERNEL_COMMAND_TEXT_SECTION = 31  # its linked text, section 32
KERNEL_COMMAND_STRIDE = 8


def command_flags(*, command_id: int, flags: int, junctioned_gf_count: int) -> int:
    """The flags this command entry should carry, given the character.

    Summon is the only one this touches, and only its disabled bit: everything
    else in the byte belongs to the game. A character with a GF gets the bit
    cleared rather than left alone, so junctioning one during a battle takes
    the greying off again.
    """
    flags = int(flags) & 0xFF
    if int(command_id) != GF_COMMAND_ID:
        return flags
    if summon_command_available(junctioned_gf_count=junctioned_gf_count):
        return flags & ~COMMAND_FLAG_DISABLED
    return flags | COMMAND_FLAG_DISABLED


# Not the command list: the jump table at 004BC704 is the battle menu's own
# state machine, dispatched on [1D7685B] and bounded to 0x18. Recorded so the
# next person does not spend the afternoon reading it the way this one did.
BATTLE_MENU_STATE_TABLE = 0x004BC704
BATTLE_MENU_STATE_BYTE = 0x01D7685B


def summon_command_available(*, junctioned_gf_count: int) -> bool:
    """Summon is grey when the acting character has no GF junctioned."""
    count = int(junctioned_gf_count)
    if count < 0:
        raise ValueError("Junctioned GF count cannot be negative")
    return count > 0


def summon_unavailable_reason(*, junctioned_gf_count: int) -> str:
    """What choosing a grey Summon says. Empty while Summon is usable.

    A greyed command that says nothing is indistinguishable from a broken one,
    so the slot answers the question it raises rather than only refusing.
    """
    if summon_command_available(junctioned_gf_count=junctioned_gf_count):
        return ""
    return SUMMON_UNAVAILABLE_REASON


def build_command_eligibility_patch(*, draw_once: bool = DEFAULT_DRAW_ONCE_PER_ENEMY,
                                    better_card: bool = False,
                                    streamlined_draw: bool = False,
                                    summon_gate: bool = DEFAULT_SUMMON_GATE) -> str:
    """Compose Draw, Card and Summon eligibility through their shared hooks.

    All four ride the same two menu sites, so they are one patch: the select
    site that accepts or refuses a press, and the render site that decides a
    command's colour.
    """
    if not all(isinstance(value, bool) for value in (
        draw_once, better_card, streamlined_draw, summon_gate,
    )):
        raise ValueError("Command eligibility settings must be true or false")
    if not draw_once and not better_card and not streamlined_draw and not summon_gate:
        return ""

    caves = []
    hooks = []
    if draw_once:
        caves.extend((
            (DRAW_ENTER_CAVE, _battle_enter_payload()),
            (DRAW_EXIT_CAVE, _battle_exit_payload()),
            (DRAW_RESULT_CAVE, _draw_result_payload()),
            (DRAW_CAPTURE_CAVE, _draw_capture_payload()),
        ))
        hooks.extend((
            (BATTLE_ENTER_HOOK, len(BATTLE_ENTER_ORIGINAL), DRAW_ENTER_CAVE),
            (BATTLE_EXIT_HOOK, len(BATTLE_EXIT_ORIGINAL), DRAW_EXIT_CAVE),
            (DRAW_RESULT_HOOK, len(DRAW_RESULT_ORIGINAL), DRAW_RESULT_CAVE),
            (DRAW_CAPTURE_HOOK, len(DRAW_CAPTURE_ORIGINAL), DRAW_CAPTURE_CAVE),
        ))
    # The target-mask hook belongs to the three that filter targets. Summon
    # touches neither targets nor that site, so it does not drag the hook in.
    if draw_once or better_card or streamlined_draw:
        caves.append((DRAW_TARGET_MASK_CAVE, _draw_target_mask_payload(
            draw_once=draw_once, better_card=better_card,
            streamlined_draw=streamlined_draw,
        )))
        hooks.append((DRAW_TARGET_MASK_HOOK, len(DRAW_TARGET_MASK_ORIGINAL),
                      DRAW_TARGET_MASK_CAVE))
    caves.extend((
        (DRAW_SELECT_CAVE, _draw_select_payload(
            draw_once=draw_once, better_card=better_card,
            streamlined_draw=streamlined_draw, summon_gate=summon_gate,
        )),
        (DRAW_RENDER_CAVE, _draw_render_payload(
            draw_once=draw_once, better_card=better_card,
            streamlined_draw=streamlined_draw, summon_gate=summon_gate,
        )),
    ))
    if better_card:
        caves.append((CARD_FILTER_CAVE, _card_filter_payload()))
    if summon_gate:
        caves.append((SUMMON_GATE_CAVE, _summon_gate_payload()))
    hooks.extend((
        (DRAW_SELECT_HOOK, len(DRAW_SELECT_ORIGINAL), DRAW_SELECT_CAVE),
        (DRAW_RENDER_HOOK, len(DRAW_RENDER_ORIGINAL), DRAW_RENDER_CAVE),
    ))
    lines = [
        "# Shared Draw/Card command eligibility patch.",
    ]
    if draw_once:
        lines.extend((
            "# Draw: one successful Draw per enemy actor per battle for the whole party.",
            "# Draw strength and FFNx's existing Draw/achievement wrapper remain unchanged.",
        ))
    if better_card:
        lines.append("# Better Card: hide enemies whose common and rare Card results are both FF.")
    if summon_gate:
        lines.append("# Summon: grey the GF command when the acting character has no GF junctioned.")
    if streamlined_draw:
        lines.append("# Streamlined Draw: hide enemies whose valid spells are all at the stock limit.")
    for address, payload in caves:
        lines.append(f"{address:X}:{len(payload):X}")
    if draw_once:
        lines.append(f"{DRAW_STATE:X}:8")
    if summon_gate:
        lines.append(f"{SUMMON_REFUSED_FLAG:X}:4")
    for hook, length, cave in hooks:
        replacement = _near_jump(hook, cave) + b"\x90" * (length - 5)
        lines.append(f"{hook:X} = {replacement.hex(' ').upper()}")
    for address, payload in caves:
        lines.append(f"{address:X} = {payload.hex(' ').upper()}")
    if draw_once:
        lines.append(f"{DRAW_STATE:X} = 00 00 00 00")
    return "\n".join(lines + [""])


def build_draw_patch(enabled: bool = DEFAULT_DRAW_ONCE_PER_ENEMY) -> str:
    """Compatibility wrapper for the Draw-only composition."""
    if not isinstance(enabled, bool):
        raise ValueError("Draw Once per Enemy must be true or false")
    # Draw only. Summon's gate is composed by the caller that wants both.
    return build_command_eligibility_patch(
        draw_once=enabled, better_card=False, summon_gate=False)


def build_patch(*, enabled: bool, single_gf_enabled: bool,
                fixed_command_menu_enabled: bool) -> str:
    """Keep the grouped unfinished mechanics fail closed.

    Draw has its own independent toggle and patch builder above. The grouped
    feature still includes unresolved GF Magic-page work.
    """
    if not all(isinstance(value, bool) for value in (
        enabled, single_gf_enabled, fixed_command_menu_enabled,
    )):
        raise ValueError("Battle mechanic settings must be true or false")
    if not enabled:
        return ""
    if not single_gf_enabled:
        raise RuntimeError("GF battle mechanics require Single GF")
    if not fixed_command_menu_enabled:
        raise RuntimeError("GF battle mechanics require Fixed Command Menu")
    raise RuntimeError("FF8 battle mechanics are not ready: " + " ".join(BLOCKERS))
