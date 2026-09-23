"""Issue-local FF8 inventory auto-sort patch for GitHub issue #50.

FF8's Item controller implements Sort as state 0x4F. Calling that controller
state while the Item screen is still being created skips its normal startup
states and leaves the screen black. This component instead applies the exact
inventory transform from native state 0x4F before it tail-calls the original
Item initializer. The initializer and every controller state then run normally.
"""

from __future__ import annotations


SUPPORTED_EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
DEFAULT_AUTO_SORT_INVENTORY = False

# FF8 2013 Steam English, identified by SUPPORTED_EXE_SHA256.
ITEM_OPEN_SORT_HOOK = 0x004F8146
ITEM_OPEN_SORT_ORIGINAL = bytes.fromhex("E8 35 00 00 00")
ITEM_INITIALIZER = 0x004F8180
ITEM_CONTROLLER = 0x004F81F0
NATIVE_SORT_STATE = 0x004FB422
INVENTORY_POINTER_OFFSET = 0x20
INVENTORY_SLOT_COUNT = 0xC6

# Exact state-0x4F bytes from the supported executable. They show the native
# 198-pair scan, compaction by ascending item ID, and return to Item state 3.
NATIVE_SORT_ORIGINAL = bytes.fromhex(
    "B9 32 00 00 00 33 C0 8D BC 24 C4 01 00 00 BB C6 00 00 00 F3 AB 66 AB "
    "8B 7E 20 8B C7 33 D2 33 C9 8A 10 8A 48 01 40 40 85 D2 74 0B 85 C9 "
    "74 07 88 8C 14 C4 01 00 00 4B 75 E3 8B C7 B9 C6 00 00 00 C6 00 00 "
    "40 C6 00 00 40 49 75 F5 8B CF B8 01 00 00 00 8A 94 04 C4 01 00 00 "
    "84 D2 74 06 88 01 41 88 11 41 40 3D C6 00 00 00 7E E7 E8 BE 7C FC "
    "FF 0F BE 7E 61 8D 44 24 2C 6A 09 50 68 B8 8A B8 00 E8 19 4B FC FF "
    "0F BF 4C 7C 38 83 C1 32 6A 0D 51 6A 00 6A 01 E8 95 23 FC FF 83 C4 "
    "1C C6 46 61 00 66 C7 46 10 03 00"
)

# The cave starts after Single GF's transition normalizer. No registered FF8
# gameplay component uses the following range.
CODE_CAVE = 0x027A05A0
LOCAL_BUFFER_LENGTH = 0xCC
BATTLE_SORT_CAVE = 0x027A0640
BATTLE_CACHE_HOOK = 0x0048C6E0
BATTLE_CACHE_ORIGINAL = bytes.fromhex("B8 78 8E D2 01")
BATTLE_ORDER = 0x01CFE77C
SAVED_ITEMS = 0x01CFE79C


def build_battle_sort_cave() -> bytes:
    """Order the native inverse slot map before its unchanged cache builder."""
    code = _MachineCode(BATTLE_SORT_CAVE)
    code.add(bytes.fromhex('9C 60 FC 83 EC 20 31 C0 89 E7 B9 08 00 00 00 F3 AB'))
    code.add(b'\xBE' + SAVED_ITEMS.to_bytes(4, 'little'))
    code.add(bytes.fromhex('BA C6 00 00 00'))
    code.label('scan')
    code.add(bytes.fromhex('0F B6 06 48 83 F8 1F'))
    code.branch(b'\x0F\x87', 'next')
    code.add(bytes.fromhex('80 7E 01 00'))
    code.branch(b'\x0F\x84', 'next')
    code.add(bytes.fromhex('C6 04 04 01'))
    code.label('next')
    code.add(bytes.fromhex('83 C6 02 4A'))
    code.branch(b'\x0F\x85', 'scan')
    code.add(bytes.fromhex('31 C9 B3 01'))
    code.label('pass')
    code.add(bytes.fromhex('31 C0'))
    code.label('map')
    code.add(bytes.fromhex('38 1C 04'))
    code.branch(b'\x0F\x85', 'advance')
    code.add(bytes.fromhex('88 88') + BATTLE_ORDER.to_bytes(4, 'little'))
    code.add(b'\x41')
    code.label('advance')
    code.add(bytes.fromhex('40 83 F8 20'))
    code.branch(b'\x0F\x82', 'map')
    code.add(bytes.fromhex('FE CB'))
    code.branch(b'\x0F\x89', 'pass')
    code.add(bytes.fromhex('83 C4 20 61 9D'))
    code.add(BATTLE_CACHE_ORIGINAL)
    code.add(relative_branch(b'\xE9', BATTLE_SORT_CAVE + len(code.data), BATTLE_CACHE_HOOK + 5))
    result = code.finish()
    assert BATTLE_SORT_CAVE + len(result) <= 0x027A0700
    return result


class _MachineCode:
    """Small label-aware x86 encoder for deterministic near branches."""

    def __init__(self, address: int):
        self.address = int(address)
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, bytes, str]] = []

    def add(self, data: bytes) -> None:
        self.data.extend(data)

    def label(self, name: str) -> None:
        self.labels[name] = len(self.data)

    def branch(self, opcode: bytes, label: str) -> None:
        self.data.extend(opcode)
        position = len(self.data)
        self.data.extend(b"\x00\x00\x00\x00")
        self.fixups.append((position, opcode, label))

    def finish(self) -> bytes:
        for position, _opcode, label in self.fixups:
            target = self.address + self.labels[label]
            source_after = self.address + position + 4
            self.data[position:position + 4] = int(target - source_after).to_bytes(
                4, "little", signed=True,
            )
        return bytes(self.data)


def boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Auto-sort Inventory must be true or false")
    return value


def relative_branch(opcode: bytes, source: int, target: int) -> bytes:
    if opcode not in {b"\xE8", b"\xE9"}:
        raise ValueError("Only a near call or jump is supported")
    displacement = int(target) - (int(source) + 5)
    return opcode + displacement.to_bytes(4, "little", signed=True)


def relative_call_target(source: int, instruction: bytes) -> int:
    if len(instruction) != 5 or instruction[:1] not in {b"\xE8", b"\xE9"}:
        raise ValueError("Expected one near call or jump")
    displacement = int.from_bytes(instruction[1:], "little", signed=True)
    return int(source) + 5 + displacement


def sort_inventory_pairs(pairs: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
    """Mirror FF8 state 0x4F for deterministic tests and explanations."""
    if len(pairs) != INVENTORY_SLOT_COUNT:
        raise ValueError(f"FF8 inventory must contain {INVENTORY_SLOT_COUNT} slots")
    quantities = [0] * (INVENTORY_SLOT_COUNT + 1)
    for item_id, quantity in pairs:
        item_id = int(item_id)
        quantity = int(quantity)
        if not 0 <= item_id <= INVENTORY_SLOT_COUNT:
            raise ValueError("FF8 item ID is outside the native inventory range")
        if not 0 <= quantity <= 0xFF:
            raise ValueError("FF8 item quantity must fit in one byte")
        if item_id and quantity:
            quantities[item_id] = quantity
    result = [
        (item_id, quantities[item_id])
        for item_id in range(1, INVENTORY_SLOT_COUNT + 1)
        if quantities[item_id]
    ]
    result.extend([(0, 0)] * (INVENTORY_SLOT_COUNT - len(result)))
    return result


def build_code_cave(code_cave: int = CODE_CAVE) -> bytes:
    """Sort the backing inventory, then run the untouched Item initializer."""
    code = _MachineCode(code_cave)
    code.add(bytes.fromhex(
        "9C 60 FC "                 # preserve flags/registers; clear direction
        "81 EC CC 00 00 00 "        # 204-byte local quantity table
        "31 C0 89 E7 B9 32 00 00 00 F3 AB 66 AB "
        "8B 7E 20 89 F8 BB C6 00 00 00"
    ))
    code.label("scan")
    code.add(bytes.fromhex(
        "31 D2 31 C9 8A 10 8A 48 01 83 C0 02 85 D2"
    ))
    code.branch(bytes.fromhex("0F 84"), "scan_next")
    code.add(bytes.fromhex("85 C9"))
    code.branch(bytes.fromhex("0F 84"), "scan_next")
    code.add(bytes.fromhex("88 0C 14"))  # quantity_table[item_id] = quantity
    code.label("scan_next")
    code.add(bytes.fromhex("4B"))
    code.branch(bytes.fromhex("0F 85"), "scan")

    code.add(bytes.fromhex("89 F8 B9 C6 00 00 00 31 D2"))
    code.label("clear")
    code.add(bytes.fromhex("66 89 10 83 C0 02 49"))
    code.branch(bytes.fromhex("0F 85"), "clear")

    code.add(bytes.fromhex("89 F9 B8 01 00 00 00"))
    code.label("rebuild")
    code.add(bytes.fromhex("8A 14 04 84 D2"))
    code.branch(bytes.fromhex("0F 84"), "rebuild_next")
    code.add(bytes.fromhex("88 01 88 51 01 83 C1 02"))
    code.label("rebuild_next")
    code.add(bytes.fromhex("40 3D C6 00 00 00"))
    code.branch(bytes.fromhex("0F 8E"), "rebuild")
    code.add(bytes.fromhex("81 C4 CC 00 00 00 61 9D"))
    code.add(relative_branch(
        b"\xE9", code_cave + len(code.data), ITEM_INITIALIZER,
    ))
    return code.finish()


CODE_CAVE_LENGTH = len(build_code_cave())


def build_hext(enabled: bool) -> str:
    """Return this issue's Hext component, or no patch for vanilla behavior."""
    if not boolean(enabled):
        return ""
    payload = build_code_cave()
    battle = build_battle_sort_cave()
    assert CODE_CAVE + len(payload) <= BATTLE_SORT_CAVE
    hook = relative_branch(b"\xE8", ITEM_OPEN_SORT_HOOK, CODE_CAVE)
    battle_hook = relative_branch(b"\xE9", BATTLE_CACHE_HOOK, BATTLE_SORT_CAVE)
    return "\n".join((
        "# Sort inventory with FF8's state-0x4F transform before Item startup.",
        "# The original Item initializer and controller states remain intact.",
        f"{CODE_CAVE:X}:{len(payload):X}",
        f"{ITEM_OPEN_SORT_HOOK:X} = {hook.hex(' ').upper()}",
        f"{CODE_CAVE:X} = {payload.hex(' ').upper()}",
        f"{BATTLE_SORT_CAVE:X}:{len(battle):X}",
        f"{BATTLE_SORT_CAVE:X} = {battle.hex(' ').upper()}",
        f"{BATTLE_CACHE_HOOK:X} = {battle_hook.hex(' ').upper()}",
    )) + "\n"
