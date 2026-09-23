"""Read-only compatibility checks for public 7th Heaven FF7 mod stacks.

The contract mirrors 7th Heaven source revision ae129f0: profiles keep an ordered
list of active ModIDs, library.xml maps each ModID to its installed location,
folder mods may select ModFolder/Conditional roots via mod.xml, and .iro files
are opaque unless an IRO reader is available. This module never edits 7th
Heaven state and never guesses inside .iro packages.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET


SEVENTH_HEAVEN_SOURCE_REVISION = "ae129f0bbeeeb236b1c37fb136e5fec25fd292a3"
WORKSHOP_ENV = "LEXEDITOR_FF7_7H_WORKSHOP"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children_named(node: ET.Element, name: str):
    return [child for child in node.iter() if _local(child.tag) == name]


def _text(node: ET.Element, name: str, default: str = "") -> str:
    for child in node.iter():
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return default


def _parse(path: Path) -> ET.Element:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"Invalid 7th Heaven XML: {path}: {error}") from error


def _norm(path: str) -> str:
    raw = str(path or "").replace("\\", "/").strip("/")
    pure = PurePosixPath(raw)
    if not raw or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"Unsafe 7th Heaven virtual path: {path}")
    return pure.as_posix().casefold()


def _version_key(text: str) -> tuple:
    pieces = re.findall(r"\d+|[^\d]+", text or "")
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in pieces)


def _settings(workshop: Path) -> tuple[Path, Path, str]:
    root = _parse(workshop / "settings.xml")
    library = _text(root, "LibraryLocation")
    profile = _text(root, "CurrentProfile")
    if not library:
        raise ValueError("7th Heaven settings.xml has no LibraryLocation")
    if not profile:
        raise ValueError("7th Heaven settings.xml has no CurrentProfile")
    library_path = Path(os.path.expandvars(os.path.expanduser(library))).resolve()
    return library_path, workshop / "profiles" / f"{profile}.xml", profile


def _library_locations(workshop: Path) -> dict[str, str]:
    root = _parse(workshop / "library.xml")
    result: dict[str, str] = {}
    for item in _children_named(root, "InstalledItem"):
        mod_id = _text(item, "ModID").casefold()
        if not mod_id:
            continue
        choices: list[tuple[tuple, str]] = []
        for version in _children_named(item, "InstalledVersion"):
            location = _text(version, "InstalledLocation")
            if location:
                choices.append((_version_key(_text(version, "Version")), location))
        if choices:
            choices.sort(key=lambda row: row[0])
            result[mod_id] = choices[-1][1]
    return result


def _active_profile(profile_path: Path) -> list[dict]:
    root = _parse(profile_path)
    rows: list[dict] = []
    for item in _children_named(root, "ProfileItem"):
        if _text(item, "IsModActive").casefold() not in {"true", "1"}:
            continue
        mod_id = _text(item, "ModID")
        if not mod_id:
            continue
        rows.append({"modId": mod_id, "name": _text(item, "Name") or mod_id})
    return rows


def _mod_roots(folder: Path) -> tuple[list[Path], list[Path]]:
    mod_xml = folder / "mod.xml"
    if not mod_xml.is_file():
        return [folder], []
    root = _parse(mod_xml)
    ordinary: list[Path] = []
    conditional: list[Path] = []
    for node in root.iter():
        kind = _local(node.tag)
        if kind == "ModFolder":
            name = (node.attrib.get("Folder") or "").strip()
            if name:
                ordinary.append(folder / name)
        elif kind == "Conditional":
            name = (node.attrib.get("Folder") or "").strip()
            if name:
                conditional.append(folder / name)
    if not ordinary and not conditional:
        ordinary.append(folder)
    return ordinary, conditional


def _direct_files(root: Path) -> set[str]:
    direct = root / "direct"
    if not direct.is_dir():
        return set()
    result = set()
    base = root.resolve()
    for path in direct.rglob("*"):
        if path.is_file():
            result.add(_norm(path.resolve().relative_to(base).as_posix()))
    return result


def scan_7h_stack(workshop_root: Path, direct_paths) -> dict:
    """Compare Lexeditor Direct Mode paths with one 7H active profile.

    direct_paths are relative to FFNx's Direct root. Same-path results are
    reported, never assigned a guessed winner. IRO packages remain opaque.
    """
    workshop = Path(workshop_root).resolve()
    library_root, profile_path, profile_name = _settings(workshop)
    library = _library_locations(workshop)
    active = _active_profile(profile_path)
    wanted = {_norm("direct/" + str(path)) for path in direct_paths}
    overlaps, conditional_overlaps, opaque, missing = [], [], [], []
    order = []

    for index, item in enumerate(active):
        mod_id = item["modId"].casefold()
        location = library.get(mod_id)
        row = {**item, "order": index}
        if not location:
            missing.append({**row, "reason": "Active ModID is absent from library.xml"})
            order.append({**row, "location": None, "kind": "missing"})
            continue
        source = (library_root / location).resolve()
        kind = "iro" if location.casefold().endswith(".iro") else "folder"
        order.append({**row, "location": str(source), "kind": kind})
        if kind == "iro":
            opaque.append({**row, "location": str(source),
                "reason": "IRO contents were not inspected; no IRO parser is claimed by this check"})
            continue
        if not source.is_dir():
            missing.append({**row, "location": str(source), "reason": "Installed folder is missing"})
            continue
        ordinary, conditional = _mod_roots(source)
        for virtual in sorted(set().union(*(_direct_files(root) for root in ordinary)) & wanted):
            overlaps.append({**row, "path": virtual, "location": str(source)})
        for virtual in sorted(set().union(*(_direct_files(root) for root in conditional)) & wanted):
            conditional_overlaps.append({**row, "path": virtual, "location": str(source),
                "reason": "7th Heaven conditional activation was not evaluated"})

    complete = not opaque and not missing and not conditional_overlaps
    return {
        "provider": "7th Heaven",
        "sourceRevision": SEVENTH_HEAVEN_SOURCE_REVISION,
        "checked": True,
        "profile": profile_name,
        "profilePath": str(profile_path),
        "libraryRoot": str(library_root),
        "active": order,
        "overlaps": overlaps,
        "conditionalOverlaps": conditional_overlaps,
        "opaque": opaque,
        "missing": missing,
        "complete": complete,
        "clear": complete and not overlaps,
        "message": (
            f"{len(overlaps)} definite Direct Mode overlap(s) found."
            if overlaps else
            "No definite Direct Mode overlap found, but the active stack is only partially inspectable."
            if not complete else
            "No Direct Mode overlap found in the inspected active folder stack."
        ),
    }


def configured_stack(direct_paths) -> dict:
    value = os.environ.get(WORKSHOP_ENV, "").strip()
    if not value:
        return {
            "provider": "7th Heaven",
            "sourceRevision": SEVENTH_HEAVEN_SOURCE_REVISION,
            "checked": False,
            "overlaps": [], "conditionalOverlaps": [], "opaque": [], "missing": [],
            "complete": False, "clear": False,
            "message": f"Set {WORKSHOP_ENV} to a 7thWorkshop directory to inspect an active 7th Heaven profile read-only.",
        }
    try:
        return scan_7h_stack(Path(value), direct_paths)
    except (OSError, ValueError) as error:
        return {
            "provider": "7th Heaven",
            "sourceRevision": SEVENTH_HEAVEN_SOURCE_REVISION,
            "checked": True,
            "overlaps": [], "conditionalOverlaps": [], "opaque": [], "missing": [],
            "complete": False, "clear": False, "error": str(error),
            "message": f"7th Heaven stack could not be completely inspected: {error}",
        }
