"""Read-only serialized-export evidence for split FF7R cooked packages.

Object-table ownership proves *which* exports/classes exist, but not which
serialized property names occur inside one export payload. This module adds a
narrow layer for research probes: when a split `.uasset` header size matches the
actual `.uasset` byte length, map each export's absolute SerialOffset into the
paired `.uexp` and scan only for FName-shaped references to requested names.

A candidate becomes stronger `propertyTagLike` evidence only when the following
FName resolves to a known `*Property` serializer name. Generic Size/ArrayIndex
fields are then checked, and the old UE4 FPropertyTag type-specific prefix is
parsed conservatively from the package's own file version. For StructProperty
this can identify StructName/StructGuid, the optional PropertyGuid flag, and the
bounded value start without guessing fixed FF7R offsets.

This remains read-only research evidence. A structurally valid property tag does
not prove that a candidate property owns the visible lock-on reticle, that its
value is active-state-only, or that rewriting it is safe.
"""

from __future__ import annotations

from pathlib import Path
import math
import struct
from typing import Any, Iterable

from .archive import installed_paks
from .package_probe import PackageObjectTable, parse_object_table
from .raw_asset_probe import select_shadowed_assets
from .tooling import get_file, list_pak


MAX_REFS = 256
MAX_ERRORS = 128
MAX_FNAME_NUMBER = 1_000_000
MAX_PROPERTY_VALUE_SIZE = 256 * 1024 * 1024
MAX_PROPERTY_ARRAY_INDEX = 1_000_000
KNOWN_PROPERTY_TYPES = frozenset({
    "ArrayProperty", "BoolProperty", "ByteProperty", "ClassProperty",
    "DelegateProperty", "DoubleProperty", "EnumProperty", "FloatProperty",
    "Int16Property", "Int64Property", "Int8Property", "IntProperty",
    "InterfaceProperty", "MapProperty", "MulticastDelegateProperty",
    "NameProperty", "ObjectProperty", "SetProperty", "SoftClassProperty",
    "SoftObjectProperty", "StrProperty", "StructProperty", "TextProperty",
    "UInt16Property", "UInt32Property", "UInt64Property", "WeakObjectProperty",
})

# UE4 object-version gates used by FPropertyTag's old-format serializer. FF7R's
# package parser already exposes FileVersionUE4, so the serialized probe can use
# the package's own value instead of assuming one engine minor globally.
VER_UE4_ARRAY_PROPERTY_INNER_TAGS = 228
VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT = 322
VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG = 336
VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 365


def _matched_name_indices(table: PackageObjectTable, tokens: Iterable[str]) -> dict[int, str]:
    folded = tuple(str(token).casefold() for token in tokens if str(token).strip())
    return {
        index: name
        for index, name in enumerate(table.names)
        if any(token in name.casefold() for token in folded)
    }


def _fname_at(data: bytes, offset: int, table: PackageObjectTable) -> tuple[str, int] | None:
    if offset < 0 or offset + 8 > len(data):
        return None
    index, number = struct.unpack_from("<iI", data, offset)
    if index < 0 or index >= len(table.names) or number > MAX_FNAME_NUMBER:
        return None
    name = table.names[index]
    return (name if number == 0 else f"{name}_{number - 1}", number)


def _property_tag_header_fields(data: bytes, offset: int, property_type: str) -> dict[str, Any]:
    """Return the generic Size/ArrayIndex prefix after name+type FNames."""
    if property_type not in KNOWN_PROPERTY_TYPES or offset < 0 or offset + 24 > len(data):
        return {
            "propertyTagHeaderPlausible": False,
            "declaredValueSize": None,
            "arrayIndex": None,
        }
    declared_size, array_index = struct.unpack_from("<ii", data, offset + 16)
    plausible = bool(
        0 <= declared_size <= MAX_PROPERTY_VALUE_SIZE
        and 0 <= array_index <= MAX_PROPERTY_ARRAY_INDEX
    )
    return {
        "propertyTagHeaderPlausible": plausible,
        "declaredValueSize": declared_size if plausible else None,
        "arrayIndex": array_index if plausible else None,
    }


def _read_required_fname(
    data: bytes,
    cursor: int,
    table: PackageObjectTable,
) -> tuple[str, int] | None:
    row = _fname_at(data, cursor, table)
    if row is None:
        return None
    return row[0], cursor + 8


def _property_tag_layout_fields(
    data: bytes,
    offset: int,
    property_type: str,
    table: PackageObjectTable,
    *,
    declared_size: int | None,
    header_plausible: bool,
) -> dict[str, Any]:
    """Conservatively parse old-format UE4 type metadata and bound the value.

    This is intentionally not a general property-value deserializer. It parses
    only FPropertyTag metadata whose field order is version-gated by the package's
    FileVersionUE4, then proves that the declared value fits inside this export.
    """
    result: dict[str, Any] = {
        "propertyTagLayoutPlausible": False,
        "typeMetadata": {},
        "valueOffset": None,
        "valueEndOffset": None,
        "valueHex": "",
        "linearColorValuePlausible": False,
        "linearColorValue": None,
    }
    if not header_plausible or declared_size is None:
        return result

    cursor = offset + 24
    metadata: dict[str, Any] = {}

    if property_type == "StructProperty":
        struct_name = _read_required_fname(data, cursor, table)
        if struct_name is None:
            return result
        metadata["structName"] = struct_name[0]
        cursor = struct_name[1]
        if table.file_version >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG:
            if cursor + 16 > len(data):
                return result
            metadata["structGuidHex"] = data[cursor:cursor + 16].hex()
            cursor += 16
        else:
            metadata["structGuidHex"] = None
    elif property_type == "BoolProperty":
        if cursor + 1 > len(data):
            return result
        metadata["boolTagValue"] = int(data[cursor])
        cursor += 1
    elif property_type in {"ByteProperty", "EnumProperty"}:
        enum_name = _read_required_fname(data, cursor, table)
        if enum_name is None:
            return result
        metadata["enumName"] = enum_name[0]
        cursor = enum_name[1]
    elif (
        property_type == "ArrayProperty"
        and table.file_version >= VER_UE4_ARRAY_PROPERTY_INNER_TAGS
    ):
        inner = _read_required_fname(data, cursor, table)
        if inner is None:
            return result
        metadata["innerType"] = inner[0]
        cursor = inner[1]
    elif (
        property_type == "SetProperty"
        and table.file_version >= VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT
    ):
        inner = _read_required_fname(data, cursor, table)
        if inner is None:
            return result
        metadata["innerType"] = inner[0]
        cursor = inner[1]
    elif (
        property_type == "MapProperty"
        and table.file_version >= VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT
    ):
        inner = _read_required_fname(data, cursor, table)
        if inner is None:
            return result
        value_type = _read_required_fname(data, inner[1], table)
        if value_type is None:
            return result
        metadata["innerType"] = inner[0]
        metadata["valueType"] = value_type[0]
        cursor = value_type[1]

    if table.file_version >= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG:
        if cursor + 1 > len(data):
            return result
        has_property_guid = int(data[cursor])
        if has_property_guid not in (0, 1):
            return result
        metadata["hasPropertyGuid"] = bool(has_property_guid)
        cursor += 1
        if has_property_guid:
            if cursor + 16 > len(data):
                return result
            metadata["propertyGuidHex"] = data[cursor:cursor + 16].hex()
            cursor += 16
    else:
        metadata["hasPropertyGuid"] = None

    value_end = cursor + declared_size
    if value_end < cursor or value_end > len(data):
        return result

    value = data[cursor:value_end]
    result.update({
        "propertyTagLayoutPlausible": True,
        "typeMetadata": metadata,
        "valueOffset": cursor,
        "valueEndOffset": value_end,
        "valueHex": value.hex(),
    })

    # FLinearColor is a particularly useful read-only lock-on tint lead: its
    # tagged StructProperty payload is four float32 components. Report it only
    # when the struct type and exact declared size agree and all components are
    # finite/bounded; do not infer SlateColor or other structs from raw bytes.
    struct_name = str(metadata.get("structName", ""))
    if property_type == "StructProperty" and struct_name.casefold() == "linearcolor" and declared_size == 16:
        red, green, blue, alpha = struct.unpack_from("<ffff", value, 0)
        components = (red, green, blue, alpha)
        if all(math.isfinite(component) and abs(component) <= 1_000_000 for component in components):
            result["linearColorValuePlausible"] = True
            result["linearColorValue"] = {
                "r": red,
                "g": green,
                "b": blue,
                "a": alpha,
            }
    return result


def _export_identity(table: PackageObjectTable, export_index: int) -> dict[str, Any]:
    row = table.export_rows()[export_index]
    return {
        "exportIndex": export_index,
        "objectName": row.get("objectName"),
        "objectPath": row.get("objectPath"),
        "outerPath": row.get("outerPath"),
        "className": row.get("className"),
        "classPath": row.get("classPath"),
        "serialSize": row.get("serialSize"),
        "serialOffset": row.get("serialOffset"),
    }


def extract_serialized_name_refs(
    uasset: bytes,
    uexp: bytes,
    *,
    tokens: Iterable[str],
    label: str = "cooked package",
    limit: int = MAX_REFS,
) -> dict[str, Any]:
    """Return bounded candidate FName/property-tag references per export."""
    if limit <= 0:
        return {
            "mappingTrusted": False,
            "mappingReason": "non-positive-limit",
            "refs": [],
            "unmappedExports": [],
        }
    table = parse_object_table(uasset, label=label)
    # FF7R split packages observed by Lexeditor serialize export offsets as if
    # `.uasset + .uexp` were one package. Only trust that mapping when the
    # package-declared header boundary exactly equals the physical .uasset size.
    if table.total_header_size != len(uasset):
        return {
            "mappingTrusted": False,
            "mappingReason": "total-header-size-does-not-match-uasset-length",
            "totalHeaderSize": table.total_header_size,
            "uassetSize": len(uasset),
            "uexpSize": len(uexp),
            "fileVersion": table.file_version,
            "refs": [],
            "unmappedExports": [],
        }

    matched = _matched_name_indices(table, tokens)
    refs: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    for export in table.exports:
        if export.serial_size <= 0:
            continue
        start = export.serial_offset - table.total_header_size
        end = start + export.serial_size
        identity = _export_identity(table, export.index)
        if start < 0 or end < start or end > len(uexp):
            unmapped.append({
                **identity,
                "uexpStart": start,
                "uexpEnd": end,
            })
            continue
        payload = uexp[start:end]
        # Property tags are not guaranteed to remain 4-byte aligned: old-format
        # BoolVal and HasPropertyGuid metadata are byte-sized. Scan bytewise, but
        # require the name index, bounded FName number, known property type, generic
        # header, and type-specific versioned layout independently so stronger
        # evidence stays highly constrained.
        for relative in range(0, max(0, len(payload) - 7)):
            name_index, number = struct.unpack_from("<iI", payload, relative)
            if name_index not in matched or number > MAX_FNAME_NUMBER:
                continue
            type_ref = _fname_at(payload, relative + 8, table)
            type_name = type_ref[0] if type_ref else ""
            property_like = type_name in KNOWN_PROPERTY_TYPES
            tag_header = _property_tag_header_fields(payload, relative, type_name)
            layout = _property_tag_layout_fields(
                payload,
                relative,
                type_name,
                table,
                declared_size=tag_header["declaredValueSize"],
                header_plausible=bool(tag_header["propertyTagHeaderPlausible"]),
            )
            context_start = max(0, relative - 16)
            context_end = min(len(payload), relative + 80)
            refs.append({
                **identity,
                "name": matched[name_index] if number == 0 else f"{matched[name_index]}_{number - 1}",
                "nameIndex": name_index,
                "nameNumber": number,
                "propertyType": type_name,
                "propertyTagLike": property_like,
                **tag_header,
                **layout,
                "exportRelativeOffset": relative,
                "uexpOffset": start + relative,
                "contextHex": payload[context_start:context_end].hex(),
            })
            if len(refs) >= limit:
                break
        if len(refs) >= limit:
            break

    refs.sort(key=lambda row: (
        not bool(row["propertyTagLayoutPlausible"]),
        not bool(row["propertyTagHeaderPlausible"]),
        not bool(row["propertyTagLike"]),
        int(row["exportIndex"]),
        int(row["exportRelativeOffset"]),
        str(row["name"]).casefold(),
    ))
    reported = refs[:limit]
    return {
        "mappingTrusted": True,
        "mappingReason": "serial-offset-minus-total-header-size",
        "totalHeaderSize": table.total_header_size,
        "uassetSize": len(uasset),
        "uexpSize": len(uexp),
        "fileVersion": table.file_version,
        "matchedNameCount": len(matched),
        "refs": reported,
        "refsTruncated": len(refs) >= limit,
        "propertyTagLikeCount": sum(bool(row["propertyTagLike"]) for row in reported),
        "propertyTagHeaderPlausibleCount": sum(
            bool(row["propertyTagHeaderPlausible"]) for row in reported
        ),
        "propertyTagLayoutPlausibleCount": sum(
            bool(row["propertyTagLayoutPlausible"]) for row in reported
        ),
        "linearColorValueCandidateCount": sum(
            bool(row["linearColorValuePlausible"]) for row in reported
        ),
        "unmappedExports": unmapped,
        "notes": [
            "FName-shaped hits are candidate serialized references, not semantic ownership proof.",
            "propertyTagLike requires the immediately following FName to resolve to a known UE *Property serializer type.",
            "propertyTagHeaderPlausible additionally requires non-negative bounded generic Size and ArrayIndex fields after the two FNames.",
            "propertyTagLayoutPlausible parses old-format UE4 type metadata and optional PropertyGuid using the package FileVersionUE4, then proves the declared value range stays inside the export.",
            "For StructProperty, typeMetadata records StructName and version-gated StructGuid. A LinearColor value is decoded only when StructName is exactly LinearColor and declared size is exactly 16 bytes.",
            "A valid LinearColor payload is still read-only evidence; this probe does not prove reticle ownership, active-state scope, or authorize replacement bytes.",
            "No export bytes are modified by this probe.",
        ],
    }


def probe_installed_serialized_exports(
    game_root: Path,
    *,
    terms: Iterable[str],
    tokens: Iterable[str],
) -> dict[str, Any]:
    """Find matching installed asset pairs and scan serialized export evidence."""
    game_root = Path(game_root).resolve()
    listings: list[tuple[str, list[str]]] = []
    paks: dict[str, Path] = {}
    errors: list[str] = []
    for pak in installed_paks(game_root):
        relative = pak.relative_to(game_root).as_posix()
        paks[relative] = pak
        try:
            listings.append((relative, list_pak(pak)))
        except Exception as error:
            if len(errors) < MAX_ERRORS:
                errors.append(f"{relative}: {error}")

    results = []
    for candidate in select_shadowed_assets(listings, terms=terms):
        sources = candidate.get("files", {})
        uasset_source = sources.get(".uasset")
        uexp_source = sources.get(".uexp")
        if not uasset_source or not uexp_source:
            continue
        try:
            uasset = get_file(paks[uasset_source["pak"]], uasset_source["path"])
            uexp = get_file(paks[uexp_source["pak"]], uexp_source["path"])
            evidence = extract_serialized_name_refs(
                uasset, uexp, tokens=tokens, label=uasset_source["path"],
            )
        except Exception as error:
            if len(errors) < MAX_ERRORS:
                errors.append(
                    f"{candidate['asset']}: serialized export probe failed: {error}"
                )
            continue
        results.append({
            "asset": candidate["asset"],
            "uasset": uasset_source,
            "uexp": uexp_source,
            **evidence,
        })

    return {
        "terms": list(terms),
        "assets": results,
        "scanErrors": errors,
        "notes": [
            "Serialized export evidence is read-only and is not sufficient by itself to authorize arbitrary UMG mutation.",
        ],
    }