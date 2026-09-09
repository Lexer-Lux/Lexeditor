"""Optional Bannerlord XSD discovery and attribute-control enrichment.

The Modding Kit ships schema files under XmlSchemas. Lexeditor uses them only
when a unique matching schema can be identified; otherwise ModuleData stays on
its conservative syntax-derived controls.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET


XS = "{http://www.w3.org/2001/XMLSchema}"
_INTEGER_TYPES = {
    "byte",
    "int",
    "integer",
    "long",
    "negativeInteger",
    "nonNegativeInteger",
    "nonPositiveInteger",
    "positiveInteger",
    "short",
    "unsignedByte",
    "unsignedInt",
    "unsignedLong",
    "unsignedShort",
}
_NUMERIC_TYPES = _INTEGER_TYPES | {"decimal", "double", "float"}


def schema_roots(game_root: Path) -> list[Path]:
    """Return known Modding Kit schema locations without requiring the Kit."""
    candidates = [game_root / "XmlSchemas", game_root / "XMLEditor" / "XmlSchemas"]
    return [path for path in candidates if path.is_dir()]


def _local_type(value: str) -> str:
    return str(value or "").split(":")[-1]


def _restriction(simple_type: ET.Element | None) -> dict:
    if simple_type is None:
        return {}
    restriction = simple_type.find(f"{XS}restriction")
    if restriction is None:
        return {}
    base = _local_type(restriction.attrib.get("base", ""))
    choices = [
        value.attrib.get("value", "")
        for value in restriction.findall(f"{XS}enumeration")
        if value.attrib.get("value") is not None
    ]
    result = {"type": base}
    if choices:
        result["choices"] = choices
    for tag, key in (("minInclusive", "min"), ("maxInclusive", "max")):
        node = restriction.find(f"{XS}{tag}")
        if node is not None and "value" in node.attrib:
            try:
                result[key] = float(node.attrib["value"])
            except ValueError:
                pass
    return result


def _collect_simple_types(root: ET.Element) -> dict[str, dict]:
    result = {}
    for node in root.findall(f"{XS}simpleType"):
        name = node.attrib.get("name", "")
        if name:
            result[name] = _restriction(node)
    return result


def _attribute_rule(attribute: ET.Element, simple_types: dict[str, dict]) -> dict:
    type_name = _local_type(attribute.attrib.get("type", ""))
    rule = dict(simple_types.get(type_name, {}))
    if not rule and type_name:
        rule["type"] = type_name
    inline = attribute.find(f"{XS}simpleType")
    if inline is not None:
        rule.update(_restriction(inline))
    rule["required"] = attribute.attrib.get("use", "") == "required"
    default = attribute.attrib.get("default")
    fixed = attribute.attrib.get("fixed")
    if default is not None:
        rule["default"] = default
    if fixed is not None:
        rule["fixed"] = fixed
    return rule


def _complex_type_rules(root: ET.Element, simple_types: dict[str, dict]) -> dict[str, dict[str, dict]]:
    result: dict[str, dict[str, dict]] = {}
    for complex_type in root.findall(f"{XS}complexType"):
        name = complex_type.attrib.get("name", "")
        if not name:
            continue
        attributes: dict[str, dict] = {}
        for attribute in complex_type.findall(f".//{XS}attribute"):
            attribute_name = attribute.attrib.get("name", "")
            if attribute_name:
                attributes[attribute_name] = _attribute_rule(attribute, simple_types)
        result[name] = attributes
    return result


def _element_types(root: ET.Element) -> dict[str, str]:
    """Map unambiguous named elements to their declared complex/simple type."""
    found: dict[str, set[str]] = {}
    for element in root.findall(f".//{XS}element"):
        name = element.attrib.get("name", "")
        type_name = _local_type(element.attrib.get("type", ""))
        if name and type_name:
            found.setdefault(name, set()).add(type_name)
    return {name: next(iter(types)) for name, types in found.items() if len(types) == 1}


def _inline_element_rules(root: ET.Element, simple_types: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """Capture attributes for elements whose complexType is declared inline."""
    found: dict[str, list[dict[str, dict]]] = {}
    for element in root.findall(f".//{XS}element"):
        name = element.attrib.get("name", "")
        complex_type = element.find(f"{XS}complexType")
        if not name or complex_type is None:
            continue
        attributes = {}
        for attribute in complex_type.findall(f".//{XS}attribute"):
            attribute_name = attribute.attrib.get("name", "")
            if attribute_name:
                attributes[attribute_name] = _attribute_rule(attribute, simple_types)
        found.setdefault(name, []).append(attributes)
    return {name: variants[0] for name, variants in found.items() if len(variants) == 1}


@lru_cache(maxsize=256)
def _parse_schema_cached(path_text: str, mtime_ns: int) -> dict:
    path = Path(path_text)
    root = ET.parse(path).getroot()
    simple_types = _collect_simple_types(root)
    complex_types = _complex_type_rules(root, simple_types)
    element_types = _element_types(root)
    inline = _inline_element_rules(root, simple_types)

    elements: dict[str, dict[str, dict]] = dict(inline)
    for element_name, type_name in element_types.items():
        if type_name in complex_types:
            elements[element_name] = complex_types[type_name]

    global_elements = [
        node.attrib.get("name", "")
        for node in root.findall(f"{XS}element")
        if node.attrib.get("name")
    ]
    return {
        "path": str(path),
        "id": root.attrib.get("id", ""),
        "stem": path.stem,
        "globalElements": global_elements,
        "elements": elements,
    }


def parse_schema(path: Path) -> dict:
    stat = path.stat()
    return _parse_schema_cached(str(path.resolve()), stat.st_mtime_ns)


def _schema_files(game_root: Path) -> list[Path]:
    files = []
    for root in schema_roots(game_root):
        files.extend(path for path in root.rglob("*.xsd") if path.is_file())
    return sorted(set(files), key=lambda value: value.as_posix().casefold())


def find_schema(game_root: Path, schema_id: str, root_tag: str) -> dict | None:
    """Return a schema only when the best score is unique enough to trust."""
    wanted_id = schema_id.casefold().strip()
    wanted_root = root_tag.casefold().strip()
    candidates = []
    for path in _schema_files(game_root):
        try:
            schema = parse_schema(path)
        except (ET.ParseError, OSError):
            continue
        score = 0
        if wanted_id:
            if schema["id"].casefold() == wanted_id:
                score += 100
            if schema["stem"].casefold() == wanted_id:
                score += 90
        if wanted_root and any(value.casefold() == wanted_root for value in schema["globalElements"]):
            score += 40
        if score:
            candidates.append((score, schema))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score = candidates[0][0]
    best = [schema for score, schema in candidates if score == best_score]
    return best[0] if len(best) == 1 else None


def _control(rule: dict, current_kind: str) -> tuple[str, list[str]]:
    choices = list(rule.get("choices") or [])
    if choices:
        return "enum", choices
    type_name = _local_type(rule.get("type", ""))
    if type_name == "boolean":
        return "bool", []
    if type_name in _NUMERIC_TYPES:
        return "number", []
    return current_kind, []


def enrich_elements(elements: list[dict], schema: dict | None) -> list[dict]:
    """Attach schema metadata to both public and private attribute records."""
    if not schema:
        return elements
    rules_by_element = schema.get("elements") or {}
    for element in elements:
        rules = rules_by_element.get(element["tag"])
        if not rules:
            continue
        private = {attribute["name"]: attribute for attribute in element.get("_attributes", [])}
        public = {attribute["name"]: attribute for attribute in element.get("attributes", [])}
        for name, rule in rules.items():
            type_name = _local_type(rule.get("type", ""))
            for target in (private.get(name), public.get(name)):
                if target is None:
                    continue
                kind, choices = _control(rule, target.get("kind", "text"))
                target["kind"] = kind
                target["choices"] = choices
                target["required"] = bool(rule.get("required"))
                target["schemaType"] = type_name
                if type_name in _INTEGER_TYPES:
                    target["integer"] = True
                if "min" in rule:
                    target["min"] = rule["min"]
                if "max" in rule:
                    target["max"] = rule["max"]
                if "default" in rule:
                    target["default"] = rule["default"]
                if "fixed" in rule:
                    target["fixed"] = rule["fixed"]
    return elements
