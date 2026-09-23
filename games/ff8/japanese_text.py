"""Japanese FF8 glyph pages, based on Deling's GPL-3.0-or-later font table.

Control tokens retain the shared editor syntax. Unknown bytes stay explicit.
"""
import json
from pathlib import Path

from . import kernel_text

_TABLES = json.loads(Path(__file__).with_name("japanese_font.json").read_text(
    encoding="utf-8"))["tables"]
_GLYPHS = {}
for page, table in enumerate(_TABLES):
    for slot, glyph in enumerate(table):
        if glyph:
            _GLYPHS.setdefault(glyph, (bytes((0x18 + page,)) if page else b"")
                               + bytes((slot + 0x20,)))


def decode(data: bytes) -> str:
    out = []
    index = 0
    while index < len(data):
        value = data[index]
        size = 1
        glyph = None
        if value >= 0x20:
            glyph = _TABLES[0][value - 0x20]
        elif 0x19 <= value <= 0x1B and index + 1 < len(data):
            size = 2
            parameter = data[index + 1]
            if parameter >= 0x20:
                glyph = _TABLES[value - 0x18][parameter - 0x20]
        elif value in (0x03, 0x05, 0x0A, 0x0E) and index + 1 < len(data):
            size = 2
            glyph = kernel_text.decode(data[index:index + size])
        elif value == 0x02:
            glyph = "\n"
        elif value in (0x04, 0x06, 0x09, 0x1C) and index + 1 < len(data):
            size = 2
        out.append(glyph or "".join(f"{{x{byte:02X}}}" for byte in data[index:index + size]))
        index += size
    return "".join(out)


def encode(text: str) -> bytes:
    out = bytearray()
    index = 0
    while index < len(text):
        if text[index] == "{":
            end = text.find("}", index)
            if end < 0:
                raise ValueError("FF8 text has an opening brace without a closing brace")
            out.extend(kernel_text.encode(text[index:end + 1], compress=False))
            index = end + 1
        elif text[index] == "\n":
            out.append(2)
            index += 1
        else:
            glyph = next((glyph for glyph in sorted(_GLYPHS, key=len, reverse=True)
                          if text.startswith(glyph, index)), None)
            if glyph is None:
                raise ValueError(f"Character {text[index]!r} is not available in the Japanese FF8 font")
            out.extend(_GLYPHS[glyph])
            index += len(glyph)
    return bytes(out)
