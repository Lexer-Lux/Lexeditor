"""Edit the proven FF9 field-walkmesh floor-active bit without rewriting topology.

FF9 field ``.bgi.bytes`` TextAssets live in the numbered ``p0data1*.bin``
archives.  Memoria's pinned BGI reader/writer documents the floor table layout,
and the runtime names bit 0 ``BGI_FLOOR_ACTIVE``.  Lexeditor deliberately edits
only that one semantic bit.  Every other BGI byte -- geometry, neighbors, edge
flags, floor transforms, animation data, unknown flag bits, and padding -- is
copied verbatim into a normal Memoria loose override.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any

from . import paths
from .battle_scene import UnityArchive


BGI_MAGIC = 0xACDCDEAD
BGI_HEADER_SIZE = 64
BGI_FLOOR_SIZE = 32
BGI_FLOOR_ACTIVE = 0x0001
MAX_FLOORS = 4096
FIELD_BGI_PATH = re.compile(
    r"(?:^|/)fieldmaps/([^/]+)/([^/]+\.bgi\.bytes)$",
    re.IGNORECASE,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError("FF9 BGI data is truncated")
    return struct.unpack_from("<H", data, offset)[0]


def _floor_table(data: bytes) -> list[dict[str, int | bool]]:
    """Return floor descriptors while retaining every non-edited byte in ``data``."""
    if len(data) < BGI_HEADER_SIZE or struct.unpack_from("<I", data, 0)[0] != BGI_MAGIC:
        raise ValueError("FF9 walkmesh has an invalid BGI header")
    floor_count = _u16(data, 52)
    floor_offset = _u16(data, 54)
    if floor_count > MAX_FLOORS:
        raise ValueError("FF9 walkmesh has too many floors")
    start = 4 + floor_offset
    end = start + floor_count * BGI_FLOOR_SIZE
    if start < BGI_HEADER_SIZE or end > len(data):
        raise ValueError("FF9 walkmesh floor table is outside the BGI data")
    floors = []
    for index in range(floor_count):
        offset = start + index * BGI_FLOOR_SIZE
        flags = _u16(data, offset)
        floor_ndx = _u16(data, offset + 2)
        tri_count = _u16(data, offset + 28)
        tri_offset = _u16(data, offset + 30)
        tri_end = 4 + tri_offset + tri_count * 4
        if tri_end > len(data):
            raise ValueError("FF9 walkmesh floor triangle list is outside the BGI data")
        floors.append({
            "index": index,
            "offset": offset,
            "floorNdx": floor_ndx,
            "flags": flags,
            "active": bool(flags & BGI_FLOOR_ACTIVE),
            "otherFlags": flags & ~BGI_FLOOR_ACTIVE,
            "triangleCount": tri_count,
        })
    return floors


def _set_floor_active(data: bytes, record: int, active: bool) -> bytes:
    floors = _floor_table(data)
    if type(record) is not int or not 0 <= record < len(floors):
        raise ValueError("Changed FF9 walkmesh floor does not exist")
    out = bytearray(data)
    floor = floors[record]
    flags = int(floor["flags"])
    flags = (flags | BGI_FLOOR_ACTIVE) if active else (flags & ~BGI_FLOOR_ACTIVE)
    struct.pack_into("<H", out, int(floor["offset"]), flags)
    return bytes(out)


class FieldWalkmeshStore:
    KEY = "field-walkmesh"

    def __init__(self, game_root: Path | None = None, project_root: Path | None = None):
        self.game_root = Path(game_root or paths.GAME_ROOT)
        self.project_root = Path(project_root or paths.PROJECT_ROOT)
        self._archive_signature: tuple[tuple[str, int, int], ...] | None = None
        self._vanilla: dict[str, bytes] = {}

    def _archives(self) -> list[Path]:
        return sorted((self.game_root / "StreamingAssets").glob("p0data1*.bin"))

    def _signature(self) -> tuple[tuple[str, int, int], ...]:
        result = []
        for archive in self._archives():
            try:
                stat = archive.stat()
            except OSError:
                continue
            result.append((str(archive.resolve()), stat.st_size, stat.st_mtime_ns))
        return tuple(result)

    @staticmethod
    def _relative(asset_path: str) -> str | None:
        normalized = asset_path.replace("\\", "/")
        match = FIELD_BGI_PATH.search(normalized)
        if not match:
            return None
        folder, filename = match.groups()
        return (Path("StreamingAssets") / "Assets" / "Resources" / "FieldMaps" /
                folder / filename).as_posix()

    def _vanilla_assets(self) -> dict[str, bytes]:
        signature = self._signature()
        if signature == self._archive_signature:
            return self._vanilla
        result: dict[str, bytes] = {}
        for archive_path in self._archives():
            archive = UnityArchive(archive_path)
            paths_by_info = archive._asset_bundle_paths()
            for obj in archive.objects:
                if obj.type_id != 49:
                    continue
                relative = self._relative(paths_by_info.get(obj.info, obj.name))
                if not relative:
                    continue
                payload = archive._object_payload(obj)
                # Parse now so corrupt/unexpected objects never enter the editable set.
                _floor_table(payload)
                if relative in result and result[relative] != payload:
                    raise ValueError(f"Duplicate FF9 walkmesh asset: {relative}")
                result[relative] = payload
        self._archive_signature = signature
        self._vanilla = result
        return result

    def _project_assets(self) -> dict[str, Path]:
        root = self.project_root / "StreamingAssets" / "Assets" / "Resources" / "FieldMaps"
        if not root.is_dir():
            return {}
        result = {}
        for file in root.glob("*/*.bgi.bytes"):
            if not file.is_file():
                continue
            relative = file.relative_to(self.project_root).as_posix()
            # Keep this surface narrow: only canonical FieldMaps loose overrides.
            if self._relative(relative) is not None:
                result[relative] = file
        return result

    def _sources(self) -> dict[str, tuple[bytes, str, Path | None]]:
        vanilla = self._vanilla_assets()
        project = self._project_assets()
        result: dict[str, tuple[bytes, str, Path | None]] = {}
        for relative in sorted(set(vanilla) | set(project)):
            file = project.get(relative)
            if file is not None:
                raw = file.read_bytes()
                _floor_table(raw)
                result[relative] = (raw, "project", file)
            elif relative in vanilla:
                result[relative] = (vanilla[relative], "vanilla", None)
        return result

    def status_rows(self) -> list[dict[str, Any]]:
        available = bool(self._archives()) or bool(self._project_assets())
        return [{
            "key": self.KEY,
            "tab": "world",
            "label": "Field walkmesh floors",
            "relativePath": "StreamingAssets/p0data1*.bin → StreamingAssets/Assets/Resources/FieldMaps/*/*.bgi.bytes",
            "controls": "Field walkmesh floor active/inactive state (BGI_FLOOR_ACTIVE)",
            "available": available,
            "source": "vanilla/project" if available else None,
            "sourcePath": str(self.game_root / "StreamingAssets" / "p0data1*.bin") if available else None,
            "projectPath": str(self.project_root / "StreamingAssets/Assets/Resources/FieldMaps"),
            "notes": (
                "Partial p0data1 integration. Lexeditor edits only Memoria's documented floor-active bit and "
                "preserves geometry, triangle/edge topology, floor transforms, animations, every other flag bit, "
                "and all unknown bytes verbatim in a canonical loose .bgi.bytes override. Backgrounds and cameras "
                "remain separate unintegrated field-scene areas."
            ),
        }]

    @staticmethod
    def _fields() -> list[dict[str, Any]]:
        return [
            {"key": "Field", "label": "Field", "declaredType": "Path", "editable": False, "kind": "stored"},
            {"key": "Floor", "label": "Floor", "declaredType": "UInt16", "editable": False, "kind": "stored"},
            {"key": "Active", "label": "Floor active", "declaredType": "Boolean", "editable": True, "kind": "boolean"},
            {"key": "Triangles", "label": "Triangles", "declaredType": "UInt16", "editable": False, "kind": "stored"},
            {"key": "OtherFlags", "label": "Other flag bits", "declaredType": "UInt16", "editable": False, "kind": "stored"},
        ]

    def load(self, key: str) -> dict[str, Any]:
        if key != self.KEY:
            raise KeyError("Unknown FF9 field-walkmesh dataset")
        rows = []
        hashes = {}
        sources = self._sources()
        for relative, (raw, source_kind, _file) in sources.items():
            hashes[relative] = _sha256(raw)
            folder = Path(relative).parent.name
            for floor in _floor_table(raw):
                index = int(floor["index"])
                floor_ndx = int(floor["floorNdx"])
                rows.append({
                    "line": len(rows),
                    "id": f"{folder}:{floor_ndx}",
                    "name": f"{folder} · Floor {floor_ndx}",
                    "scene": relative,
                    "record": index,
                    "source": source_kind,
                    "values": {
                        "Field": folder,
                        "Floor": floor_ndx,
                        "Active": bool(floor["active"]),
                        "Triangles": int(floor["triangleCount"]),
                        "OtherFlags": int(floor["otherFlags"]),
                    },
                })
        status = self.status_rows()[0]
        return {**status, "sha256": "", "sceneHashes": hashes,
                "fields": self._fields(), "rows": rows}

    def save(self, key: str, expected_hashes: dict[str, str], changes: list[dict[str, Any]]) -> dict[str, Any]:
        if key != self.KEY or not isinstance(expected_hashes, dict) or not isinstance(changes, list):
            raise ValueError("Invalid FF9 field-walkmesh save")
        grouped: dict[str, list[dict[str, Any]]] = {}
        for change in changes:
            if not isinstance(change, dict) or not isinstance(change.get("scene"), str):
                raise ValueError("Changed FF9 walkmesh floor is invalid")
            values = change.get("values")
            if not isinstance(values, dict) or set(values) - {"Active"}:
                raise ValueError("Only FF9 walkmesh floor activity is editable")
            if "Active" in values and type(values["Active"]) is not bool:
                raise ValueError("FF9 walkmesh floor activity must be true or false")
            grouped.setdefault(change["scene"], []).append(change)

        for relative, asset_changes in grouped.items():
            sources = self._sources()
            if relative not in sources:
                raise ValueError("Changed FF9 walkmesh does not belong to this project")
            raw, _source_kind, project_file = sources[relative]
            expected = expected_hashes.get(relative)
            if not expected or expected != _sha256(raw):
                raise RuntimeError(f"Walkmesh {relative} changed outside Lexeditor. Reload before saving.")
            edited = raw
            for change in asset_changes:
                record = change.get("record")
                if "Active" in change["values"]:
                    edited = _set_floor_active(edited, record, change["values"]["Active"])
            if edited == raw:
                continue
            target = self.project_root / Path(relative)
            if project_file is None and target.exists():
                raise RuntimeError(f"Walkmesh {relative} appeared in the project. Reload before saving.")
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".lexeditor.tmp", dir=target.parent)
            temporary = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(edited)
                    output.flush()
                    os.fsync(output.fileno())
                latest = self._sources().get(relative)
                if latest is None or _sha256(latest[0]) != expected:
                    raise RuntimeError(f"Walkmesh {relative} changed before saving. Reload first.")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return self.load(key)
