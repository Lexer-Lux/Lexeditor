"""FF8's Streamlined Draw battle-menu patch.

The supported executable has two independent delays after an enemy is chosen:
the spell list and the Stock/Cast list. This patch preserves the native Draw
source, target, amount, stock-add, and queue paths. It only selects the sole
available spell automatically, selects the native Stock descriptor after a
spell is chosen, and removes enemies whose valid spells are all at the acting
character's configured stock limit.
"""

from __future__ import annotations

from .shared_magic_issue_51 import MAGIC_STOCK_LIMIT as DEFAULT_MAGIC_STOCK_LIMIT


DEFAULT_STREAMLINED_DRAW = False

DRAW_COMMAND_ID = 6
CAST_COMMAND_ID = 9
STOCK_COMMAND_ID = 10

DRAW_SPELLS = 0x01D768F4
DRAW_SPELL_CURSOR = 0x01D768D8
DRAW_MODE_CURSOR = 0x01D768D9

# After the native Draw source builder has copied the selected enemy's four
# spell records, this branch distinguishes no spells from one-or-more spells.
# The cave strengthens it to distinguish zero, one, and several spells.
SPELL_COUNT_HOOK = 0x004AE02D
SPELL_COUNT_ORIGINAL = bytes.fromhex("3B D5 0F 85 FE 07 00 00")
NO_SPELLS_STATE = 0x004AE035
OPEN_SPELL_LIST_STATE = 0x004AE833
COMMIT_SELECTED_SPELL_STATE = 0x004AE2EC

# 0048CAE0 creates two adjacent native descriptors after a spell is selected:
# Stock (command 10) first and Cast (command 9) second. Vanilla then enters
# state 18 to open their two-entry list. The patch fixes its cursor to entry 0
# and enters state 26, the native descriptor-commit state, instead.
MODE_LIST_HOOK = 0x004AE31E
MODE_LIST_ORIGINAL = bytes.fromhex("B8 12 00 00 00")
MODE_LIST_CONTINUE = 0x004AE323
COMMIT_SELECTED_MODE = 26

SPELL_COUNT_CAVE = 0x027A1400
MODE_LIST_CAVE = 0x027A1480

# Target filtering runs through the shared Draw/Card command hooks in
# battle_issue_54. The predicate itself lives here so Streamlined Draw owns one
# stock rule and one future-configurable limit byte. Shared Magic mirrors the
# canonical pool into every active actor, so the acting actor remains the
# correct read source in both private and shared modes.
STOCK_FILTER_CAVE = 0x027A1600
MAGIC_STOCK_LIMIT_VALUE = 0x027A17F0
ACTIVE_BATTLE_ACTOR = 0x01D76844
BATTLE_ACTOR_MAGIC_BASE = 0x01CFF082
BATTLE_ACTOR_STRIDE = 0x1D0
BATTLE_MAGIC_SLOT_COUNT = 32
BATTLE_MAGIC_SLOT_SIZE = 5
ENEMY_DRAW_BASE = 0x01D28F18
ENEMY_DRAW_STRIDE = 0x47  # Native (slot * 9 * 8) - slot = 71 bytes.
FIRST_ENEMY_ACTOR = 3
LAST_ENEMY_ACTOR = 6
DRAW_SPELL_SLOT_COUNT = 4
MAX_DRAW_MAGIC_ID = 0x3F

# Existing Draw Once / Better Card owns these command-list hooks. Streamlined
# Draw operates later in the native Draw controller and does not replace them.
TARGET_DESCRIPTOR_DISPATCHER = 0x004BC770
SHARED_DRAW_HOOKS = (0x004BC7B5, 0x004BC81A, 0x004BCB3B)


class _Code:
    def __init__(self, address: int):
        self.address = int(address)
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
        for position, label in self.fixups:
            target = self.address + self.labels[label]
            source_after = self.address + position + 4
            self.data[position:position + 4] = int(
                target - source_after,
            ).to_bytes(4, "little", signed=True)
        return bytes(self.data)


def _near_jump(source: int, target: int) -> bytes:
    return b"\xE9" + int(target - source - 5).to_bytes(4, "little", signed=True)


def _absolute_jump(code: _Code, target: int) -> None:
    code.add(_near_jump(code.address + len(code.data), target))


def _stock_limit(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Magic stock limit must be a whole number from 1 to 255")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Magic stock limit must be a whole number from 1 to 255") from error
    if str(value).strip() not in {str(result), f"{result}.0"} or not 1 <= result <= 255:
        raise ValueError("Magic stock limit must be a whole number from 1 to 255")
    return result


def enemy_has_drawable_stock(spells: list[int] | tuple[int, ...],
                             stock: dict[int, int],
                             maximum: int = DEFAULT_MAGIC_STOCK_LIMIT) -> bool:
    """Return true when one valid enemy spell is below the configured maximum."""
    limit = _stock_limit(maximum)
    if len(spells) != DRAW_SPELL_SLOT_COUNT:
        raise ValueError("An FF8 enemy must provide four Draw spell slots")
    return any(
        0 < int(spell_id) <= MAX_DRAW_MAGIC_ID
        and int(stock.get(int(spell_id), 0)) < limit
        for spell_id in spells
    )


def filter_draw_target_mask(mask: int, enemy_spells: dict[int, list[int]],
                            stock: dict[int, int],
                            maximum: int = DEFAULT_MAGIC_STOCK_LIMIT) -> int:
    """Mirror the runtime filter for enemy actor bits three through six."""
    result = int(mask) & 0xFFFF
    for actor in range(FIRST_ENEMY_ACTOR, LAST_ENEMY_ACTOR + 1):
        if result & (1 << actor) and not enemy_has_drawable_stock(
            enemy_spells.get(actor, [0] * DRAW_SPELL_SLOT_COUNT), stock, maximum,
        ):
            result &= ~(1 << actor)
    return result


def build_stock_filter_code_cave() -> bytes:
    """Filter EAX's target mask against the acting character's live stock."""
    code = _Code(STOCK_FILTER_CAVE)
    code.add(bytes.fromhex("53 55 56 57 89 C7"))
    code.add(b"\x0F\xB6\x2D" + ACTIVE_BATTLE_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("83 FD 02"))
    code.branch(bytes.fromhex("0F 87"), "done")
    code.add(bytes.fromhex("69 ED D0 01 00 00"))
    code.add(b"\x81\xC5" + BATTLE_ACTOR_MAGIC_BASE.to_bytes(4, "little"))
    code.add(bytes.fromhex("BE 03 00 00 00"))
    code.label("enemy")
    code.add(bytes.fromhex("0F A3 F7"))
    code.branch(bytes.fromhex("0F 83"), "next_enemy")
    code.add(bytes.fromhex("89 F1 83 E9 03 6B C9 47"))
    code.add(b"\x81\xC1" + ENEMY_DRAW_BASE.to_bytes(4, "little"))
    code.add(bytes.fromhex("BB 04 00 00 00"))
    code.label("spell")
    code.add(bytes.fromhex("0F B6 01 84 C0"))
    code.branch(bytes.fromhex("0F 84"), "next_spell")
    code.add(bytes.fromhex("3C 40"))
    code.branch(bytes.fromhex("0F 83"), "next_spell")
    code.add(bytes.fromhex("51 53 89 EA B9 20 00 00 00"))
    code.label("stock_slot")
    code.add(bytes.fromhex("38 02"))
    code.branch(bytes.fromhex("0F 84"), "stock_found")
    code.add(bytes.fromhex("83 C2 05 49"))
    code.branch(bytes.fromhex("0F 85"), "stock_slot")
    code.add(bytes.fromhex("5B 59"))
    code.branch(b"\xE9", "drawable")
    code.label("stock_found")
    code.add(b"\x8A\x25" + MAGIC_STOCK_LIMIT_VALUE.to_bytes(4, "little"))
    code.add(bytes.fromhex("38 62 01 5B 59"))
    code.branch(bytes.fromhex("0F 82"), "drawable")
    code.label("next_spell")
    code.add(bytes.fromhex("83 C1 04 4B"))
    code.branch(bytes.fromhex("0F 85"), "spell")
    code.add(bytes.fromhex("0F B3 F7"))
    code.label("drawable")
    code.label("next_enemy")
    code.add(bytes.fromhex("46 83 FE 07"))
    code.branch(bytes.fromhex("0F 8C"), "enemy")
    code.label("done")
    code.add(bytes.fromhex("89 F8 5F 5E 5D 5B C3"))
    return code.finish()


def _spell_count_payload() -> bytes:
    code = _Code(SPELL_COUNT_CAVE)
    code.add(bytes.fromhex("85 D2"))  # Native loop leaves zero for no spell.
    code.branch(bytes.fromhex("0F 84"), "none")
    code.add(b"\xA1" + DRAW_SPELLS.to_bytes(4, "little"))
    code.add(bytes.fromhex("31 C9 31 D2 53 31 DB"))
    code.label("loop")
    code.add(bytes.fromhex("80 3C 98 00"))
    code.branch(bytes.fromhex("0F 84"), "next")
    code.add(bytes.fromhex("41 89 DA"))
    code.label("next")
    code.add(bytes.fromhex("43 83 FB 04"))
    code.branch(bytes.fromhex("0F 8C"), "loop")
    code.add(bytes.fromhex("5B 83 F9 01"))
    code.branch(bytes.fromhex("0F 85"), "several")
    code.add(b"\x88\x15" + DRAW_SPELL_CURSOR.to_bytes(4, "little"))
    _absolute_jump(code, COMMIT_SELECTED_SPELL_STATE)
    code.label("none")
    _absolute_jump(code, NO_SPELLS_STATE)
    code.label("several")
    _absolute_jump(code, OPEN_SPELL_LIST_STATE)
    return code.finish()


def _mode_list_payload() -> bytes:
    code = _Code(MODE_LIST_CAVE)
    code.add(b"\xC6\x05" + DRAW_MODE_CURSOR.to_bytes(4, "little") + b"\x00")
    code.add(b"\xB8" + COMMIT_SELECTED_MODE.to_bytes(4, "little"))
    _absolute_jump(code, MODE_LIST_CONTINUE)
    return code.finish()


def build_hext(enabled: bool,
               magic_stock_limit: int = DEFAULT_MAGIC_STOCK_LIMIT) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Streamlined Draw must be true or false")
    if not enabled:
        return ""
    limit = _stock_limit(magic_stock_limit)
    spell_payload = _spell_count_payload()
    mode_payload = _mode_list_payload()
    stock_payload = build_stock_filter_code_cave()
    if STOCK_FILTER_CAVE + len(stock_payload) > MAGIC_STOCK_LIMIT_VALUE:
        raise AssertionError("Streamlined Draw stock filter overlaps its limit value")
    spell_hook = _near_jump(SPELL_COUNT_HOOK, SPELL_COUNT_CAVE)
    spell_hook += b"\x90" * (len(SPELL_COUNT_ORIGINAL) - len(spell_hook))
    return "\n".join((
        "# Streamlined Draw: auto-select a sole spell and always use native Stock.",
        "# Enemies with no spell below the configured stock limit are not valid Draw targets.",
        "# Native Draw targeting, amount, stock-add, queue, and FFNx wrappers remain intact.",
        f"{SPELL_COUNT_CAVE:X}:{len(spell_payload):X}",
        f"{MODE_LIST_CAVE:X}:{len(mode_payload):X}",
        f"{STOCK_FILTER_CAVE:X}:{len(stock_payload):X}",
        f"{MAGIC_STOCK_LIMIT_VALUE:X}:1",
        f"{SPELL_COUNT_HOOK:X} = {spell_hook.hex(' ').upper()}",
        f"{MODE_LIST_HOOK:X} = {_near_jump(MODE_LIST_HOOK, MODE_LIST_CAVE).hex(' ').upper()}",
        f"{SPELL_COUNT_CAVE:X} = {spell_payload.hex(' ').upper()}",
        f"{MODE_LIST_CAVE:X} = {mode_payload.hex(' ').upper()}",
        f"{STOCK_FILTER_CAVE:X} = {stock_payload.hex(' ').upper()}",
        f"{MAGIC_STOCK_LIMIT_VALUE:X} = {limit:02X}",
        "",
    ))
