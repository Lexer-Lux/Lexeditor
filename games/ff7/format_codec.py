"""Bounded FF7 English text, LZS and binary helpers; no installed assets.

Encoding and container facts: cebix/ff7tools and Shojy/Elena, credited in
THIRD_PARTY.md. Unknown text bytes are represented reversibly as \\xHH.
"""
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import struct

TEXT_MAP = (
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"
    "`abcdefghijklmnopqrstuvwxyz{|}~ ÄÅÇÉÑÖÜáàâäãåçéèêëíìîïñóòôöõúù"
    "ûü♥°¢£↔→♪ßα  ´¨≠ÆØ∞±≤≥¥µ∂ΣΠπ⌡ªºΩæø¿¡¬√ƒ≈∆«»… ÀÃÕŒœ"
    "–—“”‘’÷◊ÿŸ⁄ ‹›ﬁﬂ■‧‚„‰ÂÊÁËÈÍÎÏÌÓÔ ÒÚÛÙıˆ˜¯˘˙˚¸˝˛ˇ       "
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def bounds(data, offset: int, size: int) -> None:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(f"Truncated FF7 data at 0x{offset:X}, need {size} bytes")


def read_int(data, offset: int, size: int = 2, signed: bool = False) -> int:
    bounds(data, offset, size)
    return int.from_bytes(data[offset:offset + size], "little", signed=signed)


def command_size(byte: int) -> int:
    return 3 if 0xEA <= byte <= 0xF0 else 2 if byte == 0xF8 else 1


def text_end(data, start=0) -> int:
    pos = start
    while pos < len(data):
        byte = data[pos]
        if byte == 255:
            return pos
        size = command_size(byte)
        bounds(data, pos, size)
        pos += size
    raise ValueError("FF7 string is missing its terminator")


def decode_text(data: bytes) -> str:
    end, out, pos = text_end(data), [], 0
    while pos < end:
        byte, size = data[pos], command_size(data[pos])
        if size > 1:
            out.extend(f"\\x{value:02X}" for value in data[pos:pos + size])
        elif byte < 0xE7 and byte < len(TEXT_MAP) and TEXT_MAP.index(TEXT_MAP[byte]) == byte:
            out.append("\\\\" if TEXT_MAP[byte] == "\\" else TEXT_MAP[byte])
        else:
            out.append(f"\\x{byte:02X}")
        pos += size
    return "".join(out)


def encode_text(text: str) -> bytes:
    if type(text) is not str or len(text) > 65535:
        raise ValueError("FF7 text must be a string, at most 65535 characters")
    out, pos = bytearray(), 0
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            if text[pos:pos + 2] == "\\\\":
                out.append(TEXT_MAP.index("\\")); pos += 2; continue
            if text[pos:pos + 2] != "\\x" or pos + 4 > len(text):
                raise ValueError("Use \\\\ for a backslash or \\xHH for a game byte")
            token = text[pos + 2:pos + 4]
            if any(c not in '0123456789abcdefABCDEF' for c in token):
                raise ValueError("Invalid \\xHH text escape")
            out.append(int(token, 16)); pos += 4; continue
        if char not in TEXT_MAP or TEXT_MAP.index(char) >= 0xE7:
            raise ValueError(f"{char!r} is not in the English FF7 encoding")
        out.append(TEXT_MAP.index(char)); pos += 1
    # Appending a terminator must not complete a truncated control's argument.
    pos = 0
    while pos < len(out):
        byte, size = out[pos], command_size(out[pos])
        if byte in (0xF9, 0xFF):
            raise ValueError("Raw dictionary references and embedded terminators are not editable text")
        bounds(out, pos, size)
        pos += size
    return bytes(out) + b'\xff'


def string_table(data: bytes) -> list[str]:
    if not data:
        return []
    first = read_int(data, 0)
    if first < 2 or first % 2 or first > len(data):
        raise ValueError("Invalid FF7 string pointer table")

    def expand(start, stop, depth=0):
        if depth > 32 or start < first or start >= len(data):
            raise ValueError("Invalid FF7 text dictionary reference")
        out, pos = bytearray(), start
        while pos < min(stop, len(data)):
            byte = data[pos]; pos += 1
            if byte == 0xF9:
                if pos >= stop:
                    raise ValueError("Truncated dictionary reference")
                bounds(data, pos, 1)
                arg = data[pos]; pos += 1
                ref = pos - (arg & 63) - 3
                if ref >= pos - 2:
                    raise ValueError("Self/forward dictionary reference")
                raw, ended = expand(ref, ref + (arg >> 6) * 2 + 4, depth + 1)
                out.extend(raw)
                if ended:
                    return out, True
            else:
                out.append(byte)
                if byte == 255:
                    return out, True
                args = command_size(byte) - 1
                if pos + args > stop:
                    raise ValueError("Truncated text control")
                bounds(data, pos, args)
                out.extend(data[pos:pos + args]); pos += args
            if len(out) > 65535:
                raise ValueError("Expanded FF7 text exceeds the section limit")
        return out, False

    strings = []
    for address in struct.unpack_from('<' + 'H' * (first // 2), data):
        raw, ended = expand(address, len(data))
        if not ended:
            raise ValueError("Unterminated FF7 text")
        strings.append(decode_text(raw))
    return strings


def pack_strings(strings: list[str]) -> bytes:
    if not strings:
        return b''
    if len(strings) > 32767:
        raise ValueError("Too many FF7 strings")
    body, addresses, known = bytearray(), [], {}
    for text in strings:
        raw = encode_text(text)
        if raw not in known:
            known[raw] = len(body)
            body.extend(raw)
        addresses.append(2 * len(strings) + known[raw])
    if len(body) % 2:
        body.append(255)
    if len(body) + 2 * len(strings) > 65535:
        raise ValueError("Text section exceeds its 16-bit container capacity")
    return struct.pack('<' + 'H' * len(addresses), *addresses) + body


def lzs_decode(data: bytes, limit: int = 32 * 1024 * 1024) -> bytes:
    if read_int(data, 0, 4) != len(data) - 4:
        raise ValueError("LZS compressed-size header does not match its file")
    ring, write, pos, out = bytearray(4096), 0xFEE, 4, bytearray()
    while pos < len(data):
        flags = data[pos]; pos += 1
        if pos == len(data):
            raise ValueError("LZS flag byte has no tokens")
        for bit in range(8):
            if pos == len(data):
                break
            if flags & (1 << bit):
                if len(out) >= limit:
                    raise ValueError("LZS output exceeds its bounded buffer")
                byte = data[pos]; pos += 1
                out.append(byte); ring[write] = byte; write = (write + 1) & 4095
            else:
                bounds(data, pos, 2)
                low, high = data[pos:pos + 2]; pos += 2
                start, length = low | ((high & 0xF0) << 4), (high & 15) + 3
                if len(out) + length > limit:
                    raise ValueError("LZS output exceeds its bounded buffer")
                for index in range(length):
                    byte = ring[(start + index) & 4095]
                    out.append(byte); ring[write] = byte; write = (write + 1) & 4095
    return bytes(out)


def lzs_encode(data: bytes) -> bytes:
    index, encoded = 0, bytearray()
    positions = defaultdict(lambda: deque(maxlen=64))
    while index < len(data):
        flag_at = len(encoded); encoded.append(0)
        for bit in range(8):
            if index == len(data):
                break
            best, match = 0, 0
            for candidate in reversed(positions[data[index:index + 3]]):
                if index - candidate > 4096:
                    break
                length = 0
                while length < 18 and index + length < len(data) and data[candidate + length] == data[index + length]:
                    length += 1
                if length > best:
                    best, match = length, candidate
                if best == 18:
                    break
            if best >= 3:
                pointer = (match + 0xFEE) & 4095
                encoded.extend((pointer & 255, ((pointer >> 4) & 0xF0) | (best - 3)))
            else:
                best = 1; encoded[flag_at] |= 1 << bit; encoded.append(data[index])
            for consumed in range(index, index + best):
                positions[data[consumed:consumed + 3]].append(consumed)
            index += best
    return struct.pack('<I', len(encoded)) + encoded
