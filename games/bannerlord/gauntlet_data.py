"""Structured editing for Bannerlord Gauntlet prefab XML without whole-file reserialization."""
from __future__ import annotations

import math
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, unescape


_ENUMS = {
    "WidthSizePolicy": ("Fixed", "StretchToParent", "CoverChildren"),
    "HeightSizePolicy": ("Fixed", "StretchToParent", "CoverChildren"),
    "HorizontalAlignment": ("Left", "Center", "Right"),
    "VerticalAlignment": ("Top", "Center", "Bottom"),
    "Brush.TextHorizontalAlignment": ("Left", "Center", "Right"),
    "Brush.TextVerticalAlignment": ("Top", "Center", "Bottom"),
}
_ATTRIBUTE = re.compile(r'([A-Za-z_:][\w:.-]*)\s*=\s*(["\'])(.*?)\2', re.DOTALL)
_TAG = re.compile(r"\s*([A-Za-z_:][\w:.-]*)")
_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")


def list_prefabs(project: Path) -> list[str]:
    root = project / "GUI" / "Prefabs"
    if not root.is_dir():
        return []
    return [
        path.relative_to(project).as_posix()
        for path in sorted(root.rglob("*.xml"), key=lambda value: value.as_posix().casefold())
        if path.is_file()
    ]


def _prefab_path(project: Path, requested: str) -> Path:
    if not requested:
        raise ValueError("Missing Gauntlet prefab path")
    root = (project / "GUI" / "Prefabs").resolve()
    target = (project / requested).resolve()
    if root not in target.parents or target.suffix.casefold() != ".xml":
        raise ValueError("Gauntlet editor only opens XML files under GUI/Prefabs")
    if not target.is_file():
        raise FileNotFoundError(target)
    return target


def _decode(value: str) -> str:
    return unescape(value, {"&quot;": '"', "&apos;": "'"})


def _kind(name: str, value: str) -> tuple[str, list[str]]:
    if value.startswith("@") or value.startswith("{"):
        return "binding", []
    choices = _ENUMS.get(name)
    if choices and value in choices:
        return "enum", list(choices)
    if value.casefold() in {"true", "false"}:
        return "bool", []
    if _NUMBER.fullmatch(value):
        return "number", []
    return "text", []


def _scan(text: str) -> list[dict]:
    elements: list[dict] = []
    stack: list[dict] = []
    root_counts: dict[str, int] = {}
    offset = 0
    while offset < len(text):
        left = text.find("<", offset)
        if left < 0:
            break
        if text.startswith("<!--", left):
            right = text.find("-->", left + 4)
            offset = len(text) if right < 0 else right + 3
            continue
        if text.startswith("<![CDATA[", left):
            right = text.find("]]>", left + 9)
            offset = len(text) if right < 0 else right + 3
            continue
        if text.startswith("<?", left):
            right = text.find("?>", left + 2)
            offset = len(text) if right < 0 else right + 2
            continue
        if text.startswith("</", left):
            right = text.find(">", left + 2)
            if stack:
                stack.pop()
            offset = len(text) if right < 0 else right + 1
            continue
        if text.startswith("<!", left):
            right = text.find(">", left + 2)
            offset = len(text) if right < 0 else right + 1
            continue

        quote = None
        right = left + 1
        while right < len(text):
            character = text[right]
            if quote:
                if character == quote:
                    quote = None
            elif character in {'"', "'"}:
                quote = character
            elif character == ">":
                break
            right += 1
        if right >= len(text):
            break

        inner = text[left + 1:right]
        tag_match = _TAG.match(inner)
        if not tag_match:
            offset = right + 1
            continue
        tag = tag_match.group(1)
        self_closing = inner.rstrip().endswith("/")
        siblings = stack[-1]["children"] if stack else root_counts
        sibling_index = siblings.get(tag, 0)
        siblings[tag] = sibling_index + 1
        prefix = stack[-1]["path"] + "/" if stack else ""
        element_path = f"{prefix}{tag}[{sibling_index}]"

        attributes = []
        for match in _ATTRIBUTE.finditer(inner, tag_match.end()):
            raw = match.group(3)
            value = _decode(raw)
            kind, choices = _kind(match.group(1), value)
            attributes.append(
                {
                    "name": match.group(1),
                    "value": value,
                    "kind": kind,
                    "choices": choices,
                    "_span": (left + 1 + match.start(3), left + 1 + match.end(3)),
                    "_quote": match.group(2),
                }
            )
        public_attributes = [
            {key: value for key, value in attribute.items() if not key.startswith("_")}
            for attribute in attributes
        ]
        identity = {row["name"]: row["value"] for row in public_attributes}
        hint = (
            identity.get("Id")
            or identity.get("DataSource")
            or identity.get("Text")
            or identity.get("Sprite")
            or identity.get("Name")
            or ""
        )
        elements.append(
            {
                "index": len(elements),
                "path": element_path,
                "tag": tag,
                "depth": len(stack),
                "line": text.count("\n", 0, left) + 1,
                "hint": hint,
                "attributes": public_attributes,
                "_attributes": attributes,
            }
        )
        if not self_closing:
            stack.append({"path": element_path, "children": {}})
        offset = right + 1
    return elements


def _public(element: dict) -> dict:
    return {key: value for key, value in element.items() if not key.startswith("_")}


def read_prefab(project: Path, requested: str) -> dict:
    path = _prefab_path(project, requested)
    text = path.read_text(encoding="utf-8-sig")
    try:
        ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"Invalid Gauntlet XML in {requested}: {error}") from error
    elements = _scan(text)
    return {
        "path": str(path),
        "relativePath": path.relative_to(project.resolve()).as_posix(),
        "elements": [_public(element) for element in elements],
        "elementCount": len(elements),
    }


def _serialize(attribute: dict, incoming) -> str:
    kind = attribute["kind"]
    original = attribute["value"]
    if kind == "bool":
        if isinstance(incoming, bool):
            value = "true" if incoming else "false"
        else:
            value = str(incoming).strip().casefold()
            if value not in {"true", "false"}:
                raise ValueError(f"{attribute['name']} must be true or false")
    elif kind == "number":
        number = float(incoming)
        if not math.isfinite(number):
            raise ValueError(f"{attribute['name']} must be finite")
        if abs(number) > 1_000_000_000:
            raise ValueError(f"{attribute['name']} magnitude is too large")
        if "." not in original and number.is_integer():
            value = str(int(number))
        else:
            value = format(number, ".12g")
    elif kind == "enum":
        value = str(incoming)
        if value not in attribute["choices"]:
            raise ValueError(
                f"{attribute['name']} must be one of: {', '.join(attribute['choices'])}"
            )
    else:
        value = str(incoming)
    if attribute["_quote"] == '"':
        return escape(value, {'"': "&quot;"})
    return escape(value, {"'": "&apos;"})


def save_prefab(project: Path, requested: str, edits: list[dict]) -> dict:
    path = _prefab_path(project, requested)
    text = path.read_text(encoding="utf-8-sig")
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
        replacement = _serialize(attribute, edit.get("value"))
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
            raise ValueError(f"Saving would create invalid Gauntlet XML: {error}") from error
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    result = read_prefab(project, requested)
    result.update({"saved": changed, "backup": str(backup) if changed else ""})
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
