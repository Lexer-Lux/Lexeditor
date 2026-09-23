"""Edit proven FF9 field-walkmesh activity bits without rewriting topology.

FF9 field ``.bgi.bytes`` TextAssets live in the numbered ``p0data1*.bin``
archives. Memoria's pinned BGI reader/writer documents both the floor and
triangle tables. Its runtime names bit 0 ``BGI_FLOOR_ACTIVE`` / ``BGI_TRI_ACTIVE``, and
Memoria's Field Creator exposes triangle bits ``0x1000`` as Alternate footstep,
``0x4000`` as Prevent NPC pathing, and ``0x8000`` as Prevent PC pathing.
Lexeditor deliberately edits only those documented semantic bits. Every other BGI byte --
geometry, neighbors, edge semantics, transforms, animation data, unknown flag
bits, and padding -- is copied verbatim into a normal Memoria loose override.

Floor rows are small enough to browse game-wide. Triangle rows are loaded one
field at a time so the UI never materializes the game's six-figure triangle
population into one client-side table.
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
BGI_TRI_SIZE = 40
BGI_FLOOR_SIZE = 32
BGI_TRI_ACTIVE = 0x0001
BGI_TRI_ALTERNATE_FOOTSTEP = 0x1000
BGI_TRI_NO_NPC = 0x4000
BGI_TRI_NO_PC = 0x8000
BGI_TRI_EDITABLE_MASK = (
    BGI_TRI_ACTIVE | BGI_TRI_ALTERNATE_FOOTSTEP | BGI_TRI_NO_NPC | BGI_TRI_NO_PC
)
BGI_FLOOR_ACTIVE = 0x0001
MAX_TRIANGLES = 65_535
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


def _i16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError("FF9 BGI data is truncated")
    return struct.unpack_from("<h", data, offset)[0]


def _validate_header(data: bytes) -> None:
    if len(data) < BGI_HEADER_SIZE or struct.unpack_from("<I", data, 0)[0] != BGI_MAGIC:
        raise ValueError("FF9 walkmesh has an invalid BGI header")


def _triangle_table(data: bytes) -> list[dict[str, int | bool]]:
    """Return triangle descriptors while retaining every non-edited byte in ``data``."""
    _validate_header(data)
    count = _u16(data, 40)
    relative_offset = _u16(data, 42)
    if count > MAX_TRIANGLES:
        raise ValueError("FF9 walkmesh has too many triangles")
    start = 4 + relative_offset
    end = start + count * BGI_TRI_SIZE
    if start < BGI_HEADER_SIZE or end > len(data):
        raise ValueError("FF9 walkmesh triangle table is outside the BGI data")
    result = []
    for index in range(count):
        offset = start + index * BGI_TRI_SIZE
        flags = _u16(data, offset)
        result.append({
            "index": index,
            "offset": offset,
            "floorNdx": _i16(data, offset + 4),
            "flags": flags,
            "active": bool(flags & BGI_TRI_ACTIVE),
            "alternateFootstep": bool(flags & BGI_TRI_ALTERNATE_FOOTSTEP),
            "preventNPC": bool(flags & BGI_TRI_NO_NPC),
            "preventPC": bool(flags & BGI_TRI_NO_PC),
            "otherFlags": flags & ~BGI_TRI_EDITABLE_MASK,
        })
    return result


def _floor_table(data: bytes) -> list[dict[str, int | bool]]:
    """Return floor descriptors while retaining every non-edited byte in ``data``."""
    _validate_header(data)
    triangle_count = _u16(data, 40)
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
        tri_start = 4 + tri_offset
        tri_end = tri_start + tri_count * 4
        if tri_start < 0 or tri_end > len(data):
            raise ValueError("FF9 walkmesh floor triangle list is outside the BGI data")
        for item in range(tri_count):
            tri_index = struct.unpack_from("<i", data, tri_start + item * 4)[0]
            if not 0 <= tri_index < triangle_count:
                raise ValueError("FF9 walkmesh floor references an invalid triangle")
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


def _set_active(data: bytes, record: int, active: bool, *, triangle: bool) -> bytes:
    rows = _triangle_table(data) if triangle else _floor_table(data)
    noun = "triangle" if triangle else "floor"
    mask = BGI_TRI_ACTIVE if triangle else BGI_FLOOR_ACTIVE
    if type(record) is not int or not 0 <= record < len(rows):
        raise ValueError(f"Changed FF9 walkmesh {noun} does not exist")
    out = bytearray(data)
    row = rows[record]
    flags = int(row["flags"])
    flags = (flags | mask) if active else (flags & ~mask)
    struct.pack_into("<H", out, int(row["offset"]), flags)
    return bytes(out)


def _set_floor_active(data: bytes, record: int, active: bool) -> bytes:
    return _set_active(data, record, active, triangle=False)


def _set_triangle_values(data: bytes, record: int, values: dict[str, bool]) -> bytes:
    rows = _triangle_table(data)
    if type(record) is not int or not 0 <= record < len(rows):
        raise ValueError("Changed FF9 walkmesh triangle does not exist")
    flags = int(rows[record]["flags"])
    masks = {
        "Active": BGI_TRI_ACTIVE,
        "AlternateFootstep": BGI_TRI_ALTERNATE_FOOTSTEP,
        "PreventNPC": BGI_TRI_NO_NPC,
        "PreventPC": BGI_TRI_NO_PC,
    }
    for key, value in values.items():
        mask = masks[key]
        flags = (flags | mask) if value else (flags & ~mask)
    out = bytearray(data)
    struct.pack_into("<H", out, int(rows[record]["offset"]), flags)
    return bytes(out)


def _set_triangle_active(data: bytes, record: int, active: bool) -> bytes:
    return _set_triangle_values(data, record, {"Active": active})


class FieldWalkmeshStore:
    FLOOR_KEY = "field-walkmesh"
    TRIANGLE_KEY = "field-walkmesh-triangles"
    KEY = FLOOR_KEY  # compatibility with the original floor-only integration
    KEYS = frozenset({FLOOR_KEY, TRIANGLE_KEY})

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

    @staticmethod
    def _validate_asset(raw: bytes) -> None:
        _triangle_table(raw)
        _floor_table(raw)

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
                self._validate_asset(payload)
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
                self._validate_asset(raw)
                result[relative] = (raw, "project", file)
            elif relative in vanilla:
                result[relative] = (vanilla[relative], "vanilla", None)
        return result

    def status_rows(self) -> list[dict[str, Any]]:
        available = bool(self._archives()) or bool(self._project_assets())
        common = {
            "tab": "world",
            "relativePath": "StreamingAssets/p0data1*.bin → StreamingAssets/Assets/Resources/FieldMaps/*/*.bgi.bytes",
            "available": available,
            "source": "vanilla/project" if available else None,
            "sourcePath": str(self.game_root / "StreamingAssets" / "p0data1*.bin") if available else None,
            "projectPath": str(self.project_root / "StreamingAssets/Assets/Resources/FieldMaps"),
        }
        return [
            {**common, "key": self.FLOOR_KEY, "label": "Field walkmesh floors",
             "controls": "Field walkmesh floor active/inactive state (BGI_FLOOR_ACTIVE)",
             "notes": (
                 "Partial p0data1 integration. Lexeditor edits only Memoria's documented floor-active bit and "
                 "preserves geometry, triangle/edge topology, floor transforms, animations, every other flag bit, "
                 "and all unknown bytes verbatim in a canonical loose .bgi.bytes override."
             )},
            {**common, "key": self.TRIANGLE_KEY, "label": "Field walkmesh triangles",
             "controls": "Per-field triangle activity (BGI_TRI_ACTIVE), alternate footstep, NPC-pathing and PC-pathing flags",
             "notes": (
                 "Partial p0data1 integration. Triangle rows are field-scoped to keep the shared Table+Detail "
                 "responsive. Lexeditor edits only Memoria's documented Active, Alternate footstep, Prevent NPC "
                 "pathing and Prevent PC pathing flags; geometry, neighbors, edge semantics, all other flag bits "
                 "and unknown bytes remain verbatim."
             )},
        ]

    @staticmethod
    def _fields(key: str) -> list[dict[str, Any]]:
        if key == FieldWalkmeshStore.TRIANGLE_KEY:
            return [
                {"key": "Field", "label": "Field", "declaredType": "Path", "editable": False, "kind": "stored"},
                {"key": "Triangle", "label": "Triangle", "declaredType": "UInt16", "editable": False, "kind": "stored"},
                {"key": "Floor", "label": "Floor", "declaredType": "Int16", "editable": False, "kind": "stored"},
                {"key": "Active", "label": "Triangle active", "declaredType": "Boolean", "editable": True, "kind": "boolean"},
                {"key": "AlternateFootstep", "label": "Alternate footstep", "declaredType": "Boolean", "editable": True, "kind": "boolean"},
                {"key": "PreventNPC", "label": "Prevent NPC pathing", "declaredType": "Boolean", "editable": True, "kind": "boolean"},
                {"key": "PreventPC", "label": "Prevent PC pathing", "declaredType": "Boolean", "editable": True, "kind": "boolean"},
                {"key": "OtherFlags", "label": "Other flag bits", "declaredType": "UInt16", "editable": False, "kind": "stored"},
            ]
        return [
            {"key": "Field", "label": "Field", "declaredType": "Path", "editable": False, "kind": "stored"},
            {"key": "Floor", "label": "Floor", "declaredType": "UInt16", "editable": False, "kind": "stored"},
            {"key": "Active", "label": "Floor active", "declaredType": "Boolean", "editable": True, "kind": "boolean"},
            {"key": "Triangles", "label": "Triangles", "declaredType": "UInt16", "editable": False, "kind": "stored"},
            {"key": "OtherFlags", "label": "Other flag bits", "declaredType": "UInt16", "editable": False, "kind": "stored"},
        ]

    def _scene_rows(self, sources: dict[str, tuple[bytes, str, Path | None]]) -> list[dict[str, str]]:
        return [{"value": relative, "label": Path(relative).parent.name, "source": source_kind}
                for relative, (_raw, source_kind, _file) in sources.items()]

    def load(self, key: str, scene: str | None = None) -> dict[str, Any]:
        if key not in self.KEYS:
            raise KeyError("Unknown FF9 field-walkmesh dataset")
        rows = []
        hashes = {}
        sources = self._sources()
        active_scene = None
        selected_sources = sources.items()
        if key == self.TRIANGLE_KEY and sources:
            if scene is not None and scene not in sources:
                raise ValueError("Unknown FF9 field-walkmesh scene")
            active_scene = scene or next(iter(sources))
            selected_sources = [(active_scene, sources[active_scene])]

        for relative, (raw, source_kind, _file) in selected_sources:
            hashes[relative] = _sha256(raw)
            folder = Path(relative).parent.name
            if key == self.TRIANGLE_KEY:
                for triangle in _triangle_table(raw):
                    index = int(triangle["index"])
                    floor_ndx = int(triangle["floorNdx"])
                    rows.append({
                        "line": index,
                        "id": index,
                        "name": f"Triangle {index}",
                        "scene": relative,
                        "record": index,
                        "source": source_kind,
                        "values": {
                            "Field": folder,
                            "Triangle": index,
                            "Floor": floor_ndx,
                            "Active": bool(triangle["active"]),
                            "AlternateFootstep": bool(triangle["alternateFootstep"]),
                            "PreventNPC": bool(triangle["preventNPC"]),
                            "PreventPC": bool(triangle["preventPC"]),
                            "OtherFlags": int(triangle["otherFlags"]),
                        },
                    })
            else:
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
        status = next(row for row in self.status_rows() if row["key"] == key)
        result = {**status, "sha256": "", "sceneHashes": hashes,
                  "fields": self._fields(key), "rows": rows}
        if key == self.TRIANGLE_KEY:
            result.update({"activeScene": active_scene, "scenes": self._scene_rows(sources)})
        return result

    def save(self, key: str, expected_hashes: dict[str, str], changes: list[dict[str, Any]]) -> dict[str, Any]:
        if key not in self.KEYS or not isinstance(expected_hashes, dict) or not isinstance(changes, list):
            raise ValueError("Invalid FF9 field-walkmesh save")
        noun = "triangle" if key == self.TRIANGLE_KEY else "floor"
        grouped: dict[str, list[dict[str, Any]]] = {}
        for change in changes:
            if not isinstance(change, dict) or not isinstance(change.get("scene"), str):
                raise ValueError(f"Changed FF9 walkmesh {noun} is invalid")
            values = change.get("values")
            allowed = ({"Active", "AlternateFootstep", "PreventNPC", "PreventPC"}
                       if key == self.TRIANGLE_KEY else {"Active"})
            if not isinstance(values, dict) or set(values) - allowed:
                raise ValueError(f"Only documented FF9 walkmesh {noun} flags are editable")
            if any(type(value) is not bool for value in values.values()):
                raise ValueError(f"FF9 walkmesh {noun} flags must be true or false")
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
                if key == self.TRIANGLE_KEY:
                    if change["values"]:
                        edited = _set_triangle_values(edited, record, change["values"])
                elif "Active" in change["values"]:
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
        scene = next(iter(grouped), next(iter(expected_hashes), None)) if key == self.TRIANGLE_KEY else None
        return self.load(key, scene)
