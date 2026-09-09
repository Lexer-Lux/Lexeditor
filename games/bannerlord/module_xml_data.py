"""Structured record editing for Bannerlord ModuleData XML documents."""
from __future__ import annotations

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from . import paths
from .module_data import read_submodule
from .xml_patch import scan_xml_start_tags, serialize_attribute
from .xsd_data import enrich_elements, find_schema


def list_documents(project: Path) -> list[str]:
    root = project / "ModuleData"
    if not root.is_dir():
        return []
    return [
        path.relative_to(project).as_posix()
        for path in sorted(root.rglob("*.xml"), key=lambda value: value.as_posix().casefold())
        if path.is_file()
    ]


def _document_path(project: Path, requested: str) -> Path:
    if not requested:
        raise ValueError("Missing ModuleData XML path")
    root = (project / "ModuleData").resolve()
    target = (project / requested).resolve()
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
        records.append(
            {
                "path": element["path"],
                "tag": element["tag"],
                "line": element["line"],
                "id": attributes.get("id") or attributes.get("Id") or "",
                "name": attributes.get("name") or attributes.get("Name") or "",
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
    descriptor = project / "SubModule.xml"
    if not descriptor.is_file():
        return ""
    try:
        module = read_submodule(descriptor)
    except Exception:
        return ""
    relative = path.relative_to((project / "ModuleData").resolve()).as_posix()
    wanted = _normalized_module_path(relative)
    for row in module.get("xmls", []):
        if _normalized_module_path(row.get("path", "")) == wanted:
            return str(row.get("id") or "")
    return ""


def _schema_for(project: Path, path: Path, root_tag: str, game_root: Path | None) -> dict | None:
    game = (game_root or paths.game_root()).resolve()
    return find_schema(game, _registration_id(project, path), root_tag)


def _scan_document(text: str, schema: dict | None) -> list[dict]:
    # ModuleData starts with syntax-safe bool/number inference, then upgrades
    # controls only when a uniquely matched Bannerlord XSD explicitly says so.
    return enrich_elements(scan_xml_start_tags(text), schema)


def read_document(project: Path, requested: str, game_root: Path | None = None) -> dict:
    path = _document_path(project, requested)
    text = path.read_text(encoding="utf-8-sig")
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
        "rootTag": root.tag,
        "recordCount": len(records),
        "records": records,
        "elements": [_public(element) for element in elements],
        "schema": public_schema,
    }


def save_document(
    project: Path,
    requested: str,
    edits: list[dict],
    game_root: Path | None = None,
) -> dict:
    path = _document_path(project, requested)
    text = path.read_text(encoding="utf-8-sig")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"Invalid Bannerlord ModuleData XML in {requested}: {error}") from error
    schema = _schema_for(project, path, root.tag, game_root)
    elements = _scan_document(text, schema)
    by_path = {element["path"]: element for element in elements}
    replacements: list[tuple[int, int, str]] = []
    touched: set[tuple[str, str]] = set()
    changed = 0

    for edit in edits:
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
        attribute = next(
            (row for row in element["_attributes"] if row["name"] == attribute_name), None
        )
        if attribute is None:
            raise ValueError(f"{element_path} no longer has attribute {attribute_name}")
        if "originalValue" in edit and str(edit["originalValue"]) != attribute["value"]:
            raise ValueError(
                f"{element_path} {attribute_name} changed on disk; reload before saving"
            )
        replacement = serialize_attribute(attribute, edit.get("value"))
        left, right = attribute["_span"]
        if text[left:right] != replacement:
            replacements.append((left, right, replacement))
            changed += 1

    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    backup = path.with_name(path.name + ".lexeditor.bak")
    if changed:
        try:
            ET.fromstring(candidate)
        except ET.ParseError as error:
            raise ValueError(f"Saving would create invalid ModuleData XML: {error}") from error
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    result = read_document(project, requested, game_root)
    result.update({"saved": changed, "backup": str(backup) if changed else ""})
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
                            "Record-oriented ModuleData XML editor. Existing nested element attributes "
                            "are edited surgically; installed XSDs enrich controls when a unique schema matches."
                        ),
                    }
                )
        rows.append(current)
    return {**value, "rows": rows}
