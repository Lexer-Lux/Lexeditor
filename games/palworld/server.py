"""Loopback service for the Palworld official mod-package editor."""

from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from runtime_bootstrap import user_data_dir

from .package import InfoDocument, PackageValidationError, StaleInfoError
from .palschema import (
    PatchValidationError,
    RawPatchDocument,
    ReadOnlyPatchError,
    StalePatchError,
    discover_raw_patches,
    field_schema,
    patch_payload,
    resolve_discovered_patch,
)
from .palschema_fields import available_fields, coerce_new_value, schema_scalar_writable


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_REQUEST_BYTES = 256 * 1024
MAX_PATCH_EDITS = 1000
MAX_PATCH_ADDS = 100

DATA_MAP = [
    {
        "filename": "Info.json",
        "controls": "Package metadata, dependencies, tags and InstallRule entries",
        "notes": "Structured/editable. Unknown future JSON keys are preserved; changed writes are stale-guarded, atomic and backed up.",
        "coverage": "structured",
        "status": "integrated",
    },
    {
        "filename": "PalSchema/<mod>/raw/*.json",
        "controls": "PalSchema DataTable → row → scalar property patches",
        "notes": "Structured/editable. Existing scalar values are editable; generated-schema scalar properties can also be added to an already-targeted explicit row.",
        "coverage": "structured",
        "status": "integrated",
    },
    {
        "filename": "Mods/NativeMods/UE4SS/Mods/PalSchema/schemas/**",
        "controls": "Generated PalSchema DataTable/enum JSON schemas",
        "notes": "Optional read-only validation source. Lexeditor consumes the user's runtime-generated schemas but never generates or rewrites them.",
        "coverage": "source",
        "status": "integrated",
    },
    {
        "filename": "PalSchema/<mod>/raw/*.jsonc",
        "controls": "PalSchema commented raw DataTable patches",
        "notes": "Structured/readable. Comments are parsed like PalSchema, but changed writes stay read-only so Lexeditor never destroys comment text.",
        "coverage": "partial",
        "status": "partial",
    },
    {
        "filename": "PalSchema raw wildcards / new rows / nested values",
        "controls": "$Filters, row creation/deletion and complex property payloads",
        "notes": "Recognized/read-only. Add-property support is deliberately limited to explicit rows already present in the patch; wildcard/new-row semantics need dedicated controls and stronger identity evidence.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "Paks/**/*.pak",
        "controls": "Official Paks InstallRule payload",
        "notes": "Package shape is recognized; Unreal PAK contents are not parsed or edited yet.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "Scripts/**",
        "controls": "Official Lua / UE4SS package payload",
        "notes": "Recognized by InstallRule only. Lexeditor does not install or replace UE4SS in this slice.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "LogicMods/**",
        "controls": "Official LogicMods package payload",
        "notes": "Recognized by InstallRule; Blueprint/asset editing requires separate format evidence.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "Mods/PalModSettings.ini",
        "controls": "Official loader activation configuration",
        "notes": "Read-only design boundary for now; activation/deactivation is deferred until ownership-aware rollback is implemented.",
        "coverage": "known",
        "status": "not-integrated",
    },
    {
        "filename": "Pal/Content/Paks/**",
        "controls": "Installed game assets",
        "notes": "Read-only source boundary. Lexeditor does not rewrite installed Palworld PAKs as a project save operation.",
        "coverage": "read-only",
        "status": "not-integrated",
    },
]


def project_root() -> Path:
    value = os.environ.get("LEXEDITOR_PALWORLD_PROJECT")
    return Path(value).expanduser().resolve() if value else (user_data_dir() / "projects" / "palworld").resolve()


def palschema_schema_root() -> Path | None:
    """Locate PalSchema's user-generated schemas without making them mandatory."""
    override = os.environ.get("LEXEDITOR_PALWORLD_PALSCHEMA_SCHEMAS")
    if override:
        candidate = Path(override).expanduser().resolve()
        return candidate if candidate.is_dir() else None
    game_value = os.environ.get("LEXEDITOR_PALWORLD_ROOT")
    if not game_value:
        return None
    candidate = (
        Path(game_value).expanduser().resolve()
        / "Mods" / "NativeMods" / "UE4SS" / "Mods" / "PalSchema" / "schemas"
    )
    return candidate if candidate.is_dir() else None


def info_path() -> Path:
    return project_root() / "Info.json"


def info_document() -> InfoDocument:
    return InfoDocument.load(info_path())


def info_payload() -> dict:
    path = info_path()
    document = InfoDocument.load(path)
    return {
        "project": str(project_root()),
        "path": str(path),
        "sourceSha256": document.source_sha256,
        "data": document.data,
        "issues": [asdict(issue) for issue in document.issues()],
    }


def safe_patch_payload(relative: str, info: dict, schema_root: Path | None) -> dict:
    """Expose only fields the current generated schema can safely validate."""
    payload = patch_payload(project_root(), info, relative, schema_root=schema_root)
    if schema_root is None:
        return payload
    for record in payload.get("records", []):
        if record.get("schemaState") in {"not-applicable", "unavailable"}:
            continue
        table = record.get("table")
        field = record.get("field")
        if not isinstance(table, str) or not isinstance(field, str) or field.startswith("(") or field == "$Filters":
            continue
        spec = field_schema(schema_root, table, field)
        writable, reason = schema_scalar_writable(spec)
        if not writable:
            record["writable"] = False
            record["reason"] = reason
            if record.get("schemaState") == "matched":
                record["schemaState"] = "constraint-unresolved"
    return payload


def validate_schema_edits(edits: list, schema_root: Path | None) -> None:
    """Fail closed on referenced constraints even if the patch value is scalar JSON."""
    if schema_root is None:
        return
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            continue
        table = edit.get("table")
        field = edit.get("field")
        if not isinstance(table, str) or not isinstance(field, str):
            continue
        spec = field_schema(schema_root, table, field)
        writable, reason = schema_scalar_writable(spec)
        if not writable:
            raise ValueError(f"edits[{index}] {table}.{field}: {reason}")


def palschema_catalog_payload() -> dict:
    info = info_document().data
    schema_root = palschema_schema_root()
    patches = discover_raw_patches(project_root(), info, schema_root=schema_root)
    if schema_root is not None:
        # Re-count fields blocked by unresolved generated constraints so the
        # file selector reflects the same fail-closed policy as the detail API.
        for row in patches:
            if row.get("errors"):
                continue
            try:
                payload = safe_patch_payload(row["path"], info, schema_root)
                row["schemaBlocked"] = sum(
                    record.get("schemaState") not in {"matched", "unavailable", "not-applicable"}
                    for record in payload.get("records", [])
                )
            except (OSError, ValueError):
                row["schemaBlocked"] = max(1, int(row.get("schemaBlocked", 0)))
    return {
        "project": str(project_root()),
        "schemaAvailable": schema_root is not None,
        "schemaRoot": str(schema_root) if schema_root is not None else "",
        "patches": patches,
    }


def palschema_fields_payload(relative: str, table: str, row: str) -> dict:
    schema_root = palschema_schema_root()
    if schema_root is None:
        raise ValueError("Generated PalSchema schemas are required to add a property")
    info = info_document().data
    target = resolve_discovered_patch(project_root(), info, relative, schema_root=schema_root)
    document = RawPatchDocument.load(target, schema_root=schema_root)
    if "*" in row:
        raise ValueError("Adding properties to wildcard rows is not supported")
    try:
        row_data = document.data[table][row]
    except (KeyError, TypeError) as error:
        raise ValueError("Add-property target must be an existing row in the selected patch") from error
    if not isinstance(row_data, dict):
        raise ValueError("Add-property target row must contain an object patch")
    return {
        "path": relative,
        "table": table,
        "row": row,
        "fields": available_fields(schema_root, table, present_fields=row_data.keys()),
    }


def apply_additions(document: RawPatchDocument, additions: list, schema_root: Path | None) -> int:
    if additions and schema_root is None:
        raise ValueError("Generated PalSchema schemas are required to add properties")
    changed = 0
    for index, addition in enumerate(additions):
        if not isinstance(addition, dict):
            raise ValueError(f"adds[{index}] must be an object")
        table = addition.get("table")
        row = addition.get("row")
        field = addition.get("field")
        if not all(isinstance(value, str) and value for value in (table, row, field)):
            raise ValueError(f"adds[{index}] needs table, row and field strings")
        if "*" in row:
            raise ValueError("Adding properties to wildcard rows is not supported")
        try:
            row_data = document.data[table][row]
        except (KeyError, TypeError) as error:
            raise ValueError("Add-property target must be an existing row in the selected patch") from error
        if not isinstance(row_data, dict):
            raise ValueError("Add-property target row must contain an object patch")
        if field in row_data:
            raise ValueError(f"{table}.{row}.{field} already exists in this patch row")
        assert schema_root is not None
        row_data[field] = coerce_new_value(schema_root, table, field, addition.get("value"))
        changed += 1
    return changed


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status: int = 200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError(f"Request body must be 1..{MAX_REQUEST_BYTES} bytes")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid JSON request: {error}") from error
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
            return
        if path == "/editor.js":
            self.send_file(PLUGIN_ROOT / "editor.js")
            return
        if path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Shared UI asset not found"}, 404)
            return
        if path == "/api/plugin":
            self.send_json({
                "apiVersion": 1,
                "pluginId": "palworld",
                "name": "Palworld",
                "hosted": True,
                "windowHost": "webview2",
                "capabilities": [
                    "official-package-info",
                    "palschema-raw-patches",
                    "palschema-generated-schemas",
                    "palschema-add-existing-row-fields",
                    "data-map",
                ],
            })
            return
        if path == "/api/info":
            try:
                self.send_json(info_payload())
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error), "project": str(project_root())}, 404)
            return
        if path == "/api/palschema/catalog":
            try:
                self.send_json(palschema_catalog_payload())
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/palschema/patch":
            try:
                values = parse_qs(parsed.query, keep_blank_values=True)
                relative = values.get("path", [""])[0]
                self.send_json(safe_patch_payload(relative, info_document().data, palschema_schema_root()))
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/palschema/fields":
            try:
                values = parse_qs(parsed.query, keep_blank_values=True)
                self.send_json(palschema_fields_payload(
                    values.get("path", [""])[0],
                    values.get("table", [""])[0],
                    values.get("row", [""])[0],
                ))
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/data-map":
            self.send_json({"rows": DATA_MAP})
            return
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/info/save":
            self.save_info()
            return
        if path == "/api/palschema/patch/save":
            self.save_palschema_patch()
            return
        self.send_json({"error": "Not found"}, 404)

    def save_info(self):
        try:
            payload = self.read_json()
            source_sha = payload.get("sourceSha256")
            changes = payload.get("changes")
            if not isinstance(source_sha, str) or len(source_sha) != 64:
                raise ValueError("sourceSha256 must be the 64-character hash returned by /api/info")
            if not isinstance(changes, dict):
                raise ValueError("changes must be a JSON object")
            path = info_path()
            document = InfoDocument.load(path)
            document.update(changes)
            document.save(path, expected_sha256=source_sha)
            self.send_json(info_payload())
        except PackageValidationError as error:
            self.send_json({"error": str(error), "issues": [asdict(issue) for issue in error.issues]}, 400)
        except StaleInfoError as error:
            self.send_json({"error": str(error)}, 409)
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)

    def save_palschema_patch(self):
        try:
            payload = self.read_json()
            relative = payload.get("path")
            source_sha = payload.get("sourceSha256")
            edits = payload.get("edits", [])
            additions = payload.get("adds", [])
            if not isinstance(source_sha, str) or len(source_sha) != 64:
                raise ValueError("sourceSha256 must be the 64-character hash returned by /api/palschema/patch")
            if not isinstance(edits, list) or len(edits) > MAX_PATCH_EDITS:
                raise ValueError(f"edits must be an array of at most {MAX_PATCH_EDITS} scalar edits")
            if not isinstance(additions, list) or len(additions) > MAX_PATCH_ADDS:
                raise ValueError(f"adds must be an array of at most {MAX_PATCH_ADDS} schema-backed additions")
            info = info_document().data
            schema_root = palschema_schema_root()
            target = resolve_discovered_patch(project_root(), info, relative, schema_root=schema_root)
            document = RawPatchDocument.load(target, schema_root=schema_root)
            validate_schema_edits(edits, schema_root)
            document.apply_edits(edits)
            apply_additions(document, additions, schema_root)
            document.save(expected_sha256=source_sha)
            self.send_json(safe_patch_payload(relative, info, schema_root))
        except PatchValidationError as error:
            self.send_json({"error": str(error), "issues": [asdict(issue) for issue in error.issues]}, 400)
        except ReadOnlyPatchError as error:
            self.send_json({"error": str(error)}, 400)
        except StalePatchError as error:
            self.send_json({"error": str(error)}, 409)
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
