"""Loopback service for the Factorio structured prototype editor."""

from __future__ import annotations

import copy
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse

from core.plugin_http import PluginRequestHandler

from .data_map import build_data_map
from .model import (
    FactorioDataError, ITEM_TYPES, KINDS, MACHINE_TYPES, OVERRIDES_FILE, PROJECT_FILE,
    SOURCE_DIR, SOURCE_DUMP, PrototypeStore, active_mods, detect_install,
    export_dependencies, export_mod, project_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.environ.get(
    "LEXEDITOR_FACTORIO_PROJECT",
    Path(os.environ.get("LOCALAPPDATA", ROOT / "out")) / "Lexeditor" / "projects" / "factorio" / "LexeditorFactorioMod",
)).expanduser().resolve()
GAME_ROOT_VALUE = os.environ.get("FACTORIO_GAME_ROOT", "").strip()
GAME_ROOT = Path(GAME_ROOT_VALUE).expanduser().resolve() if GAME_ROOT_VALUE else None
FACTORIO_FONT_FILES = frozenset({
    "TitilliumWeb-Regular.ttf",
    "TitilliumWeb-SemiBold.ttf",
    "TitilliumWeb-Bold.ttf",
})
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY = 2 * 1024 * 1024
_lock = threading.RLock()
_store: PrototypeStore | None = None
_dirty = 0
_source_fingerprint = ""
_saved_edits: dict = {}


def _fingerprint(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_path() -> Path:
    return PROJECT_ROOT / SOURCE_DIR / SOURCE_DUMP


def _snapshot_edits(store: PrototypeStore) -> dict:
    return copy.deepcopy(store.overrides.get("edits", {}))


def _dirty_records(store: PrototypeStore) -> int:
    current = store.overrides.get("edits", {})
    kinds = set(_saved_edits) | set(current)
    return sum(
        _saved_edits.get(kind, {}).get(name) != current.get(kind, {}).get(name)
        for kind in kinds
        for name in set(_saved_edits.get(kind, {})) | set(current.get(kind, {}))
    )


def _load_store(*, refresh: bool = False) -> PrototypeStore:
    global _store, _source_fingerprint, _saved_edits, _dirty
    with _lock:
        if _store is None or refresh:
            _store = PrototypeStore.from_project(PROJECT_ROOT)
            _source_fingerprint = _fingerprint(_source_path())
            _saved_edits = _snapshot_edits(_store)
            _dirty = 0
        return _store


def _require_source_unchanged() -> None:
    current = _fingerprint(_source_path())
    if not current or current != _source_fingerprint:
        raise FactorioDataError(
            "The imported Factorio prototype dump changed after this editor opened. "
            "Discard/reopen before saving or exporting."
        )


def _require_supported_install() -> None:
    # Normal desktop use always supplies a configured game root. The synthetic
    # smoke path deliberately omits one, so it can exercise the plugin without
    # proprietary game files.
    if GAME_ROOT is None:
        return
    install = detect_install(GAME_ROOT)
    if not install.supported:
        raise FactorioDataError(
            f"Factorio {install.version or 'unknown'} is not supported; "
            "this plugin targets the 2.1.x prototype line."
        )


def _require_edit_context() -> None:
    project_manifest(PROJECT_ROOT)
    _require_supported_install()


def _row(store: PrototypeStore, kind: str, name: str) -> dict:
    for row in store.rows(kind):
        if row["name"] == name:
            return row
    raise FactorioDataError(f"Unknown {kind[:-1]} prototype: {name}")


def _install_payload() -> dict:
    if GAME_ROOT is None:
        return {
            "root": "", "version": "", "supported": False,
            "dlc": {"spaceAge": False, "quality": False, "elevatedRails": False},
            "state": "not-configured",
        }
    try:
        payload = detect_install(GAME_ROOT).as_dict()
        payload["state"] = "supported" if payload["supported"] else "unsupported-version"
        return payload
    except FactorioDataError as error:
        return {
            "root": str(GAME_ROOT), "version": "", "supported": False,
            "dlc": {"spaceAge": False, "quality": False, "elevatedRails": False},
            "state": "invalid", "error": str(error),
        }


def _config() -> dict:
    try:
        manifest = project_manifest(PROJECT_ROOT)
        manifest_error = ""
    except FactorioDataError as error:
        manifest = {}
        manifest_error = str(error)
    source = _source_path()
    source_ready = source.is_file()
    counts = {kind: 0 for kind in KINDS}
    unsupported_prototypes: dict[str, int] = {}
    diagnostics: list[dict] = []
    source_error = ""
    if source_ready:
        try:
            store = _load_store()
            counts = {kind: len(store.rows(kind)) for kind in KINDS}
            modeled_types = set(ITEM_TYPES) | set(MACHINE_TYPES) | {
                "recipe", "technology", "fluid", "recipe-category",
            }
            unsupported_prototypes = {
                prototype_type: len(records)
                for prototype_type, records in store.raw.items()
                if prototype_type not in modeled_types
            }
            diagnostics = store.diagnostics()
        except FactorioDataError as error:
            source_error = str(error)
    mods: list[str] = []
    try:
        mods = active_mods(PROJECT_ROOT)
    except FactorioDataError as error:
        diagnostics.append({"severity": "error", "record": "mod-list.json", "message": str(error)})
    authored = (((manifest.get("mod") or {}).get("dependencies") or [])
                if isinstance(manifest, dict) else [])
    try:
        dependencies = (
            export_dependencies(
                PROJECT_ROOT, list(authored),
                exclude={str((manifest.get("mod") or {}).get("name", ""))},
            )
            if manifest else []
        )
    except FactorioDataError as error:
        dependencies = []
        diagnostics.append({"severity": "error", "record": PROJECT_FILE, "message": str(error)})
    install = _install_payload()
    source_space_age = "space-age" in mods
    return {
        "pluginId": "factorio",
        "projectRoot": str(PROJECT_ROOT),
        "project": manifest,
        "projectError": manifest_error,
        "source": {
            "path": str(source),
            "ready": source_ready and not source_error,
            "error": source_error,
            "immutable": True,
            "command": "factorio.exe --dump-data",
            "stage": "post source-mod prototype lifecycle snapshot",
        },
        "counts": counts,
        "unsupportedPrototypeCounts": unsupported_prototypes,
        "diagnostics": diagnostics,
        "activeMods": mods,
        "exportDependencies": dependencies,
        "install": install,
        "support": {
            "factorio": "2.1.x",
            "prototypeDocs": "2.1.20 reviewed",
            "spaceAgeInstalled": bool(install.get("dlc", {}).get("spaceAge")),
            "spaceAgeActiveInSource": source_space_age,
            "spaceAgeEditable": source_space_age,
        },
        "dirty": _dirty,
        "overridePath": str(PROJECT_ROOT / OVERRIDES_FILE),
        "buildRoot": str(PROJECT_ROOT / "build"),
    }


class Handler(PluginRequestHandler):
    def _body(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= MAX_BODY:
            raise FactorioDataError("Request body must be between 1 byte and 2 MB")
        try:
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise FactorioDataError("Request body must be valid UTF-8 JSON") from error
        if not isinstance(payload, dict):
            raise FactorioDataError("Request body must be a JSON object")
        return payload

    def _same_origin(self) -> bool:
        port = self.server.server_address[1]
        host = self.headers.get("Host", "").casefold()
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origin = self.headers.get("Origin")
        return host in allowed and (origin is None or origin == f"http://{host}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/plugin":
                self.send_json({
                    "apiVersion": 1, "pluginId": "factorio", "name": "Factorio",
                    "hosted": True, "windowHost": "webview2",
                    "projectRoot": str(PROJECT_ROOT),
                    "capabilities": [
                        "prototype-json-import", "structured-overrides",
                        "factorio-mod-export", "data-map",
                    ],
                })
            elif path == "/api/config":
                self.send_json(_config())
            elif path == "/api/data":
                query = parse_qs(parsed.query)
                kind = (query.get("kind") or [""])[0]
                if kind not in KINDS:
                    raise FactorioDataError("Choose recipes, items, machines, or technologies")
                store = _load_store()
                self.send_json({"kind": kind, "rows": store.rows(kind)})
            elif path == "/api/datamap":
                config = _config()
                self.send_json(build_data_map(
                    PROJECT_ROOT,
                    counts=config["counts"],
                    diagnostics=config["diagnostics"],
                    unsupported_prototypes=config["unsupportedPrototypeCounts"],
                ))
            elif path == "/":
                self.send_file(PLUGIN_ROOT / "editor.html")
            elif path.startswith("/game-assets/"):
                name = path.removeprefix("/game-assets/")
                if GAME_ROOT is None or name not in FACTORIO_FONT_FILES:
                    self.send_json({"error": "Factorio theme asset not available"}, 404)
                else:
                    target = GAME_ROOT / "data" / "core" / "fonts" / name
                    if target.is_file():
                        self.send_file(target)
                    else:
                        self.send_json({"error": "Factorio theme asset not available"}, 404)
            elif self.send_page_module(PLUGIN_ROOT, path):
                return
            elif path.startswith("/shared/"):
                shared = (ROOT / "ui").resolve()
                target = (shared / path.removeprefix("/shared/")).resolve()
                if shared in target.parents and target.is_file():
                    self.send_file(target)
                else:
                    self.send_json({"error": "Shared UI asset not found"}, 404)
            else:
                self.send_json({"error": "Not found"}, 404)
        except FactorioDataError as error:
            self.send_json({"error": str(error)}, 409)
        except OSError as error:
            self.send_json({"error": str(error)}, 500)

    def do_POST(self):
        global _dirty, _store, _source_fingerprint, _saved_edits
        path = urlparse(self.path).path
        if self.refuse_write_when_read_only(path):
            return
        if not self._same_origin():
            self.send_json({"error": "Cross-origin writes are not permitted"}, 403)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                self.send_json({"error": "An application/json request is required"}, 415)
                return
            if self.headers.get("Transfer-Encoding"):
                self.send_json({"error": "Chunked requests are not supported"}, 400)
                return
            body = self._body()
            if path == "/api/edit":
                _require_edit_context()
                kind = body.get("kind")
                name = body.get("name")
                if kind not in KINDS or not isinstance(name, str):
                    raise FactorioDataError("Edit must identify one supported prototype")
                store = _load_store()
                _require_source_unchanged()
                changes = store.set_edit(kind, name, body.get("changes", {}))
                _dirty = _dirty_records(store)
                self.send_json({
                    "changed": bool(changes),
                    "dirty": _dirty,
                    "row": _row(store, kind, name),
                })
            elif path == "/api/save":
                _require_edit_context()
                store = _load_store()
                _require_source_unchanged()
                store.save(PROJECT_ROOT)
                _saved_edits = _snapshot_edits(store)
                _dirty = 0
                self.send_json({"saved": True, "dirty": 0, "path": str(PROJECT_ROOT / OVERRIDES_FILE)})
            elif path == "/api/discard":
                _store = PrototypeStore.from_project(PROJECT_ROOT)
                _source_fingerprint = _fingerprint(_source_path())
                _saved_edits = _snapshot_edits(_store)
                _dirty = 0
                self.send_json({"discarded": True, "dirty": 0})
            elif path == "/api/export":
                _require_edit_context()
                store = _load_store()
                _require_source_unchanged()
                target = export_mod(PROJECT_ROOT, store=store)
                payload = target.read_bytes()
                self.send_json({
                    "exported": True,
                    "path": str(target),
                    "filename": target.name,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "gameLoaded": False,
                    "message": "Candidate built only; install/load it in Factorio for real-game acceptance.",
                })
            elif path == "/api/reopen":
                _store = PrototypeStore.from_project(PROJECT_ROOT)
                _source_fingerprint = _fingerprint(_source_path())
                _saved_edits = _snapshot_edits(_store)
                _dirty = 0
                self.send_json({"reopened": True, "dirty": 0, "config": _config()})
            else:
                self.send_json({"error": "Not found"}, 404)
        except FactorioDataError as error:
            self.send_json({"error": str(error)}, 400)
        except OSError as error:
            self.send_json({"error": str(error)}, 500)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
