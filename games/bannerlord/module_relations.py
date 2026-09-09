"""Bannerlord SubModule.xml load-order relations not covered by DependedModules."""
from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


def _ids(parent: ET.Element | None, tags: set[str]) -> list[str]:
    if parent is None:
        return []
    result = []
    seen = set()
    for element in list(parent):
        if element.tag not in tags:
            continue
        module_id = str(element.attrib.get("Id") or "").strip()
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)
        result.append(module_id)
    return result


def read_module_relations(path: Path) -> dict[str, list[str]]:
    """Read engine-honoured inverse-order and incompatibility relations.

    Current Bannerlord uses ``<Module Id=...>`` in both collections. Older
    community examples used ``<IncompatibleModule Id=...>``; accept that shape
    for compatibility without changing the file.
    """
    root = ET.parse(path).getroot()
    return {
        "loadAfterThis": _ids(root.find("ModulesToLoadAfterThis"), {"Module"}),
        "incompatible": _ids(
            root.find("IncompatibleModules"), {"Module", "IncompatibleModule"}
        ),
    }
