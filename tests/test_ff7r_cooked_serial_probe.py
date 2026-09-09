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
        "RelativeLocation",
        "BattleLockonMarker00Widget",
        "StructProperty",
        "SoftClassProperty",
        "LinearColor",
        "Vector",
        "/Game/UI/WBP_LockonDefault.WBP_LockonDefault_C",
        "RandomTintWord",
        "NotAPropertyType",
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

    def imported(class_package, class_name, outer, object_name):
        return (
            _fname(ni[class_package])
            + _fname(ni[class_name])
            + struct.pack("<i", outer)
            + _fname(ni[object_name])
        )

    header += imported("/Script/CoreUObject", "Package", 0, "/Script/EndGame")
    header += imported("/Script/CoreUObject", "Class", -1, "EndBattleLockonMarkerIcon")

    def struct_tag(name: str, struct_name: str, values: tuple[float, ...]) -> bytes:
        tag = bytearray()
        tag += _fname(ni[name])
        tag += _fname(ni["StructProperty"])
        tag += struct.pack("<ii", len(values) * 4, 0)
        tag += _fname(ni[struct_name])
        tag += b"\0" * 16
        tag += b"\0"
        tag += struct.pack("<" + "f" * len(values), *values)
        return bytes(tag)

    def soft_class_tag(name: str, asset_path: str) -> bytes:
        value = _fname(ni[asset_path]) + struct.pack("<i", 0)
        tag = bytearray()
        tag += _fname(ni[name])
        tag += _fname(ni["SoftClassProperty"])
        tag += struct.pack("<ii", len(value), 0)
        tag += b"\0"  # HasPropertyGuid for FileVersionUE4 >= 365.
        tag += value
        return bytes(tag)

    payload = bytearray()
    payload += struct_tag("ColorAndOpacity", "LinearColor", (0.0, 0.5, 1.0, 1.0))
    payload += struct_tag("BrushTintColor", "LinearColor", (1.0, 1.0, 1.0, 1.0))
    payload += struct_tag("RelativeLocation", "Vector", (100.0, -25.5, 12.25))
    payload += soft_class_tag(
        "BattleLockonMarker00Widget",
        "/Game/UI/WBP_LockonDefault.WBP_LockonDefault_C",
    )
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
    struct.pack_into("<q", header, exports_offset + 36, total_header_size)
    return bytes(header), bytes(payload)


def test_serialized_export_probe_maps_split_payload_and_versioned_property_layouts():
    uasset, uexp = _fixture()
    result = extract_serialized_name_refs(
        uasset,
        uexp,
        tokens=["Color", "Tint"],
        label="LockonWidget.uasset",
    )

    assert result["mappingTrusted"] is True
    assert result["mappingReason"] == "serial-offset-minus-total-header-size"
    assert result["fileVersion"] == 522
    refs = {row["name"]: row for row in result["refs"]}
    color = refs["ColorAndOpacity"]
    brush = refs["BrushTintColor"]
    assert color["propertyTagLike"] is True
    assert color["propertyType"] == "StructProperty"
    assert color["propertyTagHeaderPlausible"] is True
    assert color["propertyTagLayoutPlausible"] is True
    assert color["declaredValueSize"] == 16
    assert color["arrayIndex"] == 0
    assert color["typeMetadata"]["structName"] == "LinearColor"
    assert color["typeMetadata"]["structGuidHex"] == "00" * 16
    assert color["typeMetadata"]["hasPropertyGuid"] is False
    assert color["valueOffset"] == 49
    assert color["valueEndOffset"] == 65
    assert color["linearColorValuePlausible"] is True
    assert color["linearColorValue"] == {"r": 0.0, "g": 0.5, "b": 1.0, "a": 1.0}
    assert color["vectorValuePlausible"] is False
    assert color["softObjectPathValuePlausible"] is False

    assert brush["propertyTagLike"] is True
    assert brush["propertyTagHeaderPlausible"] is True
    assert brush["propertyTagLayoutPlausible"] is True
    assert brush["declaredValueSize"] == 16
    assert brush["exportRelativeOffset"] == 65
    assert brush["valueOffset"] == 114
    assert brush["linearColorValue"] == {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}
    assert refs["RandomTintWord"]["propertyTagLike"] is False
    assert refs["RandomTintWord"]["propertyTagHeaderPlausible"] is False
    assert refs["RandomTintWord"]["propertyTagLayoutPlausible"] is False
    assert color["className"] == "EndBattleLockonMarkerIcon"
    assert color["objectName"] == "LockonWidget"
    assert result["propertyTagLikeCount"] == 2
    assert result["propertyTagHeaderPlausibleCount"] == 2
    assert result["propertyTagLayoutPlausibleCount"] == 2
    assert result["linearColorValueCandidateCount"] == 2
    assert result["vectorValueCandidateCount"] == 0
    assert result["softObjectPathValueCandidateCount"] == 0


def test_exact_vector_struct_property_decodes_three_finite_float_components():
    uasset, uexp = _fixture()
    result = extract_serialized_name_refs(uasset, uexp, tokens=["RelativeLocation"])

    assert result["vectorValueCandidateCount"] == 1
    ref = result["refs"][0]
    assert ref["propertyType"] == "StructProperty"
    assert ref["typeMetadata"]["structName"] == "Vector"
    assert ref["declaredValueSize"] == 12
    assert ref["vectorValuePlausible"] is True
    assert ref["vectorValue"] == {"x": 100.0, "y": -25.5, "z": 12.25}
    assert ref["linearColorValuePlausible"] is False
    assert ref["softObjectPathValuePlausible"] is False


def test_exact_soft_class_property_decodes_asset_path_and_empty_subpath():
    uasset, uexp = _fixture()
    result = extract_serialized_name_refs(
        uasset,
        uexp,
        tokens=["BattleLockonMarker00Widget"],
    )

    assert result["softObjectPathValueCandidateCount"] == 1
    ref = result["refs"][0]
    assert ref["propertyType"] == "SoftClassProperty"
    assert ref["propertyTagLayoutPlausible"] is True
    assert ref["declaredValueSize"] == 12
    assert ref["softObjectPathValuePlausible"] is True
    assert ref["softObjectPathValue"] == {
        "assetPath": "/Game/UI/WBP_LockonDefault.WBP_LockonDefault_C",
        "subPath": "",
    }
    assert ref["linearColorValuePlausible"] is False
    assert ref["vectorValuePlausible"] is False


def test_property_type_match_with_invalid_generic_header_remains_weaker_evidence():
    uasset, uexp = _fixture()
    data = bytearray(uexp)
    struct.pack_into("<i", data, 16, -1)

    result = extract_serialized_name_refs(uasset, bytes(data), tokens=["ColorAndOpacity"])
    ref = result["refs"][0]
    assert ref["propertyTagLike"] is True
    assert ref["propertyTagHeaderPlausible"] is False
    assert ref["propertyTagLayoutPlausible"] is False
    assert ref["declaredValueSize"] is None
    assert ref["arrayIndex"] is None
    assert ref["valueOffset"] is None
    assert result["propertyTagHeaderPlausibleCount"] == 0
    assert result["propertyTagLayoutPlausibleCount"] == 0


def test_invalid_property_guid_marker_rejects_layout_without_rejecting_generic_header():
    uasset, uexp = _fixture()
    data = bytearray(uexp)
    data[48] = 2

    result = extract_serialized_name_refs(uasset, bytes(data), tokens=["ColorAndOpacity"])
    ref = result["refs"][0]
    assert ref["propertyTagHeaderPlausible"] is True
    assert ref["propertyTagLayoutPlausible"] is False
    assert ref["valueOffset"] is None
    assert ref["linearColorValuePlausible"] is False
    assert ref["vectorValuePlausible"] is False
    assert ref["softObjectPathValuePlausible"] is False


def test_declared_value_must_fit_inside_export_before_layout_is_plausible():
    uasset, uexp = _fixture()
    data = bytearray(uexp)
    struct.pack_into("<i", data, 16, 1000)

    result = extract_serialized_name_refs(uasset, bytes(data), tokens=["ColorAndOpacity"])
    ref = result["refs"][0]
    assert ref["propertyTagHeaderPlausible"] is True
    assert ref["declaredValueSize"] == 1000
    assert ref["propertyTagLayoutPlausible"] is False
    assert ref["valueOffset"] is None


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
    exports_offset = len(data) - 4 - 104
    struct.pack_into("<q", data, exports_offset + 36, len(data) + len(uexp) + 100)
    result = extract_serialized_name_refs(bytes(data), uexp, tokens=["Color"])
    assert result["mappingTrusted"] is True
    assert result["refs"] == []
    assert len(result["unmappedExports"]) == 1


def test_unaligned_fname_lookalike_needs_full_type_metadata_before_becoming_strong_layout():
    uasset, uexp = _fixture()
    data = bytearray(uexp)
    color_ref = data[:8]
    struct_ref = data[8:16]
    unaligned = bytearray(len(data))
    unaligned[2:10] = color_ref
    unaligned[10:18] = struct_ref
    struct.pack_into("<ii", unaligned, 18, 16, 0)

    result = extract_serialized_name_refs(uasset, bytes(unaligned), tokens=["ColorAndOpacity"])
    ref = next(row for row in result["refs"] if row["exportRelativeOffset"] == 2)
    assert ref["propertyTagLike"] is True
    assert ref["propertyTagHeaderPlausible"] is True
    assert ref["propertyTagLayoutPlausible"] is False
    assert ref["linearColorValuePlausible"] is False
    assert ref["vectorValuePlausible"] is False
    assert ref["softObjectPathValuePlausible"] is False
