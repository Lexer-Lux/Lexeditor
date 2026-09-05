"""Guarded in-battle Squall Switch component for Lexeditor issue #52."""

from __future__ import annotations


SWITCH_MARKER = 0xFE
SQUALL = 0
CHARACTER_SLOT = 2

DESCRIPTOR_HOOK = 0x0049580B
DESCRIPTOR_ORIGINAL = bytes.fromhex("8D 6E 1E 24 01")
LABEL_HOOK = 0x0047EBD0
LABEL_ORIGINAL = bytes.fromhex("8B 44 24 04 66 8B 04 C5 2C 3F CF 01")
DESCRIPTION_HOOK = 0x0047EC00
DESCRIPTION_ORIGINAL = bytes.fromhex("8B 44 24 04 66 8B 04 C5 2E 3F CF 01")
# This boundary runs immediately after command confirmation and before FF8's
# availability and target builders. Switch owns Squall as its implicit target,
# so it must never enter the vanilla target-selection path.
COMMAND_CONFIRM_HOOK = 0x004BBE07
COMMAND_CONFIRM_ORIGINAL = bytes.fromhex("55 57 68 30 68 D7 01")

REGISTER_SLOT = 0x004B9AD0
SET_SLOT_STATE = 0x004B9B90
HIDE_SLOT = 0x004B9C00
READ_INPUT = 0x004A8420
DRAW_TEXT = 0x004A7250
PARSE_CHARACTER = 0x00495530
PARSE_MAGIC = 0x00495960
UPDATE_LOW_HP = 0x00494360
CONTROLLER_COMMON_TAIL = 0x004BC6BE

ACTIVE_SLOT = 0x01D76843
SELECTED_ACTOR = 0x01D76844
CONTROLLER_STATE = 0x01D7685B
CONTROLLER_READY = 0x01D76840
PREPARED_COUNT = 0x01D76718
RUNTIME_ACTOR_BASE = 0x01CFF000
RUNTIME_ACTOR_STRIDE = 0x1D0
CHARACTER_ID_OFFSET = 0x1C3
SAVEMAP_CHARACTER_BASE = 0x01CFE0E8
SAVEMAP_CHARACTER_STRIDE = 0x98
GF_MASK_OFFSET = 0x58
GF_DATA_BASE = 0x01CFDCA8
GF_DATA_STRIDE = 0x44
GF_EXISTS_OFFSET = 0x11
PARTICIPANT_BASE = 0x01D27B10
PARTICIPANT_STRIDE = 0xD0
GLOBAL_PASSIVE_BYTE = 0x01CFF6D8

DESCRIPTOR_CAVE = 0x0279FB00
LABEL_CAVE = 0x0279FB60
DESCRIPTION_CAVE = 0x0279FBC0
COMMAND_CONFIRM_CAVE = 0x0279FC20
UPDATE_CAVE = 0x0279FD80
CLOSE_CAVE = 0x0279FE80
DRAW_CAVE = 0x0279FF00
REFRESH_CAVE = 0x027A0080
CLONE_CAVE = 0x027A0200
STATE_BASE = 0x027A0500
SWITCH_ACTIVE = STATE_BASE
SWITCH_ACTOR = STATE_BASE + 1
SWITCH_SELECTION = STATE_BASE + 2
SNAP_RUNTIME_14 = STATE_BASE + 4
SNAP_RUNTIME_18 = STATE_BASE + 8
SNAP_RUNTIME_1C = STATE_BASE + 12
SNAP_RUNTIME_HP = STATE_BASE + 14
SNAP_SAVE_HP = STATE_BASE + 16
SNAP_GLOBAL = STATE_BASE + 18
SWITCH_CHAR_ID = STATE_BASE + 20
SWITCH_SAVE_PTR = STATE_BASE + 24

SWITCH_TEXT = bytes.fromhex("57 75 67 72 61 66 00")
SWITCH_DESCRIPTION = bytes.fromhex(
    "57 63 6A 63 61 72 20 5F 20 62 67 64 64 63 70 63 6C 72 20 4B 4A 3B 00"
)
CURSOR_TEXT = bytes.fromhex("CB 20 00")


class _Code:
    def __init__(self, address: int):
        self.address = address
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.relative: list[tuple[int, str]] = []
        self.absolute: list[tuple[int, str]] = []

    def add(self, data: bytes) -> None:
        self.data.extend(data)

    def label(self, name: str) -> None:
        self.labels[name] = len(self.data)

    def branch(self, opcode: bytes, label: str) -> None:
        self.data.extend(opcode)
        self.relative.append((len(self.data), label))
        self.data.extend(b"\0\0\0\0")

    def address_of(self, prefix: bytes, label: str, suffix: bytes = b"") -> None:
        self.data.extend(prefix)
        self.absolute.append((len(self.data), label))
        self.data.extend(b"\0\0\0\0")
        self.data.extend(suffix)

    def call(self, target: int) -> None:
        self.add(_near(self.address + len(self.data), target, b"\xE8"))

    def jump(self, target: int) -> None:
        self.add(_near(self.address + len(self.data), target))

    def finish(self) -> bytes:
        for offset, label in self.relative:
            delta = self.address + self.labels[label] - (self.address + offset + 4)
            self.data[offset:offset + 4] = delta.to_bytes(4, "little", signed=True)
        for offset, label in self.absolute:
            target = self.address + self.labels[label]
            self.data[offset:offset + 4] = target.to_bytes(4, "little")
        return bytes(self.data)


def _near(source: int, target: int, opcode: bytes = b"\xE9") -> bytes:
    return opcode + (target - source - 5).to_bytes(4, "little", signed=True)


def _resolver_payload(address: int, original: bytes, text: bytes) -> bytes:
    code = _Code(address)
    code.add(bytes.fromhex("8B 44 24 04 3D FE 00 00 00"))
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.address_of(b"\xB8", "text")
    code.add(b"\xC3")
    code.label("vanilla")
    code.add(original)
    code.jump((LABEL_HOOK if address == LABEL_CAVE else DESCRIPTION_HOOK) + len(original))
    code.label("text")
    code.add(text)
    return code.finish()


def _descriptor_payload() -> bytes:
    code = _Code(DESCRIPTOR_CAVE)
    code.add(DESCRIPTOR_ORIGINAL)
    code.add(bytes.fromhex("80 BE C3 01 00 00 00"))
    code.branch(bytes.fromhex("0F 85"), "done")
    # Switch is intercepted before target construction. Its target byte is zero
    # because Squall is always the implicit target.
    code.add(bytes.fromhex("C7 46 26 FE A0 00 00"))
    code.label("done")
    code.jump(DESCRIPTOR_HOOK + len(DESCRIPTOR_ORIGINAL))
    return code.finish()


def _close_payload() -> bytes:
    code = _Code(CLOSE_CAVE)
    code.add(bytes.fromhex("60 6A 00 6A 00 6A 00 6A 05"))
    code.call(REGISTER_SLOT)
    code.add(bytes.fromhex("83 C4 10 6A 03 6A 04"))
    code.call(SET_SLOT_STATE)
    code.add(bytes.fromhex("83 C4 08"))
    code.add(b"\xC7\x05" + PREPARED_COUNT.to_bytes(4, "little") + bytes.fromhex("00 00 00 00"))
    code.add(b"\xC6\x05" + CONTROLLER_STATE.to_bytes(4, "little") + b"\x07")
    code.add(b"\x66\xC7\x05" + CONTROLLER_READY.to_bytes(4, "little") + bytes.fromhex("00 10"))
    code.add(b"\xC6\x05" + SWITCH_ACTIVE.to_bytes(4, "little") + b"\x00")
    code.add(bytes.fromhex("61 C3"))
    return code.finish()


def _command_confirm_payload() -> bytes:
    code = _Code(COMMAND_CONFIRM_CAVE)
    # EDI is the selected four-byte runtime command descriptor at this exact
    # boundary. Divert Switch before 0x004BC770 can build a target mask.
    code.add(bytes.fromhex("80 3F") + bytes((SWITCH_MARKER,)))
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(b"\x80\x3D" + ACTIVE_SLOT.to_bytes(4, "little") + bytes((CHARACTER_SLOT,)))
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(b"\x0F\xB6\x05" + SELECTED_ACTOR.to_bytes(4, "little") + bytes.fromhex("83 F8 0A"))
    code.branch(bytes.fromhex("0F 87"), "vanilla")
    code.add(bytes.fromhex("69 D0 D0 01 00 00"))
    code.add(b"\x80\xBA" + (RUNTIME_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little") + b"\x00")
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(bytes.fromhex("60"))
    code.add(b"\xA0" + SELECTED_ACTOR.to_bytes(4, "little"))
    code.add(b"\xA2" + SWITCH_ACTOR.to_bytes(4, "little"))
    code.add(b"\xC6\x05" + SWITCH_ACTIVE.to_bytes(4, "little") + b"\x01")
    code.add(b"\xC6\x05" + SWITCH_SELECTION.to_bytes(4, "little") + b"\xFF")
    # Prefer Squall's current one-hot GF when it exists.
    code.add(b"\x0F\xB7\x05" + (SAVEMAP_CHARACTER_BASE + GF_MASK_OFFSET).to_bytes(4, "little"))
    code.add(bytes.fromhex("85 C0"))
    code.branch(bytes.fromhex("0F 84"), "scan")
    code.add(bytes.fromhex("8D 48 FF 85 C1"))
    code.branch(bytes.fromhex("0F 85"), "scan")
    code.add(bytes.fromhex("0F BC C0 6B D0 44"))
    code.add(b"\xF6\x82" + (GF_DATA_BASE + GF_EXISTS_OFFSET).to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 84"), "scan")
    code.add(b"\xA2" + SWITCH_SELECTION.to_bytes(4, "little"))
    code.branch(b"\xE9", "opened")
    code.label("scan")
    code.add(bytes.fromhex("31 C9"))
    code.label("scan_loop")
    code.add(bytes.fromhex("6B D1 44"))
    code.add(b"\xF6\x82" + (GF_DATA_BASE + GF_EXISTS_OFFSET).to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 85"), "found")
    code.add(bytes.fromhex("41 83 F9 10"))
    code.branch(bytes.fromhex("0F 8C"), "scan_loop")
    code.branch(b"\xE9", "opened")
    code.label("found")
    code.add(b"\x88\x0D" + SWITCH_SELECTION.to_bytes(4, "little"))
    code.label("opened")
    code.add(b"\x68" + CLOSE_CAVE.to_bytes(4, "little"))
    code.add(b"\x68" + DRAW_CAVE.to_bytes(4, "little"))
    code.add(b"\x68" + UPDATE_CAVE.to_bytes(4, "little"))
    code.add(bytes.fromhex("6A 05"))
    code.call(REGISTER_SLOT)
    code.add(bytes.fromhex("83 C4 10 6A 03 6A 05"))
    code.call(SET_SLOT_STATE)
    code.add(bytes.fromhex("83 C4 08 6A 04"))
    code.call(HIDE_SLOT)
    code.add(bytes.fromhex("83 C4 04"))
    code.add(b"\xC7\x05" + PREPARED_COUNT.to_bytes(4, "little") + bytes.fromhex("00 00 00 00"))
    code.add(bytes.fromhex("61"))
    code.jump(CONTROLLER_COMMON_TAIL)
    code.label("vanilla")
    code.add(COMMAND_CONFIRM_ORIGINAL)
    code.jump(COMMAND_CONFIRM_HOOK + len(COMMAND_CONFIRM_ORIGINAL))
    return code.finish()


def _update_payload() -> bytes:
    code = _Code(UPDATE_CAVE)
    code.add(bytes.fromhex("53 56 57 6A 00"))
    code.call(READ_INPUT)
    code.add(bytes.fromhex("83 C4 04 89 C7 A8 10"))
    code.branch(bytes.fromhex("0F 85"), "cancel")
    code.add(bytes.fromhex("A8 08"))
    code.branch(bytes.fromhex("0F 85"), "confirm")
    code.add(bytes.fromhex("A9 00 10 00 00"))
    code.branch(bytes.fromhex("0F 85"), "previous")
    code.add(bytes.fromhex("A9 00 40 00 00"))
    code.branch(bytes.fromhex("0F 85"), "next")
    code.branch(b"\xE9", "done")
    code.label("next")
    code.add(b"\x0F\xB6\x0D" + SWITCH_SELECTION.to_bytes(4, "little") + bytes.fromhex("BB 10 00 00 00"))
    code.label("next_loop")
    code.add(bytes.fromhex("41 83 E1 0F 6B D1 44"))
    code.add(b"\xF6\x82" + (GF_DATA_BASE + GF_EXISTS_OFFSET).to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 85"), "select")
    code.add(bytes.fromhex("4B"))
    code.branch(bytes.fromhex("0F 85"), "next_loop")
    code.branch(b"\xE9", "done")
    code.label("previous")
    code.add(b"\x0F\xB6\x0D" + SWITCH_SELECTION.to_bytes(4, "little") + bytes.fromhex("BB 10 00 00 00"))
    code.label("previous_loop")
    code.add(bytes.fromhex("49 83 E1 0F 6B D1 44"))
    code.add(b"\xF6\x82" + (GF_DATA_BASE + GF_EXISTS_OFFSET).to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 85"), "select")
    code.add(bytes.fromhex("4B"))
    code.branch(bytes.fromhex("0F 85"), "previous_loop")
    code.branch(b"\xE9", "done")
    code.label("select")
    code.add(b"\x88\x0D" + SWITCH_SELECTION.to_bytes(4, "little"))
    code.branch(b"\xE9", "done")
    code.label("confirm")
    code.add(b"\x0F\xB6\x05" + SWITCH_SELECTION.to_bytes(4, "little") + bytes.fromhex("83 F8 0F"))
    code.branch(bytes.fromhex("0F 87"), "done")
    code.add(bytes.fromhex("50"))
    code.add(b"\x0F\xB6\x05" + SWITCH_ACTOR.to_bytes(4, "little") + bytes.fromhex("50"))
    code.call(REFRESH_CAVE)
    code.add(bytes.fromhex("83 C4 08"))
    code.label("cancel")
    code.call(CLOSE_CAVE)
    code.label("done")
    code.add(bytes.fromhex("5F 5E 5B C3"))
    return code.finish()


def _draw_payload() -> bytes:
    code = _Code(DRAW_CAVE)
    code.add(bytes.fromhex("53 55 56 57"))
    code.add(bytes.fromhex("8B 6C 24 14 8B 74 24 18 31 FF"))
    code.label("loop")
    code.add(bytes.fromhex("6B DF 44"))
    code.add(b"\xF6\x83" + (GF_DATA_BASE + GF_EXISTS_OFFSET).to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 84"), "advance")
    code.add(b"\x0F\xB6\x0D" + SWITCH_SELECTION.to_bytes(4, "little") + bytes.fromhex("39 F9"))
    code.branch(bytes.fromhex("0F 85"), "name")
    code.add(bytes.fromhex("89 F8 83 E0 07 6B C0 12 83 C0 28 BA 28 00 00 00 F7 C7 08 00 00 00"))
    code.branch(bytes.fromhex("0F 84"), "cursor_x")
    code.add(bytes.fromhex("BA AA 00 00 00"))
    code.label("cursor_x")
    code.add(bytes.fromhex("6A 07"))
    code.address_of(b"\x68", "cursor")
    code.add(bytes.fromhex("50 52 56 55"))
    code.call(DRAW_TEXT)
    code.add(bytes.fromhex("83 C4 18 89 C6"))
    code.label("name")
    code.add(bytes.fromhex("89 F8 83 E0 07 6B C0 12 83 C0 28 BA 34 00 00 00 F7 C7 08 00 00 00"))
    code.branch(bytes.fromhex("0F 84"), "name_x")
    code.add(bytes.fromhex("BA B6 00 00 00"))
    code.label("name_x")
    code.add(bytes.fromhex("81 C3"))
    code.add(GF_DATA_BASE.to_bytes(4, "little"))
    code.add(bytes.fromhex("6A 07 53 50 52 56 55"))
    code.call(DRAW_TEXT)
    code.add(bytes.fromhex("83 C4 18 89 C6"))
    code.label("advance")
    code.add(bytes.fromhex("47 83 FF 10"))
    code.branch(bytes.fromhex("0F 8C"), "loop")
    code.add(bytes.fromhex("89 F0 5F 5E 5D 5B C3"))
    code.label("cursor")
    code.add(CURSOR_TEXT)
    return code.finish()


# Exact 0x48B344..0x48B5A4 derived-state copy. The current-HP store and the
# external magic-present branch are patched by _clone_payload.
_DERIVED_TEMPLATE = bytes.fromhex("""
0f bf 86 74 01 00 00 0f bf 8e 72 01 00 00 89 82 2c 7b d2 01 8a 86 b8 01 00 00 89 8a 28 7b d2 01 8a 8e bb 01 00 00 88 82 cc 7b d2 01 8a 86 bc 01 00 00 88 8a cd 7b d2 01 8a 8e bd 01 00 00 88 82 ce 7b d2 01 8a 86 be 01 00 00 88 8a cf 7b d2 01 8a 8e bf 01 00 00 88 82 d0 7b d2 01 8a 86 c0 01 00 00 88 8a d1 7b d2 01 8a 8e c2 01 00 00 88 82 d2 7b d2 01 8a 86 c1 01 00 00 88 8a d4 7b d2 01 88 82 d3 7b d2 01 53 33 c0 8d 8e 82 00 00 00 80 39 00 0f 85 ec 01 00 00 40 83 c1 05 83 f8 20 7c ee 8b 82 18 7b d2 01 25 ff ff ff bf 89 82 18 7b d2 01 57 8d 8a 54 7b d2 01 8d 86 94 01 00 00 bf 08 00 00 00 66 8b 18 83 c0 02 66 89 19 83 c1 02 4f 75 f1 8d 9a a0 7b d2 01 b9 0a 00 00 00 b8 64 64 64 64 8b fb f3 ab 8a 86 a6 01 00 00 8a 8e a4 01 00 00 88 82 b4 7b d2 01 88 82 a2 7b d2 01 8a 86 a5 01 00 00 88 0b 8a 8e a7 01 00 00 88 82 a1 7b d2 01 8a 86 a8 01 00 00 88 8a a3 7b d2 01 8a 8e a9 01 00 00 88 82 a4 7b d2 01 8a 86 aa 01 00 00 88 8a a5 7b d2 01 8a 8e af 01 00 00 88 82 a6 7b d2 01 8a 86 ab 01 00 00 88 8a b6 7b d2 01 8a 8e ac 01 00 00 88 82 a8 7b d2 01 8a 86 ad 01 00 00 88 8a aa 7b d2 01 8a 8e ae 01 00 00 88 82 ab 7b d2 01 8a 86 b0 01 00 00 88 8a b1 7b d2 01 8b 8e 8c 01 00 00 88 82 b7 7b d2 01 66 8b 86 b4 01 00 00 89 8a 30 7b d2 01 8a 8e b6 01 00 00 66 89 82 96 7b d2 01 8a 86 c4 01 00 00 88 8a ca 7b d2 01 8a 8e c5 01 00 00 8b b6 90 01 00 00 88 82 d5 7b d2 01 88 8a d6 7b d2 01 f7 c6 00 80 00 00 b0 c8 5f 74 0c 88 82 ab 7b d2 01 88 82 aa 7b d2 01 f7 c6 00 00 08 00 74 62 88 82 b8 7b d2 01 88 82 c0 7b d2 01 88 82 b7 7b d2 01 88 82 b6 7b d2 01 88 82 b4 7b d2 01 88 82 b2 7b d2 01 88 82 b1 7b d2 01 88 82 ab 7b d2 01 88 82 aa 7b d2 01 88 82 a8 7b d2 01 88 82 a6 7b d2 01 88 82 a5 7b d2 01 88 82 a4 7b d2 01 88 82 a3 7b d2 01 88 82 a2 7b d2 01 88 82 a1 7b d2 01 88 03 8d b2 90 7b d2 01 8b 92 28 7b d2 01 56 52 55 e8 be 8d 00 00 83 c4 0c
""")


def _clone_payload() -> bytes:
    payload = bytearray(_DERIVED_TEMPLATE)
    # Never overwrite live current HP with the parser's rebuilt value.
    hp_store = 0x0048B35E - 0x0048B344
    payload[hp_store:hp_store + 6] = b"\x90" * 6
    # Redirect the spell-present branch to a local tail.
    magic_branch = 0x0048B3D6 - 0x0048B344
    magic_stub = len(payload) + 2  # POP EBX; RET precede the stub.
    displacement = magic_stub - (magic_branch + 6)
    payload[magic_branch + 2:magic_branch + 6] = displacement.to_bytes(4, "little", signed=True)
    # Relocate the safe low-HP helper call.
    call_offset = 0x0048B59D - 0x0048B344
    source = CLONE_CAVE + call_offset
    payload[call_offset:call_offset + 5] = _near(source, UPDATE_LOW_HP, b"\xE8")
    payload.extend(bytes.fromhex("5B C3"))
    stub_address = CLONE_CAVE + len(payload)
    payload.extend(b"\x8B\x82" + (PARTICIPANT_BASE + 8).to_bytes(4, "little"))
    payload.extend(bytes.fromhex("0D 00 00 00 40"))
    payload.extend(b"\x89\x82" + (PARTICIPANT_BASE + 8).to_bytes(4, "little"))
    target = CLONE_CAVE + (0x0048B3F0 - 0x0048B344)
    payload.extend(_near(stub_address + 17, target))
    return bytes(payload)


def _refresh_payload() -> bytes:
    code = _Code(REFRESH_CAVE)
    code.add(bytes.fromhex("60"))
    # PUSHAD stack: return +32, actor +36, GF +40.
    code.add(bytes.fromhex("8B 6C 24 24 8B 4C 24 28 69 F5 D0 01 00 00 81 C6"))
    code.add(RUNTIME_ACTOR_BASE.to_bytes(4, "little"))
    code.add(bytes.fromhex("0F B6 86 C3 01 00 00 69 F8 98 00 00 00 81 C7"))
    code.add(SAVEMAP_CHARACTER_BASE.to_bytes(4, "little"))
    code.add(b"\xA2" + SWITCH_CHAR_ID.to_bytes(4, "little"))
    code.add(b"\x89\x3D" + SWITCH_SAVE_PTR.to_bytes(4, "little"))
    # Snapshot parser-sensitive state.
    for source, target, size in (
        (0x14, SNAP_RUNTIME_14, 4), (0x18, SNAP_RUNTIME_18, 4),
        (0x1C, SNAP_RUNTIME_1C, 2), (0x172, SNAP_RUNTIME_HP, 2),
    ):
        if size == 4:
            code.add(b"\x8B\x86" + source.to_bytes(4, "little"))
            code.add(b"\xA3" + target.to_bytes(4, "little"))
        else:
            code.add(b"\x66\x8B\x86" + source.to_bytes(4, "little"))
            code.add(b"\x66\xA3" + target.to_bytes(4, "little"))
    code.add(bytes.fromhex("66 8B 07"))
    code.add(b"\x66\xA3" + SNAP_SAVE_HP.to_bytes(4, "little"))
    code.add(b"\xA0" + GLOBAL_PASSIVE_BYTE.to_bytes(4, "little"))
    code.add(b"\xA2" + SNAP_GLOBAL.to_bytes(4, "little"))
    # Transfer the selected GF to the target character only.
    code.add(bytes.fromhex("B8 01 00 00 00 D3 E0 89 C3 89 C2 F7 D2"))
    code.add(b"\xBF" + (SAVEMAP_CHARACTER_BASE + GF_MASK_OFFSET).to_bytes(4, "little"))
    code.add(bytes.fromhex("B9 08 00 00 00"))
    code.label("clear_loop")
    code.add(bytes.fromhex("66 21 17 81 C7 98 00 00 00 49"))
    code.branch(bytes.fromhex("0F 85"), "clear_loop")
    code.add(b"\x8B\x3D" + SWITCH_SAVE_PTR.to_bytes(4, "little"))
    code.add(bytes.fromhex("66 89 5F 58"))
    # Rebuild runtime actor and spell metadata through vanilla functions.
    code.add(b"\x0F\xB6\x05" + SWITCH_CHAR_ID.to_bytes(4, "little"))
    code.add(bytes.fromhex("55 50"))
    code.call(PARSE_CHARACTER)
    code.add(bytes.fromhex("83 C4 08"))
    code.add(b"\x0F\xB6\x05" + SWITCH_CHAR_ID.to_bytes(4, "little"))
    code.add(bytes.fromhex("55 50"))
    code.call(PARSE_MAGIC)
    code.add(bytes.fromhex("83 C4 08"))
    # Restore parser-sensitive state.
    for target, source, size in (
        (0x14, SNAP_RUNTIME_14, 4), (0x18, SNAP_RUNTIME_18, 4),
        (0x1C, SNAP_RUNTIME_1C, 2), (0x172, SNAP_RUNTIME_HP, 2),
    ):
        if size == 4:
            code.add(b"\xA1" + source.to_bytes(4, "little"))
            code.add(b"\x89\x86" + target.to_bytes(4, "little"))
        else:
            code.add(b"\x66\xA1" + source.to_bytes(4, "little"))
            code.add(b"\x66\x89\x86" + target.to_bytes(4, "little"))
    code.add(b"\x8B\x3D" + SWITCH_SAVE_PTR.to_bytes(4, "little"))
    code.add(b"\x66\xA1" + SNAP_SAVE_HP.to_bytes(4, "little") + bytes.fromhex("66 89 07"))
    code.add(b"\xA0" + SNAP_GLOBAL.to_bytes(4, "little"))
    code.add(b"\xA2" + GLOBAL_PASSIVE_BYTE.to_bytes(4, "little"))
    code.add(bytes.fromhex("89 EA 69 D2 D0 00 00 00"))
    code.call(CLONE_CAVE)
    code.add(bytes.fromhex("61 C3"))
    return code.finish()


def build_component() -> str:
    caves = (
        (DESCRIPTOR_CAVE, _descriptor_payload()),
        (LABEL_CAVE, _resolver_payload(LABEL_CAVE, LABEL_ORIGINAL, SWITCH_TEXT)),
        (DESCRIPTION_CAVE, _resolver_payload(DESCRIPTION_CAVE, DESCRIPTION_ORIGINAL, SWITCH_DESCRIPTION)),
        (COMMAND_CONFIRM_CAVE, _command_confirm_payload()),
        (UPDATE_CAVE, _update_payload()),
        (CLOSE_CAVE, _close_payload()),
        (DRAW_CAVE, _draw_payload()),
        (REFRESH_CAVE, _refresh_payload()),
        (CLONE_CAVE, _clone_payload()),
    )
    for (address, payload), (next_address, _) in zip(caves, caves[1:]):
        if address + len(payload) > next_address:
            raise AssertionError(f"Switch cave at {address:#x} overlaps the next cave")
    if caves[-1][0] + len(caves[-1][1]) > STATE_BASE:
        raise AssertionError("Switch derived-state clone overlaps Switch state")
    lines = ["# Squall Switch: guarded in-battle GF overlay and selective live refresh."]
    for address, payload in caves:
        lines.append(f"{address:X}:{len(payload):X}")
    lines.append(f"{STATE_BASE:X}:20")
    for hook, cave, original in (
        (DESCRIPTOR_HOOK, DESCRIPTOR_CAVE, DESCRIPTOR_ORIGINAL),
        (LABEL_HOOK, LABEL_CAVE, LABEL_ORIGINAL),
        (DESCRIPTION_HOOK, DESCRIPTION_CAVE, DESCRIPTION_ORIGINAL),
        (COMMAND_CONFIRM_HOOK, COMMAND_CONFIRM_CAVE, COMMAND_CONFIRM_ORIGINAL),
    ):
        patch = _near(hook, cave) + b"\x90" * (len(original) - 5)
        lines.append(f"{hook:X} = {patch.hex(' ').upper()}")
    for address, payload in caves:
        lines.append(f"{address:X} = {payload.hex(' ').upper()}")
    lines.append(f"{STATE_BASE:X} = {'00 ' * 0x20}".rstrip())
    lines.append("")
    return "\n".join(lines)
