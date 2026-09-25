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
from .memoria_csv import MemoriaDataStore, catalog
from .battle_scene import BattleSceneStore
from .field_walkmesh import FieldWalkmeshStore
from .memoria_baseline import ensure as ensure_baseline
from . import memoria_manager, features, mod_compat
from . import game_font
from core.plugin_http import PluginRequestHandler


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")
MAX_REQUEST_BYTES = 2 * 1024 * 1024
FIELD_WALKMESH = FieldWalkmeshStore()


POST_ROUTES = {"/api/save", "/api/runtime/install", "/api/runtime/recover",
               "/api/runtime/settings", "/api/features/save",
               "/api/deployment/deploy", "/api/deployment/revert"}


# Known p0data areas that remain outside Lexeditor's structured editor.
# These stay explicit even when a narrow sub-format is integrated, so partial
# coverage never hides the still-protected bytes or implies a generic raw editor.
UNRESOLVED_AREAS = (
    ("StreamingAssets/p0data1*.bin (outside integrated BGI pathing flags)", "Field backgrounds, cameras, walkmesh geometry/topology and animations",
     "Lexeditor has preservation-safe editors for BGI_FLOOR_ACTIVE plus Memoria Field Creator's documented triangle Active, Alternate footstep, Prevent NPC pathing and Prevent PC pathing flags. Background art, cameras, walkmesh geometry/topology, edge semantics, transforms, remaining/internal flag semantics and moving-platform animation data remain protected and unintegrated rather than being routed through a lossy generic editor."),
    ("StreamingAssets/p0data2.bin (outside BattleScene raw16)", "Battle geometry, scene assets and effects",
     "Enemy, encounter, enemy-attack and battle-flag BattleScene raw16 records are integrated separately. Public tooling also reads battle meshes/background assets, SPS/effect data and related scene resources from p0data2; Lexeditor has no safe structured editor for those assets yet."),
    ("StreamingAssets/p0data3.bin", "World-map geometry, materials and effects",
     "Public FF9 tooling reads and overrides world-map assets from p0data3. Lexeditor's World tab currently edits only documented Memoria CSV controls, not the packed world geometry/material/effect data."),
    ("StreamingAssets/p0data4.bin", "Field and character 3D models",
     "Public tooling identifies native Unity GameObject/skinned-mesh prefabs in p0data4 and can export them to editable model formats. Lexeditor has no preservation-tested mesh/rig import and override editor yet."),
    ("StreamingAssets/p0data5.bin", "Character and model animations",
     "Public tooling identifies serialized AnimationClips in p0data5 and Memoria supports loose animation overrides. Lexeditor has no semantic animation editor/import round-trip yet."),
    ("StreamingAssets/p0data7.bin", "Compiled field, battle and world event scripts",
     "Public tooling decodes and emits the compiled .eb event-script families loaded from p0data7. Lexeditor has no safe script decompiler/editor/recompiler UI with preservation coverage yet."),
    ("StreamingAssets/p0data6*.bin and other unmatched p0data*.bin", "Audio evidence plus remaining packed Unity asset families",
     "Public research byte-identifies at least title BGM music033.akb in p0data61.bin/p0data601.bin, and Memoria recognizes p0data61.bin, p0data62.bin and p0data63.bin as mod-content bundle names. That does not establish a bounded schema for the whole p0data6* family, so Lexeditor keeps the remaining contents visible and unintegrated rather than guessing."),
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
    integrated = []
    for row in catalog():
        available = bool(row["available"])
        integrated.append({
            "filename": row["relativePath"], "controls": row["controls"],
            "notes": (f"{row['label']}. Structured editor is integrated; writes a project overlay and never overwrites the game baseline."
                      + (" Source data is available now." if available else " The local baseline is not available yet; opening the view will retry it.")),
            "status": "integrated", "coverage": "structured",
            "openable": True, "sourceAvailable": available, "target": row["tab"],
            "dataset": row["key"], "datasetKey": row["key"],
        })
    for row in BattleSceneStore().status_rows():
        integrated.append({
            "filename": row["relativePath"], "controls": row["controls"],
            "notes": (row["notes"] + (" Source data is available now." if row["available"] else
                      " The installed p0data2 source is not available yet; opening the view shows that dependency without changing integration status.")),
            "status": "integrated", "coverage": "structured",
            "openable": True, "sourceAvailable": bool(row["available"]),
            "target": row["tab"], "datasetKey": row["key"],
        })
    for row in FIELD_WALKMESH.status_rows():
        integrated.append({
            "filename": row["relativePath"], "controls": row["controls"],
            "notes": (row["notes"] + (" Source data is available now." if row["available"] else
                      " No installed p0data1 field bundle or project BGI override is available yet; opening the view shows that dependency without changing integration status.")),
            "status": "partial", "coverage": "structured",
            "openable": True, "sourceAvailable": bool(row["available"]),
            "target": row["tab"], "datasetKey": row["key"],
        })
    launcher = paths.GAME_ROOT / "FF9_Launcher.exe"
    deployment = features.status()
    integrated.append({
        "filename": "Lexeditor/StreamingAssets/Scripts/Memoria.Scripts.Lexeditor.dll",
        "controls": "Lexeditor FF9 runtime tweaks",
        "notes": "Lexeditor-owned optional Memoria script runtime. Deploy Project activates the fixed Lexeditor mod folder; Memoria.ini remains otherwise untouched.",
        "status": "integrated", "coverage": "structured",
        "openable": True, "sourceAvailable": bool(deployment["runtimeReady"]), "target": "tweaks",
    })
    return {"contract": "Lexeditor.data-map", "rows": integrated + [{
        "filename": "FF9_Launcher.exe", "controls": "Memoria settings in its own launcher",
        "notes": "Play opens the launcher. Lexeditor does not edit Memoria.ini; Tweaks explains this handoff.",
        "status": "integrated", "coverage": "handoff", "sourceAvailable": launcher.is_file(),
        "openable": True, "target": "tweaks",
    }] + [{
        "filename": filename, "controls": controls, "notes": notes,
        "status": "not-integrated", "coverage": "unavailable", "openable": False,
    } for filename, controls, notes in UNRESOLVED_AREAS]}


def dashboard() -> dict:
    problems = paths.game_problems()
    memoria = ensure_baseline()
    available = sum(1 for row in catalog() if row["available"])
    launcher = paths.GAME_ROOT / "FF9_Launcher.exe"
    player = paths.GAME_ROOT / "x64" / "FF9.exe"
    assembly = paths.GAME_ROOT / "x64" / "FF9_Data" / "Managed" / "Assembly-CSharp.dll"
    return {
        "game": {"root": str(paths.GAME_ROOT), "executable": str(launcher),
                 "settingsExecutable": str(launcher), "ready": not problems,
                 "steamAppId": "377840", "steamBuildId": _steam_build(),
                 "launcherSha256": _hash(launcher), "playerSha256": _hash(player),
                 "assemblySha256": _hash(assembly)},
        "baseline": {"ready": available > 0, "fileCount": available,
                     "message": (f"{available} Memoria CSV datasets are available." if available else
                                 "The verified Memoria data baseline is not available yet."),
                     "memoriaRelease": memoria["release"], "memoriaSource": memoria["source"],
                     "problems": memoria["problems"]},
        "problems": problems, "project": {"root": str(paths.PROJECT_ROOT)},
        "runtime": memoria_manager.status(paths.GAME_ROOT), "features": features.load(),
        "deployment": features.status(), "modCompatibility": mod_compat.audit(),
        "scaffold": False,
    }


class Handler(PluginRequestHandler):
    server_version = "LexeditorFF9/3"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/":
                self.file_response(PLUGIN_ROOT / "editor.html")
            elif self.send_page_module(PLUGIN_ROOT, path):
                return
            elif path.startswith("/shared/"):
                shared = (LEXEDITOR_ROOT / "ui").resolve()
                target = (shared / path.removeprefix("/shared/")).resolve()
                if shared not in target.parents or not target.is_file():
                    self.json_response({"error": "Shared UI asset not found"}, 404)
                else:
                    self.file_response(target)
            elif path.startswith("/assets/") and path.removeprefix("/assets/") in game_font.FACES:
                # Private copies of the installed fonts; a missing install
                # answers 404 and the page keeps its fallback font stack.
                try:
                    font = game_font.ensure_font(path.removeprefix("/assets/"))
                except (OSError, ValueError) as error:
                    self.json_response({"error": str(error)}, 404)
                else:
                    self.file_response(font)
            elif path == "/api/plugin":
                self.json_response({"apiVersion": 1, "pluginId": "ff9", "name": "Final Fantasy IX",
                    "edition": "Steam Unity / Memoria CSV", "hosted": HOSTED, "windowHost": WINDOW_HOST,
                    "projectRoot": str(paths.PROJECT_ROOT), "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": ["data-map", "memoria-csv", "battle-scenes", "field-walkmesh", "ff9-features", "deploy", "read", "save"]})
            elif path == "/api/dashboard": self.json_response(dashboard())
            elif path == "/api/datamap": self.json_response(data_map())
            elif path == "/api/catalog": self.json_response({"datasets": catalog() + BattleSceneStore().status_rows() + FIELD_WALKMESH.status_rows()})
            elif path == "/api/dataset":
                query = parse_qs(parsed.query)
                key = query.get("key", [""])[0]
                scene = query.get("scene", [None])[0]
                self.json_response(BattleSceneStore().load(key) if key in BattleSceneStore.KEYS else FIELD_WALKMESH.load(key, scene) if key in FIELD_WALKMESH.KEYS else MemoriaDataStore().load(key))
            elif path == "/api/runtime": self.json_response(memoria_manager.status(paths.GAME_ROOT))
            elif path == "/api/runtime/available": self.json_response(memoria_manager.available())
            elif path == "/api/mod-compat": self.json_response(mod_compat.audit())
            elif path == "/api/features": self.json_response(features.load())
            elif path == "/api/deployment": self.json_response(features.status())
            else: self.json_response({"error": "Not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        if self.refuse_write_when_read_only(path):
            return
        try:
            if path not in POST_ROUTES:
                self.json_response({"error": "Not found"}, 404); return
            port = self.server.server_address[1]
            allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            host, origin = self.headers.get("Host", "").casefold(), self.headers.get("Origin")
            if host not in allowed_hosts or (origin is not None and origin not in {f"http://{host}"}):
                self.json_response({"error": "Only this editor may change FF9 data"}, 403); return
            if self.headers.get_content_type() != "application/json":
                self.json_response({"error": "An application/json request is required"}, 415); return
            if self.headers.get("Transfer-Encoding"):
                self.json_response({"error": "Chunked requests are not supported"}, 400); return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                self.json_response({"error": "Invalid or oversized request body"}, 413); return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict): raise ValueError("The request must be a JSON object")
            if path == "/api/runtime/install": result = memoria_manager.install(paths.GAME_ROOT)
            elif path == "/api/runtime/recover": result = memoria_manager.recover(paths.GAME_ROOT)
            elif path == "/api/runtime/settings": result = memoria_manager.open_settings(paths.GAME_ROOT)
            elif path == "/api/features/save": result = features.save(payload.get("features", {}), str(payload.get("sha256", "")))
            elif path == "/api/deployment/deploy": result = features.deploy()
            elif path == "/api/deployment/revert": result = features.revert()
            else:
                key = str(payload.get("key", ""))
                result = (BattleSceneStore().save(key, payload.get("sceneHashes", {}), payload.get("changes", []))
                          if key in BattleSceneStore.KEYS else
                          FIELD_WALKMESH.save(key, payload.get("sceneHashes", {}), payload.get("changes", []))
                          if key in FIELD_WALKMESH.KEYS else
                          MemoriaDataStore().save(key, str(payload.get("sha256", "")), payload.get("changes", [])))
            self.json_response(result)
        except FileNotFoundError as error: self.json_response({"error": str(error)}, 409)
        except RuntimeError as error: self.json_response({"error": str(error)}, 409)
        except Exception as error: self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
