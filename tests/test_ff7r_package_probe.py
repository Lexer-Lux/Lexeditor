from __future__ import annotations

import struct

import pytest

from games.ff7r.dataobject import FormatError
from games.ff7r.package_probe import parse_object_table


def _fstring(value: str) -> bytes:
    encoded = value.encode("utf-8") + b"\0"
    return struct.pack("<i", len(encoded)) + encoded


def _fname(index: int, number: int = 0) -> bytes:
    return struct.pack("<iI", index, number)


def fixture_object_package() -> bytes:
    names = [
        "/Script/CoreUObject",
        "Package",
        "Class",
        "/Script/EndGame",
        "EndFieldActionActorBenchBreak",
        "EndFieldActionActorVendingMachine",
        "PersistentLevel",
        "BenchActor",
        "VendingActor",
    ]
    name_index = {name: index for index, name in enumerate(names)}

    header = bytearray()
    header += struct.pack("<I", 0x9E2A83C1)
    header += struct.pack("<i", -4)  # legacy file version
    header += struct.pack("<i", 0)  # unversioned cooked UE4 package
    header += struct.pack("<i", 0)  # licensee version
    header += struct.pack("<i", 0)  # empty custom-version container
    total_header_offset = len(header)
    header += struct.pack("<i", 0)
    header += struct.pack("<i", 0)  # empty package FString
    header += struct.pack("<I", 0)  # package flags
    summary_counts = len(header)
    header += b"\0" * 36  # names/gatherable/exports/imports + depends
    header += b"\0" * (96 - len(header))

    names_offset = len(header)
    for name in names:
        header += _fstring(name)
        header += b"\0\0\0\0"  # FNameEntry hashes

    imports_offset = len(header)

    def imported(class_package: str, class_name: str, outer: int, object_name: str):
        return (
            _fname(name_index[class_package])
            + _fname(name_index[class_name])
            + struct.pack("<i", outer)
            + _fname(name_index[object_name])
        )

    # Import 0 is the EndGame script package. Imports 1/2 are native classes
    # nested under it. 28 bytes per FF7R-era FObjectImport record.
    header += imported("/Script/CoreUObject", "Package", 0, "/Script/EndGame")
    header += imported("/Script/CoreUObject", "Class", -1, "EndFieldActionActorBenchBreak")
    header += imported("/Script/CoreUObject", "Class", -1, "EndFieldActionActorVendingMachine")

    exports_offset = len(header)

    def exported(class_index: int, outer_index: int, object_name: str, serial_size: int, serial_offset: int):
        prefix = struct.pack("<iiii", class_index, 0, 0, outer_index)
        prefix += _fname(name_index[object_name])
        prefix += struct.pack("<Iqq", 0, serial_size, serial_offset)
        assert len(prefix) == 44
        return prefix + b"\0" * (104 - len(prefix))

    # Export 0 is PersistentLevel. The two actors share it as their outer.
    header += exported(0, 0, "PersistentLevel", 0, 0)
    header += exported(-2, 1, "BenchActor", 120, 0x5000)
    header += exported(-3, 1, "VendingActor", 144, 0x6000)

    depends_offset = len(header)
    header += b"\0" * 12
    total_header_size = len(header)

    struct.pack_into("<i", header, total_header_offset, total_header_size)
    struct.pack_into(
        "<iiiiiiiii",
        header,
        summary_counts,
        len(names),
        names_offset,
        0,
        0,
        3,
        exports_offset,
        3,
        imports_offset,
        depends_offset,
    )
    return bytes(header)


def test_object_probe_resolves_native_actor_classes_and_shared_outer():
    table = parse_object_table(fixture_object_package(), label="fixture.umap")
    assert table.import_stride == 28
    assert table.export_stride == 104
    assert table.summary()["exportCount"] == 3

    rows = table.export_rows()
    level, bench, vending = rows
    assert level["objectName"] == "PersistentLevel"
    assert bench["className"] == "EndFieldActionActorBenchBreak"
    assert bench["classPath"] == "/Script/EndGame.EndFieldActionActorBenchBreak"
    assert bench["objectPath"] == "PersistentLevel.BenchActor"
    assert bench["outerPath"] == "PersistentLevel"
    assert bench["serialSize"] == 120
    assert bench["serialOffset"] == 0x5000
    assert vending["className"] == "EndFieldActionActorVendingMachine"
    assert vending["classPath"] == "/Script/EndGame.EndFieldActionActorVendingMachine"
    assert vending["outerPath"] == bench["outerPath"]


def test_object_probe_preserves_fname_numeric_suffixes():
    data = bytearray(fixture_object_package())
    table = parse_object_table(data)
    # BenchActor's FName lives 16 bytes into export 1, after one 104-byte record.
    bench_name_number = (
        table.summary()["totalHeaderSize"]  # just to exercise stable summary API
    )
    assert bench_name_number > 0

    # Locate the export table from the synthetic layout without relying on a
    # private parser field: its three 104-byte records end at the 12-byte depends map.
    depends_offset = len(data) - 12
    exports_offset = depends_offset - 3 * 104
    struct.pack_into("<I", data, exports_offset + 104 + 20, 3)
    rows = parse_object_table(bytes(data)).export_rows()
    assert rows[1]["objectName"] == "BenchActor_2"
    assert rows[1]["objectPath"] == "PersistentLevel.BenchActor_2"


def test_object_probe_fails_closed_on_unsupported_export_stride():
    data = bytearray(fixture_object_package())
    # Summary's depends offset is the ninth int in the 36-byte table block at 32.
    depends_field = 32 + 8 * 4
    table = parse_object_table(data)
    depends_offset = len(data) - 12
    exports_offset = depends_offset - table.export_stride * len(table.exports)
    # Claim a next-table boundary only 40 bytes per export away, shorter than
    # the stable prefix required to read serial size/offset safely.
    struct.pack_into("<i", data, depends_field, exports_offset + len(table.exports) * 40)
    with pytest.raises(FormatError, match="export record stride"):
        parse_object_table(bytes(data), label="bad.umap")


def test_object_probe_rejects_out_of_range_package_index():
    data = bytearray(fixture_object_package())
    depends_offset = len(data) - 12
    exports_offset = depends_offset - 3 * 104
    struct.pack_into("<i", data, exports_offset + 104, -99)
    with pytest.raises(FormatError, match="class package index"):
        parse_object_table(bytes(data), label="bad-index.umap")
