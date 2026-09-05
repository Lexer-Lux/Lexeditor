"""Static, semantic, and mutation checks for FF8 Streamlined Draw."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import sys

from capstone import CS_ARCH_X86, CS_MODE_32, Cs
import pefile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import battle_issue_54, gameplay_settings, streamlined_draw  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED_EXE = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


def emitted_bytes(patch: str, address: int) -> bytes:
    match = re.search(rf"(?m)^{address:X} = ([0-9A-F ]+)$", patch)
    assert match, f"no emitted bytes for {address:08X}"
    return bytes.fromhex(match.group(1))


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == EXPECTED_EXE
pe = pefile.PE(str(EXE), fast_load=True)

# The native Draw controller copies four enemy spell records, leaves EDX zero
# only when none exists, and otherwise opens the spell-list path at 004AE833.
assert image_bytes(
    pe, streamlined_draw.SPELL_COUNT_HOOK,
    len(streamlined_draw.SPELL_COUNT_ORIGINAL),
) == streamlined_draw.SPELL_COUNT_ORIGINAL
draw_source_flow = bytes.fromhex(
    "E8 BC EA FD FF 8D 4B FD 83 C4 0C 8D 04 C9 C1 E0 03 2B C1 "
    "05 18 8F D2 01 8B 08 8B 50 04 89 0D 3C 54 D7 01 8B 48 08 "
    "89 15 40 54 D7 01 8B 50 0C A1 D4 68 D7 01 89 15 48 54 "
    "D7 01 25 FF 00 00 00 89 0D 44 54 D7 01 B9 3C 54 D7 01 8D "
    "14 C5 00 00 00 00 89 0D F4 68 D7 01 2B D0 8D 04 90 33 D2 "
    "C1 E0 04 05 00 F0 CF 01 A3 F8 68 D7 01 33 C0 80 39 00 74 "
    "03 8D 50 01 40 83 C1 04 83 F8 04 7C EF 3B D5 0F 85 FE 07 "
    "00 00"
)
assert image_bytes(pe, 0x004ADFAF, len(draw_source_flow)) == draw_source_flow

# 0048CAE0 creates the exact two native mode descriptors: Stock first and
# Cast second. This is the proved seam that the old 004BCA80 hypothesis missed.
assert streamlined_draw.STOCK_COMMAND_ID == 10
assert streamlined_draw.CAST_COMMAND_ID == 9
mode_descriptor_builder = bytes.fromhex(
    "8A 15 82 3F CF 01 C6 00 0A 88 48 01 88 50 02 88 58 03 "
    "C6 40 04 09 7D 7D 8B CD 6B C9 3C 8A 91 6D 40 CF 01 "
    "88 50 05 8A 91 6E 40 CF 01 8A 89 6F 40 CF 01 88 50 06 "
    "80 E1 80 88 58 07 B2 01"
)
assert image_bytes(pe, 0x0048CB0C, len(mode_descriptor_builder)) == mode_descriptor_builder
assert image_bytes(
    pe, streamlined_draw.MODE_LIST_HOOK,
    len(streamlined_draw.MODE_LIST_ORIGINAL),
) == streamlined_draw.MODE_LIST_ORIGINAL

# State 23 is the two-entry Stock/Cast selector. State 26 consumes its cursor,
# reads the selected native descriptor, and recognizes command 10 as Stock.
mode_selector_flow = bytes.fromhex(
    "A1 F8 68 D7 01 43 83 FB 02 7C 02 33 DB 80 3C 98 00 74 F2 "
    "6A 01 88 1D D9 68 D7 01 88 5F 59 E8 81 B3 FF FF 83 C4 04 "
    "8B 44 24 10 F6 C4 10 74 26 A1 F8 68 D7 01 4B 79 05 BB 01 "
    "00 00 00 80 3C 98 00 74 F2 6A 01 88 1D D9 68 D7 01 88 5F "
    "59 E8 52 B3 FF FF 83 C4 04 8A 44 24 14 A8 10 74 14 6A 03 "
    "E8 40 B3 FF FF 83 C4 04 B8 18 00 00 00 E9 1C 02 00 00 F6 "
    "44 24 10 40 74 43 8B 0D F8 68 D7 01 33 C0 A0 D9 68 D7 01 "
    "F6 44 81 03 02 74 1B"
)
assert image_bytes(pe, 0x004AE3DC, len(mode_selector_flow)) == mode_selector_flow
mode_commit_flow = bytes.fromhex(
    "8B 0D F8 68 D7 01 33 D2 8A 15 D9 68 D7 01 33 C0 8A 04 91 "
    "83 F8 0A A2 DD 68 D7 01 75 23 8A 0D DB 68 D7 01 B8 01 00 "
    "00 00 D3 E0 66 A3 DE 68 D7 01 B8 20 00 00 00 E9 86 01 00 "
    "00"
)
assert image_bytes(pe, 0x004AE4A9, len(mode_commit_flow)) == mode_commit_flow

assert streamlined_draw.TARGET_DESCRIPTOR_DISPATCHER == 0x004BC770
assert streamlined_draw.SHARED_DRAW_HOOKS == (
    battle_issue_54.DRAW_SELECT_HOOK,
    battle_issue_54.DRAW_TARGET_MASK_HOOK,
    battle_issue_54.DRAW_RENDER_HOOK,
)

assert streamlined_draw.build_hext(False) == ""
for invalid in (0, 1, "true", None):
    try:
        streamlined_draw.build_hext(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Streamlined Draw accepted {invalid!r}")

patch = streamlined_draw.build_hext(True)
spell_hook = emitted_bytes(patch, streamlined_draw.SPELL_COUNT_HOOK)
mode_hook = emitted_bytes(patch, streamlined_draw.MODE_LIST_HOOK)
spell_cave = emitted_bytes(patch, streamlined_draw.SPELL_COUNT_CAVE)
mode_cave = emitted_bytes(patch, streamlined_draw.MODE_LIST_CAVE)
stock_cave = emitted_bytes(patch, streamlined_draw.STOCK_FILTER_CAVE)
decoder = Cs(CS_ARCH_X86, CS_MODE_32)
assert emitted_bytes(patch, streamlined_draw.MAGIC_STOCK_LIMIT_VALUE) == b"\x64"
assert len(spell_hook) == len(streamlined_draw.SPELL_COUNT_ORIGINAL)
assert len(mode_hook) == len(streamlined_draw.MODE_LIST_ORIGINAL)
assert spell_hook[0] == mode_hook[0] == 0xE9
assert streamlined_draw.DRAW_SPELLS.to_bytes(4, "little") in spell_cave
assert streamlined_draw.DRAW_SPELL_CURSOR.to_bytes(4, "little") in spell_cave
assert streamlined_draw.DRAW_MODE_CURSOR.to_bytes(4, "little") in mode_cave
assert bytes.fromhex("B8 1A 00 00 00") in mode_cave

# A target remains eligible only when at least one of its four valid spells is
# below the one configured cap. Invalid and empty spell records do not count.
stock = {1: 100, 2: 100, 3: 99}
assert not streamlined_draw.enemy_has_drawable_stock([1, 2, 0, 0x40], stock)
assert streamlined_draw.enemy_has_drawable_stock([1, 3, 0, 0x40], stock)
assert streamlined_draw.enemy_has_drawable_stock([4, 0, 0, 0], stock)
assert not streamlined_draw.enemy_has_drawable_stock(
    [1, 2, 0, 0], {1: 50, 2: 50}, 50,
)
assert streamlined_draw.enemy_has_drawable_stock(
    [1, 2, 0, 0], {1: 50, 2: 49}, 50,
)
enemy_spells = {
    3: [1, 2, 0, 0],
    4: [1, 3, 0, 0],
    5: [0, 0, 0, 0],
    6: [4, 0, 0, 0],
}
assert streamlined_draw.filter_draw_target_mask(0x78, enemy_spells, stock) == 0x50
# When every valid spell is at or above the selected limit, the runtime mask is
# empty. A mixed enemy remains only when at least one spell is below that same
# limit. Test both vanilla-sized and byte-maximum stocks.
all_full = {actor: [1, 2, 0, 0] for actor in range(3, 7)}
assert streamlined_draw.filter_draw_target_mask(
    0x78, all_full, {1: 100, 2: 100}, 100,
) == 0
assert streamlined_draw.filter_draw_target_mask(
    0x78, all_full, {1: 255, 2: 255}, 255,
) == 0
mixed_at_255 = dict(all_full)
mixed_at_255[5] = [1, 3, 0, 0]
assert streamlined_draw.filter_draw_target_mask(
    0x78, mixed_at_255, {1: 255, 2: 255, 3: 254}, 255,
) == (1 << 5)
# Draw Once is applied to the stock-filtered set. This disjoint case must make
# Draw unavailable instead of accepting one target from each independent set.
assert streamlined_draw.filter_draw_target_mask(0x78, enemy_spells, stock) & ~0x50 == 0
for invalid_limit in (0, 256, True, 2.5, "many"):
    try:
        streamlined_draw.build_hext(True, invalid_limit)
    except ValueError:
        pass
    else:
        raise AssertionError(f"invalid stock limit accepted: {invalid_limit!r}")
assert emitted_bytes(
    streamlined_draw.build_hext(True, 50),
    streamlined_draw.MAGIC_STOCK_LIMIT_VALUE,
) == b"\x32"

# The machine predicate reads the acting actor's 32-slot live Magic mirror and
# each enemy's four Draw records. It compares quantity to the reserved cap byte
# instead of embedding vanilla's 100 in the filter.
for address in (
    streamlined_draw.ACTIVE_BATTLE_ACTOR,
    streamlined_draw.BATTLE_ACTOR_MAGIC_BASE,
    streamlined_draw.ENEMY_DRAW_BASE,
    streamlined_draw.MAGIC_STOCK_LIMIT_VALUE,
):
    assert address.to_bytes(4, "little") in stock_cave
def assert_stock_filter_contract(payload: bytes) -> None:
    instructions = list(decoder.disasm(payload, streamlined_draw.STOCK_FILTER_CAVE))
    assert any(i.mnemonic == "imul" and "0x1d0" in i.op_str for i in instructions)
    assert any(i.mnemonic == "imul" and "0x47" in i.op_str for i in instructions)
    assert any(i.mnemonic == "mov" and i.op_str == "ebx, 4" for i in instructions)
    assert any(i.mnemonic == "mov" and i.op_str == "ecx, 0x20" for i in instructions)
    assert any(i.mnemonic == "cmp" and i.op_str == "esi, 7" for i in instructions)
    assert streamlined_draw.MAGIC_STOCK_LIMIT_VALUE.to_bytes(4, "little") in payload
    assert bytes.fromhex("80 7A 01 64") not in payload
    cap_load = next(i for i in instructions if i.mnemonic == "mov" and
                    i.op_str == "ah, byte ptr [0x27a17f0]")
    compare = instructions[instructions.index(cap_load) + 1]
    below = instructions[instructions.index(cap_load) + 4]
    assert compare.mnemonic == "cmp" and compare.op_str == "byte ptr [edx + 1], ah"
    assert below.mnemonic == "jb", "stock equal to the cap must not remain drawable"
    # Missing stock and below-cap stock converge on the same drawable target.
    missing_jump = next(i for i in instructions if i.address == 0x027A1673)
    assert int(missing_jump.op_str, 16) == int(below.op_str, 16)


assert_stock_filter_contract(stock_cave)
literal_limit_mutant = stock_cave.replace(
    b"\x8A\x25" + streamlined_draw.MAGIC_STOCK_LIMIT_VALUE.to_bytes(4, "little"),
    bytes.fromhex("B4 64 90 90 90 90"),
)
try:
    assert_stock_filter_contract(literal_limit_mutant)
except AssertionError:
    pass
else:
    raise AssertionError("a hard-coded vanilla stock limit passed the contract")
below_branch_mutant = bytearray(stock_cave)
below_branch_mutant[0x027A1683 - streamlined_draw.STOCK_FILTER_CAVE] = 0x73  # jae
try:
    assert_stock_filter_contract(bytes(below_branch_mutant))
except AssertionError:
    pass
else:
    raise AssertionError("an inverted full-stock comparison passed the contract")

# The shared command hooks compose the stock filter with Draw Once. The same
# filtered mask controls target display, command selection, and grey rendering.
combined = battle_issue_54.build_command_eligibility_patch(
    draw_once=True, better_card=True, streamlined_draw=True,
)
def assert_one_filter_call(payload: bytes, address: int) -> None:
    instructions = list(decoder.disasm(payload, address))
    calls = [
        instruction for instruction in instructions
        if instruction.mnemonic == "call"
        and int(instruction.op_str, 16) == streamlined_draw.STOCK_FILTER_CAVE
    ]
    assert len(calls) == 1
    call_index = instructions.index(calls[0])
    assert any(
        instruction.mnemonic == "not"
        for instruction in instructions[call_index + 1:]
    ), "Draw Once did not consume Streamlined Draw's filtered mask"


for cave_address in (
    battle_issue_54.DRAW_TARGET_MASK_CAVE,
    battle_issue_54.DRAW_SELECT_CAVE,
    battle_issue_54.DRAW_RENDER_CAVE,
):
    payload = emitted_bytes(combined, cave_address)
    assert_one_filter_call(payload, cave_address)
    call = next(
        instruction for instruction in decoder.disasm(payload, cave_address)
        if instruction.mnemonic == "call"
        and int(instruction.op_str, 16) == streamlined_draw.STOCK_FILTER_CAVE
    )
    mutant = bytearray(payload)
    mutant[call.address - cave_address:call.address - cave_address + call.size] = b"\x90" * call.size
    try:
        assert_one_filter_call(bytes(mutant), cave_address)
    except AssertionError:
        pass
    else:
        raise AssertionError(f"missing stock filter call passed at {cave_address:08X}")

# Prove the empty filtered mask reaches both native disabled behavior and the
# descriptor's grey flag. The target-mask cave also returns the filtered mask,
# so enemies at full stock cannot remain selectable through a different UI
# surface.
streamlined_only = battle_issue_54.build_command_eligibility_patch(
    draw_once=False, better_card=False, streamlined_draw=True,
)
target_payload = emitted_bytes(streamlined_only, battle_issue_54.DRAW_TARGET_MASK_CAVE)
select_payload = emitted_bytes(streamlined_only, battle_issue_54.DRAW_SELECT_CAVE)
render_payload = emitted_bytes(streamlined_only, battle_issue_54.DRAW_RENDER_CAVE)


def assert_target_returns_filter(payload: bytes) -> None:
    instructions = list(decoder.disasm(payload, battle_issue_54.DRAW_TARGET_MASK_CAVE))
    call_index = next(index for index, item in enumerate(instructions)
                      if item.mnemonic == "call" and
                      int(item.op_str, 16) == streamlined_draw.STOCK_FILTER_CAVE)
    assert instructions[call_index + 1].mnemonic == "mov"
    assert instructions[call_index + 1].op_str == "edi, eax"


def assert_empty_mask_disables(payload: bytes) -> None:
    instructions = list(decoder.disasm(payload, battle_issue_54.DRAW_SELECT_CAVE))
    call_index = next(index for index, item in enumerate(instructions)
                      if item.mnemonic == "call" and
                      int(item.op_str, 16) == streamlined_draw.STOCK_FILTER_CAVE)
    test, branch = instructions[call_index + 1:call_index + 3]
    assert test.mnemonic == "test" and test.op_str == "eax, eax"
    assert branch.mnemonic == "je"
    disabled_label = int(branch.op_str, 16)
    disabled_jump = next(item for item in instructions if item.address == disabled_label)
    assert disabled_jump.mnemonic == "jmp"
    assert int(disabled_jump.op_str, 16) == battle_issue_54.DRAW_SELECT_DISABLED


def assert_empty_mask_greys(payload: bytes) -> None:
    instructions = list(decoder.disasm(payload, battle_issue_54.DRAW_RENDER_CAVE))
    call_index = next(index for index, item in enumerate(instructions)
                      if item.mnemonic == "call" and
                      int(item.op_str, 16) == streamlined_draw.STOCK_FILTER_CAVE)
    test, branch, grey = instructions[call_index + 1:call_index + 4]
    assert test.mnemonic == "test" and test.op_str == "eax, eax"
    assert branch.mnemonic == "jne"
    assert grey.mnemonic == "or" and grey.op_str == "bl, 2"
    assert int(branch.op_str, 16) == instructions[call_index + 4].address


assert_target_returns_filter(target_payload)
assert_empty_mask_disables(select_payload)
assert_empty_mask_greys(render_payload)
assert image_bytes(pe, 0x004BCB66, 7) == bytes.fromhex("F6 C3 02 74 02 33 C9")

for payload, assertion, address, old, new, message in (
    (target_payload, assert_target_returns_filter, battle_issue_54.DRAW_TARGET_MASK_CAVE,
     bytes.fromhex("89 C7"), bytes.fromhex("89 F8"),
     "a target-mask cave that discarded the filtered mask passed"),
    (select_payload, assert_empty_mask_disables, battle_issue_54.DRAW_SELECT_CAVE,
     bytes.fromhex("0F 84"), bytes.fromhex("0F 85"),
     "an inverted empty-mask command gate passed"),
    (render_payload, assert_empty_mask_greys, battle_issue_54.DRAW_RENDER_CAVE,
     bytes.fromhex("80 CB 02"), bytes.fromhex("90 90 90"),
     "an empty-mask render path without the grey flag passed"),
):
    mutant = payload.replace(old, new, 1)
    assert mutant != payload
    try:
        assertion(mutant)
    except (AssertionError, StopIteration):
        pass
    else:
        raise AssertionError(message)
generated = gameplay_settings.build_hext(
    25, streamlined_draw_enabled=True,
)
for hook in streamlined_draw.SHARED_DRAW_HOOKS:
    assert re.search(rf"(?m)^{hook:X} = ", generated)

# The sole-spell cave must count all four records. The mode cave must force
# cursor zero. Capstone guards the key semantics, not only the raw literals.
spell_instructions = list(decoder.disasm(spell_cave, streamlined_draw.SPELL_COUNT_CAVE))
mode_instructions = list(decoder.disasm(mode_cave, streamlined_draw.MODE_LIST_CAVE))
assert any(i.mnemonic == "cmp" and i.op_str == "ebx, 4" for i in spell_instructions)
assert any(i.mnemonic == "cmp" and i.op_str == "ecx, 1" for i in spell_instructions)
assert any(
    i.mnemonic == "mov" and "byte ptr [0x1d768d8], dl" == i.op_str
    for i in spell_instructions
)
assert any(
    i.mnemonic == "mov" and "byte ptr [0x1d768d9], 0" == i.op_str
    for i in mode_instructions
)

# Mutation contract: the disproven generic magic-menu boundaries and the three
# shared Draw/Card hooks can never appear as this feature's patch sites.
for forbidden in (
    0x004BBDF5, 0x004BBE1A, 0x004BCA80, 0x0048C9A0,
    *streamlined_draw.SHARED_DRAW_HOOKS,
):
    assert not re.search(rf"(?m)^{forbidden:X} = ", patch)

print("FF8 Streamlined Draw static and semantic checks passed")
