"""Loopback service for the Dark Souls III parameter editor."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from plugin_files import atomic_write
from plugin_http import PluginRequestHandler

from .formats import DS3FormatError, RegulationDocument, TARGET_TABLES


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
METADATA_ROOT = PLUGIN_ROOT / "metadata"
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
PROJECT = Path(os.environ.get(
    "LEXEDITOR_DS3_PROJECT",
    str(Path.home() / "Lexeditor Mods" / "Dark Souls III"),
)).expanduser()
GAME_ROOT = Path(os.environ.get(
    "LEXEDITOR_DS3_ROOT",
    r"C:\Program Files (x86)\Steam\steamapps\common\DARK SOULS III",
)).expanduser()
SOURCE_OVERRIDE = os.environ.get("LEXEDITOR_DS3_SOURCE", "").strip()
PROJECT_MARKER = ".lexeditor-ds3-project"
MAX_JSON_BYTES = 256 * 1024

TABLE_LABELS = {
    "EquipParamWeapon": "Weapons",
    "EquipParamProtector": "Armor",
    "EquipParamAccessory": "Rings",
    "Magic": "Spells",
    "SpEffectParam": "Effects",
    "NpcParam": "Enemies",
}

_LOCK = threading.RLock()
_DOCUMENT: RegulationDocument | None = None
_SOURCE_PATH: Path | None = None
_SOURCE_HASH: str | None = None
_OUTPUT_HASH_AT_LOAD: str | None = None


def _path_within(path: Path, root: Path) -> bool:
    candidate = Path(path).resolve()
    boundary = Path(root).resolve()
    return candidate == boundary or boundary in candidate.parents


def _project_output() -> Path:
    return PROJECT / "Data0.bdt"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_candidates() -> list[Path]:
    candidates = [_project_output()]
    if SOURCE_OVERRIDE:
        candidates.append(Path(SOURCE_OVERRIDE).expanduser())
    candidates.append(GAME_ROOT / "Game" / "Data0.bdt")
    return candidates


def _find_source() -> Path:
    for candidate in _source_candidates():
        if candidate.is_file():
            return candidate.resolve()
    expected = ", ".join(str(path) for path in _source_candidates())
    raise FileNotFoundError(f"No Dark Souls III Data0.bdt source found. Checked: {expected}")


def _reload() -> RegulationDocument:
    global _DOCUMENT, _SOURCE_PATH, _SOURCE_HASH, _OUTPUT_HASH_AT_LOAD
    source = _find_source()
    raw = source.read_bytes()
    _DOCUMENT = RegulationDocument(raw, METADATA_ROOT)
    _SOURCE_PATH = source
    _SOURCE_HASH = hashlib.sha256(raw).hexdigest()
    output = _project_output()
    _OUTPUT_HASH_AT_LOAD = _sha256_path(output) if output.is_file() else None
    return _DOCUMENT


def _document() -> RegulationDocument:
    global _DOCUMENT
    with _LOCK:
        return _DOCUMENT if _DOCUMENT is not None else _reload()


def _state() -> dict:
    document = _document()
    return {
        "source": str(_SOURCE_PATH or ""),
        "project": str(PROJECT.resolve()),
        "output": str(_project_output().resolve()),
        "dirtyCount": document.dirty_count,
        "archiveMembers": document.binder.file_count,
        "tables": [
            {
                "id": table,
                "label": TABLE_LABELS[table],
                "rows": len(document.params[table].rows),
                "paramType": document.schemas[table].param_type,
                "dataVersion": document.schemas[table].data_version,
            }
            for table in TARGET_TABLES
        ],
        "target": {
            "platform": "PC / Steam",
            "appVersion": "1.15.2",
            "regulationVersion": "1.35",
            "paramdefDataVersion": 201,
        },
        "realGameVerified": False,
    }


def _data_map() -> dict:
    rows = []
    for table in TARGET_TABLES:
        rows.append({
            "id": f"data0:{table}",
            "filename": "Game/Data0.bdt",
            "controls": f"{TABLE_LABELS[table]} — {table}.param",
            "notes": (
                "Structured editing uses pinned Smithbox PARAMDEF, field-layout, annotation, "
                "enum, reference, and row-name metadata. Only audited fixed-width cells are changed."
            ),
            "coverage": "structured",
            "status": "integrated",
            "targets": [{"id": table, "label": TABLE_LABELS[table]}],
        })
    rows.append({
        "id": "data0:other",
        "filename": "Game/Data0.bdt",
        "controls": "Other regulation parameters",
        "notes": (
            "Not exposed yet. Their archive bytes are retained unchanged when an integrated "
            "field is edited and exported. Maps, models, text, events, and 3D editing remain "
            "later scope rather than being represented as a generic raw-file editor."
        ),
        "coverage": "unavailable",
        "status": "not-integrated",
    })
    return {"rows": rows}


def _info() -> dict:
    state = _state()
    return {
        **state,
        "loading": {
            "source": "Installed Game/Data0.bdt until the project has a saved Data0.bdt.",
            "output": "Save writes only <project>/Data0.bdt with an atomic replace.",
            "runtime": (
                "Lexeditor does not install, configure, or enable a DS3 mod loader in this plugin. "
                "A loader must be configured separately for offline acceptance."
            ),
        },
        "safety": (
            "Installed game files are read-only. No online, anti-cheat, executable, save, "
            "or game-install setting is changed."
        ),
    }


def _read_json(handler: PluginRequestHandler) -> dict:
    origin = handler.headers.get("Origin")
    if origin and origin != f"http://{handler.headers.get('Host')}":
        raise PermissionError("Cross-origin writes are not permitted")
    size = int(handler.headers.get("Content-Length", "0"))
    if not 0 < size <= MAX_JSON_BYTES:
        raise ValueError("Request body is empty or too large")
    value = json.loads(handler.rfile.read(size))
    if not isinstance(value, dict):
        raise ValueError("JSON body must be an object")
    return value


def _save() -> dict:
    global _DOCUMENT
    with _LOCK:
        document = _document()
        if _path_within(PROJECT, GAME_ROOT):
            raise ValueError(
                f"DS3 projects must stay outside the game installation: {PROJECT}"
            )
        if not PROJECT.is_dir() or not (PROJECT / PROJECT_MARKER).is_file():
            raise FileNotFoundError(
                f"Selected DS3 project is missing {PROJECT_MARKER}: {PROJECT}"
            )
        destination = _project_output()
        if _SOURCE_PATH is None or _SOURCE_HASH is None:
            raise RuntimeError("DS3 source state is unavailable; reopen the editor before saving")
        if not _SOURCE_PATH.is_file() or _sha256_path(_SOURCE_PATH) != _SOURCE_HASH:
            raise ValueError(
                "DS3 source Data0.bdt changed after it was opened; discard/reopen before exporting."
            )
        current_output_hash = _sha256_path(destination) if destination.is_file() else None
        if _OUTPUT_HASH_AT_LOAD is None:
            if current_output_hash is not None:
                raise ValueError(
                    "DS3 project Data0.bdt was created externally after this editor opened; "
                    "discard/reopen before exporting."
                )
        elif current_output_hash != _OUTPUT_HASH_AT_LOAD:
            raise ValueError(
                "DS3 project Data0.bdt changed externally after this editor opened; "
                "discard/reopen before exporting."
            )
        atomic_write(destination, document.export())
        _DOCUMENT = None
        reloaded = _reload()
        return {
            "saved": True,
            "path": str(destination.resolve()),
            "dirtyCount": reloaded.dirty_count,
            "source": str(_SOURCE_PATH or ""),
        }


def _discard() -> dict:
    global _DOCUMENT
    with _LOCK:
        _DOCUMENT = None
        document = _reload()
        return {
            "discarded": True,
            "dirtyCount": document.dirty_count,
            "source": str(_SOURCE_PATH or ""),
        }


class Handler(PluginRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/":
                self.send_file(PLUGIN_ROOT / "editor.html")
            elif self.send_page_module(PLUGIN_ROOT, path):
                return
            elif path.startswith("/shared/"):
                shared = (ROOT / "ui").resolve()
                name = path.removeprefix("/shared/")
                target = (shared / name).resolve()
                if shared in target.parents and target.is_file():
                    self.send_file(target)
                elif name == "distribution-notices.json":
                    # Frozen builds may generate this optional shared file.
                    # Source/candidate builds have no generated package notices.
                    self.send_json([])
                else:
                    self.send_json({"error": "Shared UI asset not found"}, 404)
            elif path == "/api/plugin":
                self.send_json({
                    "apiVersion": 1,
                    "pluginId": "ds3",
                    "name": "Dark Souls III",
                    "hosted": True,
                    "windowHost": "webview2",
                    "capabilities": [
                        "params",
                        "project-export",
                        "data-map",
                        "byte-preserving-roundtrip",
                    ],
                })
            elif path == "/api/state":
                self.send_json(_state())
            elif path == "/api/info":
                self.send_json(_info())
            elif path == "/api/datamap":
                self.send_json(_data_map())
            elif path == "/api/table":
                table = str(query.get("name", [""])[0])
                if table not in TARGET_TABLES:
                    raise ValueError(f"Unsupported DS3 table: {table}")
                document = _document()
                self.send_json({
                    "table": table,
                    "label": TABLE_LABELS[table],
                    "rows": document.list_rows(table),
                    "dirtyCount": document.dirty_count,
                })
            elif path == "/api/row":
                table = str(query.get("table", [""])[0])
                row_id = int(query.get("id", [""])[0])
                if table not in TARGET_TABLES:
                    raise ValueError(f"Unsupported DS3 table: {table}")
                document = _document()
                self.send_json({
                    "table": table,
                    "row": document.read_row(table, row_id),
                    "dirtyCount": document.dirty_count,
                })
            else:
                self.send_json({"error": "Not found"}, 404)
        except (DS3FormatError, FileNotFoundError, OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = _read_json(self)
            if path == "/api/edit":
                table = str(payload.get("table", ""))
                row_id = int(payload.get("id"))
                field = str(payload.get("field", ""))
                if table not in TARGET_TABLES:
                    raise ValueError(f"Unsupported DS3 table: {table}")
                with _LOCK:
                    document = _document()
                    row = document.edit(table, row_id, field, payload.get("value"))
                    self.send_json({"row": row, "dirtyCount": document.dirty_count})
            elif path == "/api/save":
                self.send_json(_save())
            elif path == "/api/discard":
                self.send_json(_discard())
            else:
                self.send_json({"error": "Not found"}, 404)
        except PermissionError as error:
            self.send_json({"error": str(error)}, 403)
        except (DS3FormatError, FileNotFoundError, OSError, ValueError, TypeError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
