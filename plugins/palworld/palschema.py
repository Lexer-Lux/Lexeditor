"""Safe structured editing for PalSchema ``raw`` DataTable patches.

PalSchema's raw loader reads only direct ``raw/*.json`` / ``raw/*.jsonc`` files
under each mod folder. The JSON shape is data-table -> row -> property. When the
user has PalSchema's generated ``schemas`` directory, Lexeditor also consumes the
upstream-generated raw DataTable and enum JSON schemas instead of guessing types.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable


MAX_PATCH_BYTES = 8 * 1024 * 1024
MAX_SCHEMA_BYTES = 16 * 1024 * 1024
RESERVED_FILTER = "$Filters"
ENUM_REF_PREFIX = "../enums.schema.json#/definitions/"


@dataclass(frozen=True)
class PatchIssue:
    severity: str
    code: str
    path: str
    message: str


class PatchValidationError(ValueError):
    def __init__(self, issues: list[PatchIssue]):
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues if issue.severity == "error"))


class StalePatchError(RuntimeError):
    """Raised when a raw patch changed after Lexeditor read it."""


class ReadOnlyPatchError(RuntimeError):
    """Raised when a structurally recognized patch is intentionally not writable."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strip_jsonc_comments(text: str) -> str:
    """Remove // and /* */ comments without touching strings or newlines.

    PalSchema passes ``ignore_comments=true`` to nlohmann/json for .jsonc.
    Replacing comment characters with spaces preserves line/column positions for
    diagnostics while giving Python's JSON parser equivalent comment tolerance.
    """
    out = list(text)
    i = 0
    in_string = False
    escaped = False
    while i < len(out):
        ch = out[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "/" and i + 1 < len(out) and out[i + 1] == "/":
            out[i] = out[i + 1] = " "
            i += 2
            while i < len(out) and out[i] not in "\r\n":
                out[i] = " "
                i += 1
            continue
        if ch == "/" and i + 1 < len(out) and out[i + 1] == "*":
            out[i] = out[i + 1] = " "
            i += 2
            while i + 1 < len(out):
                if out[i] == "*" and out[i + 1] == "/":
                    out[i] = out[i + 1] = " "
                    i += 2
                    break
                if out[i] not in "\r\n":
                    out[i] = " "
                i += 1
            else:
                raise ValueError("Unterminated block comment in JSONC patch")
            continue
        i += 1
    return "".join(out)


def parse_patch_bytes(raw: bytes, suffix: str) -> dict[str, Any]:
    if len(raw) > MAX_PATCH_BYTES:
        raise ValueError(f"PalSchema patch exceeds the {MAX_PATCH_BYTES}-byte safety limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"PalSchema patch is not valid UTF-8: {error}") from error
    if suffix.casefold() == ".jsonc":
        text = _strip_jsonc_comments(text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid PalSchema {suffix} patch: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("PalSchema raw patch root must be a JSON object")
    return value


def validate_raw_patch(data: Any) -> list[PatchIssue]:
    """Validate only loader mechanics that PalSchema itself proves."""
    issues: list[PatchIssue] = []

    def error(code: str, path: str, message: str) -> None:
        issues.append(PatchIssue("error", code, path, message))

    def warning(code: str, path: str, message: str) -> None:
        issues.append(PatchIssue("warning", code, path, message))

    if not isinstance(data, dict):
        return [PatchIssue("error", "root.object", "$", "PalSchema raw patch root must be an object.")]

    for table_name, table in data.items():
        table_path = str(table_name)
        if not isinstance(table_name, str) or not table_name:
            error("table.name", "$", "DataTable names must be non-empty strings.")
            continue
        if not isinstance(table, dict):
            error("table.object", table_path, "Each DataTable value must be an object of row patches.")
            continue
        if "Rows" in table:
            error(
                "row.fmodel-wrapper",
                table_path + ".Rows",
                "PalSchema rejects the FModel 'Rows' wrapper; put row entries directly under the DataTable.",
            )
        for row_name, row in table.items():
            row_path = f"{table_path}.{row_name}"
            if row_name == "Rows":
                continue
            if not isinstance(row_name, str) or not row_name:
                error("row.name", table_path, "Row names must be non-empty strings.")
                continue
            if row is None:
                warning("row.delete", row_path, "Null deletes this row in PalSchema.")
                continue
            if not isinstance(row, dict):
                error("row.object", row_path, "A row patch must be an object or null.")
                continue
            if "*" in row_name and RESERVED_FILTER in row and not isinstance(row[RESERVED_FILTER], list):
                error("filters.array", row_path + "." + RESERVED_FILTER, "$Filters must be an array.")
            for field_name in row:
                if not isinstance(field_name, str) or not field_name:
                    error("field.name", row_path, "Property names must be non-empty strings.")
    return issues


def _scalar_kind(value: Any) -> str | None:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return None


def _load_json_object(path: Path, limit: int) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    if len(raw) > limit:
        raise ValueError(f"JSON metadata file exceeds the {limit}-byte safety limit: {path.name}")
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON metadata {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON metadata root must be an object: {path}")
    return value


def _safe_table_schema_path(schema_root: Path, table_name: str) -> Path | None:
    if not table_name or table_name in {".", ".."} or "/" in table_name or "\\" in table_name:
        return None
    root = Path(schema_root).resolve()
    target = (root / "raw" / f"{table_name}.schema.json").resolve()
    if root not in target.parents:
        return None
    return target


def _json_pointer_name(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def field_schema(schema_root: Path | None, table_name: str, field_name: str) -> dict[str, Any]:
    """Read one property description from PalSchema's generated schema tree.

    Missing schema infrastructure means Lexeditor falls back to type-preserving
    patch editing. Once a generated schema tree is available, missing table/field
    definitions are significant and changed writes fail closed.
    """
    if schema_root is None:
        return {"state": "unavailable"}
    root = Path(schema_root).resolve()
    if not root.is_dir():
        return {"state": "unavailable"}
    table_path = _safe_table_schema_path(root, table_name)
    if table_path is None:
        return {"state": "table-invalid", "reason": "DataTable name cannot map to a generated schema file."}
    if not table_path.is_file():
        return {"state": "table-missing", "reason": "Generated schema has no entry for this DataTable."}
    try:
        table_schema = _load_json_object(table_path, MAX_SCHEMA_BYTES)
    except (OSError, ValueError) as error:
        return {"state": "schema-error", "reason": str(error)}
    additional = table_schema.get("additionalProperties", {})
    properties = additional.get("properties", {}) if isinstance(additional, dict) else {}
    if not isinstance(properties, dict) or field_name not in properties:
        return {"state": "field-missing", "reason": "Generated DataTable schema does not contain this property."}
    spec = properties[field_name]
    if not isinstance(spec, dict):
        return {"state": "schema-error", "reason": "Generated property schema is not an object."}

    schema_type = spec.get("type") if isinstance(spec.get("type"), str) else None
    if schema_type is None and isinstance(spec.get("oneOf"), list):
        schema_type = "complex"
    description = spec.get("description") if isinstance(spec.get("description"), str) else ""
    enum_values: list[Any] = []
    reference = spec.get("$ref") if isinstance(spec.get("$ref"), str) else ""
    if reference.startswith(ENUM_REF_PREFIX):
        enum_name = _json_pointer_name(reference.removeprefix(ENUM_REF_PREFIX))
        enum_path = root / "enums.schema.json"
        try:
            enum_schema = _load_json_object(enum_path, MAX_SCHEMA_BYTES)
            definitions = enum_schema.get("definitions", {})
            enum_definition = definitions.get(enum_name, {}) if isinstance(definitions, dict) else {}
            values = enum_definition.get("enum", []) if isinstance(enum_definition, dict) else []
            if isinstance(values, list):
                enum_values = deepcopy(values)
        except (OSError, ValueError):
            enum_values = []

    return {
        "state": "matched",
        "type": schema_type or "complex",
        "description": description,
        "enumValues": enum_values,
        "reference": reference,
    }


def _value_matches_schema(value: Any, schema_type: str, enum_values: list[Any]) -> bool:
    if schema_type == "boolean":
        valid = isinstance(value, bool)
    elif schema_type == "integer":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif schema_type == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif schema_type == "string":
        valid = isinstance(value, str)
    elif schema_type == "object":
        valid = isinstance(value, dict)
    elif schema_type == "array":
        valid = isinstance(value, list)
    else:
        valid = False
    if valid and enum_values:
        valid = value in enum_values
    return valid


def _schema_kind(schema_type: str) -> str:
    return {
        "boolean": "bool",
        "integer": "int",
        "number": "float",
        "string": "string",
    }.get(schema_type, "complex")


def _record_schema(schema_root: Path | None, table_name: str, field_name: str, value: Any) -> dict[str, Any]:
    spec = field_schema(schema_root, table_name, field_name)
    state = spec.get("state")
    if state == "unavailable":
        return {
            "schemaState": "unavailable",
            "schemaType": "",
            "schemaDescription": "",
            "enumValues": [],
            "schemaKind": _scalar_kind(value) or "complex",
            "schemaWritable": _scalar_kind(value) is not None,
            "schemaReason": "No generated PalSchema schema is available; preserving the patch's existing scalar JSON type.",
        }
    if state != "matched":
        return {
            "schemaState": state,
            "schemaType": "",
            "schemaDescription": "",
            "enumValues": [],
            "schemaKind": "complex",
            "schemaWritable": False,
            "schemaReason": str(spec.get("reason", "Generated schema could not validate this property.")),
        }

    schema_type = str(spec.get("type", "complex"))
    enum_values = list(spec.get("enumValues", []))
    matches = _value_matches_schema(value, schema_type, enum_values)
    return {
        "schemaState": "matched" if matches else "value-mismatch",
        "schemaType": schema_type,
        "schemaDescription": str(spec.get("description", "")),
        "enumValues": enum_values,
        "schemaKind": _schema_kind(schema_type),
        "schemaWritable": matches and _schema_kind(schema_type) != "complex",
        "schemaReason": (
            "Generated PalSchema schema matched this property."
            if matches
            else "Current patch value does not match the generated PalSchema property schema; write disabled."
        ),
    }


def flatten_records(data: dict[str, Any], *, writable: bool, schema_root: Path | None = None) -> list[dict[str, Any]]:
    """Flatten table/row/property patches for the shared table/detail UI."""
    records: list[dict[str, Any]] = []
    for table_name, table in data.items():
        if not isinstance(table, dict):
            continue
        for row_name, row in table.items():
            if row_name == "Rows":
                continue
            if row is None:
                records.append({
                    "table": table_name,
                    "row": row_name,
                    "field": "(delete row)",
                    "value": None,
                    "kind": "delete",
                    "writable": False,
                    "reason": "PalSchema null row deletion is shown read-only in this slice.",
                    "schemaState": "not-applicable",
                    "schemaType": "",
                    "schemaDescription": "",
                    "enumValues": [],
                })
                continue
            if not isinstance(row, dict):
                continue
            for field_name, value in row.items():
                if field_name == RESERVED_FILTER:
                    records.append({
                        "table": table_name,
                        "row": row_name,
                        "field": field_name,
                        "value": deepcopy(value),
                        "kind": "filters",
                        "writable": False,
                        "reason": "$Filters are recognized but require a dedicated semantic editor.",
                        "schemaState": "not-applicable",
                        "schemaType": "",
                        "schemaDescription": "",
                        "enumValues": [],
                    })
                    continue
                metadata = _record_schema(schema_root, table_name, field_name, value)
                kind = metadata["schemaKind"]
                can_write = bool(writable and metadata["schemaWritable"])
                reason = metadata["schemaReason"]
                if not writable:
                    reason = "JSONC changed writes are read-only so Lexeditor preserves comments. " + reason
                records.append({
                    "table": table_name,
                    "row": row_name,
                    "field": field_name,
                    "value": deepcopy(value),
                    "kind": kind,
                    "writable": can_write,
                    "reason": reason,
                    "schemaState": metadata["schemaState"],
                    "schemaType": metadata["schemaType"],
                    "schemaDescription": metadata["schemaDescription"],
                    "enumValues": metadata["enumValues"],
                })
    return records


def _coerce_scalar(original: Any, value: Any, path: str) -> Any:
    kind = _scalar_kind(original)
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{path} must remain a boolean")
        return value
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{path} must remain an integer")
        return value
    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path} must remain numeric")
        return float(value)
    if kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path} must remain a string")
        return value
    raise ValueError(f"{path} is not a writable scalar property")


def _coerce_schema_value(spec: dict[str, Any], value: Any, path: str) -> Any:
    if spec.get("state") != "matched":
        raise ValueError(f"{path} is not present in the active generated PalSchema schema")
    schema_type = str(spec.get("type", ""))
    enum_values = list(spec.get("enumValues", []))
    if schema_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{path} must be a boolean")
        result: Any = value
    elif schema_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{path} must be an integer")
        result = value
    elif schema_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path} must be numeric")
        result = float(value)
    elif schema_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a string")
        result = value
    else:
        raise ValueError(f"{path} is not a schema-backed scalar property")
    if enum_values and result not in enum_values:
        raise ValueError(f"{path} must be one of the generated enum values")
    return result


class RawPatchDocument:
    """One direct ``raw/*.json[c]`` PalSchema patch."""

    def __init__(self, path: Path, data: dict[str, Any], source_bytes: bytes, schema_root: Path | None = None):
        self.path = Path(path)
        self.data = deepcopy(data)
        self._original = deepcopy(data)
        self._source_bytes = source_bytes
        self.source_sha256 = sha256_bytes(source_bytes)
        self.schema_root = Path(schema_root).resolve() if schema_root is not None else None

    @property
    def writable(self) -> bool:
        return self.path.suffix.casefold() == ".json"

    @classmethod
    def load(cls, path: Path, *, schema_root: Path | None = None) -> "RawPatchDocument":
        path = Path(path)
        suffix = path.suffix.casefold()
        if suffix not in {".json", ".jsonc"}:
            raise ValueError("PalSchema raw patches must end in .json or .jsonc")
        raw = path.read_bytes()
        return cls(path, parse_patch_bytes(raw, suffix), raw, schema_root=schema_root)

    def issues(self) -> list[PatchIssue]:
        return validate_raw_patch(self.data)

    def records(self) -> list[dict[str, Any]]:
        return flatten_records(self.data, writable=self.writable, schema_root=self.schema_root)

    def apply_edits(self, edits: Iterable[dict[str, Any]]) -> int:
        changed = 0
        schema_available = self.schema_root is not None and self.schema_root.is_dir()
        for index, edit in enumerate(edits):
            if not isinstance(edit, dict):
                raise ValueError(f"edits[{index}] must be an object")
            table = edit.get("table")
            row = edit.get("row")
            field = edit.get("field")
            if not all(isinstance(value, str) and value for value in (table, row, field)):
                raise ValueError(f"edits[{index}] needs table, row and field strings")
            try:
                row_data = self.data[table][row]
            except (KeyError, TypeError) as error:
                raise ValueError(f"Unknown PalSchema patch target {table}.{row}.{field}") from error
            if not isinstance(row_data, dict) or field == RESERVED_FILTER or field not in row_data:
                raise ValueError(f"Unsupported PalSchema patch target {table}.{row}.{field}")
            original = row_data[field]
            path = f"{table}.{row}.{field}"
            if schema_available:
                spec = field_schema(self.schema_root, table, field)
                if spec.get("state") != "matched" or not _value_matches_schema(
                    original, str(spec.get("type", "")), list(spec.get("enumValues", []))
                ):
                    raise ValueError(f"{path} does not match the active generated PalSchema schema")
                replacement = _coerce_schema_value(spec, edit.get("value"), path)
            else:
                replacement = _coerce_scalar(original, edit.get("value"), path)
            if replacement != original:
                row_data[field] = replacement
                changed += 1
        return changed

    def serialized(self) -> bytes:
        return (json.dumps(self.data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    def save(self, *, expected_sha256: str | None = None, backup: bool = True) -> str:
        errors = [issue for issue in self.issues() if issue.severity == "error"]
        if errors:
            raise PatchValidationError(errors)

        current = self.path.read_bytes()
        current_sha = sha256_bytes(current)
        expected = expected_sha256 if expected_sha256 is not None else self.source_sha256
        if expected and current_sha != expected:
            raise StalePatchError(f"{self.path.name} changed on disk after it was loaded; reload before saving.")

        if self.data == self._original:
            return current_sha
        if not self.writable:
            raise ReadOnlyPatchError(
                "Changed .jsonc patches are read-only so Lexeditor never destroys comments; "
                "use .json for structured writes."
            )

        payload = self.serialized()
        if backup:
            shutil.copyfile(self.path, self.path.with_name(self.path.name + ".lexeditor.bak"))

        fd, temp_name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

        self._source_bytes = payload
        self.source_sha256 = sha256_bytes(payload)
        self._original = deepcopy(self.data)
        return self.source_sha256


def _safe_relative_target(value: str) -> Path | None:
    text = value.strip().replace("\\", "/")
    if not text or text.startswith("/") or ":" in text.split("/", 1)[0]:
        return None
    parts = [part for part in text.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None
    return Path(*parts)


def palschema_roots(project_root: Path, info: dict[str, Any]) -> list[Path]:
    """Resolve only official PalSchema InstallRule targets inside the project."""
    project = Path(project_root).resolve()
    roots: list[Path] = []
    for rule in info.get("InstallRule", []):
        if not isinstance(rule, dict) or rule.get("Type") != "PalSchema":
            continue
        for target in rule.get("Targets", []):
            if not isinstance(target, str):
                continue
            relative = _safe_relative_target(target)
            if relative is None:
                continue
            candidate = (project / relative).resolve()
            if candidate != project and project in candidate.parents and candidate not in roots:
                roots.append(candidate)
    return roots


def discover_raw_patches(
    project_root: Path,
    info: dict[str, Any],
    *,
    schema_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Find direct raw/*.json[c] files, matching PalSchema's non-recursive loader."""
    project = Path(project_root).resolve()
    result: list[dict[str, Any]] = []
    for root in palschema_roots(project, info):
        if not root.is_dir():
            continue
        for mod_dir in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
            raw_dir = mod_dir / "raw"
            if not mod_dir.is_dir() or not raw_dir.is_dir():
                continue
            for path in sorted(raw_dir.iterdir(), key=lambda value: value.name.casefold()):
                if not path.is_file() or path.suffix.casefold() not in {".json", ".jsonc"}:
                    continue
                try:
                    relative = path.resolve().relative_to(project).as_posix()
                    document = RawPatchDocument.load(path, schema_root=schema_root)
                    errors = sum(issue.severity == "error" for issue in document.issues())
                    records = document.records()
                    schema_blocked = sum(
                        row.get("schemaState") not in {"matched", "unavailable", "not-applicable"}
                        for row in records
                    )
                    result.append({
                        "path": relative,
                        "mod": mod_dir.name,
                        "name": path.name,
                        "writable": document.writable,
                        "records": len(records),
                        "errors": errors,
                        "schemaBlocked": schema_blocked,
                    })
                except (OSError, ValueError):
                    relative = path.resolve().relative_to(project).as_posix()
                    result.append({
                        "path": relative,
                        "mod": mod_dir.name,
                        "name": path.name,
                        "writable": False,
                        "records": 0,
                        "errors": 1,
                        "schemaBlocked": 0,
                    })
    return result


def resolve_discovered_patch(
    project_root: Path,
    info: dict[str, Any],
    relative: str,
    *,
    schema_root: Path | None = None,
) -> Path:
    """Resolve only a file present in the current official PalSchema catalog."""
    if not isinstance(relative, str) or not relative:
        raise ValueError("PalSchema patch path is required")
    catalog = {row["path"] for row in discover_raw_patches(project_root, info, schema_root=schema_root)}
    if relative not in catalog:
        raise ValueError("PalSchema patch is outside the discovered official package targets")
    project = Path(project_root).resolve()
    target = (project / Path(relative)).resolve()
    if project not in target.parents or not target.is_file():
        raise ValueError("PalSchema patch is unavailable")
    return target


def patch_payload(
    project_root: Path,
    info: dict[str, Any],
    relative: str,
    *,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    path = resolve_discovered_patch(project_root, info, relative, schema_root=schema_root)
    document = RawPatchDocument.load(path, schema_root=schema_root)
    return {
        "path": relative,
        "sourceSha256": document.source_sha256,
        "writable": document.writable,
        "schemaAvailable": bool(schema_root is not None and Path(schema_root).is_dir()),
        "issues": [issue.__dict__ for issue in document.issues()],
        "records": document.records(),
    }
