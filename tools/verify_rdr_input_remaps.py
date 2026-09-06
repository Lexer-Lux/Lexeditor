"""Portable contracts for RDR1 camp-Travel and cutscene-Skip WSC remaps."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.rdr import input_remaps as remaps
from games.rdr import script_features as scripts


def push_string(value: bytes) -> bytes:
    assert len(value) <= 255
    return bytes((111, len(value))) + value


def native(index: int, params: int, returns: bool) -> bytes:
    assert 0 <= index < 1024
    first = (params << 1) | int(returns) | ((index >> 8) << 6)
    return bytes((44, first, index & 0xFF))


def enter() -> bytes:
    return bytes((45, 0, 0, 0, 0))


def fixture(code: bytes, natives: list[int]) -> tuple[bytes, int]:
    assert len(code) <= 0x3000
    # Keep CodeLength above the older passenger-coach audit floor and below one
    # 16 KiB code page. NOP padding is genuine zero growth space for relocation.
    code_length = 0x3000
    raw = bytearray(0x6000)
    code_table = 0x100
    native_table = 0x200
    code_page = 0x1000
    struct.pack_into('<I', raw, 8, 0x50000000 | code_table)
    struct.pack_into('<I', raw, 12, code_length)
    struct.pack_into('<I', raw, 32, len(natives))
    struct.pack_into('<I', raw, 36, 0x50000000 | native_table)
    struct.pack_into('<I', raw, code_table, 0x50000000 | code_page)
    for index, value in enumerate(natives):
        struct.pack_into('<I', raw, native_table + index * 4, value)
    raw[code_page:code_page + len(code)] = code
    return bytes(raw), code_page


def patch_relative(code: bytearray, offset: int, target: int) -> None:
    struct.pack_into('>h', code, offset + 1, target - (offset + 3))


def patch_switch(code: bytearray, offset: int, target: int) -> None:
    # one case; target is relative to offset+8 for case zero
    struct.pack_into('>h', code, offset + 6, target - (offset + 8))


def camp_fixture() -> tuple[bytes, dict]:
    code = bytearray()
    code.extend(enter())
    call_at = len(code)
    code.extend(b'\x52\x00\x00')
    jump_at = len(code)
    code.extend(b'\x62\x00\x00')
    switch_at = len(code)
    code.extend(bytes((110, 1, 0, 0, 0, 0, 0, 0)))
    pointer_at = len(code)
    code.extend(b'\x41\x00\x00')  # PushShort function pointer.
    label_at = len(code)
    code.extend(push_string(remaps.PASS_CAMP_TRAVEL))
    code.extend(bytes((37, 100)))
    action_at = len(code)
    code.extend(push_string(b'@UI.ACCEPT'))
    # Remaining ADD_SCRIPT_USE_CONTEXT args: synthetic integer/null values.
    code.extend(bytes((139, 139, 139, 139, 138, 139)))
    code.extend(native(0, 9, True))
    code.append(122)
    function_at = 0x100
    assert len(code) < function_at
    code.extend(b'\x00' * (function_at - len(code)))
    code.extend(enter())
    code.append(122)

    code[call_at] = 82 + (function_at >> 16)
    struct.pack_into('>H', code, call_at + 1, function_at & 0xFFFF)
    patch_relative(code, jump_at, function_at)
    patch_switch(code, switch_at, function_at)
    struct.pack_into('>H', code, pointer_at + 1, function_at)
    raw, page = fixture(bytes(code), [remaps.ADD_SCRIPT_USE_CONTEXT_HASH])
    return raw, {
        'page': page, 'action': action_at, 'function': function_at,
        'call': call_at, 'jump': jump_at, 'switch': switch_at, 'pointer': pointer_at,
        'label': label_at,
    }


def target_of_jump(code: bytes | bytearray, offset: int) -> int:
    return offset + 3 + struct.unpack_from('>h', bytes(code), offset + 1)[0]


def target_of_switch(code: bytes | bytearray, offset: int) -> int:
    return offset + 8 + struct.unpack_from('>h', bytes(code), offset + 6)[0]


def target_of_call(code: bytes | bytearray, offset: int) -> int:
    return ((code[offset] - 82) << 16) | struct.unpack_from('>H', bytes(code), offset + 1)[0]


def cutscene_fixture() -> tuple[bytes, int]:
    code = bytearray(enter())
    action_at = len(code)
    code.extend(push_string(remaps.CUTSCENE_OLD_ACTION))
    code.extend(bytes((140, 139)))  # true, 0
    code.extend(native(0, 3, True))
    for marker in remaps.CUTSCENE_MARKERS:
        code.extend(push_string(marker))
    code.extend(bytes((140, 140)))
    code.extend(native(1, 2, False))
    code.append(122)
    # A second function uses UI.ACCEPT for a non-cutscene action. It must remain.
    code.extend(enter())
    code.extend(push_string(remaps.CUTSCENE_OLD_ACTION))
    code.extend(bytes((140, 139)))
    code.extend(native(0, 3, True))
    code.append(122)
    raw, _page = fixture(bytes(code), [
        remaps.IS_DIGITAL_ACTION_PRESSED_HASH,
        remaps.CUTSCENE_STOP_HASH,
    ])
    return raw, action_at


def expect_failure(label, fn, text):
    try:
        fn()
    except (ValueError, RuntimeError) as error:
        assert text in str(error), (label, error)
    else:
        raise AssertionError(f'{label} unexpectedly succeeded')


def main() -> None:
    raw, info = camp_fixture()
    patched, reports = remaps.patch_camp_travel(raw, 0)
    assert len(reports) == 1 and reports[0]['new'] == '@GENERIC.ZOOM_RADAR'
    assert reports[0]['delta'] == len(remaps.CAMP_NEW_ACTION) - len(b'@UI.ACCEPT')
    before = scripts._script_layout(raw, 0)['code']
    after = scripts._script_layout(patched, 0)['code']
    delta = reports[0]['delta']
    moved_function = info['function'] + delta
    assert target_of_call(after, info['call']) == moved_function
    assert target_of_jump(after, info['jump']) == moved_function
    assert target_of_switch(after, info['switch']) == moved_function
    assert struct.unpack_from('>H', bytes(after), info['pointer'] + 1)[0] == moved_function
    assert remaps.CAMP_NEW_ACTION in bytes(after)
    assert remaps.PASS_CAMP_TRAVEL in bytes(after)
    assert b'@UI.ACCEPT' not in bytes(after[:moved_function])

    # Invalid growth space must fail rather than overwrite another resource object.
    blocked = bytearray(raw)
    old_len = scripts._script_layout(raw, 0)['codeLength']
    blocked[info['page'] + old_len] = 0x7F
    expect_failure('occupied page tail', lambda: remaps.patch_camp_travel(bytes(blocked), 0),
                   'zero padding')

    cut_raw, _ = cutscene_fixture()
    cut_patched, cut_reports = remaps.patch_cutscene_skip(cut_raw, 0)
    assert len(cut_reports) == 1
    cut_code = bytes(scripts._script_layout(cut_patched, 0)['code'])
    assert remaps.CUTSCENE_NEW_ACTION in cut_code
    # One unrelated UI.ACCEPT remains in the second function.
    assert cut_code.count(remaps.CUTSCENE_OLD_ACTION) == 1
    assert all(marker in cut_code for marker in remaps.CUTSCENE_MARKERS)

    # A function with the same input native but no cutscene markers is not a candidate.
    plain = bytearray(enter())
    plain.extend(push_string(remaps.CUTSCENE_OLD_ACTION))
    plain.extend(bytes((140, 139)))
    plain.extend(native(0, 3, True))
    plain.append(122)
    plain_raw, _ = fixture(bytes(plain), [remaps.IS_DIGITAL_ACTION_PRESSED_HASH])
    untouched, report = remaps.patch_cutscene_skip(plain_raw, 0)
    assert untouched == plain_raw and report == []

    print('PASS RDR input remaps: camp Travel action relocates calls/jumps/switches/function pointers; cutscene Skip is structurally scoped')


if __name__ == '__main__':
    main()
