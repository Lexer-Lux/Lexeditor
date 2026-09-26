"""Read vanilla FF9 battle scenes from p0data2 and write Memoria raw16 overlays.

The Unity serialized-file/container facts used here were cross-checked against
the permissively licensed UnityPy reader and Hades Workshop's published FF9
research. No third-party parser or binary is bundled or invoked. Lexeditor only
reads the installed archive; saves are standalone raw16 project overlays.

Battle-record layouts mirror Memoria v2025.07.04
(``d8df6e69ddb618adc753a27d9424409d66216a35``): enemy and pattern records follow
``BTL_SCENE.cs`` ``ReadBattleScene``; the 16-byte enemy-attack (``AA_DATA``)
records and the scene-header battle flags follow that same reader plus
``AA_DATA.cs``, ``BTL_REF.cs``, ``BattleCommandInfo.cs``, ``BitUtil.cs``,
``SB2_HEAD.cs`` and ``BTL_SCENE_INFO.cs``. Target,
display-mode and status-set names come from Memoria's verified ``TargetType``,
``TargetDisplay`` and ``StatusSetId`` enums. Hades Workshop ``Source/Enemies.h``
was audited for enemy-attack category/type semantics; its abstracted spell
model does not map onto the Steam ``AA_DATA`` record, so no Hades-derived
attack semantics were adopted and no Hades source was copied. Bytes without
verified semantics -- the attack sound bits Memoria reads and discards, header
version/counts, scene-flag bits 12-15, enemy pads -- are preserved verbatim and
never offered as editable fields.
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
            raise ValueError(f"{self.path.name} has an unexpected size")
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
                raise ValueError(f"Unity archive object points outside {self.path.name}")
            records.append((info, absolute, size, type_id, type_index, flags))
        # Version 15 records have 25 bytes plus alignment before the NEXT
        # record. The script-reference count follows the last stripped byte
        # directly, without that three-byte alignment.
        self.object_table_end = pos - 3 if object_count else pos
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

    def external_files(self) -> list[str]:
        """Read the version-15 metadata's external PPtr file table."""
        data, pos = self.data, self.object_table_end
        count = _u32(data, pos); pos += 4
        if count > MAX_OBJECTS:
            raise ValueError("Unity archive has too many script references")
        for _ in range(count):
            pos = _align4(pos + 4) + 8
        count = _u32(data, pos); pos += 4
        if count > MAX_OBJECTS:
            raise ValueError("Unity archive has too many external files")
        result = []
        for _ in range(count):
            end = data.find(b"\0", pos, pos + 4096)
            if end < 0:
                raise ValueError("Unity external-file name is truncated")
            pos = end + 1 + 20  # empty name, GUID and external type
            end = data.find(b"\0", pos, pos + 4096)
            if end < 0:
                raise ValueError("Unity external-file path is truncated")
            result.append(data[pos:end].decode("utf-8"))
            pos = end + 1
        return result

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


@dataclass(frozen=True)
class BitField:
    key: str
    label: str
    offset: int  # word offset within the record
    shift: int
    width: int
    size: int  # word size in bytes (2 or 4, little-endian)
    kind: str  # "boolean" | "integer" | "enum" | "stored" (read-only)
    choices: tuple[str, ...] = ()


# Verified Memoria TargetType enum (TargetType.cs). All 16 values of the 4-bit
# field are named, so the whole range is a closed enum.
TARGET_NAMES = (
    "SingleAny", "SingleAlly", "SingleEnemy", "ManyAny",
    "ManyAlly", "ManyEnemy", "All", "AllAlly",
    "AllEnemy", "Random", "RandomAlly", "RandomEnemy",
    "Everyone", "Self", "Automatic", "Special",
)
TARGET_CHOICES = tuple(f"{name}({index})" for index, name in enumerate(TARGET_NAMES))


# Memoria v2025.07.04, Assembly-CSharp/Global/BTL_SCENE.cs ReadBattleScene:
# each attack record is 16 bytes: a UInt32 targeting/VFX bitfield (bit order
# per BitUtil.ReadBits, LSB first), four BTL_REF bytes, category, status set,
# MP, type, Vfx2 and the numeric name reference.
ATTACK_INFO_BITS = (
    BitField("Target", "Target", 0, 0, 4, 4, "enum", TARGET_CHOICES),
    BitField("DefaultAlly", "Default ally", 0, 4, 1, 4, "boolean"),
    # Memoria names TargetDisplay 0-4 (None, Hp, Mp, Debuffs, Buffs); 5-7 are
    # representable but unnamed, so the field stays a bounded integer.
    BitField("DisplayStats", "Display stats", 0, 5, 3, 4, "integer"),
    BitField("VfxIndex", "VFX index", 0, 8, 9, 4, "integer"),
    # Bits 17-28: Memoria reads twelve sound bits and discards them. Shown
    # read-only so the preserved value stays visible; never writable.
    BitField("LegacySfx", "Legacy sound bits", 0, 17, 12, 4, "stored"),
    BitField("ForDead", "For dead", 0, 29, 1, 4, "boolean"),
    BitField("DefaultCamera", "Default camera", 0, 30, 1, 4, "boolean"),
    BitField("DefaultOnDead", "Default on dead", 0, 31, 1, 4, "boolean"),
)
ATTACK_FIELDS = (
    _field("ScriptId", "Script ID", 4, "<B"),
    _field("Power", "Power", 5, "<B"),
    _field("Elements", "Elements", 6, "<B"),
    _field("Rate", "Rate", 7, "<B"),
    # Memoria loads Category/Type without documenting their values; the stored
    # bytes stay editable but carry no invented enum.
    _field("Category", "Category", 8, "<B"),
    # StatusSetId: 0-38 verified (None..LesserBadBreath); the byte range stays
    # open because higher values are representable but unnamed.
    _field("AddStatusNo", "Added status set", 9, "<B"),
    _field("MP", "MP", 10, "<B"),
    _field("Type", "Type", 11, "<B"),
    _field("Vfx2", "VFX 2", 12, "<H"),
    # Memoria keeps AA_DATA.Name as the decimal text of this UInt16.
    _field("Name", "Name reference", 14, "<H"),
)


# Scene-header battle flags (SB2_HEAD.Flags, SetupSceneInfo + BTL_SCENE_INFO).
# Memoria inverts NOWINPOSE/NORUNAWAY into WinPose/Runaway for its own API; the
# on-disk bits mean "no pose"/"no escape", so those honest names are used.
# Bits 12-15 have named constants but no consuming code path in the pinned
# revision; they stay read-only and preserved.
SCENE_FLAG_BITS = (
    BitField("SpecialStart", "Scripted start", 4, 0, 1, 2, "boolean"),
    BitField("BackAttack", "Back attack", 4, 1, 1, 2, "boolean"),
    BitField("NoGameOver", "No game over", 4, 2, 1, 2, "boolean"),
    BitField("NoExp", "No EXP", 4, 3, 1, 2, "boolean"),
    BitField("NoWinPose", "No victory pose", 4, 4, 1, 2, "boolean"),
    BitField("NoRunaway", "No escape", 4, 5, 1, 2, "boolean"),
    BitField("NoNeighboring", "No neighboring", 4, 6, 1, 2, "boolean"),
    BitField("NoMagical", "No magic", 4, 7, 1, 2, "boolean"),
    BitField("ReverseAttack", "Reverse attack", 4, 8, 1, 2, "boolean"),
    BitField("FixedCamera1", "Fixed camera 1", 4, 9, 1, 2, "boolean"),
    BitField("FixedCamera2", "Fixed camera 2", 4, 10, 1, 2, "boolean"),
    BitField("AfterEvent", "After event", 4, 11, 1, 2, "boolean"),
    BitField("OtherFlags", "Other flag bits", 4, 12, 4, 2, "stored"),
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

    @property
    def attack_start(self) -> int:
        return 8 + 56 * self.pattern_count + 116 * self.type_count

    def read(self, base: int, field: Field) -> int:
        return struct.unpack_from(field.fmt, self.data, base + field.offset)[0]

    def read_bits(self, base: int, bit: BitField) -> Any:
        fmt = "<I" if bit.size == 4 else "<H"
        word = struct.unpack_from(fmt, self.data, base + bit.offset)[0]
        raw = (word >> bit.shift) & ((1 << bit.width) - 1)
        if bit.kind == "boolean":
            return bool(raw)
        if bit.kind == "enum":
            return bit.choices[raw]
        return raw

    def write_bits(self, base: int, bit: BitField, value: Any) -> None:
        if bit.kind == "stored":
            raise ValueError(f"{bit.label} is read-only and preserved verbatim")
        if bit.kind == "boolean":
            if type(value) is not bool:
                raise ValueError(f"{bit.label} must be true or false")
            raw = 1 if value else 0
        elif bit.kind == "enum":
            if not isinstance(value, str) or value not in bit.choices:
                raise ValueError(f"{bit.label} must be one of its named values")
            raw = bit.choices.index(value)
        else:
            maximum = (1 << bit.width) - 1
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
                raise ValueError(f"{bit.label} must be a whole number from 0 through {maximum}")
            raw = value
        fmt = "<I" if bit.size == 4 else "<H"
        address = base + bit.offset
        word = struct.unpack_from(fmt, self.data, address)[0]
        mask = ((1 << bit.width) - 1) << bit.shift
        struct.pack_into(fmt, self.data, address, (word & ~mask) | (raw << bit.shift))

    def write(self, base: int, field: Field, value: Any) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or not field.min <= value <= field.max:
            raise ValueError(f"{field.label} must be a whole number from {field.min} through {field.max}")
        if field.key == "MonsterCount" and value > 4:
            raise ValueError("Monster count must be from 0 through 4")
        if field.key.startswith("Slot") and field.key.endswith("Type") and value >= self.type_count:
            raise ValueError(f"{field.label} must refer to an enemy type in this scene (0 through {max(0, self.type_count - 1)})")
        struct.pack_into(field.fmt, self.data, base + field.offset, value)


class BattleSceneStore:
    KEYS = frozenset({"enemies", "encounters", "enemy-attacks", "scene-flags"})

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
        # Memoria AssetManager resolves battle-scene TextAssets through the
        # StreamingAssets/Assets/Resources loose-override tree. Hades Workshop
        # and ff9mapkit emit the same path with the serialized TextAsset suffix.
        return (Path("StreamingAssets") / "Assets" / "Resources" / "BattleMap" /
                "BattleScene" / f"EVT_BATTLE_{scene}" / "dbfile0000.raw16.bytes")

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
        note = "Reads vanilla battle-scene TextAssets from p0data2; saves canonical Memoria loose raw16 project overlays under StreamingAssets/Assets/Resources, which Deploy Project copies into the Lexeditor mod folder."
        common = {
            "relativePath": "StreamingAssets/p0data2.bin → StreamingAssets/Assets/Resources/BattleMap/BattleScene/*/dbfile0000.raw16.bytes",
            "available": available, "source": "vanilla" if available else None,
            "sourcePath": str(self.archive_path) if available else None,
            "projectPath": str(self.project_root / "StreamingAssets/Assets/Resources/BattleMap/BattleScene"),
        }
        return [
            {**common, "key": "enemies", "tab": "enemies", "label": "Enemies", "controls": "Enemy HP/MP, rewards, stats, elements, defences, Blue Magic, geometry, SFX, card and shadow fields", "notes": note},
            {**common, "key": "encounters", "tab": "encounters", "label": "Encounters", "controls": "Pattern rate, monster count, camera, AP and four enemy placements", "notes": note},
            {**common, "key": "enemy-attacks", "tab": "enemies", "label": "Enemy attacks", "controls": "Attack targeting, VFX, script, power, elements, rate, category, status set, MP, type and name reference", "notes": note + " The twelve legacy sound bits Memoria reads and discards are shown read-only and preserved verbatim."},
            {**common, "key": "scene-flags", "tab": "encounters", "label": "Battle scene flags", "controls": "Scripted start, back attack, game-over/EXP/pose/escape rules, neighboring, magic, reverse attack, fixed cameras and post-battle event", "notes": note + " Header version, record counts and flag bits 12-15 have no verified gameplay semantics and stay preserved, never editable."},
        ]

    @staticmethod
    def _descriptors(fields: tuple[Field, ...], bits: tuple[BitField, ...] = ()) -> list[dict[str, Any]]:
        result = []
        for bit in bits:
            if bit.kind == "boolean":
                result.append({"key": bit.key, "label": bit.label, "declaredType": "Boolean",
                               "editable": True, "kind": "boolean"})
            elif bit.kind == "enum":
                result.append({"key": bit.key, "label": bit.label, "declaredType": "TargetType",
                               "editable": True, "kind": "enum", "choices": list(bit.choices)})
            elif bit.kind == "stored":
                result.append({"key": bit.key, "label": bit.label,
                               "declaredType": "UInt32" if bit.size == 4 else "UInt16",
                               "editable": False, "kind": "stored"})
            else:
                result.append({"key": bit.key, "label": bit.label,
                               "declaredType": "UInt32" if bit.size == 4 else "UInt16",
                               "editable": True, "kind": "integer",
                               "min": 0, "max": (1 << bit.width) - 1})
        for field in fields:
            maximum = 4 if field.key == "MonsterCount" else field.max
            result.append({"key": field.key, "label": field.label, "declaredType": field.fmt[-1],
                           "editable": True, "kind": "integer", "min": field.min, "max": maximum})
        return result

    LAYOUT_FIELDS = {"enemies": ENEMY_FIELDS, "encounters": PATTERN_FIELDS,
                     "enemy-attacks": ATTACK_FIELDS, "scene-flags": ()}
    LAYOUT_BITS: dict[str, tuple[BitField, ...]] = {"enemies": (), "encounters": (),
                     "enemy-attacks": ATTACK_INFO_BITS, "scene-flags": SCENE_FLAG_BITS}

    @staticmethod
    def _layout(key: str, scene: BattleScene) -> tuple[int, int, int, str]:
        if key == "enemies":
            return scene.enemy_start, 116, scene.type_count, "Enemy"
        if key == "encounters":
            return 8, 56, scene.pattern_count, "Pattern"
        if key == "enemy-attacks":
            return scene.attack_start, 16, scene.attack_count, "Attack"
        if key == "scene-flags":
            return 0, 0, 1, "Scene"
        raise KeyError("Unknown FF9 battle-scene dataset")

    def load(self, key: str) -> dict[str, Any]:
        if key not in self.KEYS:
            raise KeyError("Unknown FF9 battle-scene dataset")
        rows = []
        scene_hashes = {}
        fields, bits = self.LAYOUT_FIELDS[key], self.LAYOUT_BITS[key]
        for scene_name in sorted(self._scenes()):
            data, source_kind, _ = self._source(scene_name)
            scene = BattleScene(scene_name, data)
            scene_hashes[scene_name] = _sha256(data)
            start, stride, count, noun = self._layout(key, scene)
            for index in range(count):
                base = start + index * stride
                values = {bit.key: scene.read_bits(base, bit) for bit in bits}
                values.update({field.key: scene.read(base, field) for field in fields})
                label = f"{scene_name} · {noun} {index + 1}"
                bounds = {}
                if key == "encounters":
                    bounds["MonsterCount"] = {"min": 0, "max": 4}
                    type_max = max(0, scene.type_count - 1)
                    for slot in range(1, 5):
                        bounds[f"Slot{slot}Type"] = {"min": 0, "max": type_max}
                rows.append({"line": len(rows), "id": f"{scene_name}:{index}", "name": label,
                             "scene": scene_name, "record": index, "source": source_kind,
                             "fieldBounds": bounds, "values": values})
        status = next(row for row in self.status_rows() if row["key"] == key)
        return {**status, "sha256": _sha256(self.archive_path.read_bytes()) if self.archive_path.is_file() else "",
                "sceneHashes": scene_hashes, "fields": self._descriptors(fields, bits), "rows": rows}

    def save(self, key: str, expected_scene_hashes: dict[str, str], changes: list[dict[str, Any]]) -> dict[str, Any]:
        if key not in self.KEYS or not isinstance(changes, list):
            raise ValueError("Invalid FF9 battle-scene save")
        fields = {field.key: field for field in self.LAYOUT_FIELDS[key]}
        bits = {bit.key: bit for bit in self.LAYOUT_BITS[key]}
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
            start, stride, limit, _noun = self._layout(key, scene)
            for change in scene_changes:
                index = change.get("record")
                values = change.get("values")
                if type(index) is not int or not 0 <= index < limit or not isinstance(values, dict):
                    raise ValueError("Changed battle record does not belong to this scene")
                base = start + index * stride
                for field_key, value in values.items():
                    field = fields.get(field_key)
                    if field is not None:
                        scene.write(base, field, value)
                        continue
                    bit = bits.get(field_key)
                    if bit is None:
                        raise ValueError(f"{field_key} is not editable")
                    scene.write_bits(base, bit, value)
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
