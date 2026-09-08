from __future__ import annotations

import struct

import pytest

from games.ff7r.cooked_serial_edit import rewrite_unique_linear_color
from games.ff7r.cooked_serial_probe import extract_serialized_name_refs


def _fstring(value: str) -> bytes:
    raw = value.encode("utf-8") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def _fname(index: int, number: int = 0) -> bytes:
    return struct.pack("<iI", index, number)


def _fixture(*values: tuple[float, float, float, float]):
    values = values or ((1.0, 1.0, 1.0, 1.0),)
    names = [
        "/Script/CoreUObject",
        "Package",
        "Class",
        "/Script/EndGame",
        "EndBattleLockonMarkerIcon",
        "LockonWidget",
        "ColorAndOpacity",
        "StructProperty",
        "LinearColor",
    ]
    ni = {name: index for index, name in enumerate(names)}

    header = bytearray()
    header += struct.pack("<I", 0x9E2A83C1)
    header += struct.pack("<i", -4)
    header += struct.pack("<i", 522)
    header += struct.pack("<i", 0)
    header += struct.pack("<i", 0)
    total_header_offset = len(header)
    header += struct.pack("<i", 0)
    header += struct.pack("<i", 0)
    header += struct.pack("<I", 0)
    summary_counts = len(header)
    header += b"\0" * 36
    header += b"\0" * (96 - len(header))

    names_offset = len(header)
    for name in names:
        header += _fstring(name) + b"\0\0\0\0"

    imports_offset = len(header)

    def imported(class_package: str, class_name: str, outer: int, object_name: str) -> bytes:
        return (
            _fname(ni[class_package])
            + _fname(ni[class_name])
            + struct.pack("<i", outer)
            + _fname(ni[object_name])
        )

    header += imported("/Script/CoreUObject", "Package", 0, "/Script/EndGame")
    header += imported("/Script/CoreUObject", "Class", -1, "EndBattleLockonMarkerIcon")

    payload = bytearray()
    for rgba in values:
        payload += _fname(ni["ColorAndOpacity"])
        payload += _fname(ni["StructProperty"])
        payload += struct.pack("<ii", 16, 0)
        payload += _fname(ni["LinearColor"])
        payload += b"\0" * 16
        payload += b"\0"
        payload += struct.pack("<ffff", *rgba)

    exports_offset = len(header)
    export = bytearray()
    export += struct.pack("<iiii", -2, 0, 0, 0)
    export += _fname(ni["LockonWidget"])
    export += struct.pack("<Iqq", 0, len(payload), 0)
    export += b"\0" * (104 - len(export))
    header += export
    depends_offset = len(header)
    header += b"\0" * 4
    total_header_size = len(header)

    struct.pack_into("<i", header, total_header_offset, total_header_size)
    struct.pack_into(
        "<iiiiiiiii",
        header,
        summary_counts,
        len(names), names_offset,
        0, 0,
        1, exports_offset,
        2, imports_offset,
        depends_offset,
    )
    struct.pack_into("<q", header, exports_offset + 36, total_header_size)
    return bytes(header), bytes(payload)


def test_unique_linear_color_rewrite_changes_only_proven_16_value_bytes():
    uasset, uexp = _fixture((1.0, 1.0, 1.0, 1.0))

    changed, report = rewrite_unique_linear_color(
        uasset,
        uexp,
        property_name="ColorAndOpacity",
        class_name="EndBattleLockonMarkerIcon",
        object_name="LockonWidget",
        expected_rgba=(1.0, 1.0, 1.0, 1.0),
        replacement_rgba=(1.0, 0.0, 0.0, 1.0),
    )

    assert len(changed) == len(uexp)
    start = report["uexpValueOffset"]
    end = start + report["valueSize"]
    assert changed[:start] == uexp[:start]
    assert changed[end:] == uexp[end:]
    assert changed[start:end] == struct.pack("<ffff", 1.0, 0.0, 0.0, 1.0)
    assert report["fixedWidth"] is True
    assert report["bytesOutsideValuePreserved"] is True
    assert report["beforeDecoded"] == {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}
    assert report["afterDecoded"] == {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}

    reprobe = extract_serialized_name_refs(uasset, changed, tokens=("ColorAndOpacity",))
    assert reprobe["linearColorValueCandidateCount"] == 1
    assert reprobe["refs"][0]["linearColorValue"] == report["afterDecoded"]


def test_stale_expected_rgba_refuses_rewrite():
    uasset, uexp = _fixture((1.0, 1.0, 1.0, 1.0))

    with pytest.raises(ValueError, match="do not match expected_rgba"):
        rewrite_unique_linear_color(
            uasset,
            uexp,
            property_name="ColorAndOpacity",
            class_name="EndBattleLockonMarkerIcon",
            object_name="LockonWidget",
            expected_rgba=(0.0, 0.0, 0.0, 1.0),
            replacement_rgba=(1.0, 0.0, 0.0, 1.0),
        )


def test_duplicate_matching_linear_color_properties_fail_closed():
    uasset, uexp = _fixture(
        (1.0, 1.0, 1.0, 1.0),
        (0.5, 0.5, 0.5, 1.0),
    )

    with pytest.raises(ValueError, match="expected exactly one"):
        rewrite_unique_linear_color(
            uasset,
            uexp,
            property_name="ColorAndOpacity",
            class_name="EndBattleLockonMarkerIcon",
            object_name="LockonWidget",
            expected_rgba=(1.0, 1.0, 1.0, 1.0),
            replacement_rgba=(1.0, 0.0, 0.0, 1.0),
        )


def test_wrong_owner_or_untrusted_package_mapping_cannot_be_rewritten():
    uasset, uexp = _fixture((1.0, 1.0, 1.0, 1.0))

    with pytest.raises(ValueError, match="expected exactly one"):
        rewrite_unique_linear_color(
            uasset,
            uexp,
            property_name="ColorAndOpacity",
            class_name="Image",
            object_name="LockonWidget",
            expected_rgba=(1.0, 1.0, 1.0, 1.0),
            replacement_rgba=(1.0, 0.0, 0.0, 1.0),
        )

    with pytest.raises(ValueError, match="mapping is not trusted"):
        rewrite_unique_linear_color(
            uasset + b"trailing",
            uexp,
            property_name="ColorAndOpacity",
            class_name="EndBattleLockonMarkerIcon",
            object_name="LockonWidget",
            expected_rgba=(1.0, 1.0, 1.0, 1.0),
            replacement_rgba=(1.0, 0.0, 0.0, 1.0),
        )


def test_rewrite_rejects_nonfinite_or_wrong_arity_rgba():
    uasset, uexp = _fixture()

    with pytest.raises(ValueError, match="exactly four"):
        rewrite_unique_linear_color(
            uasset,
            uexp,
            property_name="ColorAndOpacity",
            class_name="EndBattleLockonMarkerIcon",
            object_name="LockonWidget",
            expected_rgba=(1.0, 1.0, 1.0, 1.0),
            replacement_rgba=(1.0, 0.0, 0.0),
        )

    with pytest.raises(ValueError, match="finite and bounded"):
        rewrite_unique_linear_color(
            uasset,
            uexp,
            property_name="ColorAndOpacity",
            class_name="EndBattleLockonMarkerIcon",
            object_name="LockonWidget",
            expected_rgba=(1.0, 1.0, 1.0, 1.0),
            replacement_rgba=(float("nan"), 0.0, 0.0, 1.0),
        )
