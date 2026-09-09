"""Loopback HTTP service for the FFX/X-2 HD Remaster collection editor."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import ctb_base, deployment, gear_shops, item_prices, item_shops, mix_table, paths, theme, treasures
from .vbf import VBFError, VBFIndex, extract_to, read_entry, read_index


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")
MAX_REQUEST_BYTES = 256 * 1024
POST_ROUTES = {
    "/api/project/extract", "/api/treasures/save", "/api/item-prices/save", "/api/ctb-base/save",
    "/api/mix-table/save", "/api/item-shops/save", "/api/gear-shops/save",
    "/api/deployment/deploy", "/api/deployment/revert",
}
_INDEX_CACHE: dict[str, tuple[tuple[int, int], VBFIndex]] = {}
_META_CACHE: tuple[tuple[int, int], VBFIndex] | None = None


def _game_key(value: str) -> str:
    key = str(value).casefold()
    if key not in paths.ARCHIVES:
        raise ValueError("game must be 'x' or 'x2'")
    return key


def _index(game: str) -> VBFIndex:
    key = _game_key(game)
    target = paths.ARCHIVES[key]
    stat = target.stat()
    signature = (stat.st_size, stat.st_mtime_ns)
    cached = _INDEX_CACHE.get(key)
    if cached is not None and cached[0] == signature and cached[1].path == target:
        return cached[1]
    parsed = read_index(target)
    _INDEX_CACHE[key] = (signature, parsed)
    return parsed


def _meta_index() -> VBFIndex | None:
    global _META_CACHE
    target = paths.META_ARCHIVE
    if not target.is_file():
        return None
    stat = target.stat()
    signature = (stat.st_size, stat.st_mtime_ns)
    if _META_CACHE is not None and _META_CACHE[0] == signature and _META_CACHE[1].path == target:
        return _META_CACHE[1]
    parsed = read_index(target)
    _META_CACHE = (signature, parsed)
    return parsed


def _find_entry(index: VBFIndex, game: str, archive_path: str):
    """Resolve either the game-facing or raw VBF spelling of one entry."""
    for candidate in paths.source_archive_candidates(game, archive_path):
        try:
            return index.find(candidate)
        except FileNotFoundError:
            continue
    raise FileNotFoundError(archive_path)


def _project_target(game: str, archive_path: str) -> Path:
    key = _game_key(game)
    root = paths.PROJECT_ROOT.resolve()
    virtual_path = paths.efl_archive_path(key, archive_path)
    target = (root / "efl" / key / Path(*virtual_path.split("/"))).resolve()
    if root != target and root not in target.parents:
        raise ValueError("Project target escaped the selected project root")
    return target


def _archive_status(game: str) -> dict:
    key = _game_key(game)
    target = paths.ARCHIVES[key]
    if not target.is_file():
        return {"game": key, "label": paths.GAME_LABELS[key], "path": str(target),
                "ready": False, "error": "Archive is missing", "fileCount": 0}
    try:
        index = _index(key)
        return {"game": key, "label": paths.GAME_LABELS[key], "path": str(target),
                "ready": True, "headerMd5": index.header_md5,
                "headerBytes": index.header_length, "fileCount": index.file_count,
                "bytes": target.stat().st_size}
    except (OSError, VBFError) as error:
        return {"game": key, "label": paths.GAME_LABELS[key], "path": str(target),
                "ready": False, "error": str(error), "fileCount": 0}


def theme_status() -> dict:
    """Build cosmetic assets when possible without making them a readiness gate."""
    indexes: dict[str, VBFIndex] = {}
    for key, target in paths.ARCHIVES.items():
        if not target.is_file():
            continue
        try:
            indexes[key] = _index(key)
        except (OSError, VBFError):
            continue
    if not indexes:
        return {
            "source": "fallback",
            "background": {"ready": False, "note": "Installed VBFs are unavailable."},
            "font": {"webReady": False, "atlasRecognized": 0, "atlasCached": 0},
            "textures": {"recognized": 0, "cached": 0, "browserPngCached": 0},
            "sfx": {"webReady": False, "recognizedBanks": 0, "cachedBanks": 0},
        }
    try:
        return theme.build(paths.THEME_CACHE_ROOT, indexes, _meta_index())
    except (OSError, VBFError, ValueError) as error:
        return {
            "source": "fallback", "error": str(error),
            "background": {"ready": False, "note": "Installed-game theme extraction failed; fallback styling remains active."},
            "font": {"webReady": False, "atlasRecognized": 0, "atlasCached": 0},
            "textures": {"recognized": 0, "cached": 0, "browserPngCached": 0},
            "sfx": {"webReady": False, "recognizedBanks": 0, "cachedBanks": 0},
        }


def _structured_current(archive_path: str) -> tuple[VBFIndex, Path, bytes, str]:
    index = _index("x")
    entry = _find_entry(index, "x", archive_path)
    target = _project_target("x", entry.path)
    if target.is_file():
        return index, target, target.read_bytes(), "project"
    return index, target, read_entry(index, entry), "archive"


def _structured_payload(archive_path: str, builder) -> dict:
    index, target, data, source = _structured_current(archive_path)
    result = builder(data)
    result.update({
        "game": "x", "archivePath": archive_path, "headerMd5": index.header_md5,
        "source": source, "staged": target.is_file(), "projectPath": str(target),
    })
    return result


def _structured_save(request: dict, archive_path: str, apply, builder, label: str) -> dict:
    index, target, data, _source = _structured_current(archive_path)
    if str(request.get("headerMd5", "")) != index.header_md5:
        raise RuntimeError(f"The FFX VBF changed; refresh {label} before saving")
    current_baseline = treasures.sha256_bytes(data)
    if str(request.get("baselineSha256", "")) != current_baseline:
        raise RuntimeError(f"{Path(archive_path).name} changed outside this editor; refresh {label} before saving")
    edits = request.get("edits")
    edited = apply(data, edits)
    paths.ensure_project()
    treasures.atomic_write(target, edited)
    result = _structured_payload(archive_path, builder)
    result["saved"] = len(edits)
    return result


def treasure_catalog() -> dict:
    return _structured_payload(treasures.ARCHIVE_PATH, treasures.payload)


def save_treasures(request: dict) -> dict:
    return _structured_save(request, treasures.ARCHIVE_PATH, treasures.apply_edits, treasures.payload, "Treasures")


def item_price_catalog() -> dict:
    return _structured_payload(item_prices.ARCHIVE_PATH, item_prices.payload)


def save_item_prices(request: dict) -> dict:
    return _structured_save(request, item_prices.ARCHIVE_PATH, item_prices.apply_edits, item_prices.payload, "Item Prices")


def ctb_base_catalog() -> dict:
    return _structured_payload(ctb_base.ARCHIVE_PATH, ctb_base.payload)


def save_ctb_base(request: dict) -> dict:
    return _structured_save(request, ctb_base.ARCHIVE_PATH, ctb_base.apply_edits, ctb_base.payload, "CTB Base")


def mix_catalog() -> dict:
    return _structured_payload(mix_table.ARCHIVE_PATH, mix_table.payload)


def save_mix(request: dict) -> dict:
    return _structured_save(request, mix_table.ARCHIVE_PATH, mix_table.apply_edits, mix_table.payload, "Mix Table")


def item_shop_catalog() -> dict:
    return _structured_payload(item_shops.ARCHIVE_PATH, item_shops.payload)


def save_item_shops(request: dict) -> dict:
    return _structured_save(request, item_shops.ARCHIVE_PATH, item_shops.apply_edits, item_shops.payload, "Item Shops")


def gear_shop_catalog() -> dict:
    return _structured_payload(gear_shops.ARCHIVE_PATH, gear_shops.payload)


def save_gear_shops(request: dict) -> dict:
    return _structured_save(request, gear_shops.ARCHIVE_PATH, gear_shops.apply_edits, gear_shops.payload, "Gear Shops")


def _map_structured_row(archive_path: str, controls: str, builder, notes) -> dict:
    try:
        state = _structured_payload(archive_path, builder)
        status = "integrated"
        note = notes(state)
    except (OSError, VBFError, ValueError) as error:
        status = "partial"
        note = f"Recognized structured table, but it is unavailable: {error}"
    return {
        "filename": archive_path, "controls": controls, "notes": note,
        "status": status, "coverage": "structured-record-editor",
        "openable": status == "integrated", "game": "x",
    }


def data_map() -> dict:
    rows: list[dict] = []
    for key, filename in (("x", "data/FFX_Data.vbf"), ("x2", "data/FFX2_Data.vbf")):
        state = _archive_status(key)
        rows.append({
            "filename": filename,
            "controls": "Validated VBF archive index, search, read-only extraction to project overlay",
            "notes": f"{paths.GAME_LABELS[key]} archive. Installed bytes are read-only. Extract creates a Fahrenheit EFL project copy.",
            "status": "integrated" if state["ready"] else "partial",
            "coverage": "archive-index-and-extract", "openable": state["ready"], "target": "archives", "game": key,
        })
    structured = [
        (treasures.ARCHIVE_PATH, "Structured treasure reward editor", treasures.payload,
         lambda s: f"{len(s['rows'])} reward records; edits only kind, quantity and 16-bit type ID.", "treasures"),
        (item_prices.ARCHIVE_PATH, "Structured item/command gil-price editor", item_prices.payload,
         lambda s: f"{len(s['rows'])} four-byte prices mapped to command IDs starting at 0x{s['commandBase']:04X}.", "item-prices"),
        (ctb_base.ARCHIVE_PATH, "Structured CTB tick-speed and ICV-bonus editor", ctb_base.payload,
         lambda s: f"{len(s['rows'])} two-byte Agility records with derived initial-CTB ranges.", "ctb-base"),
        (mix_table.ARCHIVE_PATH, "Structured Rikku Mix result editor", mix_table.payload,
         lambda s: f"{len(s['rows'])} ingredient rows × {s['partnerCount']} partner slots of 16-bit result command IDs.", "mix-table"),
        (item_shops.ARCHIVE_PATH, "Structured 16-slot item shop editor", item_shops.payload,
         lambda s: f"{len(s['rows'])} shops with {s['slotCount']} item/command ID slots; leading legacy rate is read-only.", "item-shops"),
        (gear_shops.ARCHIVE_PATH, "Structured 16-slot gear shop editor", gear_shops.payload,
         lambda s: f"{len(s['rows'])} shops with {s['slotCount']} gear-index slots; leading legacy rate is read-only.", "gear-shops"),
    ]
    for archive_path, controls, builder, notes, target in structured:
        row = _map_structured_row(archive_path, controls, builder, notes)
        row["target"] = target
        rows.append(row)
    themed = theme_status()
    theme_parts = []
    if themed.get("background", {}).get("ready"): theme_parts.append("title/menu PNG active")
    if themed.get("font", {}).get("atlasRecognized"): theme_parts.append(f"{themed['font']['atlasRecognized']} font atlas source(s) recognized")
    if themed.get("textures", {}).get("recognized"): theme_parts.append(f"{themed['textures']['recognized']} menu texture source(s) recognized")
    if themed.get("sfx", {}).get("recognizedBanks"): theme_parts.append(f"{themed['sfx']['recognizedBanks']} UI-audio bank(s) recognized")
    rows.extend([
        {"filename": "data/metamenu.vbf + menu/font/sound resources", "controls": "Private installed-game theme cache",
         "notes": "; ".join(theme_parts) or "Theme extraction falls back safely when cosmetic source assets are unavailable.",
         "status": "partial" if themed.get("source") == "installed-game" else "not-integrated", "coverage": "game-derived-theme", "openable": False},
        {"filename": "FFX_Data/ffx_ps2/ffx/**/battle/kernel/*", "controls": "Remaining gameplay/kernel family",
         "notes": "Treasure rewards, item prices, CTB timing, Mix results, item shops and gear shops are structured; other kernel tables remain available through the VBF browser.",
         "status": "partial", "coverage": "six-structured-families", "openable": False},
        {"filename": "FFX2_Data/ffx_ps2/ffx2/**", "controls": "Recognized FFX-2 game-data families",
         "notes": "Files can be located and staged through the VBF browser. FFX-2 format-specific editors remain to be implemented.",
         "status": "not-integrated", "coverage": "recognized", "openable": False},
        {"filename": "fahrenheit/mods/lexeditor-ffx-x2/efl/{x,x2}/**", "controls": "Reversible file-only Fahrenheit deployment",
         "notes": "Deploy copies only the selected Lexeditor project into its owned Fahrenheit mod folder and preserves unrelated loadorder entries.",
         "status": "integrated" if deployment.status(paths.GAME_ROOT, paths.PROJECT_ROOT)["fahrenheitReady"] else "partial",
         "coverage": "deployment", "openable": True, "target": "deployment"},
    ])
    return {"contract": "Lexeditor.data-map", "rows": rows}


def dashboard() -> dict:
    archives = [_archive_status("x"), _archive_status("x2")]
    deploy = deployment.status(paths.GAME_ROOT, paths.PROJECT_ROOT)
    return {
        "game": {"root": str(paths.GAME_ROOT), "ready": not paths.game_problems(), "steamAppId": "359870",
                 "launcher": str(paths.GAME_ROOT / "FFX&X-2_LAUNCHER.exe"),
                 "executables": [str(paths.GAME_ROOT / "FFX.exe"), str(paths.GAME_ROOT / "FFX-2.exe")]},
        "archives": archives, "project": {"root": str(paths.PROJECT_ROOT), "fileCount": deploy["projectFileCount"]},
        "deployment": deploy, "theme": theme_status(), "problems": paths.game_problems(),
    }


def archive_catalog(game: str, query: str, offset: int, limit: int) -> dict:
    key = _game_key(game)
    index = _index(key)
    needle = query.casefold().strip()
    rows = [entry for entry in index.entries if not needle or needle in entry.path.casefold()]
    offset = max(0, offset); limit = min(250, max(1, limit)); page = rows[offset:offset + limit]
    return {"game": key, "headerMd5": index.header_md5, "total": len(rows), "offset": offset, "limit": limit,
            "entries": [{"path": entry.path, "eflPath": paths.efl_archive_path(key, entry.path), "bytes": entry.size,
                         "blocks": entry.block_count, "staged": _project_target(key, entry.path).is_file()} for entry in page],
            "projectRoot": str(paths.PROJECT_ROOT.resolve())}


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorFFXX2/1"
    def log_message(self, _format, *_args): return
    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate"); self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def file_response(self, target: Path):
        data = target.read_bytes(); self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate"); self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        parsed = urlparse(self.path); route = parsed.path
        try:
            if route == "/": self.file_response(PLUGIN_ROOT / "editor.html")
            elif route.startswith("/shared/"):
                shared = (LEXEDITOR_ROOT / "ui").resolve(); target = (shared / route.removeprefix("/shared/")).resolve()
                self.file_response(target) if shared in target.parents and target.is_file() else self.json_response({"error": "Shared UI asset not found"}, 404)
            elif route.startswith("/theme/"): self.file_response(theme.asset_path(paths.THEME_CACHE_ROOT, route.removeprefix("/theme/")))
            elif route == "/api/plugin":
                self.json_response({"apiVersion": 1, "pluginId": "ffx-x2", "name": "Final Fantasy X/X-2 HD Remaster",
                    "edition": "Steam collection / VBF / Fahrenheit EFL", "hosted": HOSTED, "windowHost": WINDOW_HOST,
                    "projectRoot": str(paths.PROJECT_ROOT), "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": ["data-map", "vbf-index", "vbf-extract", "project-overlay", "ffx-treasure-editor",
                        "ffx-item-price-editor", "ffx-ctb-base-editor", "ffx-mix-editor", "ffx-item-shop-editor",
                        "ffx-gear-shop-editor", "installed-game-theme", "fahrenheit-deploy"]})
            elif route == "/api/dashboard": self.json_response(dashboard())
            elif route == "/api/datamap": self.json_response(data_map())
            elif route == "/api/theme": self.json_response(theme_status())
            elif route == "/api/treasures": self.json_response(treasure_catalog())
            elif route == "/api/item-prices": self.json_response(item_price_catalog())
            elif route == "/api/ctb-base": self.json_response(ctb_base_catalog())
            elif route == "/api/mix-table": self.json_response(mix_catalog())
            elif route == "/api/item-shops": self.json_response(item_shop_catalog())
            elif route == "/api/gear-shops": self.json_response(gear_shop_catalog())
            elif route == "/api/archive":
                q = parse_qs(parsed.query); self.json_response(archive_catalog(q.get("game", ["x"])[0], q.get("q", [""])[0], int(q.get("offset", ["0"])[0]), int(q.get("limit", ["100"])[0])))
            elif route == "/api/deployment": self.json_response(deployment.status(paths.GAME_ROOT, paths.PROJECT_ROOT))
            else: self.json_response({"error": "Not found"}, 404)
        except FileNotFoundError as error: self.json_response({"error": str(error)}, 404)
        except (OSError, VBFError, ValueError, RuntimeError) as error: self.json_response({"error": str(error)}, 400)
    def do_POST(self):
        route = urlparse(self.path).path
        try:
            if route not in POST_ROUTES: self.json_response({"error": "Not found"}, 404); return
            port = self.server.server_address[1]; allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}; host = self.headers.get("Host", "").casefold(); origin = self.headers.get("Origin")
            if host not in allowed_hosts or (origin is not None and origin not in {f"http://{host}"}): self.json_response({"error": "Only this editor may change FFX/X-2 project data"}, 403); return
            if self.headers.get_content_type() != "application/json": self.json_response({"error": "An application/json request is required"}, 415); return
            if self.headers.get("Transfer-Encoding"): self.json_response({"error": "Chunked requests are not supported"}, 400); return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES: self.json_response({"error": "Invalid or oversized request body"}, 413); return
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(request, dict): raise ValueError("The request must be a JSON object")
            if route == "/api/project/extract":
                key = _game_key(str(request.get("game", ""))); index = _index(key)
                if str(request.get("headerMd5", "")) != index.header_md5: raise RuntimeError("The VBF index changed; refresh the archive browser before extracting")
                entry = _find_entry(index, key, str(request.get("path", ""))); paths.ensure_project(); result = extract_to(index, entry, _project_target(key, entry.path))
                result.update({"game": key, "archivePath": entry.path, "eflPath": paths.efl_archive_path(key, entry.path), "headerMd5": index.header_md5})
            elif route == "/api/treasures/save": result = save_treasures(request)
            elif route == "/api/item-prices/save": result = save_item_prices(request)
            elif route == "/api/ctb-base/save": result = save_ctb_base(request)
            elif route == "/api/mix-table/save": result = save_mix(request)
            elif route == "/api/item-shops/save": result = save_item_shops(request)
            elif route == "/api/gear-shops/save": result = save_gear_shops(request)
            elif route == "/api/deployment/deploy": result = deployment.deploy(paths.GAME_ROOT, paths.PROJECT_ROOT)
            else: result = deployment.revert(paths.GAME_ROOT, paths.PROJECT_ROOT)
            self.json_response(result)
        except FileExistsError as error: self.json_response({"error": str(error)}, 409)
        except FileNotFoundError as error: self.json_response({"error": str(error)}, 409)
        except RuntimeError as error: self.json_response({"error": str(error)}, 409)
        except (OSError, VBFError, ValueError, json.JSONDecodeError) as error: self.json_response({"error": str(error)}, 400)


def create_server(port=PORT): return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__": create_server().serve_forever()
