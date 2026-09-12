"""Resolve PalSchema's generated utility string constraints conservatively.

PalSchema's generated raw DataTable schemas reference ``utility.schema.json``
for Unreal object/class path strings. Lexeditor consumes only the two upstream
path definitions whose semantics are explicit and keeps all other utility refs
fail-closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from .palschema import MAX_SCHEMA_BYTES, field_schema


UTILITY_REF_PREFIX = "../utility.schema.json#/definitions/"
SUPPORTED_UTILITY_DEFINITIONS = frozenset({"ObjectPathRegex", "ClassPathRegex"})


def _json_pointer_name(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def _read_json_object(path: Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    if len(raw) > MAX_SCHEMA_BYTES:
        raise ValueError(f"Generated utility schema exceeds the {MAX_SCHEMA_BYTES}-byte safety limit")
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid generated PalSchema utility schema: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Generated PalSchema utility schema root must be an object")
    return value


def resolve_utility_constraint(schema_root: Path | None, reference: str) -> dict[str, Any]:
    """Resolve one known generated utility ref without following arbitrary files."""
    if not reference.startswith(UTILITY_REF_PREFIX):
        return {"resolved": False, "reason": "Property does not use a PalSchema utility reference."}
    name = _json_pointer_name(reference.removeprefix(UTILITY_REF_PREFIX))
    if name not in SUPPORTED_UTILITY_DEFINITIONS:
        return {
            "resolved": False,
            "name": name,
            "reason": f"Generated utility definition {name!r} is not an integrated Lexeditor constraint.",
        }
    if schema_root is None:
        return {"resolved": False, "name": name, "reason": "Generated PalSchema schemas are unavailable."}
    root = Path(schema_root).resolve()
    path = root / "utility.schema.json"
    if not path.is_file():
        return {
            "resolved": False,
            "name": name,
            "reason": "Generated utility.schema.json is missing; referenced path write disabled.",
        }
    try:
        schema = _read_json_object(path)
        definitions = schema.get("definitions", {})
        definition = definitions.get(name, {}) if isinstance(definitions, dict) else {}
        pattern = definition.get("pattern") if isinstance(definition, dict) else None
        description = definition.get("description") if isinstance(definition, dict) else ""
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"Generated utility definition {name!r} has no regex pattern")
        re.compile(pattern)
    except (OSError, ValueError, re.error) as error:
        return {"resolved": False, "name": name, "reason": str(error)}
    return {
        "resolved": True,
        "name": name,
        "pattern": pattern,
        "description": description if isinstance(description, str) else "",
    }


def validate_utility_value(
    schema_root: Path | None,
    reference: str,
    value: Any,
    *,
    label: str = "value",
) -> str:
    constraint = resolve_utility_constraint(schema_root, reference)
    if not constraint.get("resolved"):
        raise ValueError(str(constraint.get("reason", "Generated utility constraint could not be resolved.")))
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if re.fullmatch(str(constraint["pattern"]), value) is None:
        raise ValueError(f"{label} does not match PalSchema {constraint['name']}")
    return value


def apply_existing_utility_policy(payload: dict[str, Any], schema_root: Path | None) -> dict[str, Any]:
    """Re-enable only existing JSON string fields whose utility ref resolves."""
    result = deepcopy(payload)
    if schema_root is None:
        return result
    patch_writable = result.get("writable") is True
    for record in result.get("records", []):
        if not isinstance(record, dict):
            continue
        table = record.get("table")
        field = record.get("field")
        if not isinstance(table, str) or not isinstance(field, str):
            continue
        spec = field_schema(schema_root, table, field)
        reference = str(spec.get("reference", ""))
        if not reference.startswith(UTILITY_REF_PREFIX):
            continue
        constraint = resolve_utility_constraint(schema_root, reference)
        record["utilityConstraint"] = constraint.get("name", "")
        if not constraint.get("resolved"):
            record["writable"] = False
            record["schemaState"] = "constraint-unresolved"
            record["reason"] = str(constraint.get("reason", "Generated utility constraint could not be resolved."))
            continue
        try:
            validate_utility_value(schema_root, reference, record.get("value"), label=f"{table}.{field}")
        except ValueError as error:
            record["writable"] = False
            record["schemaState"] = "value-mismatch"
            record["reason"] = str(error)
            continue
        record["schemaState"] = "matched"
        record["writable"] = bool(patch_writable and record.get("kind") == "string")
        record["reason"] = (
            f"Resolved generated PalSchema {constraint['name']} constraint; "
            "existing path edits are syntax-validated."
        )
    return result
