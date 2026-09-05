"""Guarded fixed-command Shoot runtime slice for GitHub issue #54."""

from __future__ import annotations

IRVINE = 2
SHOT = 0x0E
CHARACTER_SLOT = 2
ACTIVE_SLOT = 0x01D76843
BATTLE_ACTOR_BASE = 0x01CFF000
BATTLE_ACTOR_STRIDE = 0x1D0
CHARACTER_ID_OFFSET = 0x1C3
SHOT_ACTOR = 0x01D27B0F
PARTICIPANT_BASE = 0x01D27B10
PARTICIPANT_STRIDE = 0xD0
IRVINE_WEAPON_ID = 0x01CFE221
WEAPON_BASE = 0x01CF7408
WEAPON_STRIDE = 12
SHOTS_OFFSET = 3

QUEUE_CALL = 0x004BC492
QUEUE_ORIGINAL = bytes.fromhex("E8 89 88 FC FF")
QUEUE_FUNCTION = 0x00484D20
QUEUE_CALLS = (0x00483EE5, 0x004BB5DC, 0x004BB63E, 0x004BB69F, QUEUE_CALL)
UI_OPEN_CALL = 0x0048D1E4
UI_OPEN_FUNCTION = 0x004AD7D0
UI_OPEN_CAVE = 0x0279F640
POST_FIRE_HOOK = 0x004ADAA1
POST_FIRE_ORIGINAL = bytes.fromhex("A0 20 A2 D2 01")
SHOT_UI_UNREGISTER_CALL = 0x004ADBAC
SHOT_UI_UNREGISTER_ORIGINAL = bytes.fromhex("E8 1F BF 00 00")
UNREGISTER_UI = 0x004B9AD0
RETURN_TO_COMMANDS = 0x00485030
READY_HOOK = 0x004843D5
READY_ORIGINAL = bytes.fromhex("8B 56 FC 8B 06")
DESCRIPTOR_HOOK = 0x00495805
DESCRIPTOR_ORIGINAL = bytes.fromhex("8B 86 90 01 00 00")

DESCRIPTOR_CAVE = 0x0279F600
QUEUE_CAVE = 0x0279F660
POST_FIRE_CAVE = 0x0279F6C0
FINISH_CAVE = 0x0279F7A0
READY_CAVE = 0x0279F820
ACTIVE_STATE = 0x0279F880  # 0 off, 1 opened, 2 fired
SHOOT_LOCK = 0x0279F881


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


def _near(source: int, target: int, opcode: bytes = b"\xE9") -> bytes:
    return opcode + (target - source - 5).to_bytes(4, "little", signed=True)


def _call(code: _Code, target: int) -> None:
    code.add(_near(code.address + len(code.data), target, b"\xE8"))


def _jump(code: _Code, target: int) -> None:
    code.add(_near(code.address + len(code.data), target))


def _queue_payload() -> bytes:
    """Mark only a confirmed state-12 Irvine action record for command 0x0E."""
    code = _Code(QUEUE_CAVE)
    # The detour CALL adds its own return address. The original cdecl arguments
    # therefore begin at ESP+4: index, actor, command, parameter, target.
    code.add(bytes.fromhex("83 7C 24 0C 0E"))  # command argument
    code.branch(bytes.fromhex("0F 85"), "queue")
    code.add(b"\x80\x3D" + ACTIVE_SLOT.to_bytes(4, "little") + bytes((CHARACTER_SLOT,)))
    code.branch(bytes.fromhex("0F 85"), "queue")
    code.add(bytes.fromhex("8B 4C 24 08 83 F9 02"))  # actor argument
    code.branch(bytes.fromhex("0F 87"), "queue")
    code.add(bytes.fromhex("69 C9 D0 01 00 00"))
    code.add(b"\x80\xB9" + (BATTLE_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little") + bytes((IRVINE,)))
    code.branch(bytes.fromhex("0F 85"), "queue")
    code.add(b"\xC6\x05" + ACTIVE_STATE.to_bytes(4, "little") + b"\x01")
    code.label("queue")
    _jump(code, QUEUE_FUNCTION)  # tail jump preserves the five cdecl arguments
    return code.finish()


def _descriptor_payload() -> bytes:
    """Install vanilla Shot in Irvine's fixed slot and apply the lock flag."""
    code = _Code(DESCRIPTOR_CAVE)
    code.add(DESCRIPTOR_ORIGINAL)
    code.add(b"\x80\xBE" + CHARACTER_ID_OFFSET.to_bytes(4, "little") + bytes((IRVINE,)))
    code.branch(bytes.fromhex("0F 85"), "done")
    # Runtime descriptor bytes: command 0x0E, menu/submenu 0x84, enemy target
    # 0x40, flags 0. Bit 1 of flags is the vanilla disabled/grey state.
    code.add(bytes.fromhex("C7 46 26 0E 84 40 00"))
    code.add(b"\x80\x3D" + SHOOT_LOCK.to_bytes(4, "little") + b"\x00")
    code.branch(bytes.fromhex("0F 84"), "done")
    code.add(bytes.fromhex("80 4E 29 02"))
    code.label("done")
    _jump(code, DESCRIPTOR_HOOK + len(DESCRIPTOR_ORIGINAL))
    return code.finish()


def _post_fire_payload() -> bytes:
    code = _Code(POST_FIRE_CAVE)
    code.add(bytes.fromhex("9C 60"))
    # State 1 is the first pending shot; state 2 means at least one shot fired.
    # Both states must charge ATB. Only state 0 belongs to vanilla Shot.
    code.add(b"\x80\x3D" + ACTIVE_STATE.to_bytes(4, "little") + b"\x00")
    code.branch(bytes.fromhex("0F 84"), "replay")
    code.add(b"\x0F\xB6\x0D" + SHOT_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("83 F9 0A"))
    code.branch(bytes.fromhex("0F 87"), "replay")
    code.add(bytes.fromhex("69 D1 D0 01 00 00"))
    code.add(b"\x80\xBA" + (BATTLE_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little") + bytes((IRVINE,)))
    code.branch(bytes.fromhex("0F 85"), "replay")
    code.add(b"\x0F\xB6\x15" + IRVINE_WEAPON_ID.to_bytes(4, "little"))
    code.add(bytes.fromhex("8D 14 52 C1 E2 02"))
    code.add(b"\x0F\xB6\x8A" + (WEAPON_BASE + SHOTS_OFFSET).to_bytes(4, "little"))
    code.add(bytes.fromhex("83 F9 01"))
    code.branch(bytes.fromhex("0F 82"), "fallback")
    code.add(bytes.fromhex("83 F9 0A"))
    code.branch(bytes.fromhex("0F 86"), "value_ok")
    code.label("fallback")
    code.add(bytes.fromhex("B9 01 00 00 00"))
    code.label("value_ok")
    code.add(b"\x0F\xB6\x15" + SHOT_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("69 D2 D0 00 00 00"))
    code.add(b"\x8B\x82" + (PARTICIPANT_BASE + 0x10).to_bytes(4, "little"))
    code.add(bytes.fromhex("8D 44 08 FF 52 33 D2 F7 F1 5A"))  # preserve actor offset across DIV
    code.add(b"\x8B\x9A" + (PARTICIPANT_BASE + 0x14).to_bytes(4, "little"))
    code.add(bytes.fromhex("2B D8"))
    code.branch(bytes.fromhex("0F 8D"), "store")
    code.add(bytes.fromhex("33 DB"))
    code.label("store")
    code.add(b"\x89\x9A" + (PARTICIPANT_BASE + 0x14).to_bytes(4, "little"))
    code.add(b"\xC6\x05" + ACTIVE_STATE.to_bytes(4, "little") + b"\x02")
    code.add(bytes.fromhex("85 DB"))
    code.branch(bytes.fromhex("0F 85"), "replay")
    code.add(bytes.fromhex("C6 05 5B 67 D7 01 01"))  # native Shot close request at zero ATB
    code.label("replay")
    code.add(bytes.fromhex("61 9D"))
    code.add(POST_FIRE_ORIGINAL)
    _jump(code, POST_FIRE_HOOK + 5)
    return code.finish()


def _ui_open_payload() -> bytes:
    code = _Code(UI_OPEN_CAVE)
    code.add(b"\x80\x3D" + ACTIVE_STATE.to_bytes(4, "little") + b"\x00")
    code.branch(bytes.fromhex("0F 84"), "vanilla")
    # Fixed Shoot has no Limit Break crisis roll. Use the native crisis-level-1 Shot
    # duration instead of indexing its table with an unset crisis level.
    code.add(bytes.fromhex("0F B6 05 4C 8B CF 01 89 44 24 08"))
    code.label("vanilla")
    _jump(code, UI_OPEN_FUNCTION)
    return code.finish()


def _finish_payload() -> bytes:
    """Unregister Shot slot 6 first, then return custom Shoot to commands."""
    code = _Code(FINISH_CAVE)
    # SHOT_UI_UNREGISTER_CALL is replaced with a JMP, not a CALL. Entry to this
    # cave therefore has no detour return address. The original four unregister
    # arguments, plus the two earlier call arguments cleaned by 0x4ADBB1, must
    # remain untouched until the vanilla caller performs ADD ESP,18.
    _call(code, UNREGISTER_UI)
    code.add(b"\x80\x3D" + ACTIVE_STATE.to_bytes(4, "little") + b"\x00")
    code.branch(bytes.fromhex("0F 84"), "return")
    code.add(b"\x80\x3D" + ACTIVE_STATE.to_bytes(4, "little") + b"\x02")
    # Cancel before firing restores commands without locking Shoot.
    code.branch(bytes.fromhex("0F 85"), "no_lock")
    code.add(b"\xC6\x05" + SHOOT_LOCK.to_bytes(4, "little") + b"\x01")
    code.label("no_lock")
    code.add(b"\xC6\x05" + ACTIVE_STATE.to_bytes(4, "little") + b"\x00")
    code.add(b"\x0F\xB6\x05" + SHOT_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("50"))
    _call(code, RETURN_TO_COMMANDS)
    code.add(bytes.fromhex("83 C4 04"))
    code.label("return")
    _jump(code, SHOT_UI_UNREGISTER_CALL + 5)
    return code.finish()


def _ready_payload() -> bytes:
    code = _Code(READY_CAVE)
    code.add(READY_ORIGINAL)
    code.add(bytes.fromhex("9C 51"))
    code.add(bytes.fromhex("83 FF 0A"))
    code.branch(bytes.fromhex("0F 87"), "done")
    code.add(bytes.fromhex("69 CF D0 01 00 00"))
    code.add(b"\x80\xB9" + (BATTLE_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little") + bytes((IRVINE,)))
    code.branch(bytes.fromhex("0F 85"), "done")
    code.add(b"\xC6\x05" + SHOOT_LOCK.to_bytes(4, "little") + b"\x00")
    code.label("done")
    code.add(bytes.fromhex("59 9D"))
    _jump(code, READY_HOOK + 5)
    return code.finish()


def build_component() -> str:
    # The fixed-menu resolver owns all custom command names. Shoot emits it even
    # when used alone. When the full fixed menu is composed after Switch, this
    # later hook also preserves Switch and Selphie's Summon name.
    from . import fixed_command_menu

    label_payload = fixed_command_menu._command_label_payload()
    caves = (
        (DESCRIPTOR_CAVE, _descriptor_payload()),
        (QUEUE_CAVE, _queue_payload()),
        (POST_FIRE_CAVE, _post_fire_payload()),
        (FINISH_CAVE, _finish_payload()),
        (READY_CAVE, _ready_payload()),
        (UI_OPEN_CAVE, _ui_open_payload()),
    )
    lines = ["# Irvine fixed Shoot: confirmed queue, ATB cost, same-turn return and next-ready lock."]
    for address, payload in caves:
        lines.append(f"{address:X}:{len(payload):X}")
    lines.append(f"{fixed_command_menu.COMMAND_LABEL_CAVE:X}:{len(label_payload):X}")
    lines.extend((f"{ACTIVE_STATE:X}:1", f"{SHOOT_LOCK:X}:1"))
    for hook, cave in ((DESCRIPTOR_HOOK, DESCRIPTOR_CAVE),
                       (POST_FIRE_HOOK, POST_FIRE_CAVE),
                       (SHOT_UI_UNREGISTER_CALL, FINISH_CAVE), (READY_HOOK, READY_CAVE)):
        lines.append(f"{hook:X} = {_near(hook, cave).hex(' ').upper()}")
    for hook in QUEUE_CALLS:
        lines.append(f"{hook:X} = {_near(hook, QUEUE_CAVE, bytes((0xE8,))).hex(' ').upper()}")
    lines.append(f"{UI_OPEN_CALL:X} = {_near(UI_OPEN_CALL, UI_OPEN_CAVE, bytes((0xE8,))).hex(' ').upper()}")
    label_patch = _near(
        fixed_command_menu.COMMAND_LABEL_HOOK,
        fixed_command_menu.COMMAND_LABEL_CAVE,
    ) + b"\x90" * (len(fixed_command_menu.COMMAND_LABEL_ORIGINAL) - 5)
    lines.append(
        f"{fixed_command_menu.COMMAND_LABEL_HOOK:X} = {label_patch.hex(' ').upper()}"
    )
    for address, payload in caves:
        lines.append(f"{address:X} = {payload.hex(' ').upper()}")
    lines.append(
        f"{fixed_command_menu.COMMAND_LABEL_CAVE:X} = {label_payload.hex(' ').upper()}"
    )
    lines.extend((f"{ACTIVE_STATE:X} = 00", f"{SHOOT_LOCK:X} = 00", ""))
    return "\n".join(lines)
