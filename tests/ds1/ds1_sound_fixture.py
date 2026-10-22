"""Synthetic FSB sound banks for the DS1 sound checks."""
import struct


def bank_bytes(names=("o7230.wav", "silen.wav")):
    """An FSB4 bank with framed MPEG payloads, one stream per name."""
    frame = bytes.fromhex("fffba060") + bytes(522 - 4)
    primer = bytes.fromhex("0a00fffb") + bytes(12)
    payloads = [primer + frame + b"\0\0" + frame for _ in names]
    data = bytearray(struct.pack("<4sIII", b"FSB4", len(names), 0, 0) + bytes(32))
    for name, payload in zip(names, payloads):
        head = bytearray(80)
        struct.pack_into("<H", head, 0, 80)
        encoded = name.encode("ascii")
        head[2:2 + len(encoded)] = encoded
        struct.pack_into("<II", head, 32, 2304, len(payload))
        struct.pack_into("<I", head, 52, 44100)
        data += head
    for payload in payloads:
        data += payload
    return bytes(data)
