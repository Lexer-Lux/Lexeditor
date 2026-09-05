"""Guarded FF8 battle shortcuts for Lexeditor issue #53."""

from __future__ import annotations

from . import party_switch_issue_62


DEFAULT_UNIVERSAL_ITEM = False
DEFAULT_ENHANCED_SCAN = False
# Keep the saved-settings key compatible while the editor renames the option.
DEFAULT_SCANNED_TARGET_SCAN = DEFAULT_ENHANCED_SCAN
ENHANCED_SCAN_AVAILABLE = True

# FF8 2013 Steam English, SHA-256
# 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570.
COMMAND_INPUT_HOOK = 0x004BBDF5
COMMAND_INPUT_ORIGINAL = bytes.fromhex("A8 40 8D 3C 9E")
COMMAND_EXECUTE = 0x004BBE07
COMMAND_CONTINUE = 0x004BBE01
# 004BBDFA  C6 05 53 68 D7 01 01   mov byte ptr [0x1D76853], 1
# This store sits between the hooked instruction and both continuation
# points, so every path out of the router skipped it and left the battle
# command state at 0. FF8 then tears the opened controller down on the next
# frame (Look Left and Switch flash and close) or dereferences the unset
# state and crashes (Card Game). The router performs it once, up front.
COMMAND_STATE_STORE = bytes.fromhex("C6 05 53 68 D7 01 01")
ITEM_DISABLED_FLAGS = 0x01CFF6E8
CODE_CAVE = 0x0279EE00
ITEM_DESCRIPTOR = CODE_CAVE + 0xA0
SCAN_DESCRIPTOR = CODE_CAVE + 0xA4
CODE_CAVE_LENGTH = 0xAC

MAGIC_CONTROLLER_TAIL = 0x004C88A5
MAGIC_CONTROLLER_TAIL_ORIGINAL = bytes.fromhex("E9 E6 54 03 00")
MAGIC_CONTROLLER = 0x004FDD90
MAGIC_TARGET_CANCEL = 0x004FEDBF
MAGIC_TARGET_CANCEL_ORIGINAL = bytes.fromhex("6A 02 6A 02 E8 C8 AD FB FF")
MAGIC_TARGET_CANCEL_CONTINUE = 0x004FEDC8
MENU_SOUND = 0x004A9780
MAGIC_ACTION_FINISH = 0x004FE755
MAGIC_ACTION_FINISH_ORIGINAL = bytes.fromhex("C6 05 E4 68 D7 01 12")
MAGIC_ACTION_FINISH_CONTINUE = 0x004FE75C
MAGIC_STATE_LOOP = 0x004FE768
MAGIC_MENU_STATE = 0x01D768E4
MAGIC_LIST_CALLBACK = 0x01D768D0
MAGIC_LIST_COUNT = 0x01D768F4
MAGIC_LIST_CURSOR = 0x01D768F6
MAGIC_LIST_VISIBLE_ROWS = 0x01D768F7
MAGIC_LIST_SELECTIONS = 0x01D768EC

SCAN_INIT_CAVE = 0x027A1900
SCAN_CANCEL_CAVE = 0x027A1960
SCAN_FINISH_CAVE = 0x027A19C0
SCAN_LIST_CALLBACK = 0x027A1A20
SCAN_LIST = 0x027A1A30
SCAN_ACTIVE = 0x027A1A35
SCAN_INPUT_LATCH = 0x027A1A36

SCAN_MAGIC_ID = 50
# Native 004954B0 builds ID, quantity, status-window, target, flags.
# Use positive stock for the native signed-byte debit. Restore this private
# record each time the shortcut opens; never touch actor inventory.
SCAN_LIST_BYTES = bytes((SCAN_MAGIC_ID, 1, 0x80, 0x54, 0x00))

# FF8 keeps the PlayStation logical button layout in this command-state byte:
# L1 0x04, R1 0x08, Triangle 0x10, Circle 0x20, Cross 0x40, Square 0x80.
# Square is the configurable Card Game action and the default XInput X button.
CARD_GAME_INPUT_MASK = 0x80

ITEM_DESCRIPTOR_BYTES = bytes.fromhex("04 82 D4 00")
SCAN_DESCRIPTOR_BYTES = bytes.fromhex("02 00 00 00")
INSTANT_COMMAND_BRANCH = 0x004BC7ED
DIRECT_TARGET_BRANCH = 0x004BC808


class _Code:
    def __init__(self, address: int):
        self.address = address
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    def add(self, data: bytes) -> None:
        self.data.extend(data)

    def label(self, name: str) -> None:
        self.labels[name] = len(self.data)

    def branch(self, opcode: bytes, label: str) -> None:
        self.data.extend(opcode)
        self.fixups.append((len(self.data), label))
        self.data.extend(b"\0\0\0\0")

    def finish(self) -> bytes:
        for offset, label in self.fixups:
            delta = self.address + self.labels[label] - (self.address + offset + 4)
            self.data[offset:offset + 4] = delta.to_bytes(4, "little", signed=True)
        return bytes(self.data)


def _boolean(value, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be true or false")
    return value


def _near_jump(source: int, target: int) -> bytes:
    displacement = target - (source + 5)
    return b"\xE9" + int(displacement).to_bytes(4, "little", signed=True)


def _call(code: _Code, target: int) -> None:
    source = code.address + len(code.data)
    code.add(b"\xE8" + int(target - source - 5).to_bytes(4, "little", signed=True))


def _jump(code: _Code, target: int) -> None:
    code.add(_near_jump(code.address + len(code.data), target))


def _command_payload(*, universal_item: bool, scanned_target_scan: bool,
                     party_switch: bool = False) -> bytes:
    """Build the shared battle-only shortcut router."""
    descriptor_flags = ITEM_DESCRIPTOR + 3
    code = _Code(CODE_CAVE)
    code.add(b"\x90" * 8)
    # Replay the skipped state store before any branch. It touches neither
    # AL nor the flags, so the replayed TEST below still drives the JE.
    code.add(COMMAND_STATE_STORE)
    if universal_item:
        code.add(bytes.fromhex("A8 08"))
        code.branch(bytes.fromhex("0F 84"), "after_item")
        code.add(bytes.fromhex("C6 05") + descriptor_flags.to_bytes(4, "little") + b"\x00")
        code.add(bytes.fromhex("F6 05") + ITEM_DISABLED_FLAGS.to_bytes(4, "little"))
        code.add(bytes.fromhex("01 74 07"))
        code.add(bytes.fromhex("80 0D") + descriptor_flags.to_bytes(4, "little") + b"\x02")
        code.add(b"\xBF" + ITEM_DESCRIPTOR.to_bytes(4, "little"))
        _jump(code, COMMAND_EXECUTE)
        code.label("after_item")
    if scanned_target_scan:
        code.add(bytes.fromhex("A8") + bytes((CARD_GAME_INPUT_MASK,)))
        code.branch(bytes.fromhex("0F 84"), "scan_released")
        code.add(b"\x80\x3D" + SCAN_INPUT_LATCH.to_bytes(4, "little") + b"\x00")
        code.branch(bytes.fromhex("0F 85"), "after_scan")
        code.add(b"\xC6\x05" + SCAN_INPUT_LATCH.to_bytes(4, "little") + b"\x01")
        code.add(b"\xC6\x05" + SCAN_ACTIVE.to_bytes(4, "little") + b"\x01")
        code.add(b"\xBF" + SCAN_DESCRIPTOR.to_bytes(4, "little"))
        _jump(code, COMMAND_EXECUTE)
        code.label("scan_released")
        code.add(b"\xC6\x05" + SCAN_INPUT_LATCH.to_bytes(4, "little") + b"\x00")
        code.label("after_scan")
    code.label("replay")
    code.add(COMMAND_INPUT_ORIGINAL)
    _jump(code, COMMAND_CONTINUE)
    payload = bytearray(code.finish())
    if len(payload) > ITEM_DESCRIPTOR - CODE_CAVE:
        raise AssertionError("Battle shortcut router exceeded its fixed cave")
    payload.extend(b"\x90" * (ITEM_DESCRIPTOR - CODE_CAVE - len(payload)))
    payload.extend(ITEM_DESCRIPTOR_BYTES)
    payload.extend(SCAN_DESCRIPTOR_BYTES)
    payload.extend(b"\x90" * (CODE_CAVE_LENGTH - len(payload)))
    if len(payload) != CODE_CAVE_LENGTH:
        raise AssertionError("Battle shortcut router length changed")
    return bytes(payload)


def _scan_init_payload() -> bytes:
    """Enter native target selection after the Magic controller initializes."""
    code = _Code(SCAN_INIT_CAVE)
    _call(code, MAGIC_CONTROLLER)
    code.add(b"\x80\x3D" + SCAN_ACTIVE.to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 85"), "done")
    code.add(b"\xC7\x05" + SCAN_LIST.to_bytes(4, "little")
             + SCAN_LIST_BYTES[:4])
    code.add(b"\xC7\x05" + MAGIC_LIST_CALLBACK.to_bytes(4, "little")
             + SCAN_LIST_CALLBACK.to_bytes(4, "little"))
    code.add(b"\xC6\x05" + MAGIC_LIST_COUNT.to_bytes(4, "little") + b"\x01")
    code.add(b"\xC6\x05" + MAGIC_LIST_CURSOR.to_bytes(4, "little") + b"\x00")
    code.add(b"\xC6\x05" + MAGIC_LIST_VISIBLE_ROWS.to_bytes(4, "little") + b"\x01")
    code.add(b"\xC6\x05" + MAGIC_LIST_SELECTIONS.to_bytes(4, "little") + b"\x00")
    code.add(b"\xC6\x05" + MAGIC_MENU_STATE.to_bytes(4, "little") + b"\x08")
    code.label("done")
    code.add(b"\xC3")
    return code.finish()


def _scan_cancel_payload() -> bytes:
    """Use the native Magic cancel states when Scan targeting is cancelled."""
    code = _Code(SCAN_CANCEL_CAVE)
    code.add(b"\x80\x3D" + SCAN_ACTIVE.to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(b"\xC6\x05" + SCAN_ACTIVE.to_bytes(4, "little") + b"\x00")
    code.add(b"\xC6\x05" + MAGIC_MENU_STATE.to_bytes(4, "little") + b"\x06")
    code.add(bytes.fromhex("C6 44 24 10 06"))
    _jump(code, MAGIC_STATE_LOOP)
    code.label("vanilla")
    code.add(bytes.fromhex("6A 02 6A 02"))
    _call(code, 0x004B9B90)
    _jump(code, MAGIC_TARGET_CANCEL_CONTINUE)
    return code.finish()


def _scan_finish_payload() -> bytes:
    """Queue Scan normally, then close the menu without spending the turn."""
    code = _Code(SCAN_FINISH_CAVE)
    code.add(b"\x80\x3D" + SCAN_ACTIVE.to_bytes(4, "little") + b"\x01")
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(b"\xC6\x05" + SCAN_ACTIVE.to_bytes(4, "little") + b"\x00")
    code.add(b"\xC6\x05" + MAGIC_MENU_STATE.to_bytes(4, "little") + b"\x06")
    code.add(bytes.fromhex("C6 44 24 10 06"))
    _jump(code, MAGIC_STATE_LOOP)
    code.label("vanilla")
    code.add(MAGIC_ACTION_FINISH_ORIGINAL)
    _jump(code, MAGIC_ACTION_FINISH_CONTINUE)
    return code.finish()


def build_hext(*, universal_item: bool = DEFAULT_UNIVERSAL_ITEM,
               scanned_target_scan: bool = DEFAULT_SCANNED_TARGET_SCAN,
               party_switch: bool = party_switch_issue_62.DEFAULT_PARTY_SWITCH) -> str:
    """Build all enabled battle-only shortcuts under one input hook."""
    universal_item = _boolean(universal_item, "Universal Item")
    scanned_target_scan = _boolean(scanned_target_scan, "Enhanced Scan")
    party_switch = _boolean(party_switch, "FF10-style Party Switch")
    if not universal_item and not scanned_target_scan:
        return party_switch_issue_62.build_hext(enabled=party_switch)

    payload = _command_payload(
        universal_item=universal_item,
        scanned_target_scan=scanned_target_scan,
        party_switch=party_switch,
    )
    hook = _near_jump(COMMAND_INPUT_HOOK, CODE_CAVE)
    lines = [
        "# Universal Item uses Look Right / RB; Enhanced Scan uses Card Game / X in battle commands.",
        f"{CODE_CAVE:X}:{CODE_CAVE_LENGTH:X}",
        f"{COMMAND_INPUT_HOOK:X} = {hook.hex(' ').upper()}",
        f"{CODE_CAVE:X} = {payload.hex(' ').upper()}",
    ]
    if scanned_target_scan:
        init_payload = _scan_init_payload()
        cancel_payload = _scan_cancel_payload()
        finish_payload = _scan_finish_payload()
        callback_payload = b"\xB8" + SCAN_LIST.to_bytes(4, "little") + b"\xC3"
        lines.extend((
            "# Enhanced Scan uses FF8's native Magic target, action-producer, and queue path.",
            "# Its private one-entry list avoids Magic inventory lookup and stock consumption.",
            "# Native Magic cancel teardown returns the actor without spending the turn.",
            f"{SCAN_INIT_CAVE:X}:{len(init_payload):X}",
            f"{SCAN_CANCEL_CAVE:X}:{len(cancel_payload):X}",
            f"{SCAN_FINISH_CAVE:X}:{len(finish_payload):X}",
            f"{SCAN_LIST_CALLBACK:X}:{len(callback_payload):X}",
            f"{SCAN_LIST:X}:{len(SCAN_LIST_BYTES):X}",
            f"{SCAN_ACTIVE:X}:2",
            f"{MAGIC_CONTROLLER_TAIL:X} = {_near_jump(MAGIC_CONTROLLER_TAIL, SCAN_INIT_CAVE).hex(' ').upper()}",
            f"{MAGIC_TARGET_CANCEL:X} = {_near_jump(MAGIC_TARGET_CANCEL, SCAN_CANCEL_CAVE).hex(' ').upper()} 90 90 90 90",
            f"{MAGIC_ACTION_FINISH:X} = {_near_jump(MAGIC_ACTION_FINISH, SCAN_FINISH_CAVE).hex(' ').upper()} 90 90",
            f"{SCAN_INIT_CAVE:X} = {init_payload.hex(' ').upper()}",
            f"{SCAN_CANCEL_CAVE:X} = {cancel_payload.hex(' ').upper()}",
            f"{SCAN_FINISH_CAVE:X} = {finish_payload.hex(' ').upper()}",
            f"{SCAN_LIST_CALLBACK:X} = {callback_payload.hex(' ').upper()}",
            f"{SCAN_LIST:X} = {SCAN_LIST_BYTES.hex(' ').upper()}",
            f"{SCAN_ACTIVE:X} = 00 00",
        ))
    lines.append("")
    return "\n".join(lines)
