"""Loopback HTTP service for the Final Fantasy VII KERNEL.BIN editor."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from . import paths
from .datasets import CATEGORIES, UNRESOLVED, READ_ERRORS, load_datasets, save_datasets
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


def editor_data() -> dict:
    return load_datasets(GAME_ROOT, PROJECT_ROOT)


def platform_data() -> dict:
    return load_config(GAME_ROOT / "FFNx.toml", "FFNx", "toml", game="FF7")


def save_platform_data(payload: object) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("changes"), dict):
        raise ValueError("FFNx save payload must contain a changes object")
    # Do not accept FF8-only keys through a hand-crafted FF7 request either.
    allowed = {field["id"] for section in platform_data()["sections"]
               for field in section["fields"]}
    if set(payload["changes"]) - allowed:
        raise ValueError("FFNx change set contains settings unavailable for FF7")
    result = save_config(GAME_ROOT / "FFNx.toml", "FFNx", "toml",
        str(payload.get("sha256", "")), payload["changes"],
        (EXECUTABLE, "FF7_EN.exe", "ff7.exe"))
    # The shared writer returns all games' fields. Keep its metadata, but filter
    # its response as well so FF8 settings cannot reappear immediately on save.
    for section in result["sections"]:
        section["fields"] = [field for field in section["fields"]
            if not field.get("onlyFor") or field["onlyFor"] == "FF7"]
    result["sections"] = [section for section in result["sections"] if section["fields"]]
    return result


def data_map() -> dict:
    data = editor_data()
    rows = []
    for key, category in CATEGORIES.items():
        error = data["errors"].get(key)
        source_label = data["sourceRelativePath"] or "English KERNEL.BIN"
        notes = error or (
            f"{len(data['records'][key])} records; {len(category.fields)} bounded numeric fields. "
            f"Saves a project copy to {data['projectPath']}; installed source is unchanged. "
            "Names are read-only KERNEL.BIN text, not a kernel2.bin text editor."
        )
        if key == "characters" and not error:
            notes += " Starting stats (section 4) and limit-learning thresholds (section 3) only; growth curves, equipment and AI are preserved."
        rows.append({"filename": source_label, "controls": category.label,
            "notes": notes, "status": "blocked" if error else (
                "partial" if key == "characters" else "integrated"),
            "openable": not bool(error), "category": key,
            "sourcePath": str(GAME_ROOT / data["sourceRelativePath"]) if data["sourceRelativePath"] else ""})
    for key, area in UNRESOLVED.items():
        rows.append({"filename": area["source"], "controls": area["label"],
            "notes": area["reason"] + " " + area["unlock"],
            "status": "not-integrated", "openable": False, "category": key})
    config = GAME_ROOT / "FFNx.toml"
    try:
        available = platform_data()["available"]
        note = ("Tweaks edits FF7 and shared runtime settings in place, with backups and stale-write protection."
                if available else "Available after FFNx creates its configuration in the game directory.")
        status = "integrated" if available else "partial"
    except READ_ERRORS as error:
        available, note, status = False, str(error), "blocked"
    rows.append({"filename": "FFNx.toml", "controls": "FFNx runtime settings",
        "notes": note, "status": status, "openable": available,
        "sourcePath": str(config), "category": "tweaks"})
    return {"contract": "Lexeditor.data-map", "rows": rows}


def dashboard() -> dict:
    executable = GAME_ROOT / EXECUTABLE
    problems = [] if executable.is_file() else [f"{EXECUTABLE} is missing from {GAME_ROOT}"]
    data = editor_data()
    problems.extend(f"{CATEGORIES[key].label}: {error}" for key, error in data["errors"].items())
    count = len(data["records"])
    baseline = {"ready": bool(count), "fileCount": int(bool(data["sourceSha256"])),
        "source": str(GAME_ROOT / data["sourceRelativePath"]) if data["sourceRelativePath"] else None,
        "relativePath": data["sourceRelativePath"], "projectPath": data["projectPath"],
        "sha256": data["sourceSha256"],
        "message": f"{count} of {len(CATEGORIES)} kernel datasets are readable. Saves edit the project copy, not the installed game."}
    sounds = ensure_theme_sounds(GAME_ROOT, DATA_ROOT,
        ("data/sound", "ff7/workingdir/data/sound"), {
            "confirm": 1, "move": 1, "back": 4, "exit": 4,
            "save": 2, "launch": None,
        }, format_kind="ff7")
    return {"game": {"root": str(GAME_ROOT), "executable": str(executable), "ready": not problems},
        "baseline": baseline, "problems": problems, "themeSounds": sounds}


def save_editor_data(payload: object) -> dict:
    return save_datasets(GAME_ROOT, PROJECT_ROOT, payload)


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
                self.json_response(platform_data())
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
                self.json_response(save_platform_data(payload))
            else:
                self.json_response(save_editor_data(payload))
        except Exception as error:
            self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
