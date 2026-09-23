"""Read FF8 Scan text and build the FFNx battle_scans.msd override.

The executable offset contract comes from FF8 Ultimate Editor's documented
English Scan section. The output contract comes from FFNx's exe-data loader.
Lexeditor never modifies FF8_EN.exe.
"""

from __future__ import annotations

from pathlib import Path
import re


SCAN_COUNT = 160
EXE_SCAN_OFFSET = 0x1487474
EXE_OFFSET_SIZE = 2
MSD_OFFSET_SIZE = 4

_NAMES = (
    "Squall", "Zell", "Irvine", "Quistis", "Rinoa", "Selphie", "Seifer",
    "Edea", "Laguna", "Kiros", "Ward", "Angelo", "Griever", "Boko",
)
_NAME_BYTES = {
    **{name: bytes((0x03, 0x30 + index)) for index, name in enumerate(_NAMES[:11])},
    "Angelo": bytes((0x03, 0x40)),
    "Griever": bytes((0x03, 0x50)),
    "Boko": bytes((0x03, 0x60)),
}
_BYTE_NAMES = {value[1]: name for name, value in _NAME_BYTES.items()}

# FF8's English single-byte text table. Scan text in the installed English
# executable uses only this printable range, newlines, and character-name tags.
_GLYPHS = (
    " 0123456789%/:!?…+-=*&「」()·.,~”“‘#$'_"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "ÀÁÂÄÇÈÉÊËÌÍÎÏÑÒÓÔÖÙÚÛÜŒß"
    "àáâäçèéêëìíîïñòóôöùúûüœ"
)
_BYTE_TO_GLYPH = {0x20 + index: glyph for index, glyph in enumerate(_GLYPHS)}
_BYTE_TO_GLYPH.update({
    0xA9: "[", 0xAA: "]", 0xAB: "■", 0xAC: "○", 0xAD: "♦",
    0xAE: "【", 0xAF: "】", 0xB0: "□", 0xB2: "『", 0xB3: "』", 0xB5: ";",
})
_GLYPH_TO_BYTE = {glyph: value for value, glyph in _BYTE_TO_GLYPH.items() if glyph}
_RAW_TOKEN = re.compile(r"\{x([0-9a-fA-F]{2}|[0-9a-fA-F]{4})\}")


def decode_text(raw: bytes) -> str:
    """Decode one null-terminated FF8 English text entry."""
    result: list[str] = []
    index = 0
    while index < len(raw):
        value = raw[index]
        if value == 0:
            break
        if value == 1:
            result.append("{NewPage}")
        elif value == 2:
            result.append("\n")
        elif value == 3:
            if index + 1 >= len(raw):
                result.append("{x03}")
            else:
                code = raw[index + 1]
                name = _BYTE_NAMES.get(code)
                result.append(f"{{{name}}}" if name else f"{{x03{code:02x}}}")
                index += 1
        elif value < 0x20:
            if index + 1 < len(raw):
                result.append(f"{{x{value:02x}{raw[index + 1]:02x}}}")
                index += 1
            else:
                result.append(f"{{x{value:02x}}}")
        else:
            glyph = _BYTE_TO_GLYPH.get(value)
            result.append(glyph if glyph is not None else f"{{x{value:02x}}}")
        index += 1
    return "".join(result)


def encode_text(text: str) -> bytes:
    """Encode one editable Scan description without dropping unknown data."""
    result = bytearray()
    index = 0
    while index < len(text):
        if text[index] == "\n":
            result.append(2)
            index += 1
            continue
        if text.startswith("{NewPage}", index):
            result.append(1)
            index += len("{NewPage}")
            continue
        matched_name = next((name for name in _NAMES if text.startswith(f"{{{name}}}", index)), None)
        if matched_name is not None:
            result.extend(_NAME_BYTES[matched_name])
            index += len(matched_name) + 2
            continue
        raw_token = _RAW_TOKEN.match(text, index)
        if raw_token:
            encoded = bytes.fromhex(raw_token.group(1))
            if 0 in encoded:
                raise ValueError("A Scan description cannot contain a raw null byte")
            result.extend(encoded)
            index = raw_token.end()
            continue
        glyph = text[index]
        code = _GLYPH_TO_BYTE.get(glyph)
        if code is None:
            raise ValueError(
                f"Scan descriptions cannot encode {glyph!r} at character {index + 1}"
            )
        result.append(code)
        index += 1
    result.append(0)
    return bytes(result)


def _entries(data: bytes, offsets: list[int], text_start: int) -> list[str]:
    if len(offsets) != SCAN_COUNT or offsets != sorted(offsets):
        raise ValueError("The Scan text offset table is invalid")
    descriptions: list[str] = []
    for index, offset in enumerate(offsets):
        start = text_start + offset
        limit = text_start + offsets[index + 1] if index + 1 < len(offsets) else len(data)
        if not text_start <= start < len(data) or not start < limit <= len(data):
            raise ValueError("A Scan text offset is outside its file")
        end = data.find(b"\0", start, limit)
        if end < 0:
            raise ValueError(f"Scan text {index} has no terminator")
        descriptions.append(decode_text(data[start:end + 1]))
    return descriptions


def read_executable(path: Path) -> list[str]:
    data = path.read_bytes()
    table_size = SCAN_COUNT * EXE_OFFSET_SIZE
    if len(data) <= EXE_SCAN_OFFSET + table_size:
        raise ValueError("FF8_EN.exe does not contain the English Scan text section")
    offsets = [
        int.from_bytes(data[EXE_SCAN_OFFSET + index * 2:EXE_SCAN_OFFSET + index * 2 + 2], "little")
        for index in range(SCAN_COUNT)
    ]
    return _entries(data, offsets, EXE_SCAN_OFFSET + table_size)


def read_msd(path: Path) -> list[str]:
    data = path.read_bytes()
    table_size = SCAN_COUNT * MSD_OFFSET_SIZE
    if len(data) <= table_size:
        raise ValueError("battle_scans.msd is too short")
    offsets = [int.from_bytes(data[index * 4:index * 4 + 4], "little") for index in range(SCAN_COUNT)]
    if offsets[0] != table_size:
        raise ValueError("battle_scans.msd does not contain 160 Scan offsets")
    return _entries(data, [offset - table_size for offset in offsets], table_size)


def build_msd(descriptions: list[str]) -> bytes:
    if len(descriptions) != SCAN_COUNT:
        raise ValueError(f"FF8 requires exactly {SCAN_COUNT} Scan descriptions")
    encoded = [encode_text(str(description)) for description in descriptions]
    table_size = SCAN_COUNT * MSD_OFFSET_SIZE
    offset = table_size
    output = bytearray()
    for entry in encoded:
        output.extend(offset.to_bytes(4, "little"))
        offset += len(entry)
    for entry in encoded:
        output.extend(entry)
    return bytes(output)
