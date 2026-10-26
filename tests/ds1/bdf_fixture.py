"""Tiny BDF3 builder: synthetic .chrtpfbdt character archives for tests."""
from bhf_fixture import make_edge


BDF_MAGIC = b'BDF307D7R6\x00\x00\x00\x00\x00\x00'


def make_bdf(members):
    """members: [plain TPF bytes]; each becomes one 16-aligned DCX slot."""
    out = bytearray(BDF_MAGIC)
    for plain in members:
        out += make_edge(plain)
        while len(out) % 16:
            out += b'\x00'
    return bytes(out)
