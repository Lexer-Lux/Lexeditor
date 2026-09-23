"""Read-only compatibility checks for public 7th Heaven FF7 mod stacks.

The contract mirrors 7th Heaven source revision ae129f0: profiles keep an ordered
list of active ModIDs and settings, library.xml maps each ModID to its installed
location, folder mods select ModFolder/Conditional roots through mod.xml, and
.iro files are opaque unless an IRO reader is available. This module never edits
7th Heaven state and never guesses inside .iro packages.
"""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET


SEVENTH_HEAVEN_SOURCE_REVISION = "ae129f0bbeeeb236b1c37fb136e5fec25fd292a3"
WORKSHOP_ENV = "LEXEDITOR_FF7_7H_WORKSHOP"
_CONDITION = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(<=|>=|!=|=|<|>)\s*(-?\d+)\s*$")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children_named(node: ET.Element, name: str):
    return [child for child in node.iter() if _local(child.tag) == name]


def _direct_children_named(node: ET.Element, name: str):
    return [child for child in list(node) if _local(child.tag) == name]


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
    try:
        return (0, Decimal(str(text or "").strip()))
    except InvalidOperation:
        return (1, str(text or "").casefold())


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
        settings: dict[str, int] = {}
        for setting in _children_named(item, "ProfileSetting"):
            key, raw = _text(setting, "ID"), _text(setting, "Value")
            if not key:
                continue
            try:
                settings[key.casefold()] = int(raw)
            except ValueError:
                continue
        rows.append({
            "modId": mod_id,
            "name": _text(item, "Name") or mod_id,
            "settings": settings,
        })
    return rows


def _int_value(value, default=0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _config_condition(spec: str, settings: dict[str, int], ffnx_values: dict) -> bool:
    """Mirror 7H ProfileItem.IsConfigActive for integer profile/FFNx values."""
    match = _CONDITION.match(str(spec or ""))
    if not match:
        return False
    key, operator, raw_expected = match.groups()
    expected = int(raw_expected)
    folded = key.casefold()
    if folded.startswith("ffnx_"):
        ffnx_key = key[5:]
        lookup = {str(k).casefold(): v for k, v in (ffnx_values or {}).items()}
        actual = _int_value(lookup.get(ffnx_key.casefold(), 0))
    else:
        if folded not in settings:
            return False
        actual = settings[folded]
    return {
        "=": actual == expected,
        "!=": actual != expected,
        "<": actual < expected,
        ">": actual > expected,
        "<=": actual <= expected,
        ">=": actual >= expected,
    }[operator]


def _active_node(node: ET.Element, settings: dict[str, int], ffnx_values: dict) -> bool | None:
    kind = _local(node.tag)
    if kind == "Option":
        return _config_condition(node.text or "", settings, ffnx_values)
    children = list(node)
    values = [_active_node(child, settings, ffnx_values) for child in children]
    if any(value is None for value in values):
        return None
    bools = [bool(value) for value in values]
    if kind == "And":
        return all(bools)
    if kind == "Or":
        return any(bools)
    if kind == "Not":
        return None if len(bools) != 1 else not bools[0]
    return None


def _active_when(node: ET.Element, settings: dict[str, int], ffnx_values: dict) -> bool | None:
    attribute = next((value for key, value in node.attrib.items()
                      if _local(key).casefold() == "activewhen"), None)
    wrappers = _direct_children_named(node, "ActiveWhen")
    if wrappers:
        children = list(wrappers[0])
        if len(children) != 1:
            return None
        return _active_node(children[0], settings, ffnx_values)
    if attribute is not None:
        return _config_condition(attribute, settings, ffnx_values)
    return True


def _mod_roots(folder: Path, settings: dict[str, int], ffnx_values: dict
               ) -> tuple[list[Path], list[Path], list[Path]]:
    mod_xml = folder / "mod.xml"
    if not mod_xml.is_file():
        return [folder], [], []
    root = _parse(mod_xml)
    ordinary: list[Path] = []
    conditional: list[Path] = []
    unresolved: list[Path] = []
    declared = False
    for node in root.iter():
        kind = _local(node.tag)
        if kind not in {"ModFolder", "Conditional"}:
            continue
        declared = True
        name = (node.attrib.get("Folder") or "").strip()
        if not name:
            continue
        active = _active_when(node, settings, ffnx_values)
        if active is False:
            continue
        target = folder / name
        if active is None:
            unresolved.append(target)
        elif kind == "ModFolder":
            ordinary.append(target)
        else:
            conditional.append(target)
    if not declared:
        ordinary.append(folder)
    return ordinary, conditional, unresolved


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


def _overlap_paths(roots: list[Path], wanted: set[str]) -> list[str]:
    if not roots:
        return []
    found: set[str] = set()
    for root in roots:
        found.update(_direct_files(root))
    return sorted(found & wanted)


def scan_7h_stack(workshop_root: Path, direct_paths, *, ffnx_values: dict | None = None) -> dict:
    """Compare Lexeditor Direct Mode paths with one 7H active profile.

    direct_paths are relative to FFNx's Direct root. Same-path results are
    reported, never assigned a guessed winner. Profile-option ModFolder
    activation is evaluated from the active profile. Conditional per-file
    runtime predicates and IRO package contents remain explicitly incomplete.
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
        row = {"modId": item["modId"], "name": item["name"], "order": index}
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
        ordinary, conditional, unresolved = _mod_roots(
            source, item["settings"], ffnx_values or {})
        for virtual in _overlap_paths(ordinary, wanted):
            overlaps.append({**row, "path": virtual, "location": str(source)})
        for virtual in _overlap_paths(conditional, wanted):
            conditional_overlaps.append({**row, "path": virtual, "location": str(source),
                "reason": "7th Heaven per-file Conditional activation depends on runtime state"})
        for virtual in _overlap_paths(unresolved, wanted):
            conditional_overlaps.append({**row, "path": virtual, "location": str(source),
                "reason": "7th Heaven ActiveWhen expression could not be evaluated safely"})

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


def configured_stack(direct_paths, *, ffnx_values: dict | None = None) -> dict:
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
        return scan_7h_stack(Path(value), direct_paths, ffnx_values=ffnx_values or {})
    except (OSError, ValueError) as error:
        return {
            "provider": "7th Heaven",
            "sourceRevision": SEVENTH_HEAVEN_SOURCE_REVISION,
            "checked": True,
            "overlaps": [], "conditionalOverlaps": [], "opaque": [], "missing": [],
            "complete": False, "clear": False, "error": str(error),
            "message": f"7th Heaven stack could not be completely inspected: {error}",
        }
