"""Tiny BHF3/EDGE builders: synthetic split texture archives for tests."""
import struct
import zlib


STRICT_HEAD = bytes.fromhex('000100000000001800000024000000240000002c')


def make_edge(plain):
    """DCX-compress like the game archives: the strict header the
    shared inflate accepts."""
    stream = zlib.compress(bytes(plain), 9)
    head = bytearray(76)
    head[0:4] = b'DCX\0'
    head[4:24] = STRICT_HEAD
    head[24:28] = b'DCS\0'
    struct.pack_into('>II', head, 28, len(plain), len(stream))
    head[36:40] = b'DCP\0'
    head[40:44] = b'DFLT'
    head[68:76] = b'DCA\0\0\0\0\x08'
    return bytes(head) + stream


def make_bhf(entries):
    """entries: [(path, offset, size)]; paths like the game writes them."""
    names = [path.encode('ascii') + bytes((0,)) for path, _, _ in entries]
    base = 28 + 24 * len(entries)
    head = bytearray(28)
    head[0:12] = b'BHF307D7R6\x00\x00'
    struct.pack_into('<I', head, 16, len(entries))
    out = bytes(head)
    at, prev = base, 0
    for (_, offset, size), encoded in zip(entries, names):
        index = (len(out) - 28) // 24
        out += struct.pack('<6I', prev, 64, size, offset, index, at)
        prev, at = size, at + len(encoded)
    return out + b''.join(names)
