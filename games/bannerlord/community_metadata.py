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


def _truth(value: str | None) -> bool:
    return str(value or "").strip().casefold() == "true"


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
