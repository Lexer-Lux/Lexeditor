"""Fast LZS (LZSS) decoder for FF8 archives.

Byte-identical to ``vendor.ff8ue.lzs.Lzs.decode``: N=4096, F=18,
threshold=2, zero-filled ring starting at position N-F. The vendored
decoder yields one byte at a time through a nested call; this one
dispatches one symbol at a time and copies match runs with slices,
which is what the Models/Textures tabs spend most of their load on.
"""

from __future__ import annotations

_N = 4096
_MASK = _N - 1
_START = _N - 18
_THRESHOLD = 2


def decode_lzs(payload: bytes) -> bytes:
    """Expand LZS-compressed ``payload`` to its full bytes."""
    data = payload if isinstance(payload, bytes) else bytes(payload)
    size = len(data)
    pos = 0
    # The zero seed doubles as the ring's initial history: output byte t
    # lives at index _N + t, and matches reaching before byte 0 read zeros.
    out = bytearray(_N)
    r = _START
    flags = 0
    while pos < size:
        if not flags & 0x100:
            flags = data[pos] | 0xFF00
            pos += 1
        if flags & 1:
            if pos >= size:
                break
            out.append(data[pos])
            pos += 1
            r = (r + 1) & _MASK
        else:
            if pos + 1 >= size:
                break
            low = data[pos]
            high = data[pos + 1]
            pos += 2
            offset = low | ((high & 0xF0) << 4)
            count = (high & 0x0F) + _THRESHOLD + 1
            back = (r - offset) & _MASK or _N
            r = (r + count) & _MASK
            # A match may overlap its own source; copy in rounds that never
            # read past what is already decoded.
            src = len(out) - back
            need = count
            while need > 0:
                take = back if back < need else need
                out += out[src:src + take]
                need -= take
        flags >>= 1
    return bytes(out[_N:])
