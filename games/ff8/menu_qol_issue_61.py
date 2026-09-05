"""Issue-local FF8 menu quality-of-life patches for GitHub issue #61.

Each option is an independent fragment. A disabled option emits no bytes. An
option with no proved native path fails closed instead of installing a guess.
"""

from __future__ import annotations

from .formats import LOOKUPS


SUPPORTED_EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"

DEFAULT_ENHANCED_ABILITY_MENU = False
DEFAULT_AUTO_SORT_MAGIC = False
DEFAULT_INGAME_TIME = False
DEFAULT_BATTLE_ITEM_AUTO_SORT = False

# FF8 2013 Steam English, identified by SUPPORTED_EXE_SHA256.
MAGIC_MENU_WRAPPER = 0x004F00D0
MAGIC_SORT_RESOURCE_LOAD = 0x004F00F3
MAGIC_SORT_RESOURCE_LOAD_ORIGINAL = bytes.fromhex("E8 C8 E7 FC FF")
MAGIC_OPEN_HOOK = 0x004F00FB
MAGIC_OPEN_HOOK_ORIGINAL = bytes.fromhex("E8 70 E7 FC FF")
MAGIC_OPEN_DISPLACED_CALL = 0x004BE870
NATIVE_MAGIC_SORT = 0x004F0030
NATIVE_MAGIC_SORT_PREFIX = bytes.fromhex(
    "8B 0D 5C BB D2 01 83 EC 40 53 8B 5C 24 4C C1 E3 06 03 D9 80 3B 00 "
    "75 07 33 C0 5B 83 C4 40 C3"
)
MAGIC_REARRANGE_CALL_SITE = 0x004F4AA1
MAGIC_REARRANGE_CALL_ORIGINAL = bytes.fromhex(
    "0F BE 4D 71 33 D2 51 8A 55 64 52 E8 7F B5 FF FF 83 C4 0C"
)

# magsort.bin contains 64-byte order tables. Native mode zero is Manual; the
# first automatic table is the requested Attack / Restore / Indirect order.
ATTACK_RESTORE_INDIRECT_MODE = 1
CHARACTER_COUNT = 8

# This range starts after the last registered issue-local FF8 cave.
AUTO_SORT_MAGIC_CAVE = 0x027A0700

# BuildGFAbilityList emits complete eight-byte records. Byte +2 is 1 for an
# available, unfinished ability and 2 for a completed ability. Reordering the
# complete records keeps the cursor, learning target, AP values, and category
# attached to the same ability. The hook runs after the native builder has
# finished and before its epilogue returns the count.
ABILITY_LIST_RETURN_HOOK = 0x004ACE39
ABILITY_LIST_RETURN_ORIGINAL = bytes.fromhex("8B C7 5F 5E 5D")
ABILITY_LIST_RETURN = ABILITY_LIST_RETURN_HOOK + len(ABILITY_LIST_RETURN_ORIGINAL)
ABILITY_RECORD_SIZE = 8
ABILITY_STATE_OFFSET = 2
ABILITY_AVAILABLE = 1
ABILITY_COMPLETE = 2
ENHANCED_ABILITY_ORDER_CAVE = 0x027A1100

# BuildGFAbilityList writes each record as:
#   +0 ability id, +1 learn progress, +2 state (1 available, 2 complete),
#   +3 category, produced by bucketing the ability id at 0x004ACDA4.
# The category is therefore already in the record, so the menu's groups can be
# ordered without recomputing them. Verified by disassembly at 0x004ACD74.
ABILITY_ID_OFFSET = 0
ABILITY_CATEGORY_OFFSET = 3
ENHANCED_ABILITY_ALPHA_CAVE = 0x027A1200

# The GF ability-row renderer converts record state 1 to text palette 1 and
# state 2 to text palette 7. Palette 1 is the dim entry and palette 7 is the
# bright entry. Reverse only that palette result; do not modify record state.
ABILITY_STATE_READ = 0x004FD528
ABILITY_ROW_BOUNDS_BRANCH = 0x004FD508
ABILITY_ROW_BOUNDS_ORIGINAL = bytes.fromhex("7C 05")
# The renderer calculates page * 11 + row. Its signed comparison accepts
# negative indexes. An unsigned comparison rejects these before any record
# access, and retains the native out-of-range return for both bounds.
ABILITY_ROW_BOUNDS_SAFE = bytes.fromhex("72 05")
ABILITY_STATE_READ_ORIGINAL = bytes.fromhex("8A 1C C5 32 DD D8 01")
ABILITY_PALETTE_HOOK = 0x004FD56F
ABILITY_PALETTE_HOOK_ORIGINAL = bytes.fromhex("83 E3 06 52 50")
ABILITY_PALETTE_RETURN = ABILITY_PALETTE_HOOK + len(ABILITY_PALETTE_HOOK_ORIGINAL)
ABILITY_TEXT_RENDER_CALL = 0x004FD595
ABILITY_TEXT_RENDER_CALL_ORIGINAL = bytes.fromhex("E8 96 08 FC FF")
ABILITY_TEXT_RENDERER = 0x004BDE30
ENHANCED_ABILITY_PALETTE_CAVE = 0x027A1160

INGAME_TIME_BLOCKER = (
    "In-game Time is unresolved: FF8 imports GetLocalTime at IAT 0x00B69178, "
    "but no proved live main-menu renderer handoff was found for both the PLAY "
    "label and its digits. Writing clock time to played_time_secs would alter save data."
)
BATTLE_ITEM_AUTO_SORT_BLOCKER = (
    "Battle Item auto-sort is unresolved: native Item sort state 0x004FB422 "
    "sorts only the 198 inventory pairs at controller offset 0x20. FFNx proves "
    "battle_order[32] is a separate field, and no native automatic constructor "
    "for that field was found."
)


def boolean(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false")
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


def build_auto_sort_magic_code_cave(code_cave: int = AUTO_SORT_MAGIC_CAVE) -> bytes:
    """Run FF8's native Attack/Restore/Indirect sort for all eight characters."""
    code = bytearray()

    def call(target: int) -> None:
        source = code_cave + len(code)
        code.extend(relative_branch(b"\xE8", source, target))

    # Preserve the original wrapper call and its result. pushad stores the
    # original EAX, including the result of the displaced call.
    call(MAGIC_OPEN_DISPLACED_CALL)
    code.extend(bytes.fromhex("9C 60 31 DB"))  # pushfd; pushad; xor ebx, ebx
    loop_offset = len(code)
    code.extend(bytes((0x6A, ATTACK_RESTORE_INDIRECT_MODE, 0x53)))
    call(NATIVE_MAGIC_SORT)
    code.extend(bytes.fromhex("83 C4 08 43 83 FB") + bytes((CHARACTER_COUNT,)))
    jump_source_after = len(code) + 2
    displacement = loop_offset - jump_source_after
    if not -128 <= displacement <= 127:
        raise ValueError("Auto-sort Magic loop is outside short-jump range")
    code.extend(bytes((0x7C, displacement & 0xFF)))  # jl loop
    code.extend(bytes.fromhex("61 9D C3"))
    return bytes(code)


AUTO_SORT_MAGIC_CAVE_LENGTH = len(build_auto_sort_magic_code_cave())


def build_auto_sort_magic_hext(enabled: bool) -> str:
    if not boolean("Auto-sort Magic Menu", enabled):
        return ""
    payload = build_auto_sort_magic_code_cave()
    hook = relative_branch(b"\xE8", MAGIC_OPEN_HOOK, AUTO_SORT_MAGIC_CAVE)
    return "\n".join((
        "# Sort every character's magic when the Magic menu opens.",
        "# Mode 1 is FF8's magsort.bin Attack / Restore / Indirect table.",
        f"{AUTO_SORT_MAGIC_CAVE:X}:{len(payload):X}",
        f"{MAGIC_OPEN_HOOK:X} = {hook.hex(' ').upper()}",
        f"{AUTO_SORT_MAGIC_CAVE:X} = {payload.hex(' ').upper()}",
    )) + "\n"


def stable_ability_order(records: list[bytes]) -> list[bytes]:
    """Model the order the code cave produces, for tests and explanations.

    Category first so FF8's own groups survive, then unfinished before
    completed, then alphabetically by ability name inside each block.
    """
    if any(len(record) != ABILITY_RECORD_SIZE for record in records):
        raise ValueError("Every GF ability record must be eight bytes")
    ranks = ability_rank_table()
    return sorted(records, key=lambda record: (
        record[ABILITY_CATEGORY_OFFSET],
        record[ABILITY_STATE_OFFSET] == ABILITY_COMPLETE,
        ranks[record[ABILITY_ID_OFFSET]],
    ))


def ability_rank_table() -> bytes:
    """Alphabetical rank of every ability id, for sorting inside a code cave.

    Comparing names byte by byte at runtime would mean walking FF8's text
    table for every comparison. The names are fixed, so the ordering is
    resolved here and the cave only compares one byte per record.
    """
    named = {int(row["value"]): str(row["name"])
             for row in LOOKUPS["junctionable_ability"]["entries"]}
    order = sorted(identifier for identifier in named if identifier)
    ranked = sorted(order, key=lambda identifier: named[identifier].casefold())
    if len(ranked) > 254:
        raise ValueError("Too many abilities to rank in a single byte")
    table = bytearray([255]) * 256
    for position, identifier in enumerate(ranked):
        table[identifier] = position
    return bytes(table)


def build_enhanced_ability_order_code_cave(
    code_cave: int = ENHANCED_ABILITY_ALPHA_CAVE,
) -> bytes:
    """Group the native records by category, then order each group by name.

    The native builder emits records in ability-id order. Sorting on the key
    (category, completed, alphabetical rank) keeps FF8's own grouping and its
    unfinished-before-completed split, and only settles the order within each
    of those blocks. Whole eight-byte records move, so the cursor, AP values
    and learning target stay attached to their ability.
    """
    code = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, int]] = []

    def label(name: str) -> None:
        labels[name] = len(code)

    def short(opcode: int, target: str) -> None:
        code.append(opcode)
        fixups.append((len(code), target, 1))
        code.append(0)

    def near(target: str) -> None:
        code.append(0xE8)
        fixups.append((len(code), target, 4))
        code.extend(bytes(4))

    code.extend(bytes.fromhex("60"))                       # pushad
    code.extend(bytes.fromhex("8B B4 24 50 01 00 00"))     # mov esi,[esp+0x150]
    code.extend(bytes.fromhex("8B 2C 24"))                 # mov ebp,[esp] (native EDI)
    code.extend(bytes.fromhex("85 F6"))                    # test esi,esi
    short(0x74, "done")
    code.extend(bytes.fromhex("83 FD 01"))                 # cmp ebp,1
    short(0x7E, "done")
    code.extend(bytes.fromhex("8B DD 4B"))                 # mov ebx,ebp / dec ebx
    label("outer")
    code.extend(bytes.fromhex("8B CB"))                    # mov ecx,ebx
    code.extend(bytes.fromhex("8B FE"))                    # mov edi,esi
    label("inner")
    code.extend(bytes.fromhex("51"))                       # push ecx
    near("key")                                            # eax = key(edi)
    code.extend(bytes.fromhex("50"))                       # push eax
    code.extend(bytes.fromhex("83 C7 08"))                 # add edi,8
    near("key")                                            # eax = key(edi+8)
    code.extend(bytes.fromhex("8B D0"))                    # mov edx,eax
    code.extend(bytes.fromhex("58"))                       # pop eax
    code.extend(bytes.fromhex("83 EF 08"))                 # sub edi,8
    code.extend(bytes.fromhex("59"))                       # pop ecx
    code.extend(bytes.fromhex("3B C2"))                    # cmp eax,edx
    short(0x7E, "next")                                    # jle next
    code.extend(bytes.fromhex(
        "8B 07 8B 57 04 87 47 08 87 57 0C 89 07 89 57 04"))
    label("next")
    code.extend(bytes.fromhex("83 C7 08"))                 # add edi,8
    code.extend(bytes.fromhex("49"))                       # dec ecx
    short(0x75, "inner")
    code.extend(bytes.fromhex("4B"))                       # dec ebx
    short(0x75, "outer")
    label("done")
    code.extend(bytes.fromhex("61"))                       # popad
    code.extend(ABILITY_LIST_RETURN_ORIGINAL)
    source = code_cave + len(code)
    code.extend(relative_branch(bytes((0xE9,)), source, ABILITY_LIST_RETURN))

    # key(EDI) -> EAX = (category << 16) | (completed << 15) | alphabetical rank
    label("key")
    code.extend(bytes((0x0F, 0xB6, 0x47, ABILITY_CATEGORY_OFFSET)))
    code.extend(bytes.fromhex("C1 E0 10"))                 # shl eax,16
    code.extend(bytes((0x0F, 0xB6, 0x57, ABILITY_STATE_OFFSET)))
    code.extend(bytes.fromhex("4A"))                       # dec edx (1 -> 0, 2 -> 1)
    code.extend(bytes.fromhex("C1 E2 0F"))                 # shl edx,15
    code.extend(bytes.fromhex("0B C2"))                    # or eax,edx
    code.extend(bytes((0x0F, 0xB6, 0x57, ABILITY_ID_OFFSET)))
    rank_fixup = len(code) + 2
    code.extend(bytes.fromhex("8A 92 00 00 00 00"))        # mov dl,[edx+rank]
    code.extend(bytes.fromhex("0F B6 D2"))                 # movzx edx,dl
    code.extend(bytes.fromhex("0B C2"))                    # or eax,edx
    code.extend(bytes.fromhex("C3"))                       # ret

    while len(code) % 4:
        code.append(0x90)
    rank_address = code_cave + len(code)
    code[rank_fixup:rank_fixup + 4] = rank_address.to_bytes(4, "little")
    code.extend(ability_rank_table())

    for offset, target, size in fixups:
        if size == 1:
            displacement = labels[target] - (offset + 1)
            if not -128 <= displacement <= 127:
                raise ValueError(f"Enhanced Ability branch to {target} is too far")
            code[offset] = displacement & 0xFF
        else:
            displacement = labels[target] - (offset + 4)
            code[offset:offset + 4] = (displacement & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(code)


ENHANCED_ABILITY_ORDER_CAVE_LENGTH = len(build_enhanced_ability_order_code_cave())


def build_enhanced_ability_order_hext() -> str:
    """Build the stable full-record ordering slice."""
    payload = build_enhanced_ability_order_code_cave()
    hook = relative_branch(
        b"\xE9", ABILITY_LIST_RETURN_HOOK, ENHANCED_ABILITY_ALPHA_CAVE,
    )
    return "\n".join((
        "# Enhanced Ability Menu ordering: FF8's own category groups are kept,",
        "# unfinished entries stay ahead of completed ones, and each of those",
        "# blocks is ordered alphabetically by ability name.",
        f"{ENHANCED_ABILITY_ALPHA_CAVE:X}:{len(payload):X}",
        f"{ABILITY_LIST_RETURN_HOOK:X} = {hook.hex(' ').upper()}",
        f"{ENHANCED_ABILITY_ALPHA_CAVE:X} = {payload.hex(' ').upper()}",
    )) + "\n"


def ability_palette_for_state(state: int) -> int:
    """Mirror the requested renderer palette without changing semantic state."""
    if state == ABILITY_AVAILABLE:
        return 7
    if state == ABILITY_COMPLETE:
        return 1
    raise ValueError("GF ability state must be available or complete")


def build_enhanced_ability_palette_code_cave(
    code_cave: int = ENHANCED_ABILITY_PALETTE_CAVE,
) -> bytes:
    """Invert the native dim/bright palette result and preserve renderer arguments."""
    code = bytearray(bytes.fromhex("F7 D3 83 E3 06 52 50"))
    source = code_cave + len(code)
    code.extend(relative_branch(b"\xE9", source, ABILITY_PALETTE_RETURN))
    return bytes(code)


ENHANCED_ABILITY_PALETTE_CAVE_LENGTH = len(
    build_enhanced_ability_palette_code_cave()
)


def build_enhanced_ability_palette_hext() -> str:
    payload = build_enhanced_ability_palette_code_cave()
    hook = relative_branch(
        b"\xE9", ABILITY_PALETTE_HOOK, ENHANCED_ABILITY_PALETTE_CAVE,
    )
    return "\n".join((
        "# Enhanced Ability Menu palette: unfinished bright, completed dim.",
        f"{ABILITY_ROW_BOUNDS_BRANCH:X} = {ABILITY_ROW_BOUNDS_SAFE.hex(' ').upper()}",
        f"{ENHANCED_ABILITY_PALETTE_CAVE:X}:{len(payload):X}",
        f"{ABILITY_PALETTE_HOOK:X} = {hook.hex(' ').upper()}",
        f"{ENHANCED_ABILITY_PALETTE_CAVE:X} = {payload.hex(' ').upper()}",
    )) + "\n"


def _fail_closed(name: str, enabled: bool, blocker: str) -> str:
    if not boolean(name, enabled):
        return ""
    raise RuntimeError(blocker)


def build_enhanced_ability_menu_hext(enabled: bool) -> str:
    if not boolean("Enhanced Ability Menu", enabled):
        return ""
    return build_enhanced_ability_order_hext() + build_enhanced_ability_palette_hext()


def build_ingame_time_hext(enabled: bool) -> str:
    return _fail_closed("In-game Time", enabled, INGAME_TIME_BLOCKER)


def build_battle_item_auto_sort_hext(enabled: bool) -> str:
    return _fail_closed("Battle Item auto-sort", enabled, BATTLE_ITEM_AUTO_SORT_BLOCKER)


def build_hext(
    *,
    enhanced_ability_menu: bool = DEFAULT_ENHANCED_ABILITY_MENU,
    auto_sort_magic: bool = DEFAULT_AUTO_SORT_MAGIC,
    ingame_time: bool = DEFAULT_INGAME_TIME,
    battle_item_auto_sort: bool = DEFAULT_BATTLE_ITEM_AUTO_SORT,
) -> str:
    """Build the independent fragments in a stable order."""
    return "".join((
        build_enhanced_ability_menu_hext(enhanced_ability_menu),
        build_auto_sort_magic_hext(auto_sort_magic),
        build_ingame_time_hext(ingame_time),
        build_battle_item_auto_sort_hext(battle_item_auto_sort),
    ))
