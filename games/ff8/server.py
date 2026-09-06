"""Loopback HTTP service for the Final Fantasy VIII plugin."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import tempfile
from urllib.parse import parse_qs, unquote, urlparse

from . import card_art, cards, field_data, featured_mods, formats, gameplay_settings, paths, runtime_layout, world_geometry, world_map, world_textures
from .game_icons import icon_path, portrait_path
from .extractor import baseline_ready, manifest_path
from .ffnx_manager import status as ffnx_status
from .game_font import ensure_font
from theme_sounds import ensure_theme_sounds, sound_file
from platform_config import load_config, save_config


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")


def mods_payload() -> dict:
    return {
        "rows": runtime_layout.catalog(paths.PROJECT_ROOT, paths.MODS_ROOT),
        "composition": runtime_layout.read(paths.RUNTIME_ROOT),
        "runtimeRoot": str(paths.RUNTIME_ROOT),
    }


def dashboard() -> dict:
    problems = paths.game_problems()
    runtime_early = None
    ready = baseline_ready()
    file_count = 0
    try:
        file_count = len(json.loads(manifest_path().read_text(encoding="utf-8")).get("files", {}))
    except (OSError, ValueError, TypeError):
        pass
    runtime = ffnx_status(paths.GAME_ROOT)
    runtime["message"] = (
        runtime.get("runtimeBrokenReason")
        or "A required FFNx runtime failed to install. Gameplay tweaks will not apply."
        if runtime.get("runtimeBroken") else
        "FFNx is ready to load this project's direct overrides."
        if runtime["installed"] else
        "FFNx is not installed. Lexeditor can edit the project, but the game cannot load its overrides yet."
    )
    sounds = ensure_theme_sounds(paths.GAME_ROOT, paths.DATA_ROOT, ("Data/Sound",), {
        "confirm": 1, "move": 1, "back": 9, "exit": 9,
        "launch": 29, "save": 37,
    })
    return {
        "game": {
            "root": str(paths.GAME_ROOT),
            "executable": str(paths.GAME_ROOT / "FF8_EN.exe"),
            "ready": not problems and not runtime.get("runtimeBroken"),
        },
        "baseline": {
            "ready": ready,
            "fileCount": file_count,
            "message": (
                "The extracted gameplay-data baseline is ready."
                if ready else
                "The extracted gameplay-data baseline is not ready. Run game setup again."
            ),
        },
        "problems": problems,
        "runtime": runtime,
        "themeSounds": sounds,
        "credits": json.loads((PLUGIN_ROOT / "credits.json").read_text(encoding="utf-8")),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorFF8/1"

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

    def binary_response(self, data: bytes, content_type: str, filename: str | None = None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
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
            elif path == "/cards_ui.js":
                self.file_response(PLUGIN_ROOT / "cards_ui.js")
            elif path in ("/assets/licenses/FF8UltimateEditor-GPL-3.0.txt", "/assets/licenses/FFNx-GPL-3.0.txt", "/assets/licenses/Deling-GPL-3.0.txt", "/assets/licenses/OpenVIII-MIT.txt"):
                self.file_response(PLUGIN_ROOT / path.lstrip("/"))
            elif path == "/assets/ff8-menu.ttf":
                self.file_response(ensure_font())
            elif path.startswith("/assets/cards/") and path.endswith(".png"):
                card_id = int(path.rsplit("/", 1)[-1].removesuffix(".png"))
                self.binary_response(card_art.png_bytes(card_id), "image/png")
            elif path.startswith("/assets/icons/") and path.endswith(".png"):
                icon_id = int(Path(path).stem)
                target = icon_path(icon_id)
                if target is None:
                    self.json_response({"error": "Game icon not found"}, 404)
                else:
                    self.file_response(target)
            elif path.startswith("/assets/portraits/") and path.endswith(".png"):
                parts = Path(path).parts
                if len(parts) != 5:
                    self.json_response({"error": "Invalid portrait path"}, 404)
                else:
                    target = portrait_path(parts[3], int(Path(parts[4]).stem))
                    if target is None:
                        self.json_response({"error": "Game portrait not found"}, 404)
                    else:
                        self.file_response(target)
            elif path.startswith("/assets/world-textures/") and path.endswith(".png"):
                texture_id = int(path.rsplit("/", 1)[-1].removesuffix(".png"))
                palette = int(query.get("palette", ["0"])[0])
                dataset = query.get("dataset", ["current"])[0]
                self.binary_response(
                    world_textures.png_bytes(texture_id, palette, dataset), "image/png")
            elif path.startswith("/assets/world-textures/") and path.endswith(".tim"):
                texture_id = int(path.rsplit("/", 1)[-1].removesuffix(".tim"))
                dataset = query.get("dataset", ["current"])[0]
                self.binary_response(
                    world_textures.tim_bytes(texture_id, dataset),
                    "application/octet-stream", f"world-texture-{texture_id + 1}.tim")
            elif path == "/assets/world-map.png":
                dataset = query.get("dataset", ["current"])[0]
                self.binary_response(world_geometry.minimap_png(dataset), "image/png")
            elif path == "/assets/field-background.png":
                selected = query.get("tile", [None])[0]
                self.binary_response(field_data.background_png(
                    query.get("map", [""])[0], query.get("dataset", ["current"])[0],
                    highlight_tile=None if selected is None else int(selected)), "image/png")
            elif path.startswith("/assets/theme-sfx/") and path.endswith(".wav"):
                target = sound_file(paths.DATA_ROOT, Path(path).stem)
                if target is None:
                    self.json_response({"error": "Theme sound not found"}, 404)
                else:
                    self.file_response(target)
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
                    "pluginId": "ff8",
                    "name": "Final Fantasy 8",
                    "edition": "2013 Steam",
                    "hosted": HOSTED,
                    "windowHost": WINDOW_HOST,
                    "projectRoot": str(paths.PROJECT_ROOT),
                    "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": ["cards", "characters", "data-map", "encounters", "enemies", "gfs", "items",
                                     "magic", "menu-items", "settings", "shops", "starting-data", "weapons",
                                     "text", "world-map", "fields"],
                })
            elif path == "/api/dashboard":
                self.json_response(dashboard())
            elif path == "/api/references":
                self.json_response({"rows": formats.reference_roots()})
            elif path == "/api/mods":
                self.json_response(mods_payload())
            elif path == "/api/mods/featured":
                self.json_response({"rows": featured_mods.availability(
                    paths.PROJECT_ROOT, paths.MODS_ROOT)})
            elif path == "/api/items":
                self.json_response(formats.item_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/menu-items":
                self.json_response(formats.menu_item_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/shops":
                self.json_response(formats.shop_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/weapons":
                self.json_response(formats.weapon_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/kernel":
                self.json_response(formats.kernel_rows(
                    int(query.get("section", ["0"])[0]), query.get("dataset", ["current"])[0]))
            elif path == "/api/cards":
                self.json_response(cards.payload(query.get("dataset", ["current"])[0]))
            elif path == "/api/text":
                self.json_response(formats.text_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/enemies":
                self.json_response(formats.enemy_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/enemy-tables":
                selected = query.get("id", [None])[0]
                self.json_response(formats.enemy_table_rows(
                    query.get("dataset", ["current"])[0],
                    None if selected is None else int(selected)))
            elif path == "/api/enemy-ai":
                selected = query.get("id", [None])[0]
                self.json_response(formats.enemy_ai_rows(
                    query.get("dataset", ["current"])[0],
                    None if selected is None else int(selected)))
            elif path == "/api/enemy-battle-text":
                selected = query.get("id", [None])[0]
                self.json_response(formats.enemy_battle_text_rows(
                    query.get("dataset", ["current"])[0],
                    None if selected is None else int(selected)))
            elif path == "/api/refine":
                self.json_response(formats.refine_rows(
                    query.get("dataset", ["current"])[0]))
            elif path == "/api/encounters":
                self.json_response(formats.encounter_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/world-map":
                self.json_response(world_map.rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/fields":
                self.json_response(field_data.index_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/field":
                self.json_response(field_data.map_rows(
                    query.get("map", [""])[0], query.get("dataset", ["current"])[0]))
            elif path == "/api/init":
                self.json_response(formats.init_rows(query.get("dataset", ["current"])[0]))
            elif path == "/api/settings":
                self.json_response(gameplay_settings.payload())
            elif path == "/api/settings/runtime":
                self.json_response(gameplay_settings.runtime_status())
            elif path == "/api/platform-config":
                self.json_response(load_config(paths.GAME_ROOT / "FFNx.toml", "FFNx", "toml", game="FF8"))
            elif path == "/api/datamap":
                self.json_response(formats.data_map_rows())
            else:
                self.json_response({"error": "Not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/mods/import":
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 8 * 1024 * 1024 * 1024:
                    raise ValueError("The IROJ upload size is invalid")
                paths.MODS_ROOT.mkdir(parents=True, exist_ok=True)
                handle, temporary_name = tempfile.mkstemp(
                    prefix=".upload-", suffix=".iroj", dir=paths.MODS_ROOT.parent)
                try:
                    with os.fdopen(handle, "wb") as output:
                        remaining = length
                        while remaining:
                            block = self.rfile.read(min(remaining, 1024 * 1024))
                            if not block:
                                raise ValueError("The IROJ upload ended early")
                            output.write(block)
                            remaining -= len(block)
                    imported = runtime_layout.install_iroj(
                        Path(temporary_name), paths.PROJECT_ROOT, paths.MODS_ROOT,
                        parse_qs(parsed.query).get("filename", [""])[0])
                finally:
                    Path(temporary_name).unlink(missing_ok=True)
                self.json_response({**mods_payload(), "imported": imported})
                return
            body = self.body()
            if path == "/api/items/save":
                self.json_response(formats.save_items(body.get("edits", [])))
            elif path == "/api/menu-items/save":
                self.json_response(formats.save_menu_items(body.get("edits", [])))
            elif path == "/api/shops/save":
                self.json_response(formats.save_shops(body.get("edits", [])))
            elif path == "/api/weapons/save":
                self.json_response(formats.save_weapons(body.get("edits", [])))
            elif path == "/api/kernel/save":
                self.json_response(formats.save_kernel(int(body["section"]), body.get("edits", [])))
            elif path == "/api/cards/save":
                self.json_response(cards.save(body.get("edits", [])))
            elif path == "/api/text/save":
                self.json_response(formats.save_text(body.get("edits", [])))
            elif path == "/api/enemies/save":
                self.json_response(formats.save_enemies(body.get("edits", [])))
            elif path == "/api/enemy-tables/save":
                self.json_response(formats.save_enemy_tables(body.get("edits", [])))
            elif path == "/api/enemy-ai/save":
                self.json_response(formats.save_enemy_ai(
                    body.get("edits", []), body.get("documents", [])))
            elif path == "/api/enemy-ai/source/compile":
                self.json_response(formats.compile_enemy_ai_sources(body.get("sources", [])))
            elif path == "/api/enemy-battle-text/save":
                self.json_response(formats.save_enemy_battle_text(body.get("edits", [])))
            elif path == "/api/refine/save":
                self.json_response(formats.save_refine_tables(body.get("edits", [])))
            elif path == "/api/encounters/save":
                self.json_response(formats.save_encounters(body.get("edits", [])))
            elif path == "/api/world-map/save":
                self.json_response(world_map.save(body.get("edits", [])))
            elif path == "/api/field/save":
                self.json_response(field_data.save(body.get("edits", [])))
            elif path == "/api/field/background-preview":
                self.binary_response(field_data.background_png(
                    str(body.get("map", "")), str(body.get("dataset", "current")),
                    body.get("edits", []), body.get("activeStates"),
                    body.get("enabledLayers"), body.get("hideBackground") is True,
                    (None if body.get("highlightTile") is None
                     else int(body["highlightTile"]))), "image/png")
            elif path == "/api/init/save":
                self.json_response(formats.save_init(body.get("edits", [])))
            elif path == "/api/settings/save":
                self.json_response(gameplay_settings.save(body))
            elif path == "/api/mods/configure":
                rows = runtime_layout.configure(
                    paths.PROJECT_ROOT, paths.MODS_ROOT,
                    [str(value) for value in body.get("order", [])],
                    {str(key): value is True for key, value in body.get("enabled", {}).items()},
                    {str(mod_id): values for mod_id, values
                     in body.get("folderOptions", {}).items()},
                )
                runtime_layout.compose(
                    paths.PROJECT_ROOT, paths.RUNTIME_ROOT, rows,
                    paths.BASELINE_ROOT, formats.SECTIONS,
                    runtime_layout.prelaunch_condition_state(paths.GAME_ROOT / "FFNx.toml"),
                )
                self.json_response(mods_payload())
            elif path == "/api/mods/featured/install":
                imported = featured_mods.install_latest(
                    str(body.get("id") or ""), paths.PROJECT_ROOT, paths.MODS_ROOT)
                rows = runtime_layout.catalog(paths.PROJECT_ROOT, paths.MODS_ROOT)
                runtime_layout.compose(
                    paths.PROJECT_ROOT, paths.RUNTIME_ROOT, rows,
                    paths.BASELINE_ROOT, formats.SECTIONS,
                    runtime_layout.prelaunch_condition_state(paths.GAME_ROOT / "FFNx.toml"),
                )
                self.json_response({**mods_payload(), "installed": imported})
            elif path == "/api/settings/activate":
                self.json_response(gameplay_settings.activate())
            elif path == "/api/platform-config/save":
                self.json_response(save_config(
                    paths.GAME_ROOT / "FFNx.toml", "FFNx", "toml",
                    str(body.get("sha256", "")), body.get("changes", {}),
                    ("FF8_EN.exe", "FF8_Launcher.exe"),
                ))
            else:
                self.json_response({"error": "Not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        prefix = "/api/mods/"
        try:
            if not parsed.path.startswith(prefix) or parsed.path == "/api/mods/featured":
                self.json_response({"error": "Not found"}, 404)
                return
            mod_id = unquote(parsed.path.removeprefix(prefix))
            if not mod_id or "/" in mod_id or "\\" in mod_id:
                raise ValueError("The FF8 mod id is invalid")
            removed = runtime_layout.delete_mod(
                paths.PROJECT_ROOT, paths.MODS_ROOT, mod_id)
            rows = runtime_layout.catalog(paths.PROJECT_ROOT, paths.MODS_ROOT)
            runtime_layout.compose(
                paths.PROJECT_ROOT, paths.RUNTIME_ROOT, rows,
                paths.BASELINE_ROOT, formats.SECTIONS,
                runtime_layout.prelaunch_condition_state(paths.GAME_ROOT / "FFNx.toml"),
            )
            self.json_response({**mods_payload(), "deleted": {
                "id": removed["id"], "name": removed["name"]}})
        except Exception as error:
            self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
