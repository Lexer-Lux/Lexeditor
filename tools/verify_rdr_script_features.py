"""Portable contracts for the RDR1 passenger-coach bytecode patch."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.rdr import script_features as scripts


def fixture(native_hash=scripts.WAS_CONTEXT_EVER_PRESSED_HASH, *, opcode=scripts.OP_JUMP_FALSE):
    raw = bytearray(0x5000)
    code_table = 0x100
    native_table = 0x120
    code_page = 0x1000
    code_length = 0x2000
    struct.pack_into('<I', raw, 8, 0x50000000 | code_table)
    struct.pack_into('<I', raw, 12, code_length)
    struct.pack_into('<I', raw, 32, 1)
    struct.pack_into('<I', raw, 36, 0x50000000 | native_table)
    struct.pack_into('<I', raw, code_table, 0x50000000 | code_page)
    struct.pack_into('<I', raw, native_table, native_hash)
    start = scripts.COACH_FUNCTION_OFFSET
    body = start + 5
    raw[code_page + start:code_page + start + 5] = bytes((45, 0, 0, 0, 0))
    raw[code_page + body] = 139  # Push immediate 0: synthetic context handle.
    raw[code_page + body + 1:code_page + body + 4] = bytes((44, 3, 0))  # Native: one param, one return, index 0.
    jump = body + 4
    raw[code_page + jump] = opcode
    struct.pack_into('>h', raw, code_page + jump + 1, 3)
    raw[code_page + jump + 3:code_page + jump + 6] = b'\x00\x00\x00'
    raw[code_page + jump + 6] = 122  # ReturnP0R0.
    return bytes(raw), code_page, jump


def expect_failure(label, fn, contains):
    try:
        fn()
    except (ValueError, RuntimeError) as error:
        assert contains in str(error), (label, error)
    else:
        raise AssertionError(f'{label} unexpectedly succeeded')


def main():
    raw, page, jump = fixture()
    patched, report = scripts.patch_auto_carriage_rest(raw, 0)
    absolute = page + jump
    assert patched[absolute:absolute + 3] == bytes((scripts.OP_POP, 0, 0))
    assert patched[:absolute] == raw[:absolute]
    assert patched[absolute + 3:] == raw[absolute + 3:]
    assert report['functionOffset'] == 0x1DC8
    assert report['nativeHash'] == '0x971559CA'
    assert report['branchOffset'] == jump
    assert report['oldJumpTarget'] == jump + 6

    # Repatching must refuse the no-longer-stock shape instead of drifting further.
    expect_failure('already patched', lambda: scripts.patch_auto_carriage_rest(patched, 0), 'audited JumpFalse')
    wrong, _, _ = fixture(0x12345678)
    expect_failure('wrong native hash', lambda: scripts.patch_auto_carriage_rest(wrong, 0), 'found 0')
    wrong_jump, _, _ = fixture(opcode=98)
    expect_failure('wrong branch opcode', lambda: scripts.patch_auto_carriage_rest(wrong_jump, 0), 'audited JumpFalse')
    bad_enter = bytearray(raw)
    bad_enter[page + scripts.COACH_FUNCTION_OFFSET] = 0
    expect_failure('wrong function shape', lambda: scripts.patch_auto_carriage_rest(bytes(bad_enter), 0), 'Expected Function_41 Enter')

    # RSC85 extended flags with a single fallback 4 KiB virtual page resolve
    # object start zero, matching MagicRDR's page-walk semantics.
    packed = bytearray(16)
    struct.pack_into('<IIII', packed, 0, scripts.RSC85_MAGIC, 2, 0x80000000, 0x80000001)
    assert scripts._object_start_from_rsc85(bytes(packed)) == 0
    packed[4:8] = struct.pack('<I', 1)
    expect_failure('non-script resource', lambda: scripts._object_start_from_rsc85(bytes(packed)), 'type-2')

    print('PASS RDR carriage Rest patch: exact 3-byte branch slot, stack-preserving POP/NOP/NOP, structural drift fails closed')


if __name__ == '__main__':
    main()
