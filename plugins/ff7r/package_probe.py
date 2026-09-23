"""Read-only Unreal object-table parser for installed FF7R cooked packages.

This deliberately stops at package metadata: names, imports, and the stable
prefix of each export record.  It is intended for research probes that need to
identify an authored object/class without pretending arbitrary .umap/.uasset
payloads are safely editable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .dataobject import FormatError, MAX_NAMES, PACKAGE_TAG, Reader


MAX_IMPORTS = 1_000_000
MAX_EXPORTS = 1_000_000
MAX_RECORD_STRIDE = 512
IMPORT_PREFIX_SIZE = 28
EXPORT_PREFIX_SIZE = 44
MAX_RESOLVE_DEPTH = 64


@dataclass(frozen=True)
class NameRef:
    name: str
    number: int = 0

    @property
    def display(self) -> str:
        # Unreal's FName number 0 is the unsuffixed base name; positive values
        # are serialized one above the visible numeric suffix.
        return self.name if self.number == 0 else f"{self.name}_{self.number - 1}"


@dataclass(frozen=True)
class PackageImport:
    index: int
    class_package: NameRef
    class_name: NameRef
    outer_index: int
    object_name: NameRef


@dataclass(frozen=True)
class PackageExport:
    index: int
    class_index: int
    super_index: int
    template_index: int
    outer_index: int
    object_name: NameRef
    object_flags: int
    serial_size: int
    serial_offset: int


@dataclass(frozen=True)
class PackageObjectTable:
    names: tuple[str, ...]
    imports: tuple[PackageImport, ...]
    exports: tuple[PackageExport, ...]
    import_stride: int
    export_stride: int
    total_header_size: int
    file_version: int
    licensee_version: int

    def _object_name(self, package_index: int) -> str | None:
        if package_index == 0:
            return None
        if package_index < 0:
            index = -package_index - 1
            if 0 <= index < len(self.imports):
                return self.imports[index].object_name.display
            return None
        index = package_index - 1
        if 0 <= index < len(self.exports):
            return self.exports[index].object_name.display
        return None

    def resolve_path(self, package_index: int) -> str | None:
        """Resolve one FPackageIndex through import/export outers, fail-closing on cycles."""
        if package_index == 0:
            return None
        pieces: list[str] = []
        current = package_index
        seen: set[int] = set()
        for _ in range(MAX_RESOLVE_DEPTH):
            if current == 0:
                break
            if current in seen:
                return None
            seen.add(current)
            if current < 0:
                index = -current - 1
                if not (0 <= index < len(self.imports)):
                    return None
                row = self.imports[index]
                pieces.append(row.object_name.display)
                current = row.outer_index
            else:
                index = current - 1
                if not (0 <= index < len(self.exports)):
                    return None
                row = self.exports[index]
                pieces.append(row.object_name.display)
                current = row.outer_index
        else:
            return None
        return ".".join(reversed(pieces)) if pieces else None

    def export_rows(self) -> list[dict]:
        rows = []
        for export in self.exports:
            class_path = self.resolve_path(export.class_index)
            rows.append({
                "index": export.index,
                "packageIndex": export.index + 1,
                "objectName": export.object_name.display,
                "objectPath": self.resolve_path(export.index + 1),
                "outerIndex": export.outer_index,
                "outerPath": self.resolve_path(export.outer_index),
                "classIndex": export.class_index,
                "className": self._object_name(export.class_index),
                "classPath": class_path,
                "superIndex": export.super_index,
                "templateIndex": export.template_index,
                "serialSize": export.serial_size,
                "serialOffset": export.serial_offset,
            })
        return rows

    def summary(self) -> dict:
        return {
            "nameCount": len(self.names),
            "importCount": len(self.imports),
            "exportCount": len(self.exports),
            "importStride": self.import_stride,
            "exportStride": self.export_stride,
            "totalHeaderSize": self.total_header_size,
            "fileVersion": self.file_version,
            "licenseeVersion": self.licensee_version,
        }


def _read_fname(reader: Reader, names: tuple[str, ...] | list[str]) -> NameRef:
    index = reader.int32()
    number = reader.uint32()
    if index < 0 or index >= len(names):
        raise FormatError(f"{reader.label}: FName index {index} is outside the name table")
    return NameRef(names[index], number)


def _checked_count(value: int, maximum: int, label: str, kind: str) -> int:
    if value < 0 or value > maximum:
        raise FormatError(f"{label}: unreasonable {kind} count {value}")
    return value


def _checked_offset(value: int, size: int, label: str, kind: str, *, allow_zero: bool = True) -> int:
    if value == 0 and allow_zero:
        return value
    if value < 0 or value > size:
        raise FormatError(f"{label}: {kind} offset 0x{value:X} is outside the file")
    return value


def _derive_stride(
    *,
    start: int,
    count: int,
    minimum: int,
    candidates: Iterable[int],
    label: str,
    table_name: str,
) -> int:
    if count == 0:
        return 0
    later = sorted({int(offset) for offset in candidates if int(offset) > start})
    if not later:
        raise FormatError(f"{label}: cannot bound the {table_name} table")
    end = later[0]
    span = end - start
    if span <= 0 or span % count:
        raise FormatError(
            f"{label}: {table_name} table span {span} is not divisible by {count} records"
        )
    stride = span // count
    if stride < minimum or stride > MAX_RECORD_STRIDE:
        raise FormatError(
            f"{label}: unsupported {table_name} record stride {stride} bytes"
        )
    return stride


def parse_object_table(data: bytes | bytearray, label: str = "package") -> PackageObjectTable:
    """Parse FF7R's cooked UE4 name/import/export metadata without reading object payloads."""
    reader = Reader(data, label)
    if reader.uint32() != PACKAGE_TAG:
        raise FormatError(f"{label}: invalid Unreal package tag")
    legacy_version = reader.int32()
    if legacy_version >= 0:
        raise FormatError(f"{label}: legacy UE3 packages are not supported")
    if legacy_version != -4:
        reader.int32()  # Legacy UE3 version.
    file_version = reader.int32()
    licensee_version = reader.int32()

    # FF7R's unversioned cooked packages use an empty custom-version container.
    # Do not guess how to skip a non-empty container: object-table offsets are
    # too important to silently desynchronize.
    if legacy_version <= -2:
        custom_versions = reader.int32()
        if custom_versions != 0:
            raise FormatError(
                f"{label}: custom version tables are not supported by the read-only object probe"
            )

    total_header_size = reader.int32()
    reader.fstring()  # package/folder name
    reader.uint32()  # package flags
    names_count = _checked_count(reader.int32(), MAX_NAMES, label, "name")
    names_offset = reader.int32()
    gatherable_count = reader.int32()
    gatherable_offset = reader.int32()
    exports_count = _checked_count(reader.int32(), MAX_EXPORTS, label, "export")
    exports_offset = reader.int32()
    imports_count = _checked_count(reader.int32(), MAX_IMPORTS, label, "import")
    imports_offset = reader.int32()
    depends_offset = reader.int32()

    size = len(data)
    if total_header_size <= 0 or total_header_size > size:
        raise FormatError(f"{label}: invalid total header size {total_header_size}")
    _checked_offset(names_offset, size, label, "name", allow_zero=names_count == 0)
    _checked_offset(exports_offset, size, label, "export", allow_zero=exports_count == 0)
    _checked_offset(imports_offset, size, label, "import", allow_zero=imports_count == 0)
    _checked_offset(depends_offset, size, label, "depends")
    if gatherable_count < 0:
        raise FormatError(f"{label}: unreasonable gatherable-text count {gatherable_count}")
    _checked_offset(gatherable_offset, size, label, "gatherable text")

    reader.seek(names_offset)
    names: list[str] = []
    for _ in range(names_count):
        names.append(reader.fstring())
        reader.read(4)  # FF7R cooked FNameEntry hashes.
    names_tuple = tuple(names)

    table_offsets = (
        names_offset,
        gatherable_offset if gatherable_count else 0,
        exports_offset if exports_count else 0,
        imports_offset if imports_count else 0,
        depends_offset,
        total_header_size,
        size,
    )
    import_stride = _derive_stride(
        start=imports_offset,
        count=imports_count,
        minimum=IMPORT_PREFIX_SIZE,
        candidates=table_offsets,
        label=label,
        table_name="import",
    ) if imports_count else 0
    export_stride = _derive_stride(
        start=exports_offset,
        count=exports_count,
        minimum=EXPORT_PREFIX_SIZE,
        candidates=table_offsets,
        label=label,
        table_name="export",
    ) if exports_count else 0

    imports: list[PackageImport] = []
    for index in range(imports_count):
        reader.seek(imports_offset + index * import_stride)
        imports.append(PackageImport(
            index=index,
            class_package=_read_fname(reader, names_tuple),
            class_name=_read_fname(reader, names_tuple),
            outer_index=reader.int32(),
            object_name=_read_fname(reader, names_tuple),
        ))

    exports: list[PackageExport] = []
    for index in range(exports_count):
        reader.seek(exports_offset + index * export_stride)
        class_index = reader.int32()
        super_index = reader.int32()
        template_index = reader.int32()
        outer_index = reader.int32()
        object_name = _read_fname(reader, names_tuple)
        object_flags = reader.uint32()
        serial_size = reader.int64()
        serial_offset = reader.int64()
        if serial_size < 0 or serial_offset < 0:
            raise FormatError(f"{label}: export {index} has invalid serialized size/offset")
        imports_limit = len(imports)
        exports_limit = exports_count
        for package_index, field in (
            (class_index, "class"),
            (super_index, "super"),
            (template_index, "template"),
            (outer_index, "outer"),
        ):
            if package_index < -imports_limit or package_index > exports_limit:
                raise FormatError(
                    f"{label}: export {index} {field} package index {package_index} is outside the object tables"
                )
        exports.append(PackageExport(
            index=index,
            class_index=class_index,
            super_index=super_index,
            template_index=template_index,
            outer_index=outer_index,
            object_name=object_name,
            object_flags=object_flags,
            serial_size=serial_size,
            serial_offset=serial_offset,
        ))

    for row in imports:
        if row.outer_index < -len(imports) or row.outer_index > len(exports):
            raise FormatError(
                f"{label}: import {row.index} outer package index {row.outer_index} is outside the object tables"
            )

    return PackageObjectTable(
        names=names_tuple,
        imports=tuple(imports),
        exports=tuple(exports),
        import_stride=import_stride,
        export_stride=export_stride,
        total_header_size=total_header_size,
        file_version=file_version,
        licensee_version=licensee_version,
    )
