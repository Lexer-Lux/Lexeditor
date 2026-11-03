"""Read installed FF9 message TextAssets through mainData's ResourceManager.

Container and PPtr layouts: AssetStudio ResourceManager/SerializedFile readers.
Paths and [ENDN] entry separation: Memoria EmbadedTextResources and
EmbadedSentenseLoader. See credits.md. No game text is bundled; US
description edits write a project FF9_Data overlay, never the install.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import re
import struct

from core.plugin_files import atomic_write

from .battle_scene import UnityArchive, MAX_OBJECTS

TABLES = {"items": "item/itm_help.mes", "actions": "ability/aa_help.mes",
          "abilities": "ability/sa_help.mes", "commands": "command/com_help.mes"}

LANGUAGE = "US"
OVERLAY_BASE = Path("FF9_Data") / "EmbeddedAsset" / "Text" / LANGUAGE


def overlay_relative_path(key: str) -> Path:
    """Project-relative Memoria loose override for one description table."""
    return OVERLAY_BASE / TABLES[key]


def overlay_path(project_root: Path, key: str) -> Path:
    return Path(project_root) / overlay_relative_path(key)


def resource_references(blob: bytes) -> dict[str, tuple[int, int]]:
    if len(blob) < 4:
        raise ValueError("ResourceManager is truncated")
    count, = struct.unpack_from("<I", blob)
    if count > MAX_OBJECTS:
        raise ValueError("ResourceManager has too many entries")
    pos, result = 4, {}
    for _ in range(count):
        if pos + 4 > len(blob):
            raise ValueError("ResourceManager entry is truncated")
        size, = struct.unpack_from("<I", blob, pos); pos += 4
        end = pos + size
        aligned = (end + 3) & ~3
        if size > 4096 or aligned + 12 > len(blob):
            raise ValueError("ResourceManager path is invalid")
        path = blob[pos:end].decode("utf-8").lower()
        file_id, path_id = struct.unpack_from("<iq", blob, aligned)
        # Sprite and texture assets can share a path; message TextAssets must
        # be unique. Other resource types are outside this reader's scope.
        if path.startswith("embeddedasset/text/") and path.endswith(".mes"):
            if path in result and result[path] != (file_id, path_id):
                raise ValueError(f"Duplicate message resource path: {path}")
            result[path] = file_id, path_id
        pos = aligned + 12
    return result


def split_messages(text: str) -> list[str]:
    entries = text.lstrip("\ufeff").split("[ENDN]")
    if text.endswith("[ENDN]"):
        entries.pop()
    return entries


def join_messages(entries: list[str]) -> str:
    """Entries joined with [ENDN] plus a trailing [ENDN]: the .mes framing."""
    return "[ENDN]".join(entries) + "[ENDN]"


def text_sha256(entries: list[str]) -> str:
    return hashlib.sha256(join_messages(entries).encode("utf-8")).hexdigest()


def current_entries(game_root: Path, project_root: Path, key: str) -> tuple[list[str], str]:
    """Entries the editor shows: the project overlay wins over installed vanilla."""
    overlay = overlay_path(project_root, key)
    if overlay.is_file():
        return split_messages(overlay.read_text(encoding="utf-8")), "project"
    return messages(game_root)[key], "vanilla"


def save_descriptions(game_root: Path, project_root: Path, key: str,
                      expected_sha256: str, updates: dict) -> list[str]:
    """Write edited US description entries to the project overlay.

    The install is never written; edited tables land at
    project/FF9_Data/EmbeddedAsset/Text/US/<table>, where Memoria picks them
    up as loose TextAsset overrides after Deploy Project.
    """
    if key not in TABLES:
        raise ValueError("Unknown FF9 description table")
    if not isinstance(updates, dict):
        raise ValueError("Description changes must be an object")
    entries, _source = current_entries(game_root, project_root, key)
    if text_sha256(entries) != str(expected_sha256 or ""):
        raise RuntimeError("The FF9 description text changed outside Lexeditor. Reload it before saving.")
    result = list(entries)
    for raw_index, text in updates.items():
        if isinstance(raw_index, bool) or (isinstance(raw_index, float) and not raw_index.is_integer()):
            raise ValueError("Invalid FF9 description index: %r" % (raw_index,))
        try:
            index = int(raw_index)
        except (ValueError, TypeError):
            raise ValueError("Invalid FF9 description index: %r" % (raw_index,))
        if not 0 <= index < len(result):
            raise ValueError("FF9 description index is out of range: %d" % index)
        if not isinstance(text, str):
            raise ValueError("FF9 description %d must be text" % index)
        if "[ENDN]" in text:
            raise ValueError("FF9 description %d must not contain [ENDN]" % index)
        if chr(0) in text:
            raise ValueError("FF9 description %d must not contain NUL" % index)
        result[index] = text
    target = overlay_path(project_root, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, join_messages(result).encode("utf-8"))
    return result


def readable_message(text: str) -> str:
    """Remove the game's colour/shadow markup while retaining message text."""
    return re.sub(r"\[(?:[0-9A-Fa-f]{6}|HSHD|SHDW)\]", "", text).strip()


def add_descriptions(payload: dict, game_root: Path, project_root: Path | None = None) -> dict:
    key = payload.get("key")
    if key not in TABLES:
        return payload
    try:
        vanilla = messages(game_root)[key]
        overlay = overlay_path(project_root, key) if project_root is not None else None
        if overlay is not None and overlay.is_file():
            current = split_messages(overlay.read_text(encoding="utf-8"))
            source = "project"
        else:
            current, source = vanilla, "vanilla"
        for row in payload.get("rows", []):
            try:
                index = int(row["id"])
            except (KeyError, ValueError, TypeError):
                continue
            if 0 <= index < len(vanilla):
                row["vanillaText"] = vanilla[index]
                row["vanillaDescription"] = readable_message(vanilla[index])
            if 0 <= index < len(current):
                row["description"] = current[index]
        payload["descriptionLanguage"] = "US"
        payload["textSha256"] = text_sha256(current)
        payload["textSource"] = source
    except (OSError, ValueError, UnicodeError) as error:
        payload["descriptionError"] = str(error)
    return payload


@lru_cache(maxsize=1)
def _read_messages(directory: str, stamp: tuple, language: str) -> dict[str, list[str]]:
    root = Path(directory)
    main = UnityArchive(root / "mainData")
    refs = {}
    for obj in main.objects:
        if obj.type_id == 147:
            refs.update(resource_references(main._object_payload(obj)))
    external = main.external_files()
    wanted = {}
    for key, suffix in TABLES.items():
        path = f"embeddedasset/text/{language.lower()}/{suffix}"
        reference = refs.get(path)
        if reference is None:
            raise ValueError(f"Installed FF9 text resource is missing: {path}")
        file_id, path_id = reference
        if not 1 <= file_id <= len(external) or Path(external[file_id - 1].replace('\\', '/')).name != "resources.assets":
            raise ValueError(f"Unsupported text resource container: {path}")
        wanted[path_id] = key
    assets = UnityArchive(root / "resources.assets")
    result = {}
    for obj in assets.objects:
        if obj.info in wanted:
            if obj.type_id != 49:
                raise ValueError("Message resource is not a TextAsset")
            result[wanted[obj.info]] = split_messages(assets._object_payload(obj).decode("utf-8-sig"))
    if set(result) != set(TABLES):
        raise ValueError("FF9 message object references could not all be resolved")
    return result


def messages(game_root: Path, language: str = "US") -> dict[str, list[str]]:
    if language not in {"US", "UK", "JP", "FR", "GR", "IT", "ES"}:
        raise ValueError("Unsupported FF9 message language")
    directory = next((game_root / name for name in ("x64/FF9_Data", "FF9_Data", "x86/FF9_Data")
                      if (game_root / name / "mainData").is_file()), None)
    if directory is None:
        raise FileNotFoundError("Installed FF9 mainData was not found")
    stamp = tuple((p.stat().st_size, p.stat().st_mtime_ns)
                  for p in (directory / "mainData", directory / "resources.assets"))
    return _read_messages(str(directory), stamp, language)
