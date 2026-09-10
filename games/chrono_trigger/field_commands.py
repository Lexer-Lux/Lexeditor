"""Deterministic command boundaries for Chrono Trigger Steam field events.

The Steam port retains the classic event opcode space but changes several
argument widths. This module records byte widths only; it is a fail-closed
read-only disassembler, not an interpreter or writer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argument_bytes: int


# Argument-byte counts for the PC encoding, indexed by opcode. ``None`` means
# mode/length dependent. ``-1`` means conflicting public PC metadata: do not
# infer a boundary until an independent fixture resolves it.
_PC_ARGUMENT_BYTES: tuple[int | None, ...] = (
    0, 0, 2, 2, 2, 2, 2, 2, 0, 0, 1, 1, 1, 1, 1, 0,
    1, 1, 4, 5, 4, 4, 4, 0, 2, 1, 2, 0, 1, 0, 1, 1,
    1, 3, 3, 2, 2, 1, 1, 2, 2, 1, 0, 0, 2, 1, None, 2,
    1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 2, 1,
    1, 1, 1, 1, 1, 2, 2, 0, 3, 3, 3, 4, 3, 3, None, 2,
    3, 2, 2, 3, 3, 1, 3, 0, 3, 3, 1, 2, 0, 2, 2, 2,
    2, 2, 0, 2, 2, 2, 2, 2, 0, 2, 0, 2, 0, 0, 4, 2,
    2, 1, 1, 1, 2, 1, 1, 1, 2, 0, 3, 4, 1, 1, 0, 1,
    1, 1, 1, 3, 1, 0, 0, 1, None, 1, 1, 2, 2, 4, 1, 1,
    0, 0, 2, 0, 1, 1, 2, 2, 2, 2, 3, 0, 2, 2, -1, -1,
    2, 2, 6, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,
    0, 0, 0, 0, 0, 1, 1, 2, 1, 0, 0, 2, 0, 0, 0, 0,
    3, 2, 2, 3, 3, 0, 0, 2, 1, 3, 2, 2, 3, 2, 2, 2,
    1, 1, 2, 1, 1, 3, 1, 3, 2, 6, 0, 0, 5, 5, 5, 5,
    5, 5, 4, 1, 7, 7, 4, 2, 1, 0, 1, 2, None, 0, 0, 0,
    1, -1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 17, None,
)

_NAMES = {
    0x00: "Return", 0x01: "Color Crash",
    0x02: "Call Event (continue)", 0x03: "Call Event (sync)", 0x04: "Call Event (halt)",
    0x05: "Call PC Event (continue)", 0x06: "Call PC Event (sync)", 0x07: "Call PC Event (halt)",
    0x08: "Object Deactivation", 0x09: "Object Activation", 0x0A: "Remove Object",
    0x0B: "Disable Processing", 0x0C: "Enable Processing", 0x0D: "Movement Properties",
    0x0E: "Destination Properties", 0x0F: "Face Up", 0x10: "Jump Forward", 0x11: "Jump Backwards",
    0x12: "If 8-bit", 0x13: "If 16-bit", 0x14: "Compare Memory 8-bit", 0x15: "Compare Memory 16-bit",
    0x16: "Compare Bank 7F", 0x17: "Face Down", 0x18: "Check Storyline", 0x19: "Get Result",
    0x1A: "Jump Result", 0x1B: "Face Left", 0x1C: "Get Result (bank)", 0x1D: "Face Right",
    0x20: "Get PC1", 0x21: "Get Object Coords", 0x22: "Get PC Coords", 0x23: "Get Object Facing",
    0x24: "Get PC Facing", 0x27: "Check Object Status", 0x28: "Check Battle Range", 0x29: "Load ASCII Text",
    0x2D: "Check Button", 0x2E: "Color Math", 0x2F: "Scroll Layers", 0x30: "Jump No Dash",
    0x31: "Jump No Confirm", 0x33: "Change Palette", 0x34: "Jump No A", 0x35: "Jump No B",
    0x36: "Jump No X", 0x37: "Jump No Y", 0x38: "Jump No L", 0x39: "Jump No R",
    0x3A: "Value to Extended Memory", 0x3D: "Local to Extended Memory", 0x3E: "Extended to Local Memory",
    0x45: "Bit Set Extended Memory", 0x46: "Bit Clear Extended Memory", 0x47: "PC NOP",
    0x48: "Any to Local 8", 0x49: "Any to Local 16", 0x4A: "Value to Any 8", 0x4B: "Value to Any 16",
    0x4C: "Local to Any 8", 0x4D: "Local to Any 16", 0x4E: "Memory Copy", 0x4F: "Value to Local 8",
    0x50: "Value to Local 16", 0x51: "Local to Local 8", 0x52: "Local to Local 16",
    0x53: "Bank7F to Local 8", 0x54: "Bank7F to Local 16", 0x55: "Get Storyline Counter",
    0x56: "Value to Bank7F", 0x57: "Load Crono", 0x58: "Local to Bank7F 8", 0x59: "Local to Bank7F 16",
    0x5A: "Set Storyline", 0x5B: "Add Value", 0x5C: "Load Marle", 0x5D: "Add Memory 8",
    0x5E: "Add Memory 16", 0x5F: "Subtract Value 8", 0x60: "Subtract 16", 0x61: "Subtract Memory",
    0x62: "Load Lucca", 0x63: "Set Bit", 0x64: "Reset Bit", 0x65: "Set Bank7F Bit",
    0x66: "Reset Bank7F Bit", 0x67: "Reset Bits", 0x68: "Load Frog", 0x69: "Set Bits", 0x6A: "Load Robo",
    0x6B: "Toggle Bits", 0x6C: "Load Ayla", 0x6D: "Load Magus", 0x6E: "Jump If Extended Memory",
    0x6F: "Shift Bits", 0x70: "Party Slot to Local", 0x71: "Increment 8", 0x72: "Increment 16",
    0x73: "Decrement", 0x74: "Extended16 to Local", 0x75: "Set Byte 8", 0x76: "Set Byte 16",
    0x77: "Reset Byte", 0x78: "Local to Extended16", 0x7A: "NPC Jump", 0x7B: "NPC Jump (unused)",
    0x7C: "Turn Drawing On", 0x7D: "Turn Drawing Off", 0x7E: "Turn Drawing Off (self)", 0x7F: "Random",
    0x80: "Load PC if Party", 0x81: "Load PC", 0x82: "Load NPC", 0x83: "Load Enemy", 0x84: "NPC Solidity",
    0x87: "Script Speed", 0x88: "Multi-mode Memory Copy", 0x89: "NPC Speed", 0x8A: "NPC Speed from Memory",
    0x8B: "Set Object Position", 0x8C: "Set Position from Memory", 0x8D: "Set Pixel Position",
    0x8E: "Sprite Priority", 0x8F: "Follow at Distance", 0x90: "Drawing On", 0x91: "Drawing Off",
    0x92: "Vector Move", 0x94: "Follow Object", 0x95: "Follow PC", 0x96: "NPC Move",
    0x97: "NPC Move from Memory", 0x98: "Move Toward Object", 0x99: "Move Toward PC",
    0x9A: "Move Toward Coordinates", 0x9C: "Vector Move (keep facing)", 0x9D: "Vector Move from Memory",
    0x9E: "Move Toward Object (ambiguous PC width)", 0x9F: "Move Toward PC (ambiguous PC width)",
    0xA0: "Animated Move", 0xA1: "Animated Move from Memory", 0xA2: "PC Extended Command",
    0xA6: "NPC Facing", 0xA7: "Facing from Memory", 0xA8: "Face Object", 0xA9: "Face PC",
    0xAA: "Loop Animation", 0xAB: "Animation", 0xAC: "Static Animation", 0xAD: "Pause",
    0xAE: "Reset Animation", 0xAF: "Exploration Once", 0xB0: "Exploration", 0xB1: "Break", 0xB2: "End",
    0xB3: "Animation 0", 0xB4: "Animation 1", 0xB5: "Move to Object (loop)", 0xB6: "Move to PC (loop)",
    0xB7: "Loop Animation Count", 0xB8: "String Index", 0xB9: "Pause 1/4", 0xBA: "Pause 1/2",
    0xBB: "Personal Textbox", 0xBC: "Pause 1", 0xBD: "Pause 2", 0xC0: "Decision Box Auto",
    0xC1: "Textbox Top", 0xC2: "Textbox Bottom", 0xC3: "Decision Box Top", 0xC4: "Decision Box Bottom",
    0xC7: "Add Item from Memory", 0xC8: "Special Dialog", 0xC9: "Check Inventory", 0xCA: "Add Item",
    0xCB: "Remove Item", 0xCC: "Check Gold", 0xCD: "Add Gold", 0xCE: "Remove Gold",
    0xCF: "Check Recruited", 0xD0: "Add Reserve", 0xD1: "Remove PC", 0xD2: "Check Active PC",
    0xD3: "Add PC to Party", 0xD4: "Move to Reserve", 0xD5: "Equip Item", 0xD6: "Remove Active PC",
    0xD7: "Get Item Quantity", 0xD8: "Battle", 0xD9: "Move Party", 0xDA: "Party Follow",
    0xDC: "Change Location", 0xDD: "Change Location", 0xDE: "Change Location", 0xDF: "Change Location",
    0xE0: "Change Location", 0xE1: "Change Location (VSync)", 0xE2: "Change Location from Memory",
    0xE3: "Explore Mode", 0xE4: "Copy Tiles", 0xE5: "Copy Tiles (no VSync)", 0xE6: "Scroll Layers",
    0xE7: "Scroll Screen", 0xE8: "Play Sound", 0xEA: "Play Song", 0xEB: "Change Volume",
    0xEC: "All Purpose Sound", 0xED: "Wait for Silence", 0xEE: "Wait for Song End", 0xF0: "Darken Screen",
    0xF1: "Color Addition", 0xF2: "Fade Out", 0xF3: "Wait for Brighten", 0xF4: "Shake Screen",
    0xF8: "Restore HP/MP", 0xF9: "Restore HP", 0xFA: "Restore MP", 0xFD: "PC Unknown 0xFD",
    0xFE: "Unknown Geometry", 0xFF: "Mode 7 Scene",
}


def _dynamic_argument_bytes(data: bytes, offset: int, opcode: int) -> tuple[int | None, str | None]:
    remaining = len(data) - offset
    if remaining < 2:
        return None, "command is truncated before its mode/length byte"
    if opcode == 0x2E:
        mode = data[offset + 1] >> 4
        if mode in {4, 5}:
            return 5, None
        if mode == 8:
            # Temporal Redux's PC parser explicitly overrides mode 8 to three
            # one-byte arguments. Its generic ColorMathMenu's variable blob is
            # a SNES-side construction and is not the PC event representation.
            return 3, None
        return None, f"unknown PC color-math mode {mode}"
    if opcode == 0x4E:
        if remaining < 5:
            return None, "PC memory-copy header is truncated"
        # PC parser: [destination u16][encoded length u16][payload].
        encoded = int.from_bytes(data[offset + 3:offset + 5], "little")
        if encoded < 2:
            return None, f"PC memory-copy encoded length is invalid: {encoded}"
        return 4 + encoded - 2, None
    if opcode == 0x88:
        mode = data[offset + 1] >> 4
        # Temporal Redux's PC parser explicitly uses two one-byte arguments for
        # mode 8; the generic MultiModeMenu's appended blob is not serialized
        # by its unchanged base arg_lens and is not PC boundary evidence.
        widths = {0: 1, 2: 3, 3: 3, 4: 4, 5: 4, 8: 2}
        if mode not in widths:
            return None, f"unknown PC multi-mode copy mode {mode}"
        return widths[mode], None
    if opcode == 0xEC:
        subcommand = data[offset + 1]
        widths = {
            0x88: 1, 0xF0: 1, 0xF2: 1,
            0x14: 2, 0x19: 2,
            0x82: 3, 0x83: 3, 0x85: 3, 0x86: 3,
        }
        if subcommand not in widths:
            return None, f"unknown PC all-purpose sound subcommand 0x{subcommand:02X}"
        return widths[subcommand], None
    if opcode == 0xFF:
        mode = data[offset + 1]
        if mode <= 0x89:
            return 1, None
        if mode in {0x90, 0x97}:
            return 4, None
        if 0x91 <= mode <= 0x98:
            return 1, None
        return None, f"unknown PC Mode 7 mode 0x{mode:02X}"
    return None, "dynamic command has no decoder"


def command_spec(data: bytes, offset: int) -> tuple[CommandSpec | None, str | None]:
    if not 0 <= offset < len(data):
        return None, "command offset is outside the function"
    opcode = data[offset]
    width = _PC_ARGUMENT_BYTES[opcode]
    if width == -1:
        return None, "PC command width is unresolved in available upstream metadata"
    if width is None:
        width, error = _dynamic_argument_bytes(data, offset, opcode)
        if error:
            return None, error
    return CommandSpec(_NAMES.get(opcode, f"Opcode 0x{opcode:02X}"), int(width)), None


def disassemble_function(data: bytes, start: int, end: int) -> dict:
    if not 0 <= start <= end <= len(data):
        raise ValueError("Chrono Trigger event function bounds are invalid")
    commands = []
    pos = start
    problem = None
    while pos < end:
        spec, error = command_spec(data, pos)
        opcode = data[pos]
        if spec is None:
            problem = {"offset": pos, "opcode": opcode, "reason": error or "unknown command"}
            break
        size = 1 + spec.argument_bytes
        if pos + size > end:
            problem = {
                "offset": pos, "opcode": opcode,
                "reason": f"command needs {size} bytes but only {end - pos} remain in this function",
            }
            break
        arguments = data[pos + 1:pos + size]
        commands.append({
            "index": len(commands), "offset": pos, "opcode": opcode,
            "name": spec.name, "argumentBytes": spec.argument_bytes, "size": size,
            "argumentsHex": arguments.hex(" ").upper(),
            "rawHex": data[pos:pos + size].hex(" ").upper(),
        })
        pos += size
    return {
        "commands": commands, "decodedBytes": pos - start, "totalBytes": end - start,
        "complete": pos == end and problem is None, "problem": problem,
    }
