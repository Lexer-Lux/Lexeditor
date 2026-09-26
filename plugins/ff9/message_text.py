"""Read installed FF9 message TextAssets through mainData's ResourceManager.

Container and PPtr layouts: AssetStudio ResourceManager/SerializedFile readers.
Paths and [ENDN] entry separation: Memoria EmbadedTextResources and
EmbadedSentenseLoader. See credits.md. No game text is bundled or rewritten.
"""
from functools import lru_cache
from pathlib import Path
import re
import struct

from .battle_scene import UnityArchive, MAX_OBJECTS

TABLES = {"items": "item/itm_help.mes", "actions": "ability/aa_help.mes",
          "abilities": "ability/sa_help.mes", "commands": "command/com_help.mes"}


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


def readable_message(text: str) -> str:
    """Remove the game's colour/shadow markup while retaining message text."""
    return re.sub(r"\[(?:[0-9A-Fa-f]{6}|HSHD|SHDW)\]", "", text).strip()


def add_descriptions(payload: dict, game_root: Path) -> dict:
    key = payload.get("key")
    if key not in TABLES:
        return payload
    try:
        entries = messages(game_root)[key]
        for row in payload.get("rows", []):
            try:
                index = int(row["id"])
            except (KeyError, ValueError, TypeError):
                continue
            if 0 <= index < len(entries):
                row["vanillaDescription"] = readable_message(entries[index])
        payload["descriptionLanguage"] = "US"
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
