"""Read BLSE/BUTR community dependency metadata from Bannerlord SubModule.xml.

The community metadata is additive to TaleWorlds' native DependedModules,
ModulesToLoadAfterThis, and IncompatibleModules sections.  Keep this parser
small and read-only so unsupported attributes remain untouched by Lexeditor's
structured SubModule.xml writer until they are explicitly edited there.
"""
from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


_VALID_ORDERS = {"LoadBeforeThis", "LoadAfterThis"}
_VERSION_TYPES = {"a": 0, "b": 1, "e": 2, "v": 3, "d": 4}
_MAX_COMPONENT = 2**31 - 1
_MIN_COMPONENT = -(2**31)


def _truth(value: str | None) -> bool:
    return str(value or "").strip().casefold() == "true"


def _application_version(value: str, *, as_min: bool) -> tuple[int, int, int, int, int] | None:
    """Mirror BUTR ModuleManager's ApplicationVersion.TryParse ordering values."""
    raw = str(value or "").strip()
    parts = raw.split(".")
    if len(parts) not in {3, 4} or not parts[0]:
        return None
    version_type = _VERSION_TYPES.get(parts[0][0])
    if version_type is None:
        return None

    default = 0 if as_min else _MAX_COMPONENT
    values = [default, default, default, default]
    components = [parts[0][1:], parts[1], parts[2]] + ([parts[3]] if len(parts) == 4 else [])
    wildcard = False
    for index, component in enumerate(components):
        if wildcard:
            break
        try:
            values[index] = int(component)
        except ValueError:
            if component != "*":
                return None
            if index == 0:
                # ModuleManager uses int.MinValue for every component for a
                # major wildcard regardless of min/max parsing mode.
                values = [_MIN_COMPONENT] * 4
            else:
                values[index:] = [default] * (4 - index)
            wildcard = True
    return version_type, *values


def community_version_matches(required: str, installed: str) -> bool | None:
    """Apply BUTR community-version minimum/range semantics.

    A single community ``version`` is a minimum, including wildcard forms such
    as ``v2.1.*``. A ``min-max`` expression is an inclusive range. ``None``
    means either side could not be parsed and Lexeditor should avoid claiming a
    match or mismatch.
    """
    requirement = str(required or "").strip()
    if not requirement:
        return None
    installed_version = _application_version(installed, as_min=True)
    if installed_version is None:
        return None

    if "-" in requirement:
        low_raw, high_raw = requirement.replace(" ", "").split("-", 1)
        low = _application_version(low_raw, as_min=True)
        high = _application_version(high_raw, as_min=False)
        if low is None or high is None:
            return None
        return low <= installed_version <= high

    minimum = _application_version(requirement, as_min=True)
    if minimum is None:
        return None
    return minimum <= installed_version


def read_community_dependencies(path: Path) -> list[dict]:
    """Return BLSE ``DependedModuleMetadata`` rows in document order."""
    root = ET.parse(Path(path)).getroot()
    parent = root.find("DependedModuleMetadatas")
    if parent is None:
        return []

    rows = []
    for index, element in enumerate(child for child in list(parent) if child.tag == "DependedModuleMetadata"):
        module_id = str(element.attrib.get("id") or "").strip()
        if not module_id:
            continue
        order = str(element.attrib.get("order") or "").strip()
        if order not in _VALID_ORDERS:
            order = ""
        rows.append(
            {
                "index": index,
                "id": module_id,
                "order": order,
                "optional": _truth(element.attrib.get("optional")),
                "incompatible": _truth(element.attrib.get("incompatible")),
                "version": str(element.attrib.get("version") or "").strip(),
                "attributes": dict(element.attrib),
            }
        )
    return rows
