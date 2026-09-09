"""Read Bannerlord module metadata and describe current editor coverage."""

from __future__ import annotations

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


def _value(parent: ET.Element, tag: str) -> str:
    element = parent.find(tag)
    if element is None:
        return ""
    return element.attrib.get("value", (element.text or "").strip())


def _truth(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes"}


def _parse_tree(path: Path) -> ET.ElementTree:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser)


def read_submodule(path: Path) -> dict:
    """Parse the stable, user-facing portions of Bannerlord SubModule.xml."""
    root = _parse_tree(path).getroot()

    dependencies = []
    depended_modules = root.find("DependedModules")
    if depended_modules is not None:
        for element in depended_modules.findall("DependedModule"):
            dependencies.append(dict(element.attrib))

    submodules = []
    submodule_root = root.find("SubModules")
    if submodule_root is not None:
        for element in submodule_root.findall("SubModule"):
            tags = []
            tags_root = element.find("Tags")
            if tags_root is not None:
                tags = [dict(tag.attrib) for tag in tags_root.findall("Tag")]
            submodules.append(
                {
                    "name": _value(element, "Name"),
                    "dllName": _value(element, "DLLName"),
                    "classType": _value(element, "SubModuleClassType"),
                    "tags": tags,
                }
            )

    xmls = []
    xml_root = root.find("Xmls")
    if xml_root is not None:
        for element in xml_root.findall("XmlNode"):
            xmls.append(
                {
                    "id": _value(element, "Id"),
                    "path": _value(element, "Path"),
                    "includedGameTypes": [
                        dict(value.attrib)
                        for value in element.findall("./IncludedGameTypes/GameType")
                    ],
                }
            )

    return {
        "path": str(path),
        "name": _value(root, "Name"),
        "id": _value(root, "Id"),
        "version": _value(root, "Version"),
        "singleplayer": _truth(_value(root, "SingleplayerModule")),
        "multiplayer": _truth(_value(root, "MultiplayerModule")),
        "dependencies": dependencies,
        "submodules": submodules,
        "xmls": xmls,
    }


_EDITABLE_METADATA = {
    "name": "Name",
    "id": "Id",
    "version": "Version",
    "singleplayer": "SingleplayerModule",
    "multiplayer": "MultiplayerModule",
}


def save_module_metadata(path: Path, edits: dict) -> dict:
    """Update only the module's top-level identity/compatibility metadata."""
    unknown = set(edits) - set(_EDITABLE_METADATA)
    if unknown:
        raise ValueError(f"Unsupported SubModule.xml fields: {', '.join(sorted(unknown))}")

    tree = _parse_tree(path)
    root = tree.getroot()
    saved = 0
    for field, tag in _EDITABLE_METADATA.items():
        if field not in edits:
            continue
        element = root.find(tag)
        if element is None:
            raise ValueError(f"SubModule.xml does not contain <{tag}>")
        if field in {"singleplayer", "multiplayer"}:
            value = "true" if bool(edits[field]) else "false"
        else:
            value = str(edits[field]).strip()
            if not value:
                raise ValueError(f"{field} cannot be empty")
        if element.attrib.get("value", "") != value:
            element.set("value", value)
            saved += 1

    backup = path.with_name(path.name + ".lexeditor.bak")
    if saved:
        shutil.copy2(path, backup)
        tree.write(path, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
    return {
        "saved": saved,
        "backup": str(backup) if saved else "",
        "module": read_submodule(path),
    }


def _has(project: Path, pattern: str) -> bool:
    if any(character in pattern for character in "*?[]"):
        return any(project.glob(pattern))
    return (project / pattern).exists()


def data_map(project: Path) -> dict:
    """Describe real Bannerlord coverage without overstating editor support."""
    specs = (
        (
            "SubModule.xml",
            "Module",
            "structured",
            "integrated",
            "module",
            "Module identity, version, dependencies, and submodule entry points.",
        ),
        (
            "*.csproj",
            "Build",
            "source",
            "not-integrated",
            "",
            "C# project/build metadata is detected but not yet edited.",
        ),
        (
            "src/**/*.cs",
            "C#",
            "source",
            "not-integrated",
            "",
            "C# gameplay code is source-only in this first slice.",
        ),
        (
            "ModuleData/**/*.xml",
            "Module data",
            "source",
            "not-integrated",
            "",
            "Bannerlord ModuleData XML is detected; format-specific editors are pending.",
        ),
        (
            "GUI/**/*.xml",
            "UI",
            "source",
            "not-integrated",
            "",
            "Gauntlet/UI XML is detected; format-specific editors are pending.",
        ),
    )
    rows = []
    for index, (filename, area, coverage, status, target, notes) in enumerate(specs):
        available = _has(project, filename)
        rows.append(
            {
                "id": f"bannerlord-{index}",
                "filename": filename,
                "area": area,
                "controls": {
                    "SubModule.xml": "Module identity, version, dependencies, and entry points",
                    "*.csproj": "Build project metadata",
                    "src/**/*.cs": "Gameplay and module C# source",
                    "ModuleData/**/*.xml": "Module data XML",
                    "GUI/**/*.xml": "Gauntlet/UI XML",
                }[filename],
                "coverage": coverage,
                "status": status,
                "target": target,
                "targets": [target] if target else [],
                "openable": bool(target and available),
                "sourceAvailable": available,
                "notes": notes,
            }
        )
    return {"rows": rows}
