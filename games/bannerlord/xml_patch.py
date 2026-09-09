"""Loss-minimizing XML attribute scanning and patching shared by Bannerlord editors."""
from __future__ import annotations

import math
import re
from xml.sax.saxutils import escape, unescape


_ATTRIBUTE = re.compile(r'([A-Za-z_:][\w:.-]*)\s*=\s*(["\'])(.*?)\2', re.DOTALL)
_TAG = re.compile(r"\s*([A-Za-z_:][\w:.-]*)")
_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")


def _decode(value: str) -> str:
    return unescape(value, {"&quot;": '"', "&apos;": "'"})


def infer_kind(name: str, value: str, enums: dict[str, tuple[str, ...]] | None = None) -> tuple[str, list[str]]:
    """Infer only syntax-safe controls; domain enums must be supplied explicitly."""
    if value.startswith("@") or value.startswith("{"):
        return "binding", []
    choices = (enums or {}).get(name)
    if choices and value in choices:
        return "enum", list(choices)
    if value.casefold() in {"true", "false"}:
        return "bool", []
    if _NUMBER.fullmatch(value):
        return "number", []
    return "text", []


def scan_xml_start_tags(text: str, enums: dict[str, tuple[str, ...]] | None = None) -> list[dict]:
    """Scan start tags while retaining exact attribute-value spans in original source."""
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
            kind, choices = infer_kind(match.group(1), value, enums)
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
            or identity.get("id")
            or identity.get("DataSource")
            or identity.get("name")
            or identity.get("Name")
            or identity.get("Text")
            or identity.get("Sprite")
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


def serialize_attribute(attribute: dict, incoming) -> str:
    """Validate and XML-escape one replacement according to inferred/schema metadata."""
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
        if attribute.get("integer") and not number.is_integer():
            raise ValueError(f"{attribute['name']} must be an integer")
        if "min" in attribute and number < float(attribute["min"]):
            raise ValueError(f"{attribute['name']} must be at least {attribute['min']}")
        if "max" in attribute and number > float(attribute["max"]):
            raise ValueError(f"{attribute['name']} must be at most {attribute['max']}")
        if (attribute.get("integer") or "." not in original) and number.is_integer():
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

    fixed = attribute.get("fixed")
    if fixed is not None and value != str(fixed):
        raise ValueError(f"{attribute['name']} is fixed by the XML schema to {fixed}")
    if attribute["_quote"] == '"':
        return escape(value, {'"': "&quot;"})
    return escape(value, {"'": "&apos;"})
