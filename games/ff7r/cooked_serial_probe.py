"""Read-only serialized-export evidence for split FF7R cooked packages.

Object-table ownership proves *which* exports/classes exist, but not which
serialized property names occur inside one export payload. This module adds a
narrow layer for research probes: when a split `.uasset` header size matches the
actual `.uasset` byte length, map each export's absolute SerialOffset into the
paired `.uexp` and scan only for FName-shaped references to requested names.

A candidate becomes stronger `propertyTagLike` evidence only when the following
FName resolves to a known `*Property` serializer name. For those candidates the
probe also records the generic UE4 property-tag size/array fields when they are
plausible. This is still read-only research evidence: integer bytes can resemble
FNames/property headers, and this module does not parse, rewrite, or claim the
semantics/value layout of arbitrary UE properties.
"""

from __future__ import annotations

from pathlib import Path
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
    """Return only the generic size/array prefix after name+type FNames.

    UE4 property tags place signed int32 Size and ArrayIndex values after the
    property-name and property-type FNames. Type-specific metadata follows those
    fields, so this helper deliberately does not infer the serialized value start.
    """
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
        # UE serialized property tags are naturally 4-byte aligned. Scanning at
        # that granularity sharply reduces random integer/FName lookalikes while
        # avoiding an unsafe assumption that every tag begins at an 8-byte edge.
        for relative in range(0, max(0, len(payload) - 7), 4):
            name_index, number = struct.unpack_from("<iI", payload, relative)
            if name_index not in matched or number > MAX_FNAME_NUMBER:
                continue
            type_ref = _fname_at(payload, relative + 8, table)
            type_name = type_ref[0] if type_ref else ""
            property_like = type_name in KNOWN_PROPERTY_TYPES
            tag_header = _property_tag_header_fields(payload, relative, type_name)
            context_start = max(0, relative - 16)
            context_end = min(len(payload), relative + 40)
            refs.append({
                **identity,
                "name": matched[name_index] if number == 0 else f"{matched[name_index]}_{number - 1}",
                "nameIndex": name_index,
                "nameNumber": number,
                "propertyType": type_name,
                "propertyTagLike": property_like,
                **tag_header,
                "exportRelativeOffset": relative,
                "uexpOffset": start + relative,
                "contextHex": payload[context_start:context_end].hex(),
            })
            if len(refs) >= limit:
                break
        if len(refs) >= limit:
            break

    refs.sort(key=lambda row: (
        not bool(row["propertyTagLike"]),
        not bool(row["propertyTagHeaderPlausible"]),
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
        "matchedNameCount": len(matched),
        "refs": reported,
        "refsTruncated": len(refs) >= limit,
        "propertyTagLikeCount": sum(bool(row["propertyTagLike"]) for row in reported),
        "propertyTagHeaderPlausibleCount": sum(
            bool(row["propertyTagHeaderPlausible"]) for row in reported
        ),
        "unmappedExports": unmapped,
        "notes": [
            "FName-shaped hits are candidate serialized references, not parsed UE property values.",
            "propertyTagLike requires the immediately following FName to resolve to a known UE *Property serializer type.",
            "propertyTagHeaderPlausible additionally requires non-negative bounded generic Size and ArrayIndex fields after the two FNames.",
            "Type-specific tag metadata follows those generic fields, so declaredValueSize does not identify the serialized value start or authorize mutation.",
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
