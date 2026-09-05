"""Native execution evidence for the post-update camera seam, not live acceptance."""
from pathlib import Path
import hashlib
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_ECX, UC_X86_REG_EBX

EXE = Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe')
SHA = '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
CAMERA = 0x203ECF8
PLAYER = 0x203EE80
MOVEMENT = 0x203FE48
RETURN = 0x558FF0


def machine(exe):
    m = Uc(UC_ARCH_X86, UC_MODE_32)
    m.mem_map(0x540000, 0x19000)
    m.mem_write(0x540000, exe[0x140000:0x159000])
    m.mem_map(0x2030000, 0x20000)
    m.mem_map(0x1CA9000, 0x1000)
    m.mem_map(0x3000000, 0x2000)
    return m


def put(m, address, *words):
    m.mem_write(address, struct.pack('<' + 'I' * len(words), *words))


def follow_trace(exe, vehicle=False, delta=16, manual_policy=False, shoulder=0,
                 center_after=None, reset_at=None, core=None):
    """Execute actual terminal camera-follow branches, retaining inertia."""
    m = machine(exe)
    put(m, 0x20409E0, 0x32 if vehicle else 0)
    trace = []
    base = 0x3001000
    manual = False
    for frame in range(300):
        before = struct.unpack('<H', m.mem_read(CAMERA + 10, 2))[0]
        step = 0 if center_after is not None and frame >= center_after else delta
        if frame == reset_at:
            manual = False
            step = 0
        elif step:
            manual = True
        m.mem_write(0x203ED5E, bytes([shoulder & 255]))
        put(m, base, 0, RETURN, PLAYER, 0x203ED50, MOVEMENT, CAMERA)
        put(m, base - 0x3C, 0, 0, 0)
        m.reg_write(UC_X86_REG_EBP, base)
        m.reg_write(UC_X86_REG_ESP, base - 0x3C)
        m.reg_write(UC_X86_REG_ESI, 0x32 if vehicle else 0)
        m.reg_write(UC_X86_REG_ECX, 0)
        m.reg_write(UC_X86_REG_EBX, 0)
        m.emu_start(0x55874A if vehicle else 0x55856B, RETURN, count=500)
        native = struct.unpack('<H', m.mem_read(CAMERA + 10, 2))[0]
        yaw = ((before if manual_policy and manual and not shoulder else native) + step) & 4095
        if core is not None:
            core.stdin.write(f'{before} {native} {255 if step else 128} {int(bool(shoulder))} {int(frame == reset_at)}\n')
            core.stdin.flush()
            yaw = int(core.stdout.readline())
        m.mem_write(CAMERA + 10, struct.pack('<H', yaw))
        trace.append(yaw)
    return trace


def main():
    exe = EXE.read_bytes()
    assert hashlib.sha256(exe).hexdigest() == SHA
    for call in (0x53FBB4, 0x54101C):
        data = exe[call - 0x400000:call - 0x400000 + 5]
        assert data[0] == 0xE8
        assert call + 5 + struct.unpack('<i', data[1:])[0] == 0x557A90
        assert exe[call - 0x400000 - 20:call - 0x400000] == b''.join(
            b'\x68' + struct.pack('<I', arg)
            for arg in (CAMERA, MOVEMENT, 0x203ED50, PLAYER))
    cases = 0
    # Prove that the native right-Y consumer writes a mixed world-input field.
    # Returning center from its callback removes this source of side effects.
    for axis in (0, 64, 128, 192, 255):
        m = machine(exe)
        put(m, 0x20409A4, axis)
        m.reg_write(UC_X86_REG_ESI, 0x203ED50)
        m.reg_write(UC_X86_REG_EDI, 0)
        m.mem_write(0x203ED5B, b'\x00')
        m.emu_start(0x557477, 0x55749C, count=100)
        expected = (127 - axis) & 255 if abs(axis - 128) > 45 else 0
        assert m.mem_read(0x203ED5B, 1)[0] == expected
    for yaw in (-128, -1, 0, 1, 2048, 4095, 4096, 4223):
        m = machine(exe)
        m.mem_write(CAMERA + 10, struct.pack('<h', yaw))
        m.mem_write(PLAYER, bytes(range(32)))
        m.mem_write(0x1CA92E4, b'\x34\x12')
        base = 0x3001000
        put(m, base, 0xABCDEF, RETURN, PLAYER, 0x203ED50, MOVEMENT, CAMERA)
        put(m, base - 0x3C, 0x11, 0x22, 0x33)
        m.reg_write(UC_X86_REG_EBP, base)
        m.reg_write(UC_X86_REG_ESP, base - 0x3C)
        m.emu_start(0x558921, RETURN, count=100)
        assert struct.unpack('<H', m.mem_read(CAMERA + 10, 2))[0] == yaw % 4096
        assert bytes(m.mem_read(PLAYER, 32)) == bytes(range(32))
        assert bytes(m.mem_read(0x1CA92E4, 2)) == b'\x34\x12'
        # Execute the full immediately following native movement normalizer.
        m.reg_write(UC_X86_REG_ESP, base)
        put(m, base, RETURN, PLAYER, MOVEMENT)
        m.emu_start(0x558950, RETURN, count=100)
        assert struct.unpack('<H', m.mem_read(CAMERA + 10, 2))[0] == yaw % 4096
        assert bytes(m.mem_read(PLAYER, 32)) == bytes(range(32))
        assert bytes(m.mem_read(0x1CA92E4, 2)) == b'\x34\x12'
        # Execute downstream camera entry until its angle-difference call.
        # The actual camera tangent reaches the consumer, not an input field.
        m.mem_write(MOVEMENT + 10, struct.pack('<H', 123))
        put(m, base, RETURN)
        m.reg_write(UC_X86_REG_ESP, base)
        m.emu_start(0x544490, 0x558A00, count=100)
        stack = m.reg_read(UC_X86_REG_ESP)
        assert struct.unpack('<3I', m.mem_read(stack, 12)) == (0x5444BE, 123, yaw % 4096)
        cases += 1
    print(f'Native camera seam: {cases} boundary cases, 5 right-Y cases; both caller argument layouts passed')
    # A naive post-update delta cannot overcome the native automatic follow.
    # Preserve this regression evidence so a wrapper does not claim full orbit.
    for vehicle in (False, True):
        trace = follow_trace(exe, vehicle)
        assert max(trace) < 512, (vehicle, max(trace))
        print(f'Post-delta-only limitation: vehicle={vehicle}, max yaw={max(trace)}, final={trace[-1]}')
        controlled = follow_trace(exe, vehicle, manual_policy=True)
        assert controlled == [((frame + 1) * 16) & 4095 for frame in range(300)]
        held = follow_trace(exe, vehicle, manual_policy=True, center_after=100)
        assert held[100:] == [1600] * 200
        untouched = follow_trace(exe, vehicle, delta=0, manual_policy=True)
        assert untouched == follow_trace(exe, vehicle, delta=0)
        for shoulder in (-127, 127):
            assert follow_trace(exe, vehicle, manual_policy=True, shoulder=shoulder) == follow_trace(exe, vehicle, shoulder=shoulder)
        reset = follow_trace(exe, vehicle, manual_policy=True, center_after=100, reset_at=110)
        assert reset[110] != held[110], 'Reset must accept native follow again'
    print('Manual policy model: full orbit, center hold, native shoulders, inactive pass-through and reset passed')


if __name__ == '__main__':
    main()
