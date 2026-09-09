from __future__ import annotations

import struct

import pytest

from games.ff7r.textresource import (
    TextFormatError,
    TextResourcePackage,
    TEXT_NAME_COUNT_OFFSET,
    TEXT_NAME_MAP_OFFSET,
    TEXT_SERIAL_SIZE_FROM_END,
    UNREAL_SIGNATURE,
)


def fstring(value: str) -> bytes:
    try:
        raw = value.encode("ascii")
    except UnicodeEncodeError:
        raw = value.encode("utf-16-le")
        return struct.pack("<i", -(len(raw) // 2 + 1)) + raw + b"\0\0"
    return struct.pack("<i", len(raw) + 1) + raw + b"\0"


def fixture_pair() -> tuple[bytes, bytes]:
    names = ["ACTOR", "EMOTION"]
    uasset = bytearray(320)
    uasset[:4] = UNREAL_SIGNATURE
    struct.pack_into("<I", uasset, TEXT_NAME_COUNT_OFFSET, len(names))
    cursor = TEXT_NAME_MAP_OFFSET
    for name in names:
        encoded = fstring(name) + b"\0\0\0\0"
        uasset[cursor:cursor + len(encoded)] = encoded
        cursor += len(encoded)

    uexp = bytearray(b"\x00\x03")
    uexp += fstring("US")
    uexp += struct.pack("<iI", 0, 2)
    uexp += fstring("$Item_Test") + fstring("Buster Sword") + struct.pack("<I", 0)
    uexp += fstring("$Line_Test") + fstring("Hello") + struct.pack("<I", 1)
    uexp += struct.pack("<Ii", 0, 0) + fstring("Cloud")
    uexp += UNREAL_SIGNATURE
    struct.pack_into("<i", uasset, len(uasset) - TEXT_SERIAL_SIZE_FROM_END, len(uexp) - 4)
    return bytes(uasset), bytes(uexp)


def test_text_resource_reads_main_and_sub_entries():
    uasset, uexp = fixture_pair()
    package = TextResourcePackage.from_bytes(uasset, uexp)
    assert package.language == "US"
    assert package.text_map()["$Item_Test"] == "Buster Sword"
    assert package.entries[1].subentries[0].id == "ACTOR"
    assert package.entries[1].subentries[0].text == "Cloud"


def test_variable_length_text_write_updates_uasset_and_round_trips():
    uasset, uexp = fixture_pair()
    package = TextResourcePackage.from_bytes(uasset, uexp)
    package.apply_edits([
        {"entry": 0, "text": "An Extremely Long Buster Sword Name"},
        {"entry": 1, "text": "こんにちは、ミッドガル"},
        {"entry": 1, "subId": "ACTOR", "text": "クラウド"},
    ])
    assert len(package.uexp_bytes) != len(uexp)
    declared = struct.unpack_from(
        "<i", package.uasset_bytes, len(package.uasset_bytes) - TEXT_SERIAL_SIZE_FROM_END
    )[0]
    assert declared == len(package.uexp_bytes) - len(UNREAL_SIGNATURE)

    reread = TextResourcePackage.from_bytes(bytes(package.uasset_bytes), bytes(package.uexp_bytes))
    assert reread.entries[0].text == "An Extremely Long Buster Sword Name"
    assert reread.entries[1].text == "こんにちは、ミッドガル"
    assert reread.entries[1].subentries[0].text == "クラウド"


def test_text_resource_rejects_invalid_edits():
    uasset, uexp = fixture_pair()
    package = TextResourcePackage.from_bytes(uasset, uexp)
    with pytest.raises(ValueError, match="NUL"):
        package.apply_edits([{"entry": 0, "text": "bad\0text"}])
    with pytest.raises(KeyError, match="sub-entry"):
        package.apply_edits([{"entry": 1, "subId": "NOPE", "text": "x"}])
    with pytest.raises(IndexError, match="out of range"):
        package.apply_edits([{"entry": 99, "text": "x"}])


def test_text_resource_rejects_bad_trailing_signature():
    uasset, uexp = fixture_pair()
    damaged = bytearray(uexp)
    damaged[-4:] = b"NOPE"
    with pytest.raises(TextFormatError, match="signature"):
        TextResourcePackage.from_bytes(uasset, bytes(damaged))
