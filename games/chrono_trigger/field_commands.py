"""Deterministic Chrono Trigger Steam field-event command boundaries.

This is intentionally a disassembler metadata layer, not an event interpreter.
The PC port keeps the classic event opcode set but changes the encoded width of
several commands.  Variable-length commands are resolved from their documented
mode/length bytes and fail closed when a boundary cannot be proven.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argument_bytes: int | None


# Fixed argument byte counts for the classic event command set before the
# Steam/PC width overrides below. Dynamic commands use None.
_WIDTHS: dict[int, int | None] = {opcode: 0 for opcode in range(0x100)}


def _set(width: int | None, *opcodes: int) -> None:
    for opcode in opcodes:
        _WIDTHS[opcode] = width


_set(2, *range(0x02, 0x08))
_set(1, *range(0x0A, 0x0F), 0x10, 0x11, 0x19, 0x1E, 0x1F, 0x20, 0x25, 0x26, 0x29,
     0x2D, 0x2E, 0x30, 0x31, 0x33, *range(0x34, 0x3A), 0x3B, 0x3C,
     *range(0x3F, 0x45), 0x47, 0x55, 0x5A, 0x71, 0x72, 0x73, 0x75, 0x76, 0x77,
     0x7C, 0x7D, 0x7F, 0x80, 0x81, 0x82, 0x84, 0x87, 0x88, 0x89, 0x8A, 0x8E,
     0x8F, 0x94, 0x95, 0x9E, 0x9F, *range(0xA6, 0xAE), 0xB5, 0xB6, 0xB8,
     0xBB, 0xC1, 0xC2, 0xC7, 0xC8, 0xCA, 0xCB, 0xD0, 0xD1, 0xD3, 0xD4,
     0xD5, 0xD6, 0xD7, 0xE3, 0xE8, 0xEA, 0xF0, 0xF1, 0xF4, 0xFD, 0xFF)
_set(2, 0x18, 0x1A, 0x23, 0x24, 0x27, 0x28, 0x2C, 0x2F,
     0x4F, 0x51, 0x52, 0x5B, 0x5D, 0x5E, 0x5F, 0x61, *range(0x63, 0x68),
     0x69, 0x6B, 0x6F, 0x83, 0x8B, 0x8C, 0x92, 0x96, 0x97, 0x98, 0x99,
     0x9C, 0x9D, 0xA0, 0xA1, 0xB7, 0xC0, 0xC3, 0xC4, 0xC9, 0xCF, 0xD2,
     0xD8, 0xE7, 0xEB)
_set(3, 0x21, 0x22, 0x4F + 1, 0x53, 0x54, 0x56, 0x58, 0x59, 0x7A, 0x9A,
     0xCC, 0xDC, 0xDD, 0xDE, 0xDF, 0xE0, 0xE1, 0xEC)
_set(4, 0x12, 0x14, 0x15, 0x16, 0x4B, 0x7B, 0x8D, 0xE2, 0xE6)
_set(5, 0x13)
_set(6, 0xD9)
_set(7, 0xE4, 0xE5)
_set(17, 0xFE)
_set(None, 0x2E, 0x4E, 0x88, 0xF1, 0xFF)

# Steam/PC-specific fixed widths. These supersede the classic widths above.
_PC_WIDTHS = {
    0x1C: 1,
    0x3A: 2, 0x3D: 2, 0x3E: 2, 0x45: 2, 0x46: 2,
    0x47: 0,
    0x48: 3, 0x49: 3, 0x4A: 3, 0x4B: 4, 0x4C: 3, 0x4D: 3,
    0x60: 2, 0x6E: 4, 0x70: 2, 0x74: 2, 0x78: 2,
    0x83: 3, 0xA2: 6,
    0xB8: 1, 0xBB: 2,
    0xC0: 3, 0xC1: 2, 0xC2: 2, 0xC3: 3, 0xC4: 3,
    0xC7: 2, 0xC9: 3, 0xCA: 2, 0xCB: 2,
    0xD5: 3, 0xD7: 3,
    0xDC: 5, 0xDD: 5, 0xDE: 5, 0xDF: 5, 0xE0: 5, 0xE1: 5,
    0xFD: 1,
}

_NAMES = {
    0x00: "Return", 0x01: "Color Crash", 0x02: "Call Event (continue)",
    0x03: "Call Event (sync)", 0x04: "Call Event (halt)",
    0x05: "Call PC Event (continue)", 0x06: "Call PC Event (sync)",
    0x07: "Call PC Event (halt)", 0x08: "Object Deactivation", 0x09: "Object Activation",
    0x0A: "Remove Object", 0x0B: "Disable Processing", 0x0C: "Enable Processing",
    0x0D: "NPC Movement Properties", 0x0E: "NPC Positioning", 0x0F: "Face Up",
    0x10: "Jump Forward", 0x11: "Jump Backwards", 0x12: "If 8-bit",
    0x13: "If 16-bit", 0x14: "If Memory 8-bit", 0x15: "If Memory 16-bit",
    0x16: "If Bank 7F", 0x17: "Face Down", 0x18: "Check Storyline",
    0x19: "Get Result", 0x1A: "Jump Result", 0x1B: "Face Left", 0x1C: "Get Result (bank)",
    0x1D: "Face Right", 0x1E: "Face Object Up", 0x1F: "Face Object Down",
    0x20: "Get PC1", 0x21: "Get Object Coords", 0x22: "Get PC Coords",
    0x23: "Get Object Facing", 0x24: "Get PC Facing", 0x25: "Face Object Left",
    0x26: "Face Object Right", 0x27: "Check Object Status", 0x28: "Check Battle Range",
    0x29: "Load ASCII Text", 0x2A: "Set Flag 0x04", 0x2B: "Set Flag 0x08",
    0x2C: "Unknown 0x2C", 0x2D: "Check Button Pressed", 0x2E: "Color Math",
    0x2F: "Scroll Layers (unknown)", 0x30: "Jump No Dash", 0x31: "Jump No Confirm",
    0x32: "Set Flag 0x10", 0x33: "Change Palette", 0x34: "Jump No A",
    0x35: "Jump No B", 0x36: "Jump No X", 0x37: "Jump No Y", 0x38: "Jump No L",
    0x39: "Jump No R", 0x3A: "Copy Value to Extended Memory", 0x3B: "Jump No Dash (edge)",
    0x3C: "Jump No Confirm (edge)", 0x3D: "Local to Extended Memory",
    0x3E: "Extended to Local Memory", 0x3F: "Jump No A (edge)", 0x40: "Jump No B (edge)",
    0x41: "Jump No X (edge)", 0x42: "Jump No Y (edge)", 0x43: "Jump No L (edge)",
    0x44: "Jump No R (edge)", 0x45: "Bit Set Extended Memory",
    0x46: "Bit Clear Extended Memory", 0x47: "Animation Limiter / PC NOP",
    0x48: "Assignment Any→Local 8", 0x49: "Assignment Any→Local 16",
    0x4A: "Assignment Value→Any 8", 0x4B: "Assignment Value→Any 16",
    0x4C: "Assignment Local→Any 8", 0x4D: "Assignment Local→Any 16",
    0x4E: "Memory Copy", 0x4F: "Assignment Value→Local 8", 0x50: "Assignment Value→Local 16",
    0x51: "Assignment Local→Local 8", 0x52: "Assignment Local→Local 16",
    0x53: "Assignment Bank7F→Local 8", 0x54: "Assignment Bank7F→Local 16",
    0x55: "Get Storyline Counter", 0x56: "Assignment Value→Bank7F", 0x57: "Load Crono",
    0x58: "Assignment Local→Bank7F 8", 0x59: "Assignment Local→Bank7F 16",
    0x5A: "Assign Storyline", 0x5B: "Add Value→Memory", 0x5C: "Load Marle",
    0x5D: "Add Memory→Memory 8", 0x5E: "Add Memory→Memory 16", 0x5F: "Subtract Value→Memory 8",
    0x60: "Subtract 16", 0x61: "Subtract Memory→Memory", 0x62: "Load Lucca",
    0x63: "Set Bit", 0x64: "Reset Bit", 0x65: "Set Bank7F Bit", 0x66: "Reset Bank7F Bit",
    0x67: "Reset Bits", 0x68: "Load Frog", 0x69: "Set Bits", 0x6A: "Load Robo",
    0x6B: "Toggle Bits", 0x6C: "Load Ayla", 0x6D: "Load Magus",
    0x6E: "Jump If Extended Memory", 0x6F: "Shift Bits", 0x70: "Party Slot→Local",
    0x71: "Increment 8", 0x72: "Increment 16", 0x73: "Decrement",
    0x74: "Extended16→Local", 0x75: "Set Byte 8", 0x76: "Set Byte 16",
    0x77: "Reset Byte", 0x78: "Local→Extended16", 0x79: "Crash Alias",
    0x7A: "NPC Jump", 0x7B: "NPC Jump (unused)", 0x7C: "Turn Drawing On",
    0x7D: "Turn Drawing Off", 0x7E: "Turn Drawing Off (self)", 0x7F: "Random",
    0x80: "Load PC if Party", 0x81: "Load PC", 0x82: "Load NPC", 0x83: "Load Enemy",
    0x84: "NPC Solidity", 0x85: "Crash Alias", 0x86: "Crash Alias", 0x87: "Script Speed",
    0x88: "Multi-mode Memory Copy", 0x89: "NPC Speed", 0x8A: "NPC Speed from Memory",
    0x8B: "Set Object Position", 0x8C: "Set Object Position from Memory",
    0x8D: "Set Object Pixel Position", 0x8E: "Set Sprite Priority", 0x8F: "Follow at Distance",
    0x90: "Drawing On", 0x91: "Drawing Off", 0x92: "Vector Move", 0x93: "Crash Alias",
    0x94: "Follow Object", 0x95: "Follow PC", 0x96: "NPC Move", 0x97: "NPC Move from Memory",
    0x98: "Move Toward Object", 0x99: "Move Toward PC", 0x9A: "Move Toward Coordinates",
    0x9B: "Crash Alias", 0x9C: "Vector Move (keep facing)", 0x9D: "Vector Move from Memory",
    0x9E: "Move Toward Object (keep facing)", 0x9F: "Move Toward PC (keep facing)",
    0xA0: "Animated Move", 0xA1: "Animated Move from Memory", 0xA2: "PC Extended Command",
    0xA3: "Crash Alias", 0xA4: "Crash Alias", 0xA5: "Crash Alias", 0xA6: "NPC Facing",
    0xA7: "NPC Facing from Memory", 0xA8: "Face Object", 0xA9: "Face PC",
    0xAA: "Loop Animation", 0xAB: "Animation", 0xAC: "Static Animation", 0xAD: "Pause",
    0xAE: "Reset Animation", 0xAF: "Exploration Once", 0xB0: "Exploration",
    0xB1: "Break", 0xB2: "End", 0xB3: "Animation 0", 0xB4: "Animation 1",
    0xB5: "Move to Object (loop)", 0xB6: "Move to PC (loop)", 0xB7: "Loop Animation Count",
    0xB8: "String Index", 0xB9: "Pause 1/4", 0xBA: "Pause 1/2", 0xBB: "Personal Textbox",
    0xBC: "Pause 1", 0xBD: "Pause 2", 0xBE: "Crash Alias", 0xBF: "Crash Alias",
    0xC0: "Decision Box Auto", 0xC1: "Textbox Top", 0xC2: "Textbox Bottom",
    0xC3: "Decision Box Top", 0xC4: "Decision Box Bottom", 0xC5: "Crash Alias", 0xC6: "Crash Alias",
    0xC7: "Add Item from Memory", 0xC8: "Special Dialog", 0xC9: "Check Inventory",
    0xCA: "Add Item", 0xCB: "Remove Item", 0xCC: "Check Gold", 0xCD: "Add Gold",
    0xCE: "Remove Gold", 0xCF: "Check Recruited", 0xD0: "Add Reserve", 0xD1: "Remove PC",
    0xD2: "Check Active PC", 0xD3: "Add PC to Party", 0xD4: "Move to Reserve",
    0xD5: "Equip Item", 0xD6: "Remove Active PC", 0xD7: "Get Item Quantity",
    0xD8: "Battle", 0xD9: "Move Party", 0xDA: "Party Follow", 0xDB: "Crash Alias",
    0xDC: "Change Location", 0xDD: "Change Location", 0xDE: "Change Location",
    0xDF: "Change Location", 0xE0: "Change Location", 0xE1: "Change Location (VSync)",
    0xE2: "Change Location from Memory", 0xE3: "Explore Mode", 0xE4: "Copy Tiles",
    0xE5: "Copy Tiles (no VSync)", 0xE6: "Scroll Layers", 0xE7: "Scroll Screen",
    0xE8: "Play Sound", 0xE9: "Crash Alias", 0xEA: "Play Song", 0xEB: "Change Volume",
    0xEC: "All Purpose Sound", 0xED: "Wait for Silence", 0xEE: "Wait for Song End",
    0xEF: "Crash Alias", 0xF0: "Darken Screen", 0xF1: "Color Addition", 0xF2: "Fade Out",
    0xF3: "Wait for Brighten End", 0xF4: "Shake Screen", 0xF5: "Crash Alias",
    0xF6: "Crash Alias", 0xF7: "Crash Alias", 0xF8: "Restore HP/MP", 0xF9: "Restore HP",
    0xFA: "Restore MP", 0xFB: "Crash Alias", 0xFC: "Crash Alias", 0xFD: "PC Unknown 0xFD",
    0xFE: "Unknown Geometry", 0xFF: "Mode 7 Scene",
}

# Upstream metadata is internally inconsistent for these two opcodes: the
# table declares one argument while its PC factory emits two. Refuse to infer a
# boundary until an independent PC fixture resolves the discrepancy.
_UNRESOLVED = {0x9E, 0x9F}


def _dynamic_width(data: bytes, offset: int, opcode: int) -> tuple[int | None, str | None]:
    remaining = len(data) - offset
    if remaining < 2:
        return None, "command is truncated before its mode/length byte"
    if opcode == 0x2E:
        mode = data[offset + 1] >> 4
        if mode in {4, 5}:
            return 5, None
        if mode == 8:
            return 3, None
        return None, f"unknown PC color-math mode {mode}"
    if opcode == 0x4E:
        if remaining < 5:
            return None, "PC memory-copy header is truncated"
        encoded = int.from_bytes(data[offset + 3:offset + 5], "little")
        if encoded < 2:
            return None, f"PC memory-copy encoded length is invalid: {encoded}"
        return 4 + (encoded - 2), None
    if opcode == 0x88:
        mode = data[offset + 1] >> 4
        widths = {0: 1, 2: 3, 3: 3, 4: 4, 5: 4, 8: 2}
        if mode not in widths:
            return None, f"unknown PC multi-mode copy mode {mode}"
        return widths[mode], None
    if opcode == 0xF1:
        return (1 if data[offset + 1] == 0 else 2), None
    if opcode == 0xFF:
        return (4 if data[offset + 1] in {0x90, 0x97} else 1), None
    return None, "dynamic command has no decoder"


def command_spec(data: bytes, offset: int) -> tuple[CommandSpec | None, str | None]:
    if not 0 <= offset < len(data):
        return None, "command offset is outside the function"
    opcode = data[offset]
    if opcode in _UNRESOLVED:
        return None, "PC command width is unresolved in available upstream metadata"
    width = _PC_WIDTHS.get(opcode, _WIDTHS[opcode])
    if width is None:
        width, error = _dynamic_width(data, offset, opcode)
        if error:
            return None, error
    return CommandSpec(_NAMES.get(opcode, f"Opcode 0x{opcode:02X}"), width), None


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
        size = 1 + int(spec.argument_bytes)
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
        "commands": commands,
        "decodedBytes": pos - start,
        "totalBytes": end - start,
        "complete": pos == end and problem is None,
        "problem": problem,
    }
