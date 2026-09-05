"""Loopback HTTP service for the Final Fantasy IX editor."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
import mimetypes
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from . import paths
from .memoria_csv import DATASETS, MemoriaDataStore, catalog
from .memoria_baseline import ensure as ensure_baseline
from . import memoria_manager
from platform_config import load_config, save_config


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")


UNRESOLVED_AREAS = (
    ("StreamingAssets/p0data*.bin", "Vanilla Unity asset containers", "Hades Workshop extraction is required; Lexeditor does not guess container offsets."),
    ("Battle scenes", "Enemies and encounters", "No editable Memoria battle-scene export is present."),
)


def _hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _steam_build() -> str | None:
    manifest = paths.GAME_ROOT.parent.parent / "appmanifest_377840.acf"
    if not manifest.is_file():
        return None
    match = re.search(r'"buildid"\s+"(\d+)"', manifest.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None


def data_map() -> dict:
    """Report exact Memoria files and unresolved vanilla containers."""
    integrated = []
    for row in catalog():
        integrated.append({
            "filename": row["relativePath"],
            "controls": row["controls"],
            "notes": f"{row['label']}. Writes a project overlay; the game baseline is never overwritten.",
            "status": "integrated" if row["available"] else "partial",
            "openable": row["available"],
            "target": row["tab"],
        })
    config = paths.GAME_ROOT / "Memoria.ini"
    return {
        "contract": "Lexeditor.data-map",
        "rows": integrated + [{
            "filename": "Memoria.ini", "controls": "Memoria engine, graphics, audio, battle and mod settings",
            "notes": "The Tweaks tab edits typed values in place and preserves comments and file order."
                     if config.is_file() else "Available after Memoria creates its configuration beside FF9_Launcher.exe.",
            "status": "integrated" if config.is_file() else "partial", "openable": config.is_file(),
            "target": "tweaks",
        }] + [{
            "filename": filename, "controls": controls, "notes": notes,
            "status": "not-integrated", "openable": False,
        } for filename, controls, notes in UNRESOLVED_AREAS],
    }


def dashboard() -> dict:
    problems = paths.game_problems()
    memoria = ensure_baseline()
    available = sum(1 for row in catalog() if row["available"])
    launcher = paths.GAME_ROOT / "FF9_Launcher.exe"
    player = paths.GAME_ROOT / "x64" / "FF9.exe"
    assembly = paths.GAME_ROOT / "x64" / "FF9_Data" / "Managed" / "Assembly-CSharp.dll"
    return {
        "game": {
            "root": str(paths.GAME_ROOT),
            "executable": str(launcher),
            "ready": not problems,
            "steamAppId": "377840",
            "steamBuildId": _steam_build(),
            "launcherSha256": _hash(launcher),
            "playerSha256": _hash(player),
            "assemblySha256": _hash(assembly),
        },
        "baseline": {
            "ready": available > 0,
            "fileCount": available,
            "message": (f"{available} Memoria CSV datasets are available."
                        if available else "The verified Memoria data baseline is not available yet."),
            "memoriaRelease": memoria["release"],
            "memoriaSource": memoria["source"],
            "problems": memoria["problems"],
        },
        "problems": problems,
        "project": {"root": str(paths.PROJECT_ROOT)},
        "runtime": memoria_manager.status(paths.GAME_ROOT),
        "scaffold": False,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorFF9/2"

    def log_message(self, _format, *_args):
        return

    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def file_response(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/":
                self.file_response(PLUGIN_ROOT / "editor.html")
            elif path.startswith("/shared/"):
                shared = (LEXEDITOR_ROOT / "ui").resolve()
                target = (shared / path.removeprefix("/shared/")).resolve()
                if shared not in target.parents or not target.is_file():
                    self.json_response({"error": "Shared UI asset not found"}, 404)
                else:
                    self.file_response(target)
            elif path == "/api/plugin":
                self.json_response({
                    "apiVersion": 1,
                    "pluginId": "ff9",
                    "name": "Final Fantasy IX",
                    "edition": "Steam Unity / Memoria CSV",
                    "hosted": HOSTED,
                    "windowHost": WINDOW_HOST,
                    "projectRoot": str(paths.PROJECT_ROOT),
                    "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": ["data-map", "memoria-csv", "read", "save"],
                })
            elif path == "/api/dashboard":
                self.json_response(dashboard())
            elif path == "/api/datamap":
                self.json_response(data_map())
            elif path == "/api/catalog":
                self.json_response({"datasets": catalog()})
            elif path == "/api/dataset":
                key = parse_qs(parsed.query).get("key", [""])[0]
                self.json_response(MemoriaDataStore().load(key))
            elif path == "/api/runtime":
                self.json_response(memoria_manager.status(paths.GAME_ROOT))
            elif path == "/api/runtime/available":
                self.json_response(memoria_manager.available())
            elif path == "/api/platform-config":
                self.json_response(load_config(paths.GAME_ROOT / "Memoria.ini", "Memoria", "ini"))
            else:
                self.json_response({"error": "Not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if path not in {"/api/save", "/api/platform-config/save"}:
                self.json_response({"error": "Not found"}, 404)
                return
            if path == "/api/runtime/install":
                # Explicit editor request only; the manager verifies the
                # published digest before anything is executed.
                self.json_response(memoria_manager.install(paths.GAME_ROOT))
            elif path == "/api/platform-config/save":
                result = save_config(
                    paths.GAME_ROOT / "Memoria.ini", "Memoria", "ini",
                    str(payload.get("sha256", "")), payload.get("changes", {}),
                    ("FF9.exe", "FF9_Launcher.exe"),
                )
            else:
                result = MemoriaDataStore().save(
                    str(payload.get("key", "")),
                    str(payload.get("sha256", "")),
                    payload.get("changes", []),
                )
            self.json_response(result)
        except FileNotFoundError as error:
            self.json_response({"error": str(error)}, 409)
        except RuntimeError as error:
            self.json_response({"error": str(error)}, 409)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
