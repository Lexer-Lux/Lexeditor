"""Read and safely edit Bannerlord module metadata and editor coverage."""

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
    return str(value).strip().casefold() in {"1", "true", "yes"}


def _parse_tree(path: Path) -> ET.ElementTree:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser)


def _element_children(parent: ET.Element, tag: str) -> list[ET.Element]:
    return [child for child in list(parent) if child.tag == tag]


def read_submodule(path: Path) -> dict:
    """Parse the stable, user-facing portions of Bannerlord SubModule.xml."""
    root = _parse_tree(path).getroot()

    dependency_elements = []
    depended_modules = root.find("DependedModules")
    if depended_modules is not None:
        dependency_elements = _element_children(depended_modules, "DependedModule")
    dependencies = []
    for index, element in enumerate(dependency_elements):
        dependencies.append(
            {
                "index": index,
                "id": element.attrib.get("Id", ""),
                "dependentVersion": element.attrib.get("DependentVersion", ""),
                "optional": _truth(element.attrib.get("Optional", "false")),
                "attributes": dict(element.attrib),
            }
        )

    incompatible_elements = []
    incompatible_root = root.find("IncompatibleModules")
    if incompatible_root is not None:
        incompatible_elements = _element_children(incompatible_root, "IncompatibleModule")
    incompatible_modules = []
    for index, element in enumerate(incompatible_elements):
        incompatible_modules.append(
            {
                "index": index,
                "id": element.attrib.get("Id", ""),
                "attributes": dict(element.attrib),
            }
        )

    submodules = []
    submodule_root = root.find("SubModules")
    if submodule_root is not None:
        for index, element in enumerate(_element_children(submodule_root, "SubModule")):
            tags = []
            tags_root = element.find("Tags")
            if tags_root is not None:
                for tag_index, tag in enumerate(_element_children(tags_root, "Tag")):
                    tags.append(
                        {
                            "index": tag_index,
                            "key": tag.attrib.get("key", ""),
                            "value": tag.attrib.get("value", ""),
                            "attributes": dict(tag.attrib),
                        }
                    )
            submodules.append(
                {
                    "index": index,
                    "name": _value(element, "Name"),
                    "dllName": _value(element, "DLLName"),
                    "classType": _value(element, "SubModuleClassType"),
                    "tags": tags,
                }
            )

    xmls = []
    xml_root = root.find("Xmls")
    if xml_root is not None:
        for index, element in enumerate(_element_children(xml_root, "XmlNode")):
            game_types = []
            included = element.find("IncludedGameTypes")
            if included is not None:
                for type_index, value in enumerate(_element_children(included, "GameType")):
                    game_types.append(
                        {
                            "index": type_index,
                            "value": value.attrib.get("value", ""),
                            "attributes": dict(value.attrib),
                        }
                    )
            xmls.append(
                {
                    "index": index,
                    "id": _value(element, "Id"),
                    "path": _value(element, "Path"),
                    "includedGameTypes": game_types,
                }
            )

    return {
        "path": str(path),
        "name": _value(root, "Name"),
        "id": _value(root, "Id"),
        "version": _value(root, "Version"),
        "defaultModule": _truth(_value(root, "DefaultModule")),
        "singleplayer": _truth(_value(root, "SingleplayerModule")),
        "multiplayer": _truth(_value(root, "MultiplayerModule")),
        "dependencies": dependencies,
        "incompatibleModules": incompatible_modules,
        "submodules": submodules,
        "xmls": xmls,
    }


_EDITABLE_METADATA = {
    "name": "Name",
    "id": "Id",
    "version": "Version",
    "defaultModule": "DefaultModule",
    "singleplayer": "SingleplayerModule",
    "multiplayer": "MultiplayerModule",
}
_BOOLEAN_METADATA = {"defaultModule", "singleplayer", "multiplayer"}


def _set_value(parent: ET.Element, tag: str, value: str) -> bool:
    element = parent.find(tag)
    if element is None:
        element = ET.SubElement(parent, tag)
        element.set("value", value)
        return True
    old = element.attrib.get("value", (element.text or "").strip())
    if old == value:
        return False
    element.set("value", value)
    return True


def _normalize_metadata(edits: dict) -> dict:
    unknown = set(edits) - set(_EDITABLE_METADATA)
    if unknown:
        raise ValueError(f"Unsupported SubModule.xml fields: {', '.join(sorted(unknown))}")
    normalized = {}
    for field, raw in edits.items():
        if field in _BOOLEAN_METADATA:
            normalized[field] = "true" if bool(raw) else "false"
        else:
            value = str(raw).strip()
            if not value:
                raise ValueError(f"{field} cannot be empty")
            normalized[field] = value
    return normalized


def _child_or_create(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    return child


def _remove_tagged_children(parent: ET.Element, tag: str) -> None:
    for child in list(parent):
        if child.tag == tag:
            parent.remove(child)


def _edit_dependencies(root: ET.Element, rows: list[dict]) -> int:
    parent = _child_or_create(root, "DependedModules")
    existing = _element_children(parent, "DependedModule")
    changes = 0
    reused: set[int] = set()
    output: list[ET.Element] = []
    for position, row in enumerate(rows):
        dep_id = str(row.get("id", "")).strip()
        if not dep_id:
            raise ValueError(f"Dependency {position + 1} needs an ID")
        source_index = row.get("index")
        element = None
        if isinstance(source_index, int) and 0 <= source_index < len(existing) and source_index not in reused:
            element = existing[source_index]
            reused.add(source_index)
        if element is None:
            element = ET.Element("DependedModule")
            changes += 1
        before = dict(element.attrib)
        element.set("Id", dep_id)
        version = str(row.get("dependentVersion", "")).strip()
        if version:
            element.set("DependentVersion", version)
        else:
            element.attrib.pop("DependentVersion", None)
        optional = bool(row.get("optional", False))
        if optional:
            element.set("Optional", "true")
        else:
            element.attrib.pop("Optional", None)
        if before != element.attrib:
            changes += 1
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "DependedModule")
    for element in output:
        parent.append(element)
    return changes


def _edit_incompatible_modules(root: ET.Element, rows: list[dict]) -> int:
    parent = root.find("IncompatibleModules")
    if parent is None and not rows:
        return 0
    parent = parent if parent is not None else ET.SubElement(root, "IncompatibleModules")
    existing = _element_children(parent, "IncompatibleModule")
    changes = 0
    reused: set[int] = set()
    output: list[ET.Element] = []
    for position, row in enumerate(rows):
        module_id = str(row.get("id", "")).strip()
        if not module_id:
            raise ValueError(f"Incompatible module {position + 1} needs an ID")
        source_index = row.get("index")
        element = None
        if isinstance(source_index, int) and 0 <= source_index < len(existing) and source_index not in reused:
            element = existing[source_index]
            reused.add(source_index)
        if element is None:
            element = ET.Element("IncompatibleModule")
            changes += 1
        before = dict(element.attrib)
        element.set("Id", module_id)
        if before != element.attrib:
            changes += 1
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "IncompatibleModule")
    for element in output:
        parent.append(element)
    return changes


def _edit_tags(parent: ET.Element, rows: list[dict]) -> int:
    tags_root = parent.find("Tags")
    if tags_root is None and not rows:
        return 0
    tags_root = tags_root if tags_root is not None else ET.SubElement(parent, "Tags")
    existing = _element_children(tags_root, "Tag")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        key = str(row.get("key", "")).strip()
        if not key:
            raise ValueError(f"Submodule tag {position + 1} needs a key")
        value = str(row.get("value", "")).strip()
        source_index = row.get("index")
        element = None
        if isinstance(source_index, int) and 0 <= source_index < len(existing) and source_index not in reused:
            element = existing[source_index]
            reused.add(source_index)
        if element is None:
            element = ET.Element("Tag")
            changes += 1
        before = dict(element.attrib)
        element.set("key", key)
        element.set("value", value)
        if before != element.attrib:
            changes += 1
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(tags_root, "Tag")
    for element in output:
        tags_root.append(element)
    return changes


def _edit_submodules(root: ET.Element, rows: list[dict]) -> int:
    parent = _child_or_create(root, "SubModules")
    existing = _element_children(parent, "SubModule")
    changes = 0
    reused: set[int] = set()
    output: list[ET.Element] = []
    for position, row in enumerate(rows):
        source_index = row.get("index")
        element = None
        if isinstance(source_index, int) and 0 <= source_index < len(existing) and source_index not in reused:
            element = existing[source_index]
            reused.add(source_index)
        if element is None:
            element = ET.Element("SubModule")
            changes += 1
        name = str(row.get("name", "")).strip()
        dll_name = str(row.get("dllName", "")).strip()
        class_type = str(row.get("classType", "")).strip()
        if not name:
            raise ValueError(f"Submodule {position + 1} needs a name")
        if not dll_name:
            raise ValueError(f"Submodule {position + 1} needs a DLL name")
        if not class_type:
            raise ValueError(f"Submodule {position + 1} needs a class type")
        changes += int(_set_value(element, "Name", name))
        changes += int(_set_value(element, "DLLName", dll_name))
        changes += int(_set_value(element, "SubModuleClassType", class_type))
        changes += _edit_tags(element, list(row.get("tags") or []))
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "SubModule")
    for element in output:
        parent.append(element)
    return changes


def _edit_game_types(parent: ET.Element, rows: list[dict]) -> int:
    included = parent.find("IncludedGameTypes")
    if included is None and not rows:
        return 0
    included = included if included is not None else ET.SubElement(parent, "IncludedGameTypes")
    existing = _element_children(included, "GameType")
    changes = 0
    reused: set[int] = set()
    output: list[ET.Element] = []
    for position, row in enumerate(rows):
        value = str(row.get("value", "")).strip()
        if not value:
            raise ValueError(f"Included game type {position + 1} needs a value")
        source_index = row.get("index")
        element = None
        if isinstance(source_index, int) and 0 <= source_index < len(existing) and source_index not in reused:
            element = existing[source_index]
            reused.add(source_index)
        if element is None:
            element = ET.Element("GameType")
            changes += 1
        before = dict(element.attrib)
        element.set("value", value)
        if before != element.attrib:
            changes += 1
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(included, "GameType")
    for element in output:
        included.append(element)
    return changes


def _edit_xmls(root: ET.Element, rows: list[dict]) -> int:
    parent = root.find("Xmls")
    if parent is None and not rows:
        return 0
    parent = parent if parent is not None else ET.SubElement(root, "Xmls")
    existing = _element_children(parent, "XmlNode")
    changes = 0
    reused: set[int] = set()
    output: list[ET.Element] = []
    for position, row in enumerate(rows):
        source_index = row.get("index")
        element = None
        if isinstance(source_index, int) and 0 <= source_index < len(existing) and source_index not in reused:
            element = existing[source_index]
            reused.add(source_index)
        if element is None:
            element = ET.Element("XmlNode")
            changes += 1
        xml_id = str(row.get("id", "")).strip()
        xml_path = str(row.get("path", "")).strip()
        if not xml_id:
            raise ValueError(f"XML registration {position + 1} needs an ID")
        if not xml_path:
            raise ValueError(f"XML registration {position + 1} needs a path")
        changes += int(_set_value(element, "Id", xml_id))
        changes += int(_set_value(element, "Path", xml_path))
        changes += _edit_game_types(element, list(row.get("includedGameTypes") or []))
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "XmlNode")
    for element in output:
        parent.append(element)
    return changes


def save_module(path: Path, payload: dict) -> dict:
    """Save supported SubModule.xml sections in one backed-up write."""
    allowed = {"metadata", "dependencies", "incompatibleModules", "submodules", "xmls"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"Unsupported SubModule.xml sections: {', '.join(sorted(unknown))}")

    tree = _parse_tree(path)
    root = tree.getroot()
    changes = 0

    metadata = _normalize_metadata(dict(payload.get("metadata") or {}))
    for field, value in metadata.items():
        changes += int(_set_value(root, _EDITABLE_METADATA[field], value))

    if "dependencies" in payload:
        changes += _edit_dependencies(root, list(payload.get("dependencies") or []))
    if "incompatibleModules" in payload:
        changes += _edit_incompatible_modules(root, list(payload.get("incompatibleModules") or []))
    if "submodules" in payload:
        changes += _edit_submodules(root, list(payload.get("submodules") or []))
    if "xmls" in payload:
        changes += _edit_xmls(root, list(payload.get("xmls") or []))

    backup = path.with_name(path.name + ".lexeditor.bak")
    if changes:
        shutil.copy2(path, backup)
        ET.indent(tree, space="  ")
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        tree.write(temporary, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
        temporary.replace(path)

    return {
        "saved": changes,
        "backup": str(backup) if changes else "",
        "module": read_submodule(path),
    }


def save_module_metadata(path: Path, edits: dict) -> dict:
    """Compatibility wrapper for the original first-slice API."""
    return save_module(path, {"metadata": edits})


def _relative(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def _source_rows(project: Path, pattern: str, area: str, controls: str, notes: str) -> list[dict]:
    rows = []
    for path in sorted(project.glob(pattern)):
        if not path.is_file():
            continue
        relative = _relative(project, path)
        rows.append(
            {
                "id": "bannerlord-source-" + relative.replace("/", "-").replace("\\", "-"),
                "filename": relative,
                "area": area,
                "controls": controls,
                "coverage": "source",
                "status": "not-integrated",
                "target": "",
                "targets": [],
                "openable": True,
                "sourceOpenable": True,
                "sourceAvailable": True,
                "sourcePath": str(path),
                "notes": notes,
            }
        )
    return rows


def data_map(project: Path) -> dict:
    """Describe real Bannerlord coverage without overstating editor support."""
    rows = []
    submodule = project / "SubModule.xml"
    rows.append(
        {
            "id": "bannerlord-submodule",
            "filename": "SubModule.xml",
            "area": "Module",
            "controls": "Module identity, compatibility, dependencies, submodules, and XML registrations",
            "coverage": "structured" if submodule.is_file() else "unavailable",
            "status": "integrated" if submodule.is_file() else "not-integrated",
            "target": "module" if submodule.is_file() else "",
            "targets": ["module"] if submodule.is_file() else [],
            "openable": submodule.is_file(),
            "sourceAvailable": submodule.is_file(),
            "sourcePath": str(submodule),
            "notes": "Full structured SubModule.xml editor." if submodule.is_file()
            else "SubModule.xml is required for a Bannerlord module project.",
        }
    )

    csprojects = sorted(path for path in project.glob("*.csproj") if path.is_file())
    for index, path in enumerate(csprojects):
        relative = _relative(project, path)
        rows.append(
            {
                "id": f"bannerlord-csproj-{index}",
                "filename": relative,
                "area": "Build",
                "controls": "Target framework, language, assembly/module output, references, packages, and build targets",
                "coverage": "structured",
                "status": "integrated",
                "target": "build",
                "targets": ["build"],
                "openable": True,
                "sourceOpenable": True,
                "sourceAvailable": True,
                "sourcePath": str(path),
                "notes": "Structured MSBuild project inspection with safe editable property values.",
            }
        )

    rows.extend(_source_rows(
        project, "src/**/*.cs", "C#", "Gameplay and module C# source",
        "Detected as C# source. Format-specific C# editors are added only where Lexeditor has a real schema.",
    ))
    rows.extend(_source_rows(
        project, "ModuleData/**/*.xml", "Module data", "Bannerlord ModuleData XML",
        "Detected ModuleData XML; record-specific Bannerlord editors are still pending.",
    ))
    rows.extend(_source_rows(
        project, "GUI/**/*.xml", "UI", "Gauntlet/UI XML",
        "Detected Gauntlet XML; widget-aware editing is still pending.",
    ))
    design = project / "Design.txt"
    if design.is_file():
        rows.extend(_source_rows(
            project, "Design.txt", "Design", "Project design source",
            "Project design/reference source; not gameplay data.",
        ))
    return {"rows": rows}
