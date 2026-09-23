"""Structured record editing for Bannerlord ModuleData XML documents."""
from __future__ import annotations

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from . import paths
from .module_data import read_submodule
from .source_revision import (
    encode_utf8_source,
    read_utf8_source,
    replace_source_bytes,
    require_source_revision,
)
from .xml_patch import scan_xml_start_tags, serialize_attribute, serialize_new_attribute
from .xsd_data import enrich_elements, find_schema


def list_documents(project: Path) -> list[str]:
    root = paths.contained_project_path(project, "ModuleData")
    if not root.is_dir():
        return []
    return [
        path.relative_to(project.resolve()).as_posix()
        for path in sorted(root.rglob("*.xml"), key=lambda value: value.as_posix().casefold())
        if paths.is_contained_file(project, path)
    ]


def _document_path(project: Path, requested: str) -> Path:
    if not requested:
        raise ValueError("Missing ModuleData XML path")
    relative = Path(str(requested).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("ModuleData editor only opens XML files under ModuleData")
    root = paths.contained_project_path(project, "ModuleData")
    target = paths.contained_project_path(project, relative)
    if root not in target.parents or target.suffix.casefold() != ".xml":
        raise ValueError("ModuleData editor only opens XML files under ModuleData")
    if not target.is_file():
        raise FileNotFoundError(target)
    return target


def _public(element: dict) -> dict:
    return {key: value for key, value in element.items() if not key.startswith("_")}


def _record_rows(elements: list[dict]) -> list[dict]:
    records = []
    for element in elements:
        if element["depth"] != 1:
            continue
        attributes = {row["name"]: row["value"] for row in element["attributes"]}
        prefix = element["path"] + "/"
        descendants = [
            row for row in elements
            if row["path"] == element["path"] or row["path"].startswith(prefix)
        ]
        issue_count = sum(len(row.get("schemaIssues") or []) for row in descendants)
        records.append(
            {
                "path": element["path"],
                "tag": element["tag"],
                "line": element["line"],
                "id": attributes.get("id") or attributes.get("Id") or "",
                "name": attributes.get("name") or attributes.get("Name") or "",
                "schemaIssueCount": issue_count,
            }
        )
    return records


def _normalized_module_path(value: str) -> str:
    value = str(value or "").replace("\\", "/").strip().lstrip("/")
    if value.casefold().startswith("moduledata/"):
        value = value[len("ModuleData/"):]
    if value.casefold().endswith(".xml"):
        value = value[:-4]
    return value.casefold()


def _registration_id(project: Path, path: Path) -> str:
    try:
        descriptor = paths.contained_project_path(project, "SubModule.xml")
    except ValueError:
        return ""
    if not descriptor.is_file():
        return ""
    try:
        module = read_submodule(descriptor)
    except Exception:
        return ""
    module_data_root = paths.contained_project_path(project, "ModuleData")
    relative = path.relative_to(module_data_root).as_posix()
    wanted = _normalized_module_path(relative)
    for row in module.get("xmls", []):
        if _normalized_module_path(row.get("path", "")) == wanted:
            return str(row.get("id") or "")
    return ""


def _schema_for(project: Path, path: Path, root_tag: str, game_root: Path | None) -> dict | None:
    game = (game_root or paths.game_root()).resolve()
    return find_schema(game, _registration_id(project, path), root_tag)


def _scan_document(text: str, schema: dict | None) -> list[dict]:
    return enrich_elements(scan_xml_start_tags(text), schema)


def read_document(project: Path, requested: str, game_root: Path | None = None) -> dict:
    path = _document_path(project, requested)
    text, _encoding, revision = read_utf8_source(path)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"Invalid Bannerlord ModuleData XML in {requested}: {error}") from error
    schema = _schema_for(project, path, root.tag, game_root)
    elements = _scan_document(text, schema)
    records = _record_rows(elements)
    public_schema = None
    if schema:
        public_schema = {
            "id": schema.get("id") or schema.get("stem") or "",
            "path": schema.get("path") or "",
            "matchedByRegistration": bool(_registration_id(project, path)),
        }
    return {
        "path": str(path),
        "relativePath": path.relative_to(project.resolve()).as_posix(),
        "sourceHash": revision,
        "rootTag": root.tag,
        "recordCount": len(records),
        "records": records,
        "elements": [_public(element) for element in elements],
        "schema": public_schema,
        "schemaIssueCount": sum(len(element.get("schemaIssues") or []) for element in elements),
    }


def _record_id_attribute(element: dict) -> dict | None:
    return next((row for row in element.get("_attributes", []) if row["name"] in {"id", "Id"}), None)


def _record_element(by_path: dict[str, dict], operation: dict) -> dict:
    element_path = str(operation.get("elementPath") or "")
    element = by_path.get(element_path)
    if element is None:
        raise ValueError(f"ModuleData record changed or no longer exists: {element_path}")
    if element.get("depth") != 1:
        raise ValueError("Record lifecycle actions are limited to top-level ModuleData object records")
    expected_tag = str(operation.get("tag") or "")
    if expected_tag and expected_tag != element["tag"]:
        raise ValueError(f"ModuleData record identity changed: {element_path}")
    current_id = (_record_id_attribute(element) or {}).get("value", "")
    if "originalId" in operation and str(operation.get("originalId") or "") != str(current_id):
        raise ValueError(f"ModuleData record ID changed on disk: {element_path}")
    return element


def _duplicate_record(text: str, elements: list[dict], element: dict, new_id: str) -> tuple[int, int, str]:
    full_span = element.get("_fullSpan")
    if not full_span:
        raise ValueError(f"Could not locate the full XML span for {element['path']}")
    left, right = full_span
    snippet = text[left:right]
    id_attribute = _record_id_attribute(element)
    if id_attribute is not None:
        incoming = str(new_id or "").strip()
        if not incoming:
            raise ValueError("Duplicating a record with an id attribute requires a new ID")
        if incoming.casefold() == str(id_attribute["value"]).casefold():
            raise ValueError("Duplicate record ID must differ from the source record")
        existing_ids = {
            str(attribute["value"]).casefold()
            for row in elements if row.get("depth") == 1
            for attribute in row.get("_attributes", []) if attribute["name"] in {"id", "Id"}
        }
        if incoming.casefold() in existing_ids:
            raise ValueError(f"A top-level ModuleData record already uses ID {incoming}")
        replacement = serialize_attribute(id_attribute, incoming)
        value_left, value_right = id_attribute["_span"]
        local_left, local_right = value_left - left, value_right - left
        snippet = snippet[:local_left] + replacement + snippet[local_right:]

    line_start = text.rfind("\n", 0, left) + 1
    indentation = text[line_start:left]
    if indentation.strip():
        indentation = ""
    newline = "\r\n" if "\r\n" in text else "\n"
    return right, right, newline + indentation + snippet


def _delete_record_span(text: str, element: dict) -> tuple[int, int, str]:
    full_span = element.get("_fullSpan")
    if not full_span:
        raise ValueError(f"Could not locate the full XML span for {element['path']}")
    left, right = full_span
    line_start = text.rfind("\n", 0, left) + 1
    if not text[line_start:left].strip():
        left = line_start
    tail = right
    while tail < len(text) and text[tail] in " \t":
        tail += 1
    if text.startswith("\r\n", tail):
        right = tail + 2
    elif text.startswith("\n", tail):
        right = tail + 1
    return left, right, ""


def save_document(
    project: Path,
    requested: str,
    edits: list[dict],
    game_root: Path | None = None,
    additions: list[dict] | None = None,
    source_hash: str | None = None,
) -> dict:
    path = _document_path(project, requested)
    text, encoding, loaded_revision = read_utf8_source(path)
    if source_hash is not None:
        require_source_revision(path, source_hash)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"Invalid Bannerlord ModuleData XML in {requested}: {error}") from error
    schema = _schema_for(project, path, root.tag, game_root)
    elements = _scan_document(text, schema)
    by_path = {element["path"]: element for element in elements}
    replacements: list[tuple[int, int, str]] = []
    insertions: dict[int, list[str]] = {}
    touched: set[tuple[str, str]] = set()
    changed = 0
    record_actions = [row for row in edits if row.get("recordAction")]
    existing_edits = [row for row in edits if not row.get("addRequired") and not row.get("recordAction")]
    required_additions = [row for row in edits if row.get("addRequired")]
    required_additions.extend(list(additions or []))

    if record_actions and (existing_edits or required_additions):
        raise ValueError("Record lifecycle actions cannot be combined with attribute edits in one save")
    if len(record_actions) > 1:
        raise ValueError("Only one ModuleData record lifecycle action is allowed per save")

    if record_actions:
        operation = record_actions[0]
        element = _record_element(by_path, operation)
        action = str(operation.get("recordAction") or "")
        if action == "duplicate":
            replacements.append(_duplicate_record(text, elements, element, str(operation.get("newId") or "")))
        elif action == "delete":
            replacements.append(_delete_record_span(text, element))
        else:
            raise ValueError(f"Unsupported ModuleData record action: {action}")
        changed = 1

    for edit in existing_edits:
        element_path = str(edit.get("elementPath") or "")
        attribute_name = str(edit.get("attribute") or "")
        identity = (element_path, attribute_name)
        if identity in touched:
            raise ValueError(f"Duplicate ModuleData edit for {element_path} {attribute_name}")
        touched.add(identity)
        element = by_path.get(element_path)
        if element is None:
            raise ValueError(f"ModuleData element changed or no longer exists: {element_path}")
        expected_tag = str(edit.get("tag") or "")
        if expected_tag and expected_tag != element["tag"]:
            raise ValueError(f"ModuleData element identity changed: {element_path}")
        attribute = next((row for row in element["_attributes"] if row["name"] == attribute_name), None)
        if attribute is None:
            raise ValueError(f"{element_path} no longer has attribute {attribute_name}")
        if "originalValue" in edit and str(edit["originalValue"]) != attribute["value"]:
            raise ValueError(f"{element_path} {attribute_name} changed on disk; reload before saving")
        replacement = serialize_attribute(attribute, edit.get("value"))
        left, right = attribute["_span"]
        if text[left:right] != replacement:
            replacements.append((left, right, replacement))
            changed += 1

    for addition in required_additions:
        element_path = str(addition.get("elementPath") or "")
        attribute_name = str(addition.get("attribute") or "")
        identity = (element_path, attribute_name)
        if identity in touched:
            raise ValueError(f"Duplicate ModuleData edit for {element_path} {attribute_name}")
        touched.add(identity)
        element = by_path.get(element_path)
        if element is None:
            raise ValueError(f"ModuleData element changed or no longer exists: {element_path}")
        expected_tag = str(addition.get("tag") or "")
        if expected_tag and expected_tag != element["tag"]:
            raise ValueError(f"ModuleData element identity changed: {element_path}")
        if any(row["name"] == attribute_name for row in element["_attributes"]):
            raise ValueError(f"{element_path} already has attribute {attribute_name}; reload before saving")
        missing = next((row for row in element.get("missingRequired", []) if row.get("name") == attribute_name), None)
        if missing is None:
            raise ValueError(f"{attribute_name} is not a schema-declared missing required attribute on {element_path}")
        escaped_value = serialize_new_attribute(attribute_name, missing, addition.get("value"))
        position = int(element["_attributeInsert"])
        insertions.setdefault(position, []).append(f' {attribute_name}="{escaped_value}"')
        changed += 1

    for position, values in insertions.items():
        replacements.append((position, position, "".join(values)))

    candidate = text
    for left, right, replacement in sorted(replacements, key=lambda row: row[0], reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    backup = ""
    if changed:
        try:
            ET.fromstring(candidate)
        except ET.ParseError as error:
            raise ValueError(f"Saving would create invalid ModuleData XML: {error}") from error
        backup = replace_source_bytes(
            path, encode_utf8_source(candidate, encoding), source_hash or loaded_revision
        )
    result = read_document(project, requested, game_root)
    result.update({"saved": changed, "backup": backup})
    return result


def _has_records(path: Path) -> bool:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return False
    return any(isinstance(child.tag, str) for child in list(root))


def augment_data_map(project: Path, value: dict) -> dict:
    rows = []
    for row in value.get("rows") or []:
        current = dict(row)
        filename = str(current.get("filename") or "").replace("\\", "/")
        if filename.startswith("ModuleData/") and filename.casefold().endswith(".xml"):
            source_path = Path(str(current.get("sourcePath") or project / filename))
            if source_path.is_file() and _has_records(source_path):
                current.update(
                    {
                        "controls": "Bannerlord object records and nested XML attributes",
                        "coverage": "structured",
                        "status": "integrated",
                        "target": "moduledata",
                        "targets": ["moduledata"],
                        "openable": True,
                        "editorPath": filename,
                        "notes": (
                            "Record-oriented ModuleData XML editor with surgical attribute edits, XSD diagnostics/repair, "
                            "and loss-minimizing top-level record duplicate/delete operations."
                        ),
                    }
                )
        rows.append(current)
    return {**value, "rows": rows}