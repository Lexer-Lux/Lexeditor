"""Read and safely edit Bannerlord module metadata and editor coverage."""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from . import paths
from .community_metadata import read_community_dependencies
from .dependency_relations import dependency_declaration_conflicts


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


def _included_game_types(element: ET.Element) -> ET.Element | None:
    included = element.find("IncludedGameTypes")
    if included is None:
        # Older community examples used IncludeGameTypes. Preserve it when a
        # project already has that spelling, but create the current spelling.
        included = element.find("IncludeGameTypes")
    return included


def _xml_registration_identity(element: ET.Element) -> tuple[str, str]:
    """Read both modern XmlName attributes and the older Id/Path child shape."""
    xml_name = element.find("XmlName")
    if xml_name is not None:
        return xml_name.attrib.get("id", ""), xml_name.attrib.get("path", "")
    return _value(element, "Id"), _value(element, "Path")


def read_submodule(path: Path) -> dict:
    root = _parse_tree(path).getroot()

    dependencies = []
    depended_modules = root.find("DependedModules")
    if depended_modules is not None:
        for index, element in enumerate(_element_children(depended_modules, "DependedModule")):
            dependencies.append(
                {
                    "index": index,
                    "id": element.attrib.get("Id", ""),
                    "dependentVersion": element.attrib.get("DependentVersion", ""),
                    "optional": _truth(element.attrib.get("Optional", "false")),
                    "attributes": dict(element.attrib),
                }
            )

    modules_to_load_after_this = []
    load_after_root = root.find("ModulesToLoadAfterThis")
    if load_after_root is not None:
        for index, element in enumerate(_element_children(load_after_root, "Module")):
            modules_to_load_after_this.append(
                {"index": index, "id": element.attrib.get("Id", ""), "attributes": dict(element.attrib)}
            )

    incompatible_modules = []
    incompatible_root = root.find("IncompatibleModules")
    if incompatible_root is not None:
        elements = [
            child for child in list(incompatible_root)
            if child.tag in {"Module", "IncompatibleModule"}
        ]
        for index, element in enumerate(elements):
            incompatible_modules.append(
                {
                    "index": index,
                    "id": element.attrib.get("Id", ""),
                    "elementTag": element.tag,
                    "attributes": dict(element.attrib),
                }
            )

    submodules = []
    submodule_root = root.find("SubModules")
    if submodule_root is not None:
        for index, element in enumerate(_element_children(submodule_root, "SubModule")):
            assemblies = []
            assemblies_root = element.find("Assemblies")
            if assemblies_root is not None:
                for assembly_index, assembly in enumerate(_element_children(assemblies_root, "Assembly")):
                    assemblies.append(
                        {
                            "index": assembly_index,
                            "value": assembly.attrib.get("value", ""),
                            "attributes": dict(assembly.attrib),
                        }
                    )
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
                    "assemblies": assemblies,
                    "tags": tags,
                }
            )

    xmls = []
    xml_root = root.find("Xmls")
    if xml_root is not None:
        for index, element in enumerate(_element_children(xml_root, "XmlNode")):
            game_types = []
            included = _included_game_types(element)
            if included is not None:
                for type_index, value in enumerate(_element_children(included, "GameType")):
                    game_types.append(
                        {
                            "index": type_index,
                            "value": value.attrib.get("value", ""),
                            "attributes": dict(value.attrib),
                        }
                    )
            xml_id, xml_path = _xml_registration_identity(element)
            xmls.append(
                {
                    "index": index,
                    "id": xml_id,
                    "path": xml_path,
                    "includedGameTypes": game_types,
                }
            )

    extended_dependencies = read_community_dependencies(path)
    community_dependencies = [
        row for row in extended_dependencies
        if row.get("origin") == "DependedModuleMetadatas"
    ]
    legacy_dependencies = [
        row for row in extended_dependencies
        if row.get("origin") != "DependedModuleMetadatas"
    ]

    return {
        "path": str(path),
        "name": _value(root, "Name"),
        "id": _value(root, "Id"),
        "version": _value(root, "Version"),
        "moduleCategory": _value(root, "ModuleCategory"),
        "moduleType": _value(root, "ModuleType"),
        "url": _value(root, "Url"),
        "updateInfo": _value(root, "UpdateInfo"),
        "defaultModule": _truth(_value(root, "DefaultModule")),
        "singleplayer": _truth(_value(root, "SingleplayerModule")),
        "multiplayer": _truth(_value(root, "MultiplayerModule")),
        "dependencies": dependencies,
        "communityDependencies": community_dependencies,
        "legacyDependencies": legacy_dependencies,
        "modulesToLoadAfterThis": modules_to_load_after_this,
        "incompatibleModules": incompatible_modules,
        "submodules": submodules,
        "xmls": xmls,
    }


def is_singleplayer_module(module: dict) -> bool:
    """Mirror ModuleManager's additive modern/legacy single-player flags."""
    category = str(module.get("moduleCategory") or "").strip().casefold()
    return bool(module.get("singleplayer")) or category in {
        "singleplayer",
        "singleplayeroptional",
    }


_EDITABLE_METADATA = {
    "name": "Name",
    "id": "Id",
    "version": "Version",
    "moduleCategory": "ModuleCategory",
    "moduleType": "ModuleType",
    "url": "Url",
    "updateInfo": "UpdateInfo",
    "defaultModule": "DefaultModule",
    "singleplayer": "SingleplayerModule",
    "multiplayer": "MultiplayerModule",
}
_BOOLEAN_METADATA = {"defaultModule", "singleplayer", "multiplayer"}
_ENUM_METADATA = {
    "moduleCategory": {"Singleplayer", "SingleplayerOptional", "Multiplayer", "MultiplayerOptional", "Server", "ServerOptional"},
    "moduleType": {"Community", "Official", "OfficialOptional"},
}
_OPTIONAL_TEXT_METADATA = {"url", "updateInfo"}
_OPTIONAL_METADATA = set(_ENUM_METADATA) | _OPTIONAL_TEXT_METADATA
_UPDATE_INFO_PATTERN = re.compile(
    r"(?:NexusMods:[0-9]+|GitHub:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+|"
    r"NexusMods:[0-9]+;GitHub:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+|"
    r"GitHub:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+;NexusMods:[0-9]+)"
)
_MODULE_STRUCTURAL_TAGS = {
    "DependedModules",
    "ModulesToLoadAfterThis",
    "IncompatibleModules",
    "DependedModuleMetadatas",
    "LoadAfterModules",
    "OptionalDependModules",
    "SubModules",
    "Xmls",
}


def _set_value(parent: ET.Element, tag: str, value: str, *, submodule_order: bool = False) -> bool:
    element = parent.find(tag)
    if element is None:
        element = _submodule_child_or_create(parent, tag) if submodule_order else ET.SubElement(parent, tag)
        element.set("value", value)
        return True
    old = element.attrib.get("value", (element.text or "").strip())
    if old == value:
        return False
    element.set("value", value)
    return True


def _set_optional_value(parent: ET.Element, tag: str, value: str) -> bool:
    if value:
        return _set_value(parent, tag, value)
    element = parent.find(tag)
    if element is None:
        return False
    parent.remove(element)
    return True


def _module_child_or_create(parent: ET.Element, tag: str) -> ET.Element:
    element = parent.find(tag)
    if element is not None:
        return element
    element = ET.Element(tag)
    children = list(parent)
    structural_index = next(
        (index for index, child in enumerate(children) if child.tag in _MODULE_STRUCTURAL_TAGS),
        len(children),
    )
    parent.insert(structural_index, element)
    return element


def _set_module_value(parent: ET.Element, tag: str, value: str) -> bool:
    element = parent.find(tag)
    if element is None:
        element = _module_child_or_create(parent, tag)
        element.set("value", value)
        return True
    old = element.attrib.get("value", (element.text or "").strip())
    if old == value:
        return False
    element.set("value", value)
    return True


def _set_optional_module_value(parent: ET.Element, tag: str, value: str) -> bool:
    if value:
        return _set_module_value(parent, tag, value)
    element = parent.find(tag)
    if element is None:
        return False
    parent.remove(element)
    return True


def _normalize_metadata(edits: dict) -> dict:
    unknown = set(edits) - set(_EDITABLE_METADATA)
    if unknown:
        raise ValueError(f"Unsupported SubModule.xml fields: {', '.join(sorted(unknown))}")
    normalized = {}
    for field, raw in edits.items():
        if field in _BOOLEAN_METADATA:
            normalized[field] = "true" if bool(raw) else "false"
        elif field in _ENUM_METADATA:
            value = str(raw).strip()
            if value and value not in _ENUM_METADATA[field]:
                raise ValueError(f"{field} must be one of: {', '.join(sorted(_ENUM_METADATA[field]))}")
            normalized[field] = value
        elif field in _OPTIONAL_TEXT_METADATA:
            value = str(raw).strip()
            if field == "updateInfo" and value and _UPDATE_INFO_PATTERN.fullmatch(value) is None:
                raise ValueError(
                    "updateInfo must be NexusMods:<id>, GitHub:<user>/<repo>, or both separated by a semicolon"
                )
            normalized[field] = value
        else:
            value = str(raw).strip()
            if not value:
                raise ValueError(f"{field} cannot be empty")
            normalized[field] = value
    return normalized


_MODULE_SECTION_ORDER = (
    "DependedModules",
    "ModulesToLoadAfterThis",
    "IncompatibleModules",
    "DependedModuleMetadatas",
    "SubModules",
    "Xmls",
)
_SUBMODULE_CHILD_ORDER = ("Name", "DLLName", "SubModuleClassType", "Assemblies", "Tags")


def _insert_ordered_child(parent: ET.Element, element: ET.Element, order: tuple[str, ...]) -> ET.Element:
    """Insert a newly-created known child before the next known schema sibling.

    Existing elements are never moved. Unknown/comment nodes keep their relative
    positions; this only prevents Lexeditor-created nodes from being appended
    after later structural sections.
    """
    try:
        target_rank = order.index(element.tag)
    except ValueError:
        parent.append(element)
        return element
    for index, child in enumerate(list(parent)):
        try:
            child_rank = order.index(child.tag)
        except ValueError:
            continue
        if child_rank > target_rank:
            parent.insert(index, element)
            return element
    parent.append(element)
    return element


def _child_or_create(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag)
    if child is None:
        child = _insert_ordered_child(parent, ET.Element(tag), _MODULE_SECTION_ORDER)
    return child


def _submodule_child_or_create(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag)
    if child is None:
        child = _insert_ordered_child(parent, ET.Element(tag), _SUBMODULE_CHILD_ORDER)
    return child


def _remove_tagged_children(parent: ET.Element, tag: str) -> None:
    for child in list(parent):
        if child.tag == tag:
            parent.remove(child)


def _reuse(existing: list[ET.Element], source_index, reused: set[int], tag: str) -> tuple[ET.Element, bool]:
    if isinstance(source_index, int) and 0 <= source_index < len(existing) and source_index not in reused:
        reused.add(source_index)
        return existing[source_index], False
    return ET.Element(tag), True


def _edit_dependencies(root: ET.Element, rows: list[dict]) -> int:
    parent = _child_or_create(root, "DependedModules")
    existing = _element_children(parent, "DependedModule")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        dep_id = str(row.get("id", "")).strip()
        if not dep_id:
            raise ValueError(f"Dependency {position + 1} needs an ID")
        element, created = _reuse(existing, row.get("index"), reused, "DependedModule")
        changes += int(created)
        before = dict(element.attrib)
        element.set("Id", dep_id)
        version = str(row.get("dependentVersion", "")).strip()
        if version:
            element.set("DependentVersion", version)
        else:
            element.attrib.pop("DependentVersion", None)
        if bool(row.get("optional", False)):
            element.set("Optional", "true")
        else:
            element.attrib.pop("Optional", None)
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "DependedModule")
    for element in output:
        parent.append(element)
    return changes


def _edit_community_dependencies(root: ET.Element, rows: list[dict]) -> int:
    parent = root.find("DependedModuleMetadatas")
    if parent is None and not rows:
        return 0
    parent = parent if parent is not None else _insert_ordered_child(root, ET.Element("DependedModuleMetadatas"), _MODULE_SECTION_ORDER)
    existing = _element_children(parent, "DependedModuleMetadata")
    changes = 0
    reused: set[int] = set()
    output = []
    valid_orders = {"", "LoadBeforeThis", "LoadAfterThis"}
    for position, row in enumerate(rows):
        module_id = str(row.get("id", "")).strip()
        if not module_id:
            raise ValueError(f"BLSE dependency metadata {position + 1} needs an ID")
        order = str(row.get("order", "")).strip()
        if order not in valid_orders:
            raise ValueError("BLSE dependency order must be LoadBeforeThis, LoadAfterThis, or empty")
        element, created = _reuse(existing, row.get("index"), reused, "DependedModuleMetadata")
        changes += int(created)
        before = dict(element.attrib)
        element.set("id", module_id)
        if order:
            element.set("order", order)
        else:
            element.attrib.pop("order", None)
        version = str(row.get("version", "")).strip()
        if version:
            element.set("version", version)
        else:
            element.attrib.pop("version", None)
        if bool(row.get("optional", False)):
            element.set("optional", "true")
        else:
            element.attrib.pop("optional", None)
        if bool(row.get("incompatible", False)):
            element.set("incompatible", "true")
        else:
            element.attrib.pop("incompatible", None)
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "DependedModuleMetadata")
    for element in output:
        parent.append(element)
    return changes


_LEGACY_DEPENDENCY_ORIGINS = {
    "LoadAfterModules",
    "DependedModules/OptionalDependModule",
    "OptionalDependModules/OptionalDependModule",
    "OptionalDependModules/DependModule",
}


def _legacy_dependency_elements(root: ET.Element) -> dict[tuple[str, int], tuple[ET.Element, ET.Element]]:
    """Map normalized legacy origins/indexes back to their original XML elements."""
    result: dict[tuple[str, int], tuple[ET.Element, ET.Element]] = {}
    load_after = root.find("LoadAfterModules")
    if load_after is not None:
        for index, element in enumerate(_element_children(load_after, "LoadAfterModule")):
            if not str(element.attrib.get("Id") or "").strip():
                continue
            result[("LoadAfterModules", index)] = (load_after, element)

    optional_index = 0
    depended_modules = root.find("DependedModules")
    if depended_modules is not None:
        for element in _element_children(depended_modules, "OptionalDependModule"):
            if str(element.attrib.get("Id") or "").strip():
                result[("DependedModules/OptionalDependModule", optional_index)] = (depended_modules, element)
            optional_index += 1

    optional_root = root.find("OptionalDependModules")
    if optional_root is not None:
        for element in list(optional_root):
            if element.tag not in {"OptionalDependModule", "DependModule"}:
                continue
            origin = f"OptionalDependModules/{element.tag}"
            if str(element.attrib.get("Id") or "").strip():
                result[(origin, optional_index)] = (optional_root, element)
            optional_index += 1
    return result


def _edit_legacy_dependencies(root: ET.Element, rows: list[dict]) -> int:
    """Edit/remove existing legacy launcher relations without inventing a legacy shape."""
    existing = _legacy_dependency_elements(root)
    requested: dict[tuple[str, int], str] = {}
    for position, row in enumerate(rows):
        module_id = str(row.get("id") or "").strip()
        if not module_id:
            raise ValueError(f"Legacy dependency {position + 1} needs an ID")
        origin = str(row.get("origin") or "")
        index = row.get("index")
        if origin not in _LEGACY_DEPENDENCY_ORIGINS or not isinstance(index, int):
            raise ValueError(
                "Legacy dependency edits must reference an existing compatibility row; "
                "create new legacy rows in source XML instead"
            )
        key = (origin, index)
        if key not in existing:
            raise ValueError("Legacy dependency changed or no longer exists; reload before saving")
        _parent, existing_element = existing[key]
        current_id = str(existing_element.attrib.get("Id") or "").strip()
        original_id = str((row.get("attributes") or {}).get("Id") or "").strip()
        if original_id and current_id != original_id:
            raise ValueError("Legacy dependency changed on disk; reload before saving")
        if key in requested:
            raise ValueError("Duplicate legacy dependency edit")
        requested[key] = module_id

    changes = 0
    for key, (parent, element) in existing.items():
        if key not in requested:
            parent.remove(element)
            changes += 1
            continue
        before = dict(element.attrib)
        element.set("Id", requested[key])
        changes += int(before != element.attrib)
    return changes


def _edit_module_id_rows(
    root: ET.Element,
    parent_tag: str,
    rows: list[dict],
    *,
    label: str,
    accepted_tags: set[str],
) -> int:
    parent = root.find(parent_tag)
    if parent is None and not rows:
        return 0
    parent = parent if parent is not None else _insert_ordered_child(root, ET.Element(parent_tag), _MODULE_SECTION_ORDER)
    existing = [child for child in list(parent) if child.tag in accepted_tags]
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        module_id = str(row.get("id", "")).strip()
        if not module_id:
            raise ValueError(f"{label} {position + 1} needs an ID")
        new_tag = str(row.get("elementTag") or "Module")
        if new_tag not in accepted_tags:
            new_tag = "Module"
        element, created = _reuse(existing, row.get("index"), reused, new_tag)
        changes += int(created)
        before = dict(element.attrib)
        element.set("Id", module_id)
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    for child in list(parent):
        if child.tag in accepted_tags:
            parent.remove(child)
    for element in output:
        parent.append(element)
    return changes


def _edit_modules_to_load_after_this(root: ET.Element, rows: list[dict]) -> int:
    return _edit_module_id_rows(
        root,
        "ModulesToLoadAfterThis",
        rows,
        label="Load-after module",
        accepted_tags={"Module"},
    )


def _edit_incompatible_modules(root: ET.Element, rows: list[dict]) -> int:
    return _edit_module_id_rows(
        root,
        "IncompatibleModules",
        rows,
        label="Incompatible module",
        accepted_tags={"Module", "IncompatibleModule"},
    )

def _edit_tags(parent: ET.Element, rows: list[dict], *, ensure: bool = False) -> int:
    tags_root = parent.find("Tags")
    if tags_root is None and not rows and not ensure:
        return 0
    tags_root = tags_root if tags_root is not None else _submodule_child_or_create(parent, "Tags")
    existing = _element_children(tags_root, "Tag")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        key = str(row.get("key", "")).strip()
        if not key:
            raise ValueError(f"Submodule tag {position + 1} needs a key")
        element, created = _reuse(existing, row.get("index"), reused, "Tag")
        changes += int(created)
        before = dict(element.attrib)
        element.set("key", key)
        element.set("value", str(row.get("value", "")).strip())
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(tags_root, "Tag")
    for element in output:
        tags_root.append(element)
    return changes


def _edit_assemblies(parent: ET.Element, rows: list[dict], *, ensure: bool = False) -> int:
    assemblies_root = parent.find("Assemblies")
    if assemblies_root is None and not rows and not ensure:
        return 0
    assemblies_root = assemblies_root if assemblies_root is not None else _submodule_child_or_create(parent, "Assemblies")
    existing = _element_children(assemblies_root, "Assembly")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        value = str(row.get("value", "")).strip()
        if not value:
            raise ValueError(f"Submodule assembly {position + 1} needs a value")
        element, created = _reuse(existing, row.get("index"), reused, "Assembly")
        changes += int(created)
        before = dict(element.attrib)
        element.set("value", value)
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(assemblies_root, "Assembly")
    for element in output:
        assemblies_root.append(element)
    return changes


def _edit_submodules(root: ET.Element, rows: list[dict]) -> int:
    parent = _child_or_create(root, "SubModules")
    existing = _element_children(parent, "SubModule")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        element, created = _reuse(existing, row.get("index"), reused, "SubModule")
        changes += int(created)
        name = str(row.get("name", "")).strip()
        dll_name = str(row.get("dllName", "")).strip()
        class_type = str(row.get("classType", "")).strip()
        if not name:
            raise ValueError(f"Submodule {position + 1} needs a name")
        if not dll_name:
            raise ValueError(f"Submodule {position + 1} needs a DLL name")
        if not class_type:
            raise ValueError(f"Submodule {position + 1} needs a class type")
        changes += int(_set_value(element, "Name", name, submodule_order=True))
        changes += int(_set_value(element, "DLLName", dll_name, submodule_order=True))
        changes += int(_set_value(element, "SubModuleClassType", class_type, submodule_order=True))
        changes += _edit_assemblies(element, list(row.get("assemblies") or []), ensure=created)
        changes += _edit_tags(element, list(row.get("tags") or []), ensure=created)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "SubModule")
    for element in output:
        parent.append(element)
    return changes

def _edit_game_types(parent: ET.Element, rows: list[dict]) -> int:
    included = _included_game_types(parent)
    if included is None and not rows:
        return 0
    included = included if included is not None else ET.SubElement(parent, "IncludedGameTypes")
    existing = _element_children(included, "GameType")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        value = str(row.get("value", "")).strip()
        if not value:
            raise ValueError(f"Included game type {position + 1} needs a value")
        element, created = _reuse(existing, row.get("index"), reused, "GameType")
        changes += int(created)
        before = dict(element.attrib)
        element.set("value", value)
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(included, "GameType")
    for element in output:
        included.append(element)
    return changes


def _set_xml_registration_identity(element: ET.Element, xml_id: str, xml_path: str) -> int:
    """Preserve an existing legacy shape; new/modern rows use XmlName."""
    xml_name = element.find("XmlName")
    legacy_id = element.find("Id")
    legacy_path = element.find("Path")
    if xml_name is not None or (legacy_id is None and legacy_path is None):
        if xml_name is None:
            xml_name = ET.Element("XmlName")
            element.insert(0, xml_name)
            created = 1
        else:
            created = 0
        before = dict(xml_name.attrib)
        xml_name.set("id", xml_id)
        xml_name.set("path", xml_path)
        return created + int(before != xml_name.attrib)
    def set_legacy_value(tag: str, value: str) -> int:
        child = element.find(tag)
        if child is None:
            child = ET.Element(tag)
            included = element.find("IncludedGameTypes")
            if included is None:
                element.append(child)
            else:
                element.insert(list(element).index(included), child)
            child.set("value", value)
            return 1
        before = child.attrib.get("value", (child.text or "").strip())
        if before == value:
            return 0
        child.set("value", value)
        return 1

    return set_legacy_value("Id", xml_id) + set_legacy_value("Path", xml_path)


def _edit_xmls(root: ET.Element, rows: list[dict]) -> int:
    parent = root.find("Xmls")
    if parent is None and not rows:
        return 0
    parent = parent if parent is not None else _insert_ordered_child(root, ET.Element("Xmls"), _MODULE_SECTION_ORDER)
    existing = _element_children(parent, "XmlNode")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        element, created = _reuse(existing, row.get("index"), reused, "XmlNode")
        changes += int(created)
        xml_id = str(row.get("id", "")).strip()
        xml_path = str(row.get("path", "")).strip()
        if not xml_id:
            raise ValueError(f"XML registration {position + 1} needs an ID")
        if not xml_path:
            raise ValueError(f"XML registration {position + 1} needs a path")
        game_types = list(row.get("includedGameTypes") or [])
        if created and not game_types:
            raise ValueError(f"New XML registration {position + 1} needs at least one included game type")
        changes += _set_xml_registration_identity(element, xml_id, xml_path)
        changes += _edit_game_types(element, game_types)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(parent, "XmlNode")
    for element in output:
        parent.append(element)
    return changes


def _validate_relation_payload(path: Path, payload: dict) -> None:
    relation_keys = {
        "dependencies",
        "communityDependencies",
        "legacyDependencies",
        "modulesToLoadAfterThis",
        "incompatibleModules",
    }
    if not relation_keys.intersection(payload):
        return

    current = read_submodule(path)
    current_extended = read_community_dependencies(path)
    proposed = {
        "dependencies": list(
            payload.get("dependencies")
            if "dependencies" in payload
            else current.get("dependencies", [])
        ),
        "modulesToLoadAfterThis": list(
            payload.get("modulesToLoadAfterThis")
            if "modulesToLoadAfterThis" in payload
            else current.get("modulesToLoadAfterThis", [])
        ),
        "incompatibleModules": list(
            payload.get("incompatibleModules")
            if "incompatibleModules" in payload
            else current.get("incompatibleModules", [])
        ),
    }
    current_community = [
        row for row in current_extended
        if row.get("origin") == "DependedModuleMetadatas"
    ]
    current_legacy = [
        row for row in current_extended
        if row.get("origin") != "DependedModuleMetadatas"
    ]
    if "communityDependencies" in payload:
        structured = [dict(row) for row in list(payload.get("communityDependencies") or [])]
        for row in structured:
            row.setdefault("origin", "DependedModuleMetadatas")
    else:
        structured = current_community
    legacy = (
        [dict(row) for row in list(payload.get("legacyDependencies") or [])]
        if "legacyDependencies" in payload
        else current_legacy
    )
    extended = structured + legacy

    issues = dependency_declaration_conflicts(proposed, extended)
    if issues:
        raise ValueError(
            "Invalid Bannerlord dependency declarations: " + "; ".join(issues)
        )


def save_module(path: Path, payload: dict) -> dict:
    path = Path(path)
    path = paths.contained_project_path(path.parent, path.name, require_file=True)
    allowed = {"metadata", "dependencies", "communityDependencies", "legacyDependencies", "modulesToLoadAfterThis", "incompatibleModules", "submodules", "xmls"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"Unsupported SubModule.xml sections: {', '.join(sorted(unknown))}")
    _validate_relation_payload(path, payload)
    tree = _parse_tree(path)
    root = tree.getroot()
    changes = 0
    metadata = _normalize_metadata(dict(payload.get("metadata") or {}))
    for field, value in metadata.items():
        setter = _set_optional_module_value if field in _OPTIONAL_METADATA else _set_module_value
        changes += int(setter(root, _EDITABLE_METADATA[field], value))
    if "dependencies" in payload:
        changes += _edit_dependencies(root, list(payload.get("dependencies") or []))
    if "communityDependencies" in payload:
        changes += _edit_community_dependencies(root, list(payload.get("communityDependencies") or []))
    if "legacyDependencies" in payload:
        changes += _edit_legacy_dependencies(root, list(payload.get("legacyDependencies") or []))
    if "modulesToLoadAfterThis" in payload:
        changes += _edit_modules_to_load_after_this(root, list(payload.get("modulesToLoadAfterThis") or []))
    if "incompatibleModules" in payload:
        changes += _edit_incompatible_modules(root, list(payload.get("incompatibleModules") or []))
    if "submodules" in payload:
        changes += _edit_submodules(root, list(payload.get("submodules") or []))
    if "xmls" in payload:
        changes += _edit_xmls(root, list(payload.get("xmls") or []))

    backup = path.with_name(path.name + ".lexeditor.bak")
    if changes:
        paths.clear_write_helper(backup)
        shutil.copy2(path, backup)
        ET.indent(tree, space="  ")
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        paths.clear_write_helper(temporary)
        tree.write(temporary, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
        temporary.replace(path)
    return {"saved": changes, "backup": str(backup) if changes else "", "module": read_submodule(path)}


def save_module_metadata(path: Path, edits: dict) -> dict:
    return save_module(path, {"metadata": edits})


def _relative(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def _source_rows(
    project: Path,
    pattern: str,
    area: str,
    controls: str,
    notes: str,
    exclude: set[str] | None = None,
) -> list[dict]:
    rows = []
    excluded = exclude or set()
    for path in sorted(project.glob(pattern)):
        if not paths.is_contained_file(project, path):
            continue
        relative = _relative(project, path)
        if relative in excluded:
            continue
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
    rows = []
    submodule = project / "SubModule.xml"
    submodule_available = paths.is_contained_file(project, submodule)
    rows.append(
        {
            "id": "bannerlord-submodule",
            "filename": "SubModule.xml",
            "area": "Module",
            "controls": "Module identity/category, native, BLSE, and existing legacy launcher dependency/load-order relations, incompatibilities, submodule DLL/class/assemblies/tags, and XML registrations",
            "coverage": "structured" if submodule_available else "unavailable",
            "status": "integrated" if submodule_available else "not-integrated",
            "target": "module" if submodule_available else "",
            "targets": ["module"] if submodule_available else [],
            "openable": submodule_available,
            "sourceAvailable": submodule_available,
            "sourcePath": str(submodule),
            "notes": (
                "Structured editor for identity/category, dependency/load-order relations (including existing legacy launcher tags), incompatibilities, "
                "submodule DLL/class/assemblies/tags, and XML registrations; unsupported or unknown nodes are "
                "preserved and remain source-editable."
                if submodule_available
                else "SubModule.xml is required for a Bannerlord module project."
            ),
        }
    )

    for index, path in enumerate(sorted(path for path in project.glob("*.csproj") if paths.is_contained_file(project, path))):
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

    structured_csharp = {
        "src/CustomSkillDefinitions.cs": (
            "Skills",
            "Custom humor attributes and custom skills",
            "skills",
            "Structured editor for the LexerSkillTweaks AttributeDefinition and SkillDefinition lists.",
        ),
        "src/CustomSkillEffectRanges.cs": (
            "Effects",
            "Custom quantitative skill-effect default ranges",
            "effects",
            "Structured editor for CustomSkillEffectRanges Effect(...) low/high defaults.",
        ),
    }
    for relative, (area, controls, target, notes) in structured_csharp.items():
        source = project / relative
        if not paths.is_contained_file(project, source):
            continue
        rows.append(
            {
                "id": "bannerlord-" + target,
                "filename": relative,
                "area": area,
                "controls": controls,
                "coverage": "structured",
                "status": "integrated",
                "target": target,
                "targets": [target],
                "openable": True,
                "sourceOpenable": True,
                "sourceAvailable": True,
                "sourcePath": str(source),
                "notes": notes,
            }
        )

    rows.extend(
        _source_rows(
            project,
            "src/**/*.cs",
            "C#",
            "Gameplay and module C# source",
            "Detected as C# source. Format-specific C# editors are added only where Lexeditor has a real schema.",
            exclude=set(structured_csharp),
        )
    )
    rows.extend(
        _source_rows(
            project,
            "ModuleData/**/*.xml",
            "Module data",
            "Bannerlord ModuleData XML",
            "Detected ModuleData XML. Record-bearing files are promoted to the structured ModuleData editor by the server.",
        )
    )
    rows.extend(
        _source_rows(
            project,
            "GUI/**/*.xml",
            "UI",
            "Gauntlet/UI XML",
            "Detected GUI XML. Files under GUI/Prefabs are promoted to the structured Gauntlet editor by the server.",
        )
    )
    if paths.is_contained_file(project, project / "Design.txt"):
        rows.extend(
            _source_rows(
                project,
                "Design.txt",
                "Design",
                "Project design source",
                "Project design/reference source; not gameplay data.",
            )
        )
    return {"rows": rows}