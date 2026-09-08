from __future__ import annotations

import struct

from games.ff7r.cooked_serial_probe import extract_serialized_name_refs


def _fstring(value: str) -> bytes:
    raw = value.encode("utf-8") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def _fname(index: int, number: int = 0) -> bytes:
    return struct.pack("<iI", index, number)


def _fixture():
    names = [
        "/Script/CoreUObject",
        "Package",
        "Class",
        "/Script/EndGame",
        "EndBattleLockonMarkerIcon",
        "LockonWidget",
        "ColorAndOpacity",
        "BrushTintColor",
        "StructProperty",
        "RandomTintWord",
        "NotAPropertyType",
    ]
    ni = {name: index for index, name in enumerate(names)}

    header = bytearray()
    header += struct.pack("<I", 0x9E2A83C1)
    header += struct.pack("<i", -4)
    header += struct.pack("<i", 0)
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

    def imported(class_package, class_name, outer, object_name):
        return (
            _fname(ni[class_package])
            + _fname(ni[class_name])
            + struct.pack("<i", outer)
            + _fname(ni[object_name])
        )

    header += imported("/Script/CoreUObject", "Package", 0, "/Script/EndGame")
    header += imported("/Script/CoreUObject", "Class", -1, "EndBattleLockonMarkerIcon")

    payload = bytearray()
    payload += _fname(ni["ColorAndOpacity"])
    payload += _fname(ni["StructProperty"])
    payload += b"\xAA" * 16
    payload += _fname(ni["BrushTintColor"])
    payload += _fname(ni["StructProperty"])
    # FName-shaped but followed by a non-property type: useful weaker evidence,
    # never a parsed/property-tag claim.
    payload += _fname(ni["RandomTintWord"])
    payload += _fname(ni["NotAPropertyType"])

    exports_offset = len(header)
    export = bytearray()
    export += struct.pack("<iiii", -2, 0, 0, 0)
    export += _fname(ni["LockonWidget"])
    export += struct.pack("<Iqq", 0, len(payload), 0)
    assert len(export) == 44
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
    # Export SerialOffset is 36 bytes into the stable export prefix.
    struct.pack_into("<q", header, exports_offset + 36, total_header_size)
    return bytes(header), bytes(payload)


def test_serialized_export_probe_maps_split_payload_and_property_tag_like_refs():
    uasset, uexp = _fixture()
    result = extract_serialized_name_refs(
        uasset,
        uexp,
        tokens=["Color", "Tint"],
        label="LockonWidget.uasset",
    )

    assert result["mappingTrusted"] is True
    assert result["mappingReason"] == "serial-offset-minus-total-header-size"
    refs = {row["name"]: row for row in result["refs"]}
    assert refs["ColorAndOpacity"]["propertyTagLike"] is True
    assert refs["ColorAndOpacity"]["propertyType"] == "StructProperty"
    assert refs["BrushTintColor"]["propertyTagLike"] is True
    assert refs["BrushTintColor"]["exportRelativeOffset"] == 32
    assert refs["RandomTintWord"]["propertyTagLike"] is False
    assert refs["ColorAndOpacity"]["className"] == "EndBattleLockonMarkerIcon"
    assert refs["ColorAndOpacity"]["objectName"] == "LockonWidget"
    assert result["propertyTagLikeCount"] == 2


def test_serialized_export_probe_fails_closed_when_physical_header_boundary_disagrees():
    uasset, uexp = _fixture()
    result = extract_serialized_name_refs(
        uasset + b"trailing",
        uexp,
        tokens=["Color"],
    )
    assert result["mappingTrusted"] is False
    assert result["mappingReason"] == "total-header-size-does-not-match-uasset-length"
    assert result["refs"] == []


def test_serialized_export_probe_reports_unmapped_export_range_without_scanning_it():
    uasset, uexp = _fixture()
    data = bytearray(uasset)
    # Export table is the sole 104-byte record immediately before the 4-byte
    # depends table in this fixture. Move SerialOffset beyond the paired uexp.
    exports_offset = len(data) - 4 - 104
    struct.pack_into("<q", data, exports_offset + 36, len(data) + len(uexp) + 100)
    result = extract_serialized_name_refs(bytes(data), uexp, tokens=["Color"])
    assert result["mappingTrusted"] is True
    assert result["refs"] == []
    assert len(result["unmappedExports"]) == 1


def test_serialized_export_probe_does_not_scan_unaligned_fname_lookalike():
    uasset, uexp = _fixture()
    # Prepend two bytes, keeping the export's declared size/range internally
    # valid by replacing its payload with an unaligned-only name sequence.
    data = bytearray(uexp)
    color_ref = data[:8]
    struct_ref = data[8:16]
    unaligned = b"\x00\x00" + color_ref + struct_ref + b"\x00" * (len(data) - 18)
    result = extract_serialized_name_refs(uasset, unaligned, tokens=["ColorAndOpacity"])
    assert not any(row["propertyTagLike"] for row in result["refs"])
