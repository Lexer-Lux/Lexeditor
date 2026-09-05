"""Read and write FF8 menu/mitem.bin without rebuilding unrelated data.

The four-byte layout and finite type metadata come from FF8 Ultimate Editor
commit 343d97e9, Kadowaki.kadowakimanager and Resources/json/mitem.json.
"""

from __future__ import annotations

import json
from pathlib import Path


RECORD_SIZE = 4


def _schema(schema_root: Path) -> dict:
    return json.loads((schema_root / "mitem.json").read_text(encoding="utf-8"))


def read_rows(data: bytes, item_names: dict[int, str], schema_root: Path) -> dict:
    if len(data) % RECORD_SIZE:
        raise ValueError("mitem.bin has a partial item record")
    schema = _schema(schema_root)
    types = {int(row["id"]): row for row in schema["item_type"]}
    rows = []
    for item_id in range(len(data) // RECORD_SIZE):
        base = item_id * RECORD_SIZE
        type_id, flags, param1, param2 = data[base:base + RECORD_SIZE]
        item_type = types.get(type_id)
        rows.append({
            "id": item_id,
            "name": item_names.get(item_id, f"Item {item_id}"),
            "typeId": type_id,
            "typeName": item_type["name"] if item_type else f"Unknown type {type_id}",
            "description": item_type.get("description", "") if item_type else "",
            "flags": flags,
            "param1": param1,
            "param2": param2,
            "param1Type": item_type.get("param1", "unknown") if item_type else "unknown",
            "param2Type": item_type.get("param2", "unknown") if item_type else "unknown",
        })
    return {
        "rows": rows,
        "types": schema["item_type"],
        "flagDefinitions": schema["flag"],
        "parameterTypes": schema["param_type"],
    }


def apply_edits(data: bytes, edits: list[dict], schema_root: Path) -> tuple[bytes, int]:
    if len(data) % RECORD_SIZE:
        raise ValueError("mitem.bin has a partial item record")
    valid_types = {int(row["id"]) for row in _schema(schema_root)["item_type"]}
    raw = bytearray(data)
    seen: set[int] = set()
    for edit in edits:
        item_id = int(edit["id"])
        if item_id in seen or not 0 <= item_id < len(raw) // RECORD_SIZE:
            raise ValueError(f"Invalid or duplicate menu item id: {item_id}")
        seen.add(item_id)
        type_id = int(edit["typeId"])
        flags = int(edit["flags"])
        param1 = int(edit["param1"])
        param2 = int(edit["param2"])
        if type_id not in valid_types:
            raise ValueError(f"Unknown menu item type: {type_id}")
        if any(not 0 <= value <= 255 for value in (flags, param1, param2)):
            raise ValueError("Menu item flags and parameters must be 0 to 255")
        base = item_id * RECORD_SIZE
        raw[base:base + RECORD_SIZE] = bytes((type_id, flags, param1, param2))
    return bytes(raw), len(seen)
