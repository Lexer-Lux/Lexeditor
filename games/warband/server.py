"""Local JSON and UI service for the Warband Lexeditor plugin."""

from __future__ import annotations

import ast
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import paths
from .item_icons import CACHE as ICON_CACHE
from .catalog import DATA_CATALOG
from .dump_infopages import parse_info_pages
from .dump_troops import parse_troops
from .game_font import atlas_path as font_atlas_path, manifest as font_manifest
from .model_preview import PreviewUnavailable, preview as item_preview, texture_path as preview_texture_path


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
PROJECT = Path(paths.MOD_PROJECT)
MODULE_SYSTEM = Path(paths.MODULE_SYSTEM)
SETTINGS = Path(paths.MOD_SETTINGS)
BUILD = Path(paths.MOD_BUILD)
MODULES = Path(paths.MODULES_DIR)
PORT = int(os.environ.get("LEXEDITOR_PORT", "8766"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED", "0") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "")


def settings_rows() -> list[dict]:
    rows = []
    if not SETTINGS.is_file():
        return rows
    section = ""
    pending_comments: list[str] = []
    for line_number, raw in enumerate(SETTINGS.read_text(encoding="utf-8", errors="replace").splitlines()):
        stripped = raw.strip()
        if stripped.startswith((";", "#")):
            pending_comments.append(stripped.lstrip(";# "))
            continue
        section_match = re.match(r"\[([^\]]+)\]", stripped)
        if section_match:
            section = section_match.group(1)
            pending_comments = []
            continue
        value_match = re.match(r"^([^=]+?)\s*=\s*([^;#]*)(.*)$", raw)
        if not value_match:
            if stripped:
                pending_comments = []
            continue
        key, value, suffix = (value_match.group(1).strip(), value_match.group(2).strip(), value_match.group(3).strip())
        description = " ".join(pending_comments[-2:])
        if suffix:
            description = (description + " " + suffix.lstrip(";# ")).strip()
        pending_comments = []
        rows.append({"line": line_number, "section": section, "key": key, "value": value, "description": description})
    return rows


def save_settings(edits: list[dict]) -> dict:
    lines = SETTINGS.read_text(encoding="utf-8", errors="replace").splitlines(True)
    by_line = {int(edit["line"]): str(edit["value"]) for edit in edits}
    saved = 0
    for line_number, value in by_line.items():
        if not 0 <= line_number < len(lines):
            continue
        line = lines[line_number]
        match = re.match(r"^([^=]+?=\s*)([^;#\r\n]*)(.*)$", line)
        if not match:
            continue
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        tail = match.group(3).rstrip("\r\n")
        lines[line_number] = match.group(1) + value + tail + newline
        saved += 1
    backup = SETTINGS.with_suffix(".ini.lexeditor.bak")
    backup.write_bytes(SETTINGS.read_bytes())
    SETTINGS.write_text("".join(lines), encoding="utf-8")
    return {"saved": saved, "backup": str(backup)}


ITEM_FIELD_NAMES = ("id", "name", "meshes", "flags", "capabilities", "value", "stats", "modifierBits", "factions")


def _module_items_source() -> tuple[str, str, bytes]:
    source = MODULE_SYSTEM / "module_items.py"
    raw = source.read_bytes()
    for encoding in ("utf-8", "cp1254", "latin1"):
        try:
            return raw.decode(encoding), encoding, raw
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1"), "latin1", raw


def _skip_python_string(text: str, index: int) -> int:
    quote = text[index]
    triple = text.startswith(quote * 3, index)
    delimiter = quote * (3 if triple else 1)
    cursor = index + len(delimiter)
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text.startswith(delimiter, cursor):
            return cursor + len(delimiter)
        cursor += 1
    raise ValueError("Unterminated Python string in module_items.py")


def _item_record_spans(text: str) -> list[tuple[int, int]]:
    match = re.search(r"(?m)^\s*items\s*=\s*\[", text)
    if not match:
        raise ValueError("module_items.py does not contain an items = [...] list")
    outer = text.find("[", match.start(), match.end())
    depth = 1
    record_start = None
    spans: list[tuple[int, int]] = []
    cursor = outer + 1
    while cursor < len(text):
        char = text[cursor]
        if char in "'\"":
            cursor = _skip_python_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\n", cursor)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if char == "[":
            if depth == 1:
                record_start = cursor
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 1 and record_start is not None:
                spans.append((record_start, cursor + 1))
                record_start = None
            elif depth == 0:
                return spans
            if depth < 0:
                break
        cursor += 1
    raise ValueError("module_items.py has an unterminated items list")


def _split_item_fields(text: str, start: int, end: int) -> list[tuple[int, int]]:
    fields: list[tuple[int, int]] = []
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = start + 1
    field_start = cursor
    while cursor < end - 1:
        char = text[cursor]
        if char in "'\"":
            cursor = _skip_python_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\n", cursor, end)
            cursor = end - 1 if newline < 0 else newline + 1
            continue
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError("Unbalanced item expression in module_items.py")
            stack.pop()
        elif char == "," and not stack:
            left, right = field_start, cursor
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                fields.append((left, right))
            field_start = cursor + 1
        cursor += 1
    left, right = field_start, end - 1
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if left < right:
        fields.append((left, right))
    if stack:
        raise ValueError("Unbalanced item expression in module_items.py")
    return fields


def _literal_string(expression: str, field: str, record_index: int) -> str:
    try:
        value = ast.literal_eval(expression)
    except Exception as error:
        raise ValueError(f"Item {record_index} has an invalid {field} string") from error
    if not isinstance(value, str):
        raise ValueError(f"Item {record_index} {field} must be a string")
    return value


def _item_records(text: str) -> list[dict]:
    records: list[dict] = []
    mesh_entry = re.compile(r"\(\s*['\"]([^'\"]+)['\"]\s*,")
    for record_index, (start, end) in enumerate(_item_record_spans(text)):
        spans = _split_item_fields(text, start, end)
        if len(spans) < 8:
            raise ValueError(f"Item record {record_index} has only {len(spans)} fields")
        expressions = [text[left:right].strip() for left, right in spans]
        field_order = list(ITEM_FIELD_NAMES[:len(expressions)])
        if len(expressions) > len(ITEM_FIELD_NAMES):
            field_order += [f"extra{index + 1}" for index in range(len(expressions) - len(ITEM_FIELD_NAMES))]
        fields = dict(zip(field_order, expressions))
        fields["id"] = _literal_string(expressions[0], "id", record_index)
        fields["name"] = _literal_string(expressions[1], "name", record_index)
        meshes = mesh_entry.findall(fields.get("meshes", ""))
        flags = fields.get("flags", "")
        stats = fields.get("stats", "")
        item_type = re.search(r"\bitp_type_([a-z0-9_]+)\b", flags, re.I)
        weight = re.search(r"\bweight\(([^)]+)\)", stats)
        records.append({
            "recordIndex": record_index,
            "id": fields["id"],
            "name": fields["name"],
            "type": item_type.group(1) if item_type else "",
            "value": fields.get("value", ""),
            "weight": weight.group(1).strip() if weight else "",
            "line": text.count("\n", 0, start) + 1,
            "meshes": meshes,
            "inventoryMesh": meshes[0] if meshes else "",
            "fields": fields,
            "fieldOrder": field_order,
            "_fieldSpans": spans,
        })
    return records


def item_rows() -> list[dict]:
    source = MODULE_SYSTEM / "module_items.py"
    if not source.is_file():
        return []
    text, _encoding, _raw = _module_items_source()
    rows = []
    for record in _item_records(text):
        rows.append({key: value for key, value in record.items() if not key.startswith("_")})
    return rows


def _validate_item_expression(expression: str) -> str:
    expression = str(expression).strip()
    if not expression:
        raise ValueError("Item expressions cannot be empty")
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = 0
    while cursor < len(expression):
        char = expression[cursor]
        if char in "'\"":
            cursor = _skip_python_string(expression, cursor)
            continue
        if char == "#":
            newline = expression.find("\n", cursor)
            cursor = len(expression) if newline < 0 else newline + 1
            continue
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError("Unbalanced item expression")
            stack.pop()
        elif char == "," and not stack:
            raise ValueError("A single item field cannot contain a top-level comma")
        cursor += 1
    if stack:
        raise ValueError("Unbalanced item expression")
    return expression


def _python_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _validate_module_items_candidate(text: str, encoding: str) -> bytes:
    records = _item_records(text)
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Saving would create duplicate item IDs")
    encoded = text.encode(encoding)
    python27 = Path(r"C:\Python27\python.exe")
    if python27.is_file():
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temporary:
            temporary.write(encoded)
            temporary_path = Path(temporary.name)
        try:
            check = subprocess.run(
                [str(python27), "-c", "import sys; compile(open(sys.argv[1],'rb').read(),sys.argv[1],'exec')", str(temporary_path)],
                capture_output=True, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if check.returncode:
                raise ValueError((check.stderr or check.stdout).strip())
        finally:
            temporary_path.unlink(missing_ok=True)
    return encoded


def save_item_edits(edits: list[dict]) -> dict:
    source = MODULE_SYSTEM / "module_items.py"
    if not source.is_file():
        raise FileNotFoundError(source)
    if not edits:
        return {"saved": 0, "backup": ""}
    text, encoding, raw = _module_items_source()
    records = _item_records(text)
    by_index = {record["recordIndex"]: record for record in records}
    replacements: list[tuple[int, int, str]] = []
    edited_records: set[int] = set()
    for edit in edits:
        record_index = int(edit.get("recordIndex", -1))
        record = by_index.get(record_index)
        if record is None:
            raise ValueError(f"Item record {record_index} no longer exists")
        original_id = str(edit.get("originalId", ""))
        if original_id and original_id != record["id"]:
            raise ValueError(f"Item record {record_index} changed from {original_id} to {record['id']}; reload before saving")
        field_order = record["fieldOrder"]
        for field, value in dict(edit.get("fields") or {}).items():
            if field not in field_order:
                raise ValueError(f"Item {record['id']} has no field named {field}")
            if field == "id":
                value = str(value).strip()
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                    raise ValueError("Item IDs must contain only letters, digits, and underscores and cannot start with a digit")
                replacement = _python_string(value)
            elif field == "name":
                replacement = _python_string(str(value))
            else:
                replacement = _validate_item_expression(str(value))
            field_index = field_order.index(field)
            left, right = record["_fieldSpans"][field_index]
            replacements.append((left, right, replacement))
            edited_records.add(record_index)
    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    candidate_records = _item_records(candidate)
    if len(candidate_records) != len(records):
        raise ValueError("Saving changed the number of item records; refusing the write")
    encoded = _validate_module_items_candidate(candidate, encoding)
    backup = source.with_name(source.name + ".lexeditor.bak")
    backup.write_bytes(raw)
    source.write_bytes(encoded)
    return {"saved": len(edited_records), "backup": str(backup)}


def upgrade_rows() -> list[dict]:
    source = MODULE_SYSTEM / "module_troops.py"
    if not source.is_file():
        return []
    names = {row["id"]: row["name"] for row in parse_troops(str(source))}
    pattern = re.compile(r'^\s*(upgrade2?)\(troops,\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?')
    rows = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        match = pattern.match(line)
        if not match:
            continue
        kind, parent, first, second = match.groups()
        targets = [first] + ([second] if second else [])
        for branch, target in enumerate(targets, 1):
            rows.append({
                "fromId": parent,
                "from": f"{names.get(parent, parent)}  [{parent}]",
                "toId": target,
                "to": f"{names.get(target, target)}  [{target}]",
                "branch": f"{branch}/{len(targets)}" if kind == "upgrade2" else "1/1",
                "line": line_number,
            })
    return rows


def modules() -> list[str]:
    """Every installed Warband module.

    module.ini is what makes a folder a module; info_pages.txt is optional
    content. Filtering on the manual meant a module that ships no info pages
    vanished from the list with nothing said about it.
    """
    if not MODULES.is_dir():
        return []
    return [entry.name for entry in sorted(MODULES.iterdir())
            if entry.is_dir() and (entry / "module.ini").is_file()]


def modules_with_manual() -> list[str]:
    """Modules that actually ship an in-game manual."""
    return [name for name in modules()
            if (MODULES / name / "info_pages.txt").is_file()]


def data_map_rows() -> dict:
    """Describe actual user-facing capabilities, not merely file I/O support."""
    rows = []
    browsers = {"module_troops.py": "troops"}
    for area, records in DATA_CATALOG.items():
        for filename, controls in records:
            source = resolve_catalog_file(filename)
            source_available = source is not None and source.is_file()
            view = ""
            if filename == "settings.ini" and source_available:
                coverage, status, view = "structured", "integrated", "tweaks"
                notes = "Setting values can be edited in Tweaks. The complete file is also available as source."
            elif filename == "module_items.py" and source_available:
                coverage, status, view = "structured", "integrated", "items"
                notes = "Structured item records can be edited in Items. The complete Module System source remains available for fields Lexeditor does not interpret."
            elif filename in browsers and source_available:
                coverage, status, view = "view", "partial", browsers[filename]
                notes = "Read-only record browser. Changing records currently requires editing the Python source; this is not a structured data editor."
            elif source_available:
                coverage, status = "source", "partial"
                notes = "Source-only editing with a backup. No dedicated record editor. Python syntax validation requires the installed Python 2 validator."
            elif filename in {"Resource/*.brf", "Textures/*.dds"}:
                coverage, status, view = "view", "partial", "items"
                notes = "Read-only installed item preview dependencies. Availability is checked per mesh, material and texture; binary editing is not supported."
            else:
                coverage, status = "unavailable", "not-integrated"
                notes = ("This source file is not present in the selected project. Installed compiled modules do not supply Module System source."
                         if area != "Generated output" else
                         "No dedicated editor. Compiled text is generated by the Module System; scenes require Warband's scene editor.")
            rows.append({"filename": filename, "controls": controls, "notes": notes,
                         "status": status, "coverage": coverage, "view": view,
                         "openable": source_available, "sourceOpenable": source_available,
                         "openLabel": "Edit source (not a structured editor)" if source_available else ""})
    rows.sort(key=lambda row: row["filename"].casefold())
    return {"rows": rows, "counts": {status: sum(row["status"] == status for row in rows)
            for status in ("integrated", "partial", "not-integrated")}, "path": str(MODULE_SYSTEM)}


def resolve_catalog_file(filename: str) -> Path | None:
    known = {name for records in DATA_CATALOG.values() for name, _description in records}
    if filename not in known or "*" in filename or filename.endswith((".sco", ".brf", ".dds")):
        return None
    if filename == "settings.ini":
        return SETTINGS if SETTINGS.is_file() else None
    if filename == "module.ini":
        root = PROJECT if (PROJECT / "module.ini").is_file() else PROJECT / "Module"
        target = root / "module.ini"
        return target if target.is_file() else None
    candidate = (MODULE_SYSTEM / filename).resolve()
    if candidate.parent != MODULE_SYSTEM.resolve() or not candidate.is_file():
        return None
    return candidate


def read_catalog_file(filename: str) -> dict:
    path = resolve_catalog_file(filename)
    if path is None:
        return {"filename": filename, "editable": False, "text": "", "reason": "This catalog row is a generated or binary group."}
    raw = path.read_bytes()
    encoding = "latin1"
    text = raw.decode(encoding)
    for candidate in ("utf-8", "cp1254"):
        try:
            text = raw.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            pass
    return {"filename": filename, "editable": True, "path": str(path), "encoding": encoding, "text": text}


def save_catalog_file(filename: str, text: str, encoding: str) -> dict:
    path = resolve_catalog_file(filename)
    if path is None:
        raise ValueError("This catalog row is not an editable text file")
    encoded = text.encode(encoding)
    if path.suffix.casefold() == ".py":
        python27 = Path(r"C:\Python27\python.exe")
        if python27.is_file():
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temporary:
                temporary.write(encoded)
                temporary_path = Path(temporary.name)
            try:
                check = subprocess.run(
                    [str(python27), "-c", "import sys; compile(open(sys.argv[1],'rb').read(),sys.argv[1],'exec')", str(temporary_path)],
                    capture_output=True, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if check.returncode:
                    raise ValueError((check.stderr or check.stdout).strip())
            finally:
                temporary_path.unlink(missing_ok=True)
    backup = path.with_name(path.name + ".lexeditor.bak")
    backup.write_bytes(path.read_bytes())
    path.write_bytes(encoded)
    return {"saved": 1, "backup": str(backup)}


class BuildState:
    def __init__(self):
        self.lock = threading.Lock()
        self.lines: list[str] = []
        self.running = False
        self.return_code: int | None = None

    def start(self) -> dict:
        with self.lock:
            if self.running:
                return {"started": False, "reason": "A build is already running"}
            if not BUILD.is_file():
                raise FileNotFoundError(BUILD)
            self.lines = [f"> {BUILD}\n"]
            self.running = True
            self.return_code = None
        threading.Thread(target=self._run, daemon=True).start()
        return {"started": True}

    def _run(self) -> None:
        environment = os.environ.copy()
        environment["LEXERMOD_NOPAUSE"] = "1"
        process = subprocess.Popen(
            ["cmd.exe", "/d", "/c", str(BUILD)], cwd=str(PROJECT), env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert process.stdout
        for line in process.stdout:
            with self.lock:
                self.lines.append(line)
        process.wait()
        with self.lock:
            self.return_code = process.returncode
            self.lines.append(f"\n[exit {process.returncode}]\n")
            self.running = False

    def status(self, cursor: int) -> dict:
        with self.lock:
            return {"cursor": len(self.lines), "lines": self.lines[cursor:], "running": self.running, "returnCode": self.return_code}


BUILD_STATE = BuildState()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def json_response(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def file_response(self, path: Path):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/":
                self.file_response(PLUGIN_ROOT / "editor.html")
            elif path == "/warband/troop_trees.js":
                self.file_response(PLUGIN_ROOT / "troop_trees.js")
            elif path.startswith("/shared/"):
                shared_root = (LEXEDITOR_ROOT / "ui").resolve()
                target = (shared_root / path.removeprefix("/shared/")).resolve()
                if shared_root not in target.parents or not target.is_file():
                    self.json_response({"error": "shared UI asset not found"}, 404)
                else:
                    self.file_response(target)
            elif path == "/api/plugin":
                self.json_response({"apiVersion": 1, "pluginId": "warband", "name": "Mount & Blade: Warband", "hosted": HOSTED, "windowHost": WINDOW_HOST, "projectRoot": str(PROJECT), "editorRoot": str(PLUGIN_ROOT), "capabilities": ["build", "catalog", "data-map", "game-font", "item-edit", "item-preview", "items", "manuals", "settings", "troops", "upgrades"]})
            elif path == "/api/dashboard":
                self.json_response({"paths": {"Project": str(PROJECT), "Module System": str(MODULE_SYSTEM), "Game": paths.WARBAND_ROOT, "Installed modules": str(MODULES)}, "problems": paths.check()})
            elif path == "/api/settings":
                self.json_response({"file": str(SETTINGS), "rows": settings_rows()})
            elif path == "/api/troops":
                self.json_response({"rows": (parse_troops(str(MODULE_SYSTEM / "module_troops.py")) if (MODULE_SYSTEM / "module_troops.py").is_file() else [])})
            elif path == "/api/items":
                self.json_response({"rows": item_rows()})
            elif path == "/api/warband-font":
                self.json_response(font_manifest())
            elif path == "/api/warband-font/atlas":
                target = font_atlas_path()
                if target is None:
                    self.json_response({"error": "installed Warband font atlas not found"}, 404)
                else:
                    self.file_response(target)
            elif path == "/api/item-icon":
                target = ICON_CACHE.request(query.get("mesh", [""])[0])
                if target is None:
                    self.json_response({"pending": True, "retryAfterMs": 500}, 202)
                else:
                    self.file_response(target)
            elif path == "/api/item-preview":
                mesh = query.get("mesh", [""])[0]
                self.json_response(item_preview(mesh))
            elif path == "/api/item-preview/texture":
                target = preview_texture_path(query.get("key", [""])[0])
                if target is None:
                    self.json_response({"error": "preview texture not found"}, 404)
                else:
                    self.file_response(target)
            elif path == "/api/upgrades":
                self.json_response({"rows": upgrade_rows()})
            elif path == "/api/modules":
                self.json_response({"modules": modules()})
            elif path == "/api/manual":
                name = query.get("module", [""])[0]
                if name not in modules():
                    raise ValueError("Unknown installed module")
                manual = MODULES / name / "info_pages.txt"
                self.json_response({"module": name, "hasManual": manual.is_file(),
                                    "pages": parse_info_pages(str(manual)) if manual.is_file() else []})
            elif path == "/api/catalog":
                self.json_response({"areas": [{"name": area, "files": [{"name": name, "description": description} for name, description in rows]} for area, rows in DATA_CATALOG.items()]})
            elif path == "/api/datamap":
                self.json_response(data_map_rows())
            elif path == "/api/catalog/file":
                self.json_response(read_catalog_file(query.get("name", [""])[0]))
            elif path == "/api/build/status":
                self.json_response(BUILD_STATE.status(int(query.get("cursor", ["0"])[0])))
            else:
                self.json_response({"error": "not found"}, 404)
        except PreviewUnavailable as error:
            self.json_response({"error": str(error), "available": False}, 422)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.body()
            if path == "/api/settings/save":
                self.json_response(save_settings(body.get("edits", [])))
            elif path == "/api/items/save":
                self.json_response(save_item_edits(body.get("edits", [])))
            elif path == "/api/catalog/file/save":
                self.json_response(save_catalog_file(body.get("filename", ""), body.get("text", ""), body.get("encoding", "utf-8")))
            elif path == "/api/build/start":
                self.json_response(BUILD_STATE.start())
            else:
                self.json_response({"error": "not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    ICON_CACHE.warm(row["inventoryMesh"] for row in item_rows())
    return server


if __name__ == "__main__":
    create_server().serve_forever()
