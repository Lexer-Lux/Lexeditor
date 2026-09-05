"""Loopback HTTP service for the Final Fantasy VII KERNEL.BIN editor."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from . import paths
from .kernel import CATEGORIES, Kernel, category_metadata, resolve_kernel
from platform_config import load_config, save_config
from theme_sounds import ensure_theme_sounds, sound_file


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")
PLUGIN_ID = os.environ.get("LEXEDITOR_FF7_PLUGIN_ID", "ff7")
PLUGIN_NAME = os.environ.get("LEXEDITOR_FF7_PLUGIN_NAME", "Final Fantasy 7 (Original)")
PLUGIN_EDITION = os.environ.get("LEXEDITOR_FF7_EDITION", "Current Steam release")
GAME_ROOT = Path(os.environ.get("LEXEDITOR_FF7_ROOT", str(paths.GAME_ROOT)))
DATA_ROOT = Path(os.environ.get("LEXEDITOR_FF7_DATA_ROOT", str(paths.DATA_ROOT)))
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_FF7_PROJECT", str(paths.PROJECT_ROOT)))
EXECUTABLE = os.environ.get("LEXEDITOR_FF7_EXECUTABLE", "FFVII_LAUNCHER.exe")


UNRESOLVED_AREAS = (
    ("Characters", "Character initialization and growth data"),
    ("Enemies", "Enemy records, attacks, rewards, names, and scan text"),
    ("Encounters", "Encounter composition and placement"),
    ("Shops", "Shop inventories and prices"),
)


def _kernel_paths() -> tuple[Path, Path, Path]:
    source, relative = resolve_kernel(GAME_ROOT)
    return source, relative, PROJECT_ROOT / relative


def _active_kernel() -> tuple[Kernel, Kernel, Path, Path]:
    source, relative, project = _kernel_paths()
    vanilla = Kernel(source)
    current = Kernel(project if project.is_file() else source)
    return current, vanilla, relative, project


def data_map() -> dict:
    rows = []
    try:
        source, relative, project = _kernel_paths()
        source_label = relative.as_posix()
        for category in CATEGORIES.values():
            rows.append({
                "filename": source_label,
                "controls": f"{category.label}: {len(category.fields)} bounded numeric fields",
                "notes": (
                    f"Integrated KERNEL.BIN section {category.section}. Saves a lossless project copy "
                    f"to {project}; names and descriptions are read-only."
                ),
                "status": "integrated",
                "openable": True,
                "sourcePath": str(source),
            })
    except FileNotFoundError as error:
        rows.append({
            "filename": "English KERNEL.BIN",
            "controls": "Items, weapons, armor, accessories, and materia",
            "notes": str(error), "status": "blocked", "openable": False,
        })
    rows.extend({
        "filename": f"Unresolved / {name}", "controls": controls,
        "notes": "No proved writable format path is connected yet.",
        "status": "not-integrated", "openable": False,
    } for name, controls in UNRESOLVED_AREAS)
    config = GAME_ROOT / "FFNx.toml"
    rows.append({
        "filename": "FFNx.toml", "controls": "FFNx display, audio, rendering, mod and runtime settings",
        "notes": "The Tweaks tab edits typed values in place and preserves comments and file order."
                 if config.is_file() else "Available after FFNx creates its configuration in the game directory.",
        "status": "integrated" if config.is_file() else "partial", "openable": config.is_file(),
    })
    return {"contract": "Lexeditor.data-map", "rows": rows}


def dashboard() -> dict:
    executable = GAME_ROOT / EXECUTABLE
    problems = [] if executable.is_file() else [f"{EXECUTABLE} is missing from {GAME_ROOT}"]
    try:
        source, relative, project = _kernel_paths()
        parsed = Kernel(source)
        baseline = {
            "ready": True, "fileCount": 1, "source": str(source),
            "relativePath": relative.as_posix(), "projectPath": str(project),
            "sha256": parsed.sha256,
            "message": "English KERNEL.BIN is decoded. Five proved record sections are editable.",
        }
    except (OSError, ValueError) as error:
        problems.append(str(error))
        baseline = {"ready": False, "fileCount": 0, "message": str(error)}
    sounds = ensure_theme_sounds(GAME_ROOT, DATA_ROOT,
        ("data/sound", "ff7/workingdir/data/sound"), {
            "confirm": 1, "move": 1, "back": 4, "exit": 4,
            "save": 2, "launch": None,
        }, format_kind="ff7")
    return {
        "game": {"root": str(GAME_ROOT), "executable": str(executable), "ready": not problems},
        "baseline": baseline, "problems": problems, "themeSounds": sounds,
    }


def editor_data() -> dict:
    current, vanilla, relative, project = _active_kernel()
    return {
        "contract": "Lexeditor.ff7-kernel", "sourceRelativePath": relative.as_posix(),
        "projectPath": str(project), "usingProject": project.is_file(),
        "sourceSha256": vanilla.sha256, "categories": category_metadata(),
        "records": {key: current.records(key) for key in CATEGORIES},
        "vanilla": {key: vanilla.records(key) for key in CATEGORIES},
    }


def save_editor_data(payload: object) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), dict):
        raise ValueError("Save payload must contain a records object")
    records = payload["records"]
    if set(records) != set(CATEGORIES):
        raise ValueError("Save payload must contain every integrated FF7 category")
    source, _relative, project = _kernel_paths()
    kernel = Kernel(project if project.is_file() else source)
    for key in CATEGORIES:
        category_records = records[key]
        if not isinstance(category_records, list):
            raise ValueError(f"{CATEGORIES[key].label} records must be a list")
        kernel.apply(key, category_records)
    kernel.save(project)
    verified = Kernel(project)
    for key in CATEGORIES:
        verified.records(key)
    return {
        "saved": True, "path": str(project),
        "sha256": hashlib.sha256(project.read_bytes()).hexdigest().upper(),
        "bytes": project.stat().st_size,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorFF7/2"

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

    def editor_response(self):
        identity = {"id": PLUGIN_ID, "name": PLUGIN_NAME, "edition": PLUGIN_EDITION}
        html = (PLUGIN_ROOT / "editor.html").read_text(encoding="utf-8")
        injected = f"<script>window.__lexeditorPlugin={json.dumps(identity)};</script></head>"
        data = html.replace("</head>", injected, 1).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/":
                self.editor_response()
            elif path.startswith("/shared/"):
                shared = (LEXEDITOR_ROOT / "ui").resolve()
                target = (shared / path.removeprefix("/shared/")).resolve()
                if shared not in target.parents or not target.is_file():
                    self.json_response({"error": "Shared UI asset not found"}, 404)
                else:
                    self.file_response(target)
            elif path.startswith("/assets/theme-sfx/") and path.endswith(".wav"):
                target = sound_file(DATA_ROOT, Path(path).stem)
                self.file_response(target) if target else self.json_response({"error": "Theme sound not found"}, 404)
            elif path == "/api/plugin":
                self.json_response({
                    "apiVersion": 1, "pluginId": PLUGIN_ID, "name": PLUGIN_NAME,
                    "edition": PLUGIN_EDITION, "hosted": HOSTED, "windowHost": WINDOW_HOST,
                    "projectRoot": str(PROJECT_ROOT), "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": ["data-map", "kernel-data", "save"],
                })
            elif path == "/api/dashboard":
                self.json_response(dashboard())
            elif path == "/api/datamap":
                self.json_response(data_map())
            elif path == "/api/data":
                self.json_response(editor_data())
            elif path == "/api/platform-config":
                self.json_response(load_config(GAME_ROOT / "FFNx.toml", "FFNx", "toml"))
            else:
                self.json_response({"error": "Not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path not in {"/api/save", "/api/platform-config/save"}:
                self.json_response({"error": "Not found"}, 404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 4 * 1024 * 1024:
                raise ValueError("FF7 save payload has an invalid size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/platform-config/save":
                self.json_response(save_config(
                    GAME_ROOT / "FFNx.toml", "FFNx", "toml",
                    str(payload.get("sha256", "")), payload.get("changes", {}),
                    (EXECUTABLE, "FF7_EN.exe", "ff7.exe"),
                ))
            else:
                self.json_response(save_editor_data(payload))
        except Exception as error:
            self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
