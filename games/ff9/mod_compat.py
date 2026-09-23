"""Read-only compatibility audit for Memoria's enabled external FF9 mods.

Lexeditor never installs, edits, removes or reorders external mods here.  The
report reflects Memoria.ini + each enabled mod's public ModDescription.xml
contract and exact file-path overlap with the selected Lexeditor project.
"""
from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from . import memoria_manager, paths


MAX_DESCRIPTION_BYTES = 1024 * 1024
MAX_PROJECT_FILES = 10_000


def _decode_ini(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def _ini_setting(text: str, section_name: str, key_name: str) -> str:
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().casefold()
            continue
        if section != section_name.casefold() or "=" not in line or stripped.startswith((";", "#")):
            continue
        key, value = line.split("=", 1)
        if key.strip().casefold() == key_name.casefold():
            return value.strip()
    return ""


def _quoted_list(value: str) -> list[str]:
    values = re.findall(r'"([^"]*)"', value)
    if values:
        return [item for item in values if item]
    raw = value.strip().strip('"')
    return [raw] if raw else []


def _version(value: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", str(value or ""))]
    return tuple(numbers)


def _newer_than(value: str, baseline: str) -> bool:
    left, right = _version(value), _version(baseline)
    width = max(len(left), len(right))
    return left + (0,) * (width - len(left)) > right + (0,) * (width - len(right))


def _name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _safe_active_path(game: Path, raw: str) -> Path | None:
    normalized = raw.replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return None
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    target = game.joinpath(*parts)
    try:
        resolved = target.resolve()
        game_resolved = game.resolve()
        if resolved != game_resolved and game_resolved not in resolved.parents:
            return None
    except OSError:
        return None
    return target


def _root_name(raw: str) -> str:
    normalized = raw.replace("\\", "/").strip("/")
    return normalized.split("/", 1)[0] if normalized else ""


def _description(game: Path, root_name: str) -> dict:
    path = _safe_active_path(game, root_name)
    if path is None:
        return {"folder": root_name, "name": root_name, "metadata": False,
                "error": "Unsafe Memoria mod path"}
    source = path / "ModDescription.xml"
    if not source.is_file():
        return {"folder": root_name, "name": root_name, "metadata": False}
    try:
        if source.stat().st_size > MAX_DESCRIPTION_BYTES:
            raise ValueError("ModDescription.xml is too large")
        root = ET.fromstring(source.read_bytes())
        if root.tag != "Mod":
            raise ValueError("ModDescription.xml root is not <Mod>")
        get = lambda name: (root.findtext(name) or "").strip()
        incompatible = [part.strip() for part in get("IncompatibleWith").split(",") if part.strip()]
        return {
            "folder": root_name,
            "name": get("Name") or root_name,
            "version": get("Version"),
            "minimumMemoriaVersion": get("MinimumMemoriaVersion"),
            "incompatibleWith": incompatible,
            "metadata": True,
        }
    except (OSError, ET.ParseError, ValueError) as error:
        return {"folder": root_name, "name": root_name, "metadata": False, "error": str(error)}


def _project_files(project: Path) -> tuple[list[Path], bool]:
    root = project / "StreamingAssets"
    if not root.is_dir():
        return [], False
    result: list[Path] = []
    truncated = False
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        result.append(path.relative_to(project))
        if len(result) >= MAX_PROJECT_FILES:
            truncated = True
            break
    return result, truncated


def audit(game_root: Path | None = None, project_root: Path | None = None) -> dict:
    """Return a non-mutating Memoria/external-mod compatibility snapshot."""
    game = Path(game_root or paths.GAME_ROOT)
    project = Path(project_root or paths.PROJECT_ROOT)
    ini = game / "Memoria.ini"
    pinned = memoria_manager.PINNED_RELEASE.lstrip("vV")
    if not ini.is_file():
        return {
            "pinnedMemoria": memoria_manager.PINNED_RELEASE,
            "folderNames": [], "priorities": [], "mods": [], "declaredConflicts": [],
            "overlaps": [], "unsupportedByPinnedMemoria": [], "unknownRuntimeCompatibility": [], "mergeScripts": None,
            "projectScanTruncated": False,
        }

    try:
        text = _decode_ini(ini.read_bytes())
    except (OSError, UnicodeError) as error:
        return {"pinnedMemoria": memoria_manager.PINNED_RELEASE, "error": str(error),
                "folderNames": [], "priorities": [], "mods": [], "declaredConflicts": [],
                "overlaps": [], "unsupportedByPinnedMemoria": [], "unknownRuntimeCompatibility": [], "mergeScripts": None,
                "projectScanTruncated": False}

    folders = _quoted_list(_ini_setting(text, "Mod", "FolderNames"))
    priorities = _quoted_list(_ini_setting(text, "Mod", "Priorities"))
    merge_raw = _ini_setting(text, "Mod", "MergeScripts").split(";", 1)[0].strip().casefold()
    merge_scripts = None if not merge_raw else merge_raw in {"1", "true", "yes", "on"}
    project_files, truncated = _project_files(project)

    roots: list[str] = []
    active_paths: dict[str, list[str]] = {}
    for folder in folders:
        if _name_key(_root_name(folder)) == _name_key("Lexeditor"):
            continue
        root = _root_name(folder)
        if not root:
            continue
        key = _name_key(root)
        if key not in active_paths:
            roots.append(root)
            active_paths[key] = []
        active_paths[key].append(folder)

    mods = []
    overlaps = []
    for root in roots:
        meta = _description(game, root)
        key = _name_key(root)
        overlap_paths: list[str] = []
        for active in active_paths[key]:
            active_root = _safe_active_path(game, active)
            if active_root is None:
                continue
            for relative in project_files:
                # Project paths are game-relative from <project>; active mods are
                # folder-relative from <game>/<mod>.
                candidate = active_root / relative
                if candidate.is_file():
                    value = relative.as_posix()
                    if value not in overlap_paths:
                        overlap_paths.append(value)
        minimum = str(meta.get("minimumMemoriaVersion", ""))
        minimum_valid = not minimum or bool(_version(minimum))
        runtime_compatibility = (
            "unknown" if not minimum
            else "unsupported" if not minimum_valid or _newer_than(minimum, pinned)
            else "declared-compatible"
        )
        row = {
            **meta,
            "activePaths": list(active_paths[key]),
            "minimumMemoriaVersionValid": minimum_valid,
            "runtimeCompatibility": runtime_compatibility,
            "supportedByPinnedMemoria": (
                True if runtime_compatibility == "declared-compatible"
                else False if runtime_compatibility == "unsupported"
                else None
            ),
            "overlapPaths": overlap_paths,
        }
        mods.append(row)
        for value in overlap_paths:
            overlaps.append({"mod": row["name"], "folder": root, "path": value})

    by_name = {_name_key(mod["name"]): mod for mod in mods}
    declared = []
    seen = set()
    for mod in mods:
        for other_name in mod.get("incompatibleWith", []):
            other = by_name.get(_name_key(other_name))
            if not other:
                continue
            pair = tuple(sorted((mod["name"], other["name"]), key=str.casefold))
            marker = tuple(value.casefold() for value in pair)
            if marker not in seen:
                seen.add(marker)
                declared.append({"mods": list(pair), "source": mod["name"]})

    unsupported = [
        {"name": mod["name"], "folder": mod["folder"],
         "minimumMemoriaVersion": mod.get("minimumMemoriaVersion", ""),
         "reason": ("invalid MinimumMemoriaVersion metadata"
                    if not mod.get("minimumMemoriaVersionValid", True)
                    else "requires newer Memoria")}
        for mod in mods if mod["runtimeCompatibility"] == "unsupported"
    ]
    unknown_runtime = [
        {"name": mod["name"], "folder": mod["folder"]}
        for mod in mods if mod["runtimeCompatibility"] == "unknown"
    ]

    return {
        "pinnedMemoria": memoria_manager.PINNED_RELEASE,
        "folderNames": folders,
        "priorities": priorities,
        "lexeditorRuntimePriority": next((i for i, name in enumerate(folders)
                                           if _name_key(_root_name(name)) == _name_key("Lexeditor")), None),
        "lexeditorLauncherPriority": next((i for i, name in enumerate(priorities)
                                            if _name_key(_root_name(name)) == _name_key("Lexeditor")), None),
        "mergeScripts": merge_scripts,
        "mods": mods,
        "declaredConflicts": declared,
        "overlaps": overlaps,
        "unsupportedByPinnedMemoria": unsupported,
        "unknownRuntimeCompatibility": unknown_runtime,
        "projectScanTruncated": truncated,
    }
