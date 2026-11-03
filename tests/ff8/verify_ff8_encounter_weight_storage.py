"""Weight trailer round trips and original native file-load/pointer setup."""
from pathlib import Path
import struct
import sys
from hashlib import sha256

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP,
    UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8 import encounter_chances as chances, paths, world_map
from plugins.ff8.executable_text import SUPPORTED_EXE_SHA256


def rejects(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('Invalid encounter storage was accepted')


def run():
    for base in (bytes(192), bytes(193)):
        first = chances.with_weights(base, 2, {1: [256]+[0]*7})
        original, records = chances.read_extension(first, 2)
        assert original == base and records == [chances.DEFAULT_OUTCOMES, (256, 0, 0, 0, 0, 0, 0, 0)]
        second = chances.with_weights(first, 2, {0: [32]*8})
        assert len(first) == len(second)
        assert chances.read_extension(second, 2)[1] == [(32,)*8, records[1]]
        restored = chances.with_weights(second, 2, {0: list(chances.DEFAULT_OUTCOMES), 1: list(chances.DEFAULT_OUTCOMES)})
        assert restored == base
        for invalid in (None, [], {True: [32]*8}, {-1: [32]*8}, {2: [32]*8}, {0: [31]*8}):
            rejects(lambda: chances.with_weights(first, 2, invalid))
        damaged = bytearray(first)
        damaged[len(base)+len(base)%2+16] ^= 1
        rejects(lambda: chances.read_extension(bytes(damaged), 2))
        rejects(lambda: chances.read_extension(first, 1))
        for record, replacement in ((0, struct.pack('<8H', *([32]*8))),
                                    (1, bytes(16))):
            damaged = bytearray(first)
            start = len(base)+len(base)%2
            damaged[start+record*16:start+(record+1)*16] = replacement
            # A matching checksum cannot make invalid distributions valid.
            damaged[-32:] = sha256(damaged[start:-48]).digest()
            rejects(lambda: chances.read_extension(bytes(damaged), 2))
        for footer_index in (-40, -36):
            damaged = bytearray(first)
            damaged[footer_index] ^= 1
            rejects(lambda: chances.read_extension(bytes(damaged), 2))
    rejects(lambda: chances.with_weights(bytes(chances.MAX_WMSET_SIZE), 2, {0: [32]*8}))
    for count in (True, 0, -1, 65537, 2.0, '2'):
        rejects(lambda: chances.read_extension(bytes(192), count))
    for raw_data in (None, {}, 'world data', bytes(191), bytes(chances.MAX_WMSET_SIZE+1)):
        rejects(lambda: chances.read_extension(raw_data, 2))

    exe_path = paths.GAME_ROOT / 'FF8_EN.exe'
    source = world_map.source_path('vanilla')
    if not exe_path.exists() or not source.exists():
        print('SKIP native storage loading: installed supported executable and vanilla wmset required; trailer checks passed')
        return
    exe, raw = exe_path.read_bytes(), source.read_bytes()
    assert sha256(exe).hexdigest() == SUPPORTED_EXE_SHA256
    parsed = world_map.parse(raw)
    count = len(parsed['groups'])
    modified = chances.with_weights(raw, count, {0: [256]+[0]*7, count-1: [0]*7+[256]})
    assert modified[:len(raw)] == raw
    assert world_map.parse(modified) == parsed
    offset = chances.extension_offset(modified, count, world_map._pointers(raw)[3])
    assert offset is not None
    patch = chances.selector_patch(exe, offset)
    pe = pefile.PE(data=exe, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    load_address, next_world_address = 0x1E9DC3C, 0x1F9DC40
    assert load_address+len(modified) < next_world_address
    snapshots = []

    for payload in (raw, modified):
        engine = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0x510000, 0x50000), (0xC75000, 0x1000),
                              (0x1E90000, 0x120000), (0x2030000, 0x20000),
                              (0x30000000, 0x10000)):
            engine.mem_map(address, size)
        engine.mem_write(0x510000, image[0x510000-base:0x560000-base])
        engine.mem_write(0xC75000, image[0xC75000-base:0xC76000-base])
        engine.mem_write(load_address, b'\xa5'*(chances.MAX_WMSET_SIZE+4))
        requests = []

        def external_file_io(uc, address, size, _):
            if address not in (0x55B53E, 0x51B4E0, 0x51BDC0, 0x51BE40, 0x51BF50):
                return
            stack = uc.reg_read(UC_X86_REG_ESP)
            target, = struct.unpack('<I', uc.mem_read(stack, 4))
            args = struct.unpack('<3I', uc.mem_read(stack+4, 12))
            if address == 0x51B4E0:  # archive open
                result = 7
            elif address == 0x51BDC0:  # seek: file, offset, origin
                assert args[0] == 7 and args[1] == 0 and args[2] in (0, 2)
                result = len(payload) if args[2] == 2 else 0
            elif address == 0x51BE40:  # archive read
                assert args == (7, load_address, len(payload))
                requests.append(args)
                uc.mem_write(args[1], payload)
                result = len(payload)
            else:  # debug print / archive close
                result = 0
            uc.reg_write(UC_X86_REG_EAX, result)
            uc.reg_write(UC_X86_REG_ESP, stack+4)
            uc.reg_write(UC_X86_REG_EIP, target)

        engine.hook_add(UC_HOOK_CODE, external_file_io)
        stop, stack = 0x3000F000, 0x3000FE00
        engine.mem_write(stack, struct.pack('<3I', stop, 0xC762B4, load_address))
        engine.reg_write(UC_X86_REG_ESP, stack)
        engine.emu_start(0x52D400, stop, count=5000)
        assert engine.reg_read(UC_X86_REG_EIP) == stop
        assert engine.reg_read(UC_X86_REG_EAX) == len(payload)
        assert requests == [(7, load_address, len(payload))]
        assert bytes(engine.mem_read(load_address, len(payload))) == payload
        assert bytes(engine.mem_read(load_address+len(payload), chances.MAX_WMSET_SIZE+4-len(payload))) == b'\xa5'*(chances.MAX_WMSET_SIZE+4-len(payload))
        engine.mem_write(stack, struct.pack('<I', stop))
        engine.reg_write(UC_X86_REG_ESP, stack)
        engine.emu_start(0x542DA0, stop, count=5000)
        assert engine.reg_read(UC_X86_REG_EIP) == stop
        snapshots.append(bytes(engine.mem_read(0x2030000, 0x20000)))
        group_pointer, = struct.unpack('<I', engine.mem_read(0x2036BE8, 4))
        assert group_pointer == load_address+world_map._pointers(raw)[3]
        if payload == modified:
            engine.mem_write(chances.SELECTOR_START, patch)
            # Pointer setup and file loading precede selector execution. The
            # selector receives the actual group pointer and loaded trailer.
            for group, slot in ((0, 0), (count-1, 7)):
                for shift in range(256):
                    engine.mem_write(0x2040A61, bytes([shift, 0]))
                    engine.mem_write(0x20400A0, struct.pack('<H', 65535))
                    engine.mem_write(0x3000FDFD, b'\0')
                    engine.mem_write(0x3000FE08, struct.pack('<I', 0x30000100))
                    engine.reg_write(UC_X86_REG_EBP, 0x3000FE00)
                    engine.reg_write(UC_X86_REG_ESP, 0x3000FD00)
                    engine.reg_write(UC_X86_REG_ESI, group)
                    engine.reg_write(UC_X86_REG_EDI, group)
                    engine.emu_start(chances.SELECTOR_START, chances.SELECTOR_END, count=500)
                    assert engine.reg_read(UC_X86_REG_EIP) == chances.SELECTOR_END
                    scene, = struct.unpack('<H', engine.mem_read(0x30000100, 2))
                    assert scene == parsed['groups'][group]['encounters'][slot]
    assert snapshots[0] == snapshots[1], 'Trailer changed native section pointer setup'
    print(f'PASS encounter weight storage: bounded/checked trailer, exact restoration; native loader reads '
          f'{len(raw)} and {len(modified)} bytes, section setup unchanged; first/last of {count} groups use loaded weights')


if __name__ == '__main__':
    run()
