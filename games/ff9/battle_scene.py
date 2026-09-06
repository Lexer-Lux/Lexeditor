"""Read vanilla FF9 battle scenes from p0data2 and write Memoria raw16 overlays.

The Unity 5 archive layout follows Hades Workshop's public UnityArchiver parser;
Lexeditor only reads the installed archive. Saves are standalone raw16 files in
the selected Memoria project and never rewrite p0data2.bin.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any

from . import paths


MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_OBJECTS = 200_000
MAX_SCENES = 2_000
NAMED_TYPES = {21, 28, 43, 48, 49, 109, 115, 213}
BATTLE_PATH = re.compile(
    r"(?:^|/)battlemap/battlescene/evt_battle_([^/]+)/dbfile0000\.raw16(?:\.bytes)?$",
    re.IGNORECASE,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(data: bytes, offset: int, endian: str = "<") -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("Unity archive header is truncated")
    return struct.unpack_from(endian + "I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("Unity archive header is truncated")
    return struct.unpack_from("<i", data, offset)[0]


def _i64(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 8 > len(data):
        raise ValueError("Unity archive header is truncated")
    return struct.unpack_from("<q", data, offset)[0]


def _align4(value: int) -> int:
    return (value + 3) & ~3


@dataclass(frozen=True)
class UnityObject:
    info: int
    offset: int
    size: int
    type_id: int
    type_index: int
    flags: int
    name: str = ""


class UnityArchive:
    """Small, bounds-checked reader for the UnityRaw/serialized-file subset FF9 uses."""

    def __init__(self, path: Path):
        self.path = Path(path)
        size = self.path.stat().st_size
        if size <= 0 or size > MAX_ARCHIVE_BYTES:
            raise ValueError("p0data2.bin has an unexpected size")
        self.data = self.path.read_bytes()
        self.start = 0x70 if self.data.startswith(b"UnityRaw") else 0
        self.objects: list[UnityObject] = []
        self._parse()

    def _parse(self) -> None:
        data = self.data
        pos = self.start
        _header_size = _u32(data, pos, ">")
        _file_size = _u32(data, pos + 4, ">")
        header_id = _u32(data, pos + 8, ">")
        file_offset = _u32(data, pos + 12, ">")
        _unknown1 = _u32(data, pos + 16, ">")
        if header_id != 0x0F:
            raise ValueError("Unsupported FF9 Unity archive version")
        pos += 20
        if pos + 13 > len(data):
            raise ValueError("Unity archive type table is truncated")
        pos += 8  # Unity version string
        _unknown2 = _u32(data, pos); pos += 4
        unknown3 = data[pos]; pos += 1
        type_count = _u32(data, pos); pos += 4
        if type_count > 100_000:
            raise ValueError("Unity archive has too many type descriptors")
        for _ in range(type_count):
            kind = _i32(data, pos); pos += 4
            pos += 0x10 if kind >= 0 else 0x20
            if pos > len(data):
                raise ValueError("Unity archive type descriptor is truncated")
            if unknown3 == 1:
                amount = _u32(data, pos); text_size = _u32(data, pos + 4); pos += 8
                skip = amount * 0x18 + text_size
                if amount > 100_000 or skip > len(data) - pos:
                    raise ValueError("Unity archive extended type descriptor is invalid")
                pos += skip
        object_count = _u32(data, pos); pos += 4
        if object_count > MAX_OBJECTS:
            raise ValueError("Unity archive has too many objects")
        pos = _align4(pos)
        records = []
        for _ in range(object_count):
            if pos + 28 > len(data):
                raise ValueError("Unity archive object table is truncated")
            info, rel, size, type_id, type_index, flags = struct.unpack_from("<qIIIII", data, pos)
            pos += 28
            absolute = self.start + file_offset + rel
            if absolute < 0 or size > len(data) - absolute:
                raise ValueError("Unity archive object points outside p0data2.bin")
            records.append((info, absolute, size, type_id, type_index, flags))
        for info, absolute, size, type_id, type_index, flags in records:
            name = ""
            if type_id in NAMED_TYPES and size >= 4:
                length = _u32(data, absolute)
                if length <= size - 4 and length <= 1024 * 1024:
                    raw = data[absolute + 4:absolute + 4 + length]
                    try:
                        name = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        name = ""
            self.objects.append(UnityObject(info, absolute, size, type_id, type_index, flags, name))

    def _object_payload(self, obj: UnityObject) -> bytes:
        data = self.data
        pos = obj.offset
        end = obj.offset + obj.size
        if obj.type_id in NAMED_TYPES:
            length = _u32(data, pos); pos += 4 + length
            pos = obj.offset + 4 + _align4(length)
        if obj.type_id == 49:  # TextAsset: name + aligned text length + bytes
            size = _u32(data, pos); pos += 4
            if size > end - pos:
                raise ValueError("Unity TextAsset is truncated")
            return data[pos:pos + size]
        return data[pos:end]

    def _asset_bundle_paths(self) -> dict[int, str]:
        """Map serialized-object path IDs to AssetBundle resource paths."""
        result: dict[int, str] = {}
        for obj in self.objects:
            if obj.type_id != 142:
                continue
            data = self._object_payload(obj)
            pos = 0
            try:
                _unknown = _u32(data, pos); pos += 4
                bundle_count = _u32(data, pos); pos += 4
                if bundle_count > MAX_OBJECTS:
                    continue
                pos += bundle_count * 12
                amount = _u32(data, pos); pos += 4
                if amount > MAX_OBJECTS:
                    continue
                for _ in range(amount):
                    length = _u32(data, pos); pos += 4
                    if length > 4 * 1024 * 1024 or pos + length > len(data):
                        raise ValueError
                    path = data[pos:pos + length].decode("utf-8", errors="strict"); pos += length
                    pos = _align4(pos)
                    if pos + 20 > len(data):
                        raise ValueError
                    _index = _u32(data, pos); _unk1 = _u32(data, pos + 4); _unk2 = _u32(data, pos + 8)
                    info = _i64(data, pos + 12); pos += 20
                    result[info] = path.replace("\\", "/")
            except (ValueError, UnicodeDecodeError, struct.error):
                continue
        return result

    def battle_scenes(self) -> dict[str, bytes]:
        paths_by_info = self._asset_bundle_paths()
        result: dict[str, bytes] = {}
        for obj in self.objects:
            if obj.type_id != 49:
                continue
            full = paths_by_info.get(obj.info, obj.name).replace("\\", "/")
            match = BATTLE_PATH.search(full)
            if not match:
                continue
            scene = match.group(1)
            if scene in result:
                raise ValueError(f"Duplicate battle scene in p0data2: {scene}")
            payload = self._object_payload(obj)
            if len(payload) < 8:
                raise ValueError(f"Battle scene {scene} is truncated")
            result[scene] = payload
            if len(result) > MAX_SCENES:
                raise ValueError("Too many battle scenes in p0data2")
        return result


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    offset: int
    fmt: str
    min: int
    max: int


def _field(key: str, label: str, offset: int, fmt: str) -> Field:
    size = struct.calcsize(fmt)
    signed = fmt in {"<b", "<h", "<i"}
    bits = size * 8
    return Field(key, label, offset, fmt, -(1 << (bits - 1)) if signed else 0,
               (1 << (bits - 1)) - 1 if signed else (1 << bits) - 1)


# Memoria v2025.07.04, Assembly-CSharp/Global/BTL_SCENE.cs:
ENEMY_FIELDS = (
    _field("Moto", "Moto", 0, "<H"),
    _field("DieAt", "Die at", 1, "<B"),
    _field("Messages", "Messages", 2, "<H"),
    _field("Win", "Win", 4, "<X"),
    _field("Epense", "Expense", 5, "<B"),
    _field("Radius", "Radius", 6, "<H"),
    _field("ByteFlags", "Byte flags", 8, "<B"),
    _field("Flags", "Flags", 10, "<H"),
    _field("Exp", "Experience", 12, "<I"),
    _field("Gil", "Gil", 16, "<I"),
    _field("Draw0", "Drop 1", 20, "<B"),
    _field("Draw1", "Drop 2", 21, "<B"),
    _field("Draw2", "Drop 3", 22, "<B"),
    _field("Draw3", "Drop 4", 23, "<B"),
    _field("Steal0", "Steal 1", 24, "<B"),
    _field("Steal1", "Steal 2", 25, "<B"),
    _field("Steal2", "Steal 3", 26, "<B"),
    _field("Steal3", "Steal 4", 27, "<B"),
    _field("Geographics", "Geographics", 28, "<H"),
    _field("Flags1", "Enemy flags", 30, "<B"),
    _field("AP", "AP", 31, "<B"),
    _field("StatusU0", "Initial status low", 32, "<I"),
    _field("StatusU1", "Initial status high", 36, "<I"),
    _field("StatusR0", "Status resist low", 40, "<I"),
    _field("StatusR1", "Status resist high", 44, "<I"),
    _field("StatusA0", "Status auto low", 48, "<I"),
    _field("StatusA1", "Status auto high", 52, "<I"),
    _field("MaxHP", "Max HP", 56, "<I"),
    _field("MaxMP", "Max MP", 60, "<I"),
    _field("ElementGR0", "Element guard low", 64, "<I"),
    _field("ElementGR1", "Element guard high", 68, "<I"),
    _field("ElementAsorb", "Element absorb", 72, "<B"),
    _field("ElementHalf", "Element half", 73, "<B"),
    _field("ElementWeak", "Element weak", 74, "<B"),
    _field("Level", "Level", 75, "<B"),
    _field("Category", "Category", 76, "<H"),
    _field("Hit", "Hit", 78, "<B"),
    _field("Attack", "Attack", 79, "<B"),
    _field("AttackCount", "Attack count", 80, "<B"),
    _field("Strength", "Strength", 81, "<B"),
    _field("Magic", "Magic", 82, "<B"),
    _field("MagicDefence", "Magic defence", 83, "<B"),
    _field("Evasion", "Physical evasion", 84, "<B"),
    _field("MagicEvasion", "Magic evasion", 85, "<B"),
    _field("BlueMagic", "Blue magic", 86, "<B"),
    _field("Camera", "Camera", 87, "<B"),
    _field("Sound", "Sound", 88, "<H"),
    _field("WinScript", "Win script", 90, "<H"),
    _field("WinFootage", "Win footage", 92, "<H"),
    _field("DieSfx", "Die SFX", 94, "<H"),
    _field("Contributeds", "Contributes", 96, "<I"),
    _field("StrAsure", "Str assure", 100, "<H"),
    _field("MglAsure", "Mgl assure", 102, "<H"),
    _field("Wap", "Wap", 104, "<B"),
    _field("WapBp", "Wap back", 105, "<B"),
    _field("Wii", "Wii", 106, "<h"),
    _field("WiiBp", "Wii back", 108, "<h"),
    _field("Raduis", "Shadow radius", 110, "<H"),
    _field("RotY", "Shadow rotation", 112, "<h"),
    _field("Cart", "Card", 114, "<B"),
)

PATTERN_FIELDS = (
    _field("Rate", "Rate", 0, "<B"),
    _field("MonsterCount", "Monster count", 1, "<B"),
    _field("Camera", "Camera", 2, "<H"),
    _field("Flags", "Flags", 4, "<H"),
    _field("AP", "AP", 6, "<H"),
    _field("Pease0", "Placement 1 enabled", 8, "<B"),
    _field("Type0", "Enemy 1 type", 9, "<B"),
    _field("Flags0", "Enemy 1 flags", 10, "<H"),
    _field("X0", "Enemy 1 X", 12, "<h"),
    _field("Y0", "Enemy 1 Y", 14, "<h"),
    _field("Z0", "Enemy 1 Z", 16, "<h"),
    _field("Rot0", "Enemy 1 rotation", 18, "<h"),
    _field("Pease1", "Placement 2 enabled", 20, "<B"),
    _field("Type1", "Enemy 2 type", 21, "<B"),
    _field("Flags1", "Enemy 2 flags", 22, "<H"),
    _field("X1", "Enemy 2 X", 24, "<h"),
    _field("Y1", "Enemy 2 Y", 26, "<h"),
    _field("Z1", "Enemy 2 Z", 28, "<h"),
    _field("Rot1", "Enemy 2 rotation", 30, "<h"),
    _field("Pease2", "Placement 3 enabled", 32, "<B"),
    _field("Type2", "Enemy 3 type", 33, "<B"),
    _field("Flags2", "Enemy 3 flags", 34, "<H"),
    _field("X2", "Enemy 3 X", 36, "<h"),
    _field("Y2", "Enemy 3 Y", 38, "<h"),
    _field("Z2", "Enemy 3 Z", 40, "<h"),
    _field("Rot2", "Enemy 3 rotation", 42, "<h"),
    _field("Pease3", "Placement 4 enabled", 44, "<B"),
    _field("Type3", "Enemy 4 type", 45, "<B"),
    _field("Flags3", "Enemy 4 flags", 46, "<H"),
    _field("X3", "Enemy 4 X", 48, "<h"),
    _field("Y3", "Enemy 4 Y", 50, "<h"),
    _field("Z3", "Enemy 4 Z", 52, "<h"),
    _field("Rot3", "Enemy 4 rotation", 54, "<h"),
)


class BattleScene:
    def __init__(self, name: str, data: bytes):
        self.name, self.data = name, bytearray(data)
        if len(data) < 8:
            raise ValueError(f"Battle scene {name} is truncated")
        self.version, self.pattern_count, self.type_count, self.attack_count, self.flags = struct.unpack_from("<BBBBH", data, 0)
        if self.pattern_count > 255 or self.type_count > 255 or self.attack_count > 255:
            raise ValueError(f"Battle scene {name} has invalid counts")
        expected = 8 + 56 * self.pattern_count + 116 * self.type_count + 16 * self.attack_count
        if expected > len(data):
            raise ValueError(f"Battle scene {name} has invalid counts")

    @property
    def enemy_start(self) -> int:
        return 8 + 56 * self.pattern_count

    def read(self, base: int, field: Field) -> int:
        return struct.unpack_from(field.fmt, self.data, base + field.offset)[0]

    def write(self, base: int, field: Field, value: Any) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or not field.min <= value <= field.max:
            raise ValueError(f"{field.label} must be a whole number from {field.min} through {field.max}")
        struct.pack_into(field.fmt, self.data, base + field.offset, value)


class BattleSceneStore:
    def __init__(self):
        self.archive_path = paths.GAME_ROOT / "StreamingAssets" / "p0data2.bin"
        self.project_root = paths.PROJECT_ROOT
        self._vanilla: dict[str, bytes] | None = None

    def _scenes(self) -> dict[str, bytes]:
        if self._vanilla is None:
            if not self.archive_path.is_file():
                self._vanilla = {}
            else:
                self._vanilla = UnityArchive(self.archive_path).battle_scenes()
        return self._vanilla

    @staticmethod
    def relative(scene: str) -> Path:
        return Path("BattleMap") / "BattleScene" / f"EVT_BATTLE_{scene}" / "dbfile0000.raw,u6"

    def _source(self, scene: str) -> tuple[bytes, str, Path | None]:
        project = self.project_root / self.relative(scene)
        if project.is_file():
            return project.read_bytes(), "project", project
        data = self._scenes().get(scene)
        if data is None:
            raise KeyError(f"Unknown FF9 battle scene: {scene}")
        return data, "vanilla", None

    def status_rows(self) -> list[dict[str, Any]]:
        available = self.archive_path.is_file()
        note = "Reads vanilla battle-scene TextAssets from p0data2; saves Memoria raw16 project overlays."
        return [
            {"key": "enemies", "tab": "enemies", "label": "Enemies", "relativePath": "StreamingAssets/p0data2.bin → BattleMap/BattleScene/*/dbfile0000.raw16", "controls": "Enemy HP/MP, rewards, stats, elements, defences, Blue Magic, geometry, SFX, card and shadow fields", "available": available, "source": "vanilla" if available else None, "sourcePath": str(self.archive_path) if available else None, "projectPath": str(self.project_root / "BattleMap/BattleScene"), "notes": note},
            {"key": "encounters", "tab": "encounters", "label": "Encounters", "relativePath": "StreamingAssets/p0data2.bin → BattleMap/BattleScene/*/dbfile0000.raw,u6", "controls": "Pattern rate, monster count, camera, AP and four enemy placements", "available": available, "source": "vanilla" if available else None, "sourcePath": str(self.archive_path) if available else None, "projectPath": str(self.project_root / "BattleMap/BattleScene"), "notes": note},
        ]

    @staticmethod
    def _descriptors(fields: tuple[Field, ...]) -> list[dict[str, Any]]:
        return [{"key": f.key, "label": f.label, "declaredType": f.fmt[-1], "editable": True,
                 "kind": "integer", "min": f.min, "max": f.max} for f in fields]

    def load(self, key: str) -> dict[str, Any]:
        if key not in {"enemies", "encounters"}:
            raise KeyError("Unknown FF9 battle-scene dataset")
        rows = []
        scene_hashes = {}
        fields = ENEMY_FIELDS if key == "enemies" else PATTERN_FIELDS
        for scene_name in sorted(self._scenes()):
            data, source_kind, _ = self._source(scene_name)
            scene = BattleScene(scene_name, data)
            scene_hashes[scene_name] = _sha256(data)
            count = scene.type_count if key == "enemies" else scene.pattern_count
            stride = 116 if key == "enemies" else 56
            start = scene.enemy_start if key == "enemies" else 8
            for index in range(count):
                base = start + index * stride
                values = {field.key: scene.read(base, field) for field in fields}
                label = f"{scene_name} · {'Enemy' if key == 'enemies' else 'Pattern'} {index + 1}"
                rows.append({"line": len(rows), "id": f"{scene_name}:{index}", "name": label,
                             "scene": scene_name, "record": index, "source": source_kind, "values": values})
        status = next(row for row in self.status_rows() if row["key"] == key)
        return {**status, "sha256": _sha256(self.archive_path.read_bytes()) if self.archive_path.is_file() else "",
                "sceneHashes": scene_hashes, "fields": self._descriptors(fields), "rows": rows}

    def save(self, key: str, expected_scene_hashes: dict[str, str], changes: list[dict[str, Any]]) -> dict[str, Any]:
        if key not in {"enemies", "encounters"} or not isinstance(changes, list):
            raise ValueError("Invalid FF9 battle-scene save")
        fields = {field.key: field for field in (ENEMY_FIELDS if key == "enemies" else PATTERN_FIELDS)}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for change in changes:
            if not isinstance(change, dict) or not isinstance(change.get("scene"), str):
                raise ValueError("Changed battle record is invalid")
            grouped.setdefault(change["scene"], []).append(change)
        for name, scene_changes in grouped.items():
            raw, _kind, project = self._source(name)
            if expected_scene_hashes.get(name) != _sha256(raw):
                raise RuntimeError(f"Battle scene {name} changed outside Lexeditor. Reload before saving.")
            scene = BattleScene(name, raw)
            start = scene.enemy_start if key == "enemies" else 8
            stride = 116 if key == "enemies" else 56
            limit = scene.type_count if key == "enemies" else scene.pattern_count
            for change in scene_changes:
                index = change.get("record")
                values = change.get("values")
                if type(index) is not int or not 0 <= index < limit or not isinstance(values, dict):
                    raise ValueError("Changed battle record does not belong to this scene")
                base = start + index * stride
                for field_key, value in values.items():
                    field = fields.get(field_key)
                    if field is None:
                        raise ValueError(f"{field_key} is not editable")
                    scene.write(base, field, value)
            target = self.project_root / self.relative(name)
            if project is None and target.exists():
                raise RuntimeError(f"Battle scene {name} appeared in the project. Reload before saving.")
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".lexeditor.tmp", dir=target.parent)
            temporary = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(scene.data); output.flush(); os.fsync(output.fileno())
                # Refuse a race after the expensive parse/edit work.
                latest, _, _ = self._source(name)
                if _sha256(latest) != expected_scene_hashes[name]:
                    raise RuntimeError(f"Battle scene {name} changed before saving. Reload first.")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return self.load(key)
