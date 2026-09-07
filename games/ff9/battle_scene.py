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


# Memoria v2025.07.04, Assembly-CSharp/Global/BTL_SCENE.cs.
# Offsets mirror BinaryReader calls in ReadBattleScene exactly.
ENEMY_FIELDS = (
    _field("ResistStatus", "Resist status", 0, "<I"),
    _field("AutoStatus", "Auto status", 4, "<I"),
    _field("InitialStatus", "Initial status", 8, "<I"),
    _field("MaxHP", "Max HP", 12, "<H"), _field("MaxMP", "Max MP", 14, "<H"),
    _field("WinGil", "Gil", 16, "<H"), _field("WinExp", "Experience", 18, "<H"),
    *tuple(_field(f"WinItem{i+1}", f"Drop {i+1}", 20+i, "<B") for i in range(4)),
    *tuple(_field(f"StealItem{i+1}", f"Steal {i+1}", 24+i, "<B") for i in range(4)),
    _field("Radius", "Radius", 28, "<H"), _field("Geo", "Geometry", 30, "<h"),
    *tuple(_field(f"Motion{i+1}", f"Motion {i+1}", 32+i*2, "<H") for i in range(6)),
    _field("Mesh1", "Mesh 1", 44, "<H"), _field("Mesh2", "Mesh 2", 46, "<H"),
    _field("Flags", "Enemy flags", 48, "<H"), _field("AP", "AP", 50, "<H"),
    _field("Speed", "Speed", 52, "<B"), _field("Strength", "Strength", 53, "<B"),
    _field("Magic", "Magic", 54, "<B"), _field("Spirit", "Spirit", 55, "<B"),
    _field("ElementPad", "Element pad", 56, "<B"), _field("ElementTrans", "Element trans", 57, "<B"),
    _field("CurrentCapacity", "Current capacity", 58, "<B"), _field("MaxCapacity", "Max capacity", 59, "<B"),
    _field("GuardElement", "Guard element", 60, "<B"), _field("AbsorbElement", "Absorb element", 61, "<B"),
    _field("HalfElement", "Half element", 62, "<B"), _field("WeakElement", "Weak element", 63, "<B"),
    _field("Level", "Level", 64, "<B"), _field("Category", "Category", 65, "<B"),
    _field("HitRate", "Hit rate", 66, "<B"), _field("PhysicalDefence", "Physical defence", 67, "<B"),
    _field("PhysicalEvade", "Physical evade", 68, "<B"), _field("MagicalDefence", "Magical defence", 69, "<B"),
    _field("MagicalEvade", "Magical evade", 70, "<B"), _field("BlueMagic", "Blue Magic", 71, "<B"),
    *tuple(_field(f"Bone{i+1}", f"Bone {i+1}", 72+i, "<B") for i in range(4)),
    _field("DieSfx", "Death SFX", 76, "<H"), _field("Konran", "Confuse motion", 78, "<B"),
    _field("MessageCount", "Message count", 79, "<B"),
    *tuple(_field(f"IconBone{i+1}", f"Icon bone {i+1}", 80+i, "<B") for i in range(6)),
    *tuple(_field(f"IconY{i+1}", f"Icon Y {i+1}", 86+i, "<b") for i in range(6)),
    *tuple(_field(f"IconZ{i+1}", f"Icon Z {i+1}", 92+i, "<b") for i in range(6)),
    _field("StartSfx", "Start SFX", 98, "<H"), _field("ShadowX", "Shadow X", 100, "<H"),
    _field("ShadowZ", "Shadow Z", 102, "<H"), _field("ShadowBone", "Shadow bone", 104, "<B"),
    _field("WinCard", "Card reward", 105, "<B"), _field("ShadowOffsetX", "Shadow offset X", 106, "<h"),
    _field("ShadowOffsetZ", "Shadow offset Z", 108, "<h"), _field("ShadowBone2", "Shadow bone 2", 110, "<B"),
)
PATTERN_FIELDS = (
    _field("Rate", "Rate", 0, "<B"), _field("MonsterCount", "Monster count", 1, "<B"),
    _field("Camera", "Camera", 2, "<B"), _field("AP", "AP", 4, "<I"),
    *tuple(field for slot in range(4) for field in (
        _field(f"Slot{slot+1}Type", f"Enemy {slot+1} type", 8+slot*12, "<B"),
        _field(f"Slot{slot+1}Flags", f"Enemy {slot+1} flags", 9+slot*12, "<B"),
        _field(f"Slot{slot+1}Pease", f"Enemy {slot+1} pease", 10+slot*12, "<B"),
        _field(f"Slot{slot+1}X", f"Enemy {slot+1} X", 12+slot*12, "<h"),
        _field(f"Slot{slot+1}Y", f"Enemy {slot+1} Y", 14+slot*12, "<h"),
        _field(f"Slot{slot+1}Z", f"Enemy {slot+1} Z", 16+slot*12, "<h"),
        _field(f"Slot{slot+1}Rotation", f"Enemy {slot+1} rotation", 18+slot*12, "<h"),
    )),
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
        if field.key == "MonsterCount" and value > 4:
            raise ValueError("Monster count must be from 0 through 4")
        if field.key.startswith("Slot") and field.key.endswith("Type") and value >= self.type_count:
            raise ValueError(f"{field.label} must refer to an enemy type in this scene (0 through {max(0, self.type_count - 1)})")
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
        return Path("BattleMap") / "BattleScene" / f"EVT_BATTLE_{scene}" / "dbfile0000.raw16"

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
            {"key": "encounters", "tab": "encounters", "label": "Encounters", "relativePath": "StreamingAssets/p0data2.bin → BattleMap/BattleScene/*/dbfile0000.raw16", "controls": "Pattern rate, monster count, camera, AP and four enemy placements", "available": available, "source": "vanilla" if available else None, "sourcePath": str(self.archive_path) if available else None, "projectPath": str(self.project_root / "BattleMap/BattleScene"), "notes": note},
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
