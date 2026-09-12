"""Structured Steam datasets backed by read-only ``resources.bin`` plus project overlays.

Chrono Trigger Extender (CTExt) can redirect the game's resource loader to loose
files using the same virtual paths as ``resources.bin``. Lexeditor therefore
stores edits as loose ``Game/...`` and ``Localize/...`` project files and never
needs to overwrite the installed archive.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import struct

from .resources import ResourceArchive


MESSAGE_TABLE_FILES = (
    "cmes0.txt", "cmes1.txt", "cmes2.txt", "cmes3.txt", "cmes4.txt", "cmes5.txt",
    "kmes0.txt", "kmes1.txt", "kmes2.txt", "mesi0.txt",
    "mesk0.txt", "mesk1.txt", "mesk2.txt", "mesk3.txt", "mesk4.txt", "mess0.txt",
    "mest0.txt", "mest1.txt", "mest2.txt", "mest3.txt", "mest4.txt", "mest5.txt",
    "msg01.txt", "msg02.txt", "msg03.txt", "msg04.txt",
    "exms0.txt", "exms1.txt", "exms2.txt", "exms3.txt", "wireless1.txt", "wireless2.txt",
)

_LOCALIZE_RE = re.compile(r"^Localize/([^/]+)/msg/([^/]+\.txt)$", re.IGNORECASE)
_SCENE_RE = re.compile(r"^Game/field/Mapinfo/mapinfo_(\d+)\.dat$", re.IGNORECASE)
_FIELD_EVENT_RE = re.compile(r"^Game/field/atel/Atel_(\d+)\.dat$", re.IGNORECASE)
_WORLD_EVENT_RE = re.compile(r"^Game/world/esl/Event_(\d+)\.dat$", re.IGNORECASE)
_EXIT_TABLES = {"game/common/mapjumpoffsettbl.dat", "game/common/mapjumpdatatbl.dat"}
_TREASURE_TABLES = {"game/common/takaraoffsettbl.dat", "game/common/takaradatatbl.dat"}


@dataclass(frozen=True)
class SceneField:
    key: str
    label: str
    offset: int
    size: int

    @property
    def maximum(self) -> int:
        return 0xFF if self.size == 1 else 0xFFFF


SCENE_FIELDS = (
    SceneField("musicIndex", "Music", 0, 2),
    SceneField("tilesetL12", "Tileset L1/2", 2, 2),
    SceneField("tilesetL12Assembly", "Tileset L1/2 Assembly", 4, 2),
    SceneField("tilesetL3", "Tileset L3", 6, 2),
    SceneField("palette", "Palette", 8, 2),
    SceneField("paletteAnimations", "Palette Animations", 10, 2),
    SceneField("mapIndex", "Map", 12, 2),
    SceneField("chipAnimations", "Chip Animations", 14, 2),
    SceneField("scriptIndex", "Event Script", 16, 2),
    SceneField("unknown18", "Unknown 0x12", 18, 2),
    SceneField("scrollLeft", "Scroll Left", 20, 1),
    SceneField("scrollTop", "Scroll Top", 21, 1),
    SceneField("scrollRight", "Scroll Right", 22, 1),
    SceneField("scrollBottom", "Scroll Bottom", 23, 1),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_virtual_path(value: str) -> str:
    """Return one safe archive-style relative path."""
    text = str(value).replace("\\", "/").strip()
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ValueError("A relative Chrono Trigger resource path is required")
    parts = text.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError(f"Unsafe Chrono Trigger resource path: {value}")
    return PurePosixPath(*parts).as_posix()


class OverlayStore:
    """Resolve an editable project overlay over a vanilla Steam archive."""

    def __init__(self, archive_path: Path, project_root: Path, *, template_root: Path | None = None):
        self.archive = ResourceArchive(archive_path)
        self.project_root = Path(project_root)
        self.template_root = Path(template_root).resolve() if template_root else None

    @property
    def writable(self) -> bool:
        return self.template_root is None or self.project_root.resolve() != self.template_root

    def _project_path(self, virtual_path: str) -> Path:
        virtual = normalize_virtual_path(virtual_path)
        root = self.project_root.resolve()
        target = (root / Path(*PurePosixPath(virtual).parts)).resolve()
        if target != root and root not in target.parents:
            raise ValueError("Project resource path escaped the selected project")
        return target

    def overlay_exists(self, virtual_path: str) -> bool:
        return self._project_path(virtual_path).is_file()

    def exists(self, virtual_path: str, source: str = "mine") -> bool:
        virtual = normalize_virtual_path(virtual_path)
        if source != "vanilla" and self.overlay_exists(virtual):
            return True
        try:
            self.archive.get(virtual)
            return True
        except KeyError:
            return False

    def read(self, virtual_path: str, source: str = "mine") -> tuple[bytes, str]:
        virtual = normalize_virtual_path(virtual_path)
        if source != "vanilla":
            target = self._project_path(virtual)
            if target.is_file():
                return target.read_bytes(), "project"
        return self.archive.read(virtual), "archive"

    def write(self, virtual_path: str, data: bytes) -> Path:
        if not self.writable:
            raise RuntimeError("Create or select a Chrono Trigger mod project before saving edits")
        target = self._project_path(virtual_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
        return target

    def localization_files(self) -> list[dict]:
        rows = []
        known = {name.casefold() for name in MESSAGE_TABLE_FILES}
        for entry in self.archive.entries:
            match = _LOCALIZE_RE.match(entry.path)
            if not match:
                continue
            rows.append({
                "language": match.group(1),
                "file": match.group(2),
                "path": entry.path,
                "knownEventTable": match.group(2).casefold() in known,
                "source": "project" if self.overlay_exists(entry.path) else "archive",
            })
        return sorted(rows, key=lambda row: (row["language"].casefold(), row["file"].casefold()))

    def scene_entries(self) -> list[tuple[int, str]]:
        rows = []
        for entry in self.archive.entries:
            match = _SCENE_RE.match(entry.path)
            if match:
                rows.append((int(match.group(1)), entry.path))
        return sorted(rows)


def _decode_lines(raw: bytes) -> tuple[list[str], str, bool, bool]:
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    terminal_newline = text.endswith("\n") or text.endswith("\r")
    return text.splitlines(), newline, terminal_newline, bom


def load_message_table(store: OverlayStore, virtual_path: str, source: str = "mine") -> dict:
    virtual = normalize_virtual_path(virtual_path)
    if not _LOCALIZE_RE.match(virtual):
        raise ValueError("Only Localize/<language>/msg/*.txt resources are message tables")
    raw, origin = store.read(virtual, source)
    lines, _newline, _terminal, _bom = _decode_lines(raw)
    rows = []
    for index, line in enumerate(lines):
        if "," in line:
            key, text = line.split(",", 1)
        else:
            key, text = "", line
        rows.append({"id": index, "key": key, "text": text})
    match = _LOCALIZE_RE.match(virtual)
    return {
        "kind": "message-table",
        "path": virtual,
        "language": match.group(1) if match else "",
        "file": match.group(2) if match else PurePosixPath(virtual).name,
        "source": origin,
        "readOnly": source == "vanilla",
        "sha256": sha256(raw),
        "rows": rows,
    }


def save_message_table(store: OverlayStore, virtual_path: str, expected_sha256: str,
                       changes: list[dict]) -> dict:
    virtual = normalize_virtual_path(virtual_path)
    if not _LOCALIZE_RE.match(virtual):
        raise ValueError("Only localization message tables can be saved")
    raw, _origin = store.read(virtual, "mine")
    if sha256(raw) != expected_sha256:
        raise RuntimeError("The message table changed since it was opened; reload it before saving")
    lines, newline, terminal_newline, bom = _decode_lines(raw)
    for change in changes:
        index = int(change.get("id", -1))
        if not 0 <= index < len(lines):
            raise ValueError(f"Message row is outside the table: {index}")
        text = str(change.get("text", ""))
        if "\r" in text or "\n" in text:
            raise ValueError("Message text cannot contain raw line breaks; use the game's backslash/tag syntax")
        line = lines[index]
        key = line.split(",", 1)[0] if "," in line else ""
        lines[index] = f"{key},{text}" if key else text
    rendered = newline.join(lines) + (newline if terminal_newline else "")
    encoded = rendered.encode("utf-8")
    if bom:
        encoded = b"\xef\xbb\xbf" + encoded
    target = store.write(virtual, encoded)
    result = load_message_table(store, virtual, "mine")
    result["savedPath"] = str(target)
    return result


def parse_scene_header(raw: bytes) -> dict:
    if len(raw) < 24:
        raise ValueError(f"Chrono Trigger scene header is too short: {len(raw)} bytes")
    values = {}
    for field in SCENE_FIELDS:
        if field.size == 1:
            values[field.key] = raw[field.offset]
        else:
            values[field.key] = struct.unpack_from("<H", raw, field.offset)[0]
    return values


def load_scene(store: OverlayStore, scene_id: int, virtual_path: str, source: str = "mine") -> dict:
    raw, origin = store.read(virtual_path, source)
    return {
        "id": int(scene_id),
        "name": f"Scene {int(scene_id):04d}",
        "path": virtual_path,
        "source": origin,
        "readOnly": source == "vanilla",
        "sha256": sha256(raw),
        "values": parse_scene_header(raw),
    }


def load_scenes(store: OverlayStore, source: str = "mine", query: str = "",
                offset: int = 0, limit: int = 100) -> dict:
    needle = query.strip().casefold()
    entries = [(scene_id, path) for scene_id, path in store.scene_entries()
               if not needle or needle in str(scene_id).casefold() or needle in path.casefold()]
    offset = max(0, min(int(offset), len(entries)))
    limit = max(1, min(int(limit), 250))
    rows = [load_scene(store, scene_id, path, source) for scene_id, path in entries[offset:offset + limit]]
    return {
        "kind": "scene-headers",
        "fields": [
            {"key": field.key, "label": field.label, "kind": "integer", "min": 0, "max": field.maximum}
            for field in SCENE_FIELDS
        ],
        "matchCount": len(entries),
        "offset": offset,
        "limit": limit,
        "rows": rows,
    }


def save_scene(store: OverlayStore, scene_id: int, expected_sha256: str, values: dict) -> dict:
    matches = {number: path for number, path in store.scene_entries()}
    scene_id = int(scene_id)
    if scene_id not in matches:
        raise ValueError(f"Unknown Chrono Trigger scene: {scene_id}")
    virtual = matches[scene_id]
    raw, _origin = store.read(virtual, "mine")
    if sha256(raw) != expected_sha256:
        raise RuntimeError("The scene header changed since it was opened; reload it before saving")
    output = bytearray(raw)
    allowed = {field.key: field for field in SCENE_FIELDS}
    unknown = set(values) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown scene fields: {', '.join(sorted(unknown))}")
    for key, value in values.items():
        field = allowed[key]
        number = int(value)
        if not 0 <= number <= field.maximum:
            raise ValueError(f"{field.label} must be between 0 and {field.maximum}")
        if field.size == 1:
            output[field.offset] = number
        else:
            struct.pack_into("<H", output, field.offset, number)
    target = store.write(virtual, bytes(output))
    result = load_scene(store, scene_id, virtual, "mine")
    result["savedPath"] = str(target)
    return result


def classify_resource(path: str) -> dict:
    """Return evidence-based integration metadata for one archive path."""
    virtual = normalize_virtual_path(path)
    lower = virtual.casefold()
    if _LOCALIZE_RE.match(virtual):
        return {"kind": "localization-text", "coverage": "structured", "status": "integrated", "target": "text"}
    if _SCENE_RE.match(virtual):
        return {"kind": "scene-header", "coverage": "structured", "status": "integrated", "target": "scenes"}
    if lower in _EXIT_TABLES:
        return {"kind": "scene-exits", "coverage": "structured", "status": "integrated", "target": "scenes"}
    if lower in _TREASURE_TABLES:
        return {"kind": "scene-treasure", "coverage": "structured", "status": "integrated", "target": "scenes"}
    if _FIELD_EVENT_RE.match(virtual):
        return {"kind": "field-event-script", "coverage": "structural", "status": "partial", "target": "events"}
    if _WORLD_EVENT_RE.match(virtual):
        return {"kind": "world-event-script", "coverage": "known", "status": "partial", "target": "resources"}
    if lower.startswith("game/field/") or lower.startswith("game/world/"):
        return {"kind": "map-world-data", "coverage": "known", "status": "partial", "target": "resources"}
    suffix = PurePosixPath(virtual).suffix.casefold()
    if suffix in {".png", ".bmp"}:
        return {"kind": "image", "coverage": "raw", "status": "integrated", "target": "resources"}
    if suffix in {".sab", ".ogg", ".mp3"}:
        return {"kind": "audio", "coverage": "raw", "status": "integrated", "target": "resources"}
    if PurePosixPath(virtual).name.casefold().startswith("string_"):
        return {"kind": "font", "coverage": "encrypted", "status": "partial", "target": "resources"}
    return {"kind": "resource", "coverage": "raw", "status": "integrated", "target": "resources"}


def data_map(store: OverlayStore) -> dict:
    entries = [entry.path for entry in store.archive.entries]
    lowered = {path.casefold() for path in entries}
    counts = {
        "messages": sum(bool(_LOCALIZE_RE.match(path)) for path in entries),
        "scenes": sum(bool(_SCENE_RE.match(path)) for path in entries),
        "fieldEvents": sum(bool(_FIELD_EVENT_RE.match(path)) for path in entries),
        "worldEvents": sum(bool(_WORLD_EVENT_RE.match(path)) for path in entries),
        "exitTables": sum(path in lowered for path in _EXIT_TABLES),
        "treasureTables": sum(path in lowered for path in _TREASURE_TABLES),
    }
    rows = [
        {
            "filename": "resources.bin",
            "controls": f"ARC1 archive index ({len(entries)} resources)",
            "notes": "Vanilla Steam source. Lexeditor reads and extracts it but never overwrites it.",
            "status": "integrated", "coverage": "raw", "openable": True, "target": "resources",
        },
        {
            "filename": "Localize/*/msg/*.txt",
            "controls": f"{counts['messages']} UTF-8 localization/message resources",
            "notes": "Structured line/key editor. Saves the exact virtual path into the selected loose-file project overlay.",
            "status": "integrated" if counts["messages"] else "partial",
            "coverage": "structured", "openable": bool(counts["messages"]), "target": "text",
        },
        {
            "filename": "Game/field/Mapinfo/mapinfo_*.dat",
            "controls": f"{counts['scenes']} scene headers: music, tilesets, palette, map/script IDs and scroll bounds",
            "notes": "24-byte Steam scene-header structure is decoded and edited through project overlays.",
            "status": "integrated" if counts["scenes"] else "partial",
            "coverage": "structured", "openable": bool(counts["scenes"]), "target": "scenes",
        },
        {
            "filename": "Game/common/MapJumpOffsetTbl.dat + MapJumpDataTbl.dat",
            "controls": "Scene exits: trigger position/size, facing/shift flags, destination and destination tile",
            "notes": "PC records are fixed 8-byte entries. Existing records are editable; the shared offset table and record count stay unchanged.",
            "status": "integrated" if counts["exitTables"] == 2 else "partial",
            "coverage": "structured", "openable": counts["exitTables"] == 2, "target": "scenes",
        },
        {
            "filename": "Game/common/TakaraOffsetTbl.dat + TakaraDataTbl.dat",
            "controls": "Scene treasure: tile position, encoded contents/gold/item category and trailing u16",
            "notes": "PC records are fixed 6-byte entries. Existing records are editable; the shared offset table and record count stay unchanged.",
            "status": "integrated" if counts["treasureTables"] == 2 else "partial",
            "coverage": "structured", "openable": counts["treasureTables"] == 2, "target": "scenes",
        },
        {
            "filename": "Game/field/atel/Atel_*.dat",
            "controls": f"{counts['fieldEvents']} field event scripts: objects, 16 function slots/object and bytecode bounds",
            "notes": "Steam retains the count + function-pointer-table + bytecode layout. Structural inspection is integrated; opcode editing remains read-only.",
            "status": "partial", "coverage": "structural", "openable": True, "target": "events",
        },
        {
            "filename": "Game/world/esl/Event_*.dat",
            "controls": f"{counts['worldEvents']} world event scripts",
            "notes": "Known Steam world-script resources; structured command editing is not integrated yet.",
            "status": "partial", "coverage": "known", "openable": True, "target": "resources",
        },
        {
            "filename": "Game/field/*; Game/world/*; Game/chara/*",
            "controls": "Maps, palettes, sprites and related assets",
            "notes": "Their Steam paths and several binary layouts are documented by CTViewer. Raw access exists; structured editors are added only when the layout is proven.",
            "status": "partial", "coverage": "known", "openable": True, "target": "resources",
        },
        {
            "filename": "CTExt mods/<project>/...",
            "controls": "Loose-file runtime overlay",
            "notes": "Lexeditor projects use archive-relative Game/... and Localize/... paths compatible with CTExt resource redirection. Runtime installation/configuration is not automated yet.",
            "status": "partial", "coverage": "deployment", "openable": False,
        },
    ]
    return {"contract": "Lexeditor.data-map", "rows": rows, "counts": counts}
