"""Structured editing for Bannerlord Gauntlet prefab XML without whole-file reserialization."""
from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .paths import contained_project_path, is_contained_file
from .source_revision import (
    encode_utf8_source,
    read_utf8_source,
    replace_source_bytes,
    require_source_revision,
)
from .xml_patch import scan_xml_start_tags, serialize_attribute


_ENUMS = {
    "WidthSizePolicy": ("Fixed", "StretchToParent", "CoverChildren"),
    "HeightSizePolicy": ("Fixed", "StretchToParent", "CoverChildren"),
    "HorizontalAlignment": ("Left", "Center", "Right"),
    "VerticalAlignment": ("Top", "Center", "Bottom"),
    "Brush.TextHorizontalAlignment": ("Left", "Center", "Right"),
    "Brush.TextVerticalAlignment": ("Top", "Center", "Bottom"),
}


def list_prefabs(project: Path) -> list[str]:
    root = contained_project_path(project, "GUI", "Prefabs")
    if not root.is_dir():
        return []
    return [
        path.relative_to(project.resolve()).as_posix()
        for path in sorted(root.rglob("*.xml"), key=lambda value: value.as_posix().casefold())
        if is_contained_file(project, path)
    ]


def _prefab_path(project: Path, requested: str) -> Path:
    if not requested:
        raise ValueError("Missing Gauntlet prefab path")
    relative = Path(str(requested).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Gauntlet editor only opens XML files under GUI/Prefabs")
    root = contained_project_path(project, "GUI", "Prefabs")
    target = contained_project_path(project, relative)
    if root not in target.parents or target.suffix.casefold() != ".xml":
        raise ValueError("Gauntlet editor only opens XML files under GUI/Prefabs")
    if not target.is_file():
        raise FileNotFoundError(target)
    return target


def _scan(text: str) -> list[dict]:
    return scan_xml_start_tags(text, _ENUMS)


def _public(element: dict) -> dict:
    return {key: value for key, value in element.items() if not key.startswith("_")}


def read_prefab(project: Path, requested: str) -> dict:
    path = _prefab_path(project, requested)
    text, _encoding, revision = read_utf8_source(path)
    try:
        ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"Invalid Gauntlet XML in {requested}: {error}") from error
    elements = _scan(text)
    return {
        "path": str(path),
        "relativePath": path.relative_to(project.resolve()).as_posix(),
        "sourceHash": revision,
        "elements": [_public(element) for element in elements],
        "elementCount": len(elements),
    }


def save_prefab(
    project: Path,
    requested: str,
    edits: list[dict],
    source_hash: str | None = None,
) -> dict:
    path = _prefab_path(project, requested)
    text, encoding, loaded_revision = read_utf8_source(path)
    if source_hash is not None:
        require_source_revision(path, source_hash)
    elements = _scan(text)
    by_path = {element["path"]: element for element in elements}
    replacements: list[tuple[int, int, str]] = []
    changed = 0
    touched: set[tuple[str, str]] = set()

    for edit in edits:
        element_path = str(edit.get("elementPath") or "")
        attribute_name = str(edit.get("attribute") or "")
        key = (element_path, attribute_name)
        if key in touched:
            raise ValueError(f"Duplicate Gauntlet edit for {element_path} {attribute_name}")
        touched.add(key)
        element = by_path.get(element_path)
        if element is None:
            raise ValueError(f"Gauntlet element changed or no longer exists: {element_path}")
        expected_tag = str(edit.get("tag") or "")
        if expected_tag and expected_tag != element["tag"]:
            raise ValueError(f"Gauntlet element identity changed: {element_path}")
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
    backup = ""
    if changed:
        try:
            ET.fromstring(candidate)
        except ET.ParseError as error:
            raise ValueError(f"Saving would create invalid Gauntlet XML: {error}") from error
        backup = replace_source_bytes(
            path, encode_utf8_source(candidate, encoding), source_hash or loaded_revision
        )
    result = read_prefab(project, requested)
    result.update({"saved": changed, "backup": backup})
    return result


_PREFAB_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_. -]{0,78}")
# A mod with no prefabs yet has nothing to copy, so its first prefab can start
# from the smallest window the game loads: one widget filling the screen.
BLANK_PREFAB = (
    "<Prefab>\r\n"
    "  <Window>\r\n"
    "    <Widget WidthSizePolicy=\"StretchToParent\" HeightSizePolicy=\"StretchToParent\" />\r\n"
    "  </Window>\r\n"
    "</Prefab>\r\n"
)


def create_prefab(project: Path, source: str, name: str) -> dict:
    """A new prefab, copied from an existing one into the same folder.

    With no source it is a blank prefab directly under GUI/Prefabs. Never
    overwrites: a name that is already taken is refused.
    """
    root = contained_project_path(project, "GUI", "Prefabs")
    template = _prefab_path(project, source) if source else root / "Blank.xml"
    stem = str(name or "").strip()
    if stem.casefold().endswith(".xml"):
        stem = stem[:-4]
    if not _PREFAB_NAME.fullmatch(stem):
        raise ValueError("A prefab name uses letters, digits, spaces, dots, dashes and underscores (1-79).")
    target = template.with_name(stem + ".xml")
    if root not in target.parents:
        raise ValueError("Gauntlet prefabs are created under GUI/Prefabs")
    content = template.read_bytes() if source else BLANK_PREFAB.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(content)
    except FileExistsError as error:
        raise ValueError(f"A prefab named {target.name} already exists here.") from error
    return read_prefab(project, target.relative_to(project.resolve()).as_posix())


def duplicate_element(project: Path, requested: str, element_path: str,
                      source_hash: str | None = None) -> dict:
    """Copy an element, with everything inside it, to just after itself.

    The copy is spliced in as text, indented like the original, so the rest of
    the prefab keeps its exact formatting and comments.
    """
    path = _prefab_path(project, requested)
    text, encoding, loaded_revision = read_utf8_source(path)
    if source_hash is not None:
        require_source_revision(path, source_hash)
    element = next((row for row in _scan(text) if row["path"] == element_path), None)
    if element is None:
        raise ValueError(f"Gauntlet element changed or no longer exists: {element_path}")
    if element["depth"] == 0:
        raise ValueError("A prefab has one root element; copy an element inside it instead.")
    left, right = element["_fullSpan"]
    line_start = text.rfind("\n", 0, left) + 1
    indent = text[line_start:left] if not text[line_start:left].strip() else ""
    newline = "\r\n" if "\r\n" in text else "\n"
    copy = newline + indent + text[left:right]
    candidate = text[:right] + copy + text[right:]
    try:
        ET.fromstring(candidate)
    except ET.ParseError as error:
        raise ValueError(f"Copying would create invalid Gauntlet XML: {error}") from error
    backup = replace_source_bytes(path, encode_utf8_source(candidate, encoding), source_hash or loaded_revision)
    result = read_prefab(project, requested)
    start = right + len(newline) + len(indent)
    created = next((row for row in _scan(candidate) if row["_startTagSpan"][0] == start), None)
    result.update({"created": created["path"] if created else "", "backup": backup})
    return result


def augment_data_map(value: dict) -> dict:
    rows = []
    for row in value.get("rows") or []:
        current = dict(row)
        filename = str(current.get("filename") or "").replace("\\", "/")
        if filename.startswith("GUI/Prefabs/") and filename.casefold().endswith(".xml"):
            current.update(
                {
                    "controls": "Gauntlet widget hierarchy and existing widget attributes",
                    "coverage": "structured",
                    "status": "integrated",
                    "target": "gauntlet",
                    "targets": ["gauntlet"],
                    "openable": True,
                    "editorPath": filename,
                    "notes": (
                        "Widget-aware Gauntlet prefab editor with type-aware controls; "
                        "writes patch only changed attribute values and preserves surrounding XML."
                    ),
                }
            )
        rows.append(current)
    return {**value, "rows": rows}
