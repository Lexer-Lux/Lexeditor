"""Loopback editor service for FINAL FANTASY VII REMAKE INTERGRADE."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import parse_qs, urlparse

from .archive import build_index, preferred_pak_version
from .storage import load_package, save_edits
from .tooling import helper_status, pack_directory


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", os.environ.get("LEXEDITOR_FF7R_PORT", "0")))
GAME_ROOT = Path(os.environ.get("LEXEDITOR_FF7R_ROOT", ".")).expanduser().resolve()
DATA_ROOT = Path(os.environ.get("LEXEDITOR_FF7R_DATA_ROOT", ROOT / "out" / "ff7r-data")).expanduser().resolve()
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_FF7R_PROJECT", ROOT / "out" / "ff7r-project")).expanduser().resolve()
MAX_BODY = 16 * 1024 * 1024
_catalog_lock = threading.RLock()
_catalog_cache: dict | None = None


def catalog(*, refresh: bool = False) -> dict:
    global _catalog_cache
    with _catalog_lock:
        if refresh or _catalog_cache is None:
            _catalog_cache = build_index(GAME_ROOT, DATA_ROOT)
        return _catalog_cache


def data_payload(asset: str, *, vanilla: bool = False) -> dict:
    package, source_sha, using_project = load_package(
        GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset, vanilla=vanilla)
    return package.api_payload(source_sha256=source_sha, using_project=using_project)


def data_map_payload() -> dict:
    rows = []
    for item in catalog().get("assets", []):
        rows.append({
            "filename": item["asset"] + ".uasset / .uexp",
            "target": item["asset"],
            "controls": "Structured DataObject records; booleans, fixed-width numbers, floats and existing FNames are editable.",
            "notes": "FString text and size-changing edits are read-only; unknown bytes are preserved in the project overlay.",
            "coverage": "partial",
            "status": "partial",
        })
    return {"rows": rows}


def info_payload() -> dict:
    current = catalog()
    return {
        "gameRoot": str(GAME_ROOT),
        "dataRoot": str(DATA_ROOT),
        "projectRoot": str(PROJECT_ROOT),
        "dataObjects": len(current.get("assets", [])),
        "helper": helper_status(),
        "pakVersion": preferred_pak_version(current),
        "buildPath": str(PROJECT_ROOT / "build" / "Lexeditor-FF7R_P.pak"),
        "deployPath": str(GAME_ROOT / "End" / "Content" / "Paks" / "~mods" / "Lexeditor-FF7R_P.pak"),
    }


def build_mod() -> dict:
    content = PROJECT_ROOT / "content"
    if not content.is_dir() or not any(path.is_file() for path in content.rglob("*")):
        raise RuntimeError("The FF7R project has no saved DataObject edits to build")
    target = PROJECT_ROOT / "build" / "Lexeditor-FF7R_P.pak"
    pack_directory(content, target, version=preferred_pak_version(catalog()))
    return {"path": str(target), "size": target.stat().st_size}


def deploy_mod() -> dict:
    built = Path(build_mod()["path"])
    target = GAME_ROOT / "End" / "Content" / "Paks" / "~mods" / "Lexeditor-FF7R_P.pak"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(built, temporary)
    temporary.replace(target)
    return {"path": str(target), "size": target.stat().st_size}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200):
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

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length < 0 or length > MAX_BODY:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object")
        return payload

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/":
                return self.send_file(PLUGIN_ROOT / "editor.html")
            if path.startswith("/shared/"):
                shared = (ROOT / "ui").resolve()
                target = (shared / path.removeprefix("/shared/")).resolve()
                if shared in target.parents and target.is_file():
                    return self.send_file(target)
                return self.send_json({"error": "Shared UI asset not found"}, 404)
            if path == "/api/plugin":
                return self.send_json({
                    "apiVersion": 1,
                    "pluginId": "ff7r",
                    "name": "FINAL FANTASY VII REMAKE INTERGRADE",
                    "hosted": True,
                    "windowHost": "webview2",
                    "capabilities": ["data-map", "dataobject", "save", "build", "deploy"],
                })
            if path == "/api/catalog":
                return self.send_json(catalog(refresh=query.get("refresh") == ["1"]))
            if path == "/api/datamap":
                return self.send_json(data_map_payload())
            if path == "/api/info":
                return self.send_json(info_payload())
            if path == "/api/data":
                asset = (query.get("asset") or [""])[0]
                if not asset:
                    raise ValueError("asset is required")
                vanilla = (query.get("source") or [""])[0] == "vanilla"
                return self.send_json(data_payload(asset, vanilla=vanilla))
            return self.send_json({"error": "Not found"}, 404)
        except (ValueError, KeyError, IndexError) as error:
            return self.send_json({"error": str(error)}, 400)
        except Exception as error:
            return self.send_json({"error": str(error)}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            if path == "/api/save":
                asset = str(payload.get("asset", ""))
                edits = payload.get("edits", [])
                if not asset or not isinstance(edits, list):
                    raise ValueError("asset and edits are required")
                return self.send_json(save_edits(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
                    source_sha256=str(payload.get("sourceSha256", "")),
                    active_sha256=str(payload.get("activeSha256", "")),
                    edits=edits,
                ))
            if path == "/api/build":
                return self.send_json(build_mod())
            if path == "/api/deploy":
                return self.send_json(deploy_mod())
            return self.send_json({"error": "Not found"}, 404)
        except (ValueError, KeyError, IndexError, TypeError) as error:
            return self.send_json({"error": str(error)}, 400)
        except Exception as error:
            return self.send_json({"error": str(error)}, 500)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
