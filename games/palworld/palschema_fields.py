"""Schema-backed field catalog for safe additions to existing PalSchema rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .palschema import ENUM_REF_PREFIX, MAX_SCHEMA_BYTES, field_schema


SCALAR_SCHEMA_TYPES = {"boolean", "integer", "number", "string"}


def _table_schema_path(schema_root: Path, table_name: str) -> Path:
    if not table_name or table_name in {".", ".."} or "/" in table_name or "\\" in table_name:
        raise ValueError("DataTable name cannot map to a generated schema file")
    root = Path(schema_root).resolve()
    target = (root / "raw" / f"{table_name}.schema.json").resolve()
    if root not in target.parents:
        raise ValueError("DataTable schema path escapes the generated schema directory")
    return target


def _read_schema(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_SCHEMA_BYTES:
        raise ValueError(f"Generated schema exceeds the {MAX_SCHEMA_BYTES}-byte safety limit")
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid generated PalSchema schema: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Generated PalSchema schema root must be an object")
    return value


def schema_scalar_writable(spec: dict[str, Any]) -> tuple[bool, str]:
    if spec.get("state") != "matched":
        return False, str(spec.get("reason", "Generated schema did not resolve the property."))
    schema_type = str(spec.get("type", ""))
    if schema_type not in SCALAR_SCHEMA_TYPES:
        return False, "Only generated scalar properties are writable in this slice."
    reference = str(spec.get("reference", ""))
    if reference.startswith(ENUM_REF_PREFIX):
        if not spec.get("enumValues"):
            return False, "Generated enum reference could not be resolved; write disabled."
    elif reference:
        return False, "Generated property uses a referenced constraint that Lexeditor does not yet resolve; write disabled."
    return True, "Generated PalSchema scalar schema matched."


def default_for_schema(spec: dict[str, Any]) -> Any:
    enum_values = spec.get("enumValues", [])
    if isinstance(enum_values, list) and enum_values:
        return enum_values[0]
    schema_type = spec.get("type")
    if schema_type == "boolean":
        return False
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "string":
        return ""
    raise ValueError("Generated property is not a scalar field")


def available_fields(
    schema_root: Path | None,
    table_name: str,
    *,
    present_fields: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """List schema-backed scalar fields not already present in one patch row."""
    if schema_root is None or not Path(schema_root).is_dir():
        return []
    path = _table_schema_path(Path(schema_root), table_name)
    if not path.is_file():
        return []
    schema = _read_schema(path)
    additional = schema.get("additionalProperties", {})
    properties = additional.get("properties", {}) if isinstance(additional, dict) else {}
    if not isinstance(properties, dict):
        return []
    present = set(present_fields)
    rows: list[dict[str, Any]] = []
    for field_name in sorted(properties, key=str.casefold):
        if field_name in present:
            continue
        spec = field_schema(Path(schema_root), table_name, field_name)
        writable, reason = schema_scalar_writable(spec)
        row = {
            "name": field_name,
            "type": str(spec.get("type", "")),
            "description": str(spec.get("description", "")),
            "enumValues": list(spec.get("enumValues", [])),
            "writable": writable,
            "reason": reason,
        }
        if writable:
            row["default"] = default_for_schema(spec)
        rows.append(row)
    return rows


def coerce_new_value(schema_root: Path, table_name: str, field_name: str, value: Any) -> Any:
    spec = field_schema(Path(schema_root), table_name, field_name)
    writable, reason = schema_scalar_writable(spec)
    if not writable:
        raise ValueError(reason)
    schema_type = spec.get("type")
    if schema_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{field_name} must be a boolean")
        result: Any = value
    elif schema_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer")
        result = value
    elif schema_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name} must be numeric")
        result = float(value)
    elif schema_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        result = value
    else:
        raise ValueError(f"{field_name} is not a schema-backed scalar field")
    enum_values = list(spec.get("enumValues", []))
    if enum_values and result not in enum_values:
        raise ValueError(f"{field_name} must be one of the generated enum values")
    return result
