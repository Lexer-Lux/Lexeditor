"""Loopback editor service for FINAL FANTASY VII REMAKE INTERGRADE."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import threading
from urllib.parse import parse_qs, urlparse

from .archive import build_index, preferred_pak_version
from .atb_tweaks import has_enabled_data_overrides, materialize_atb_overrides
from .encounter_tweaks import (
    has_enabled_encounter_tweaks,
    materialize_encounter_tweaks,
)
from .graphics_tweaks import (
    config_path as graphics_config_path,
    deploy_graphics_tweaks,
    graphics_status,
)
from .minimap_semantics import (
    ENEMY_TERRITORY_TABLE_NAME,
    HIDE_NAVIMAP_FIELD,
    minimap_visibility_payload,
    save_minimap_visibility_edits,
)
from .native_probe import probe_installed_exe
from .runtime_config import load_runtime_config, save_runtime_config
from .runtime_state import deploy_runtime, runtime_status
from .semantics import (
    ECONOMY_EDIT_FIELDS,
    ECONOMY_TABLE_NAMES,
    LOOT_FIELD_PAIRS,
    LOOT_TABLE_NAME,
    economy_payload,
    loot_payload,
    save_economy_edits,
    save_loot_edits,
)
from .storage import load_package, save_edits
from .text_storage import load_text_package, resident_text_map, save_text_edits
from .tooling import FF7R_MOUNT_POINT, helper_status, pack_directory


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", os.environ.get("LEXEDITOR_FF7R_PORT", "0")))
GAME_ROOT = Path(os.environ.get("LEXEDITOR_FF7R_ROOT", ".")).expanduser().resolve()
DATA_ROOT = Path(os.environ.get("LEXEDITOR_FF7R_DATA_ROOT", ROOT / "out" / "ff7r-data")).expanduser().resolve()
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_FF7R_PROJECT", ROOT / "out" / "ff7r-project")).expanduser().resolve()
MAX_BODY = 16 * 1024 * 1024
_catalog_lock = threading.RLock()
_catalog_cache: dict | None = None

ECONOMY_GENERIC_FIELDS = {prop: field for field, prop in ECONOMY_EDIT_FIELDS.items()}
LOOT_GENERIC_FIELDS: dict[str, tuple[str, str]] = {}
for _kind, _item_prop, _chance_prop, _quantity_prop in LOOT_FIELD_PAIRS:
    LOOT_GENERIC_FIELDS[_item_prop] = (_kind, "item")
    if _chance_prop:
        LOOT_GENERIC_FIELDS[_chance_prop] = (_kind, "chance")
    if _quantity_prop:
        LOOT_GENERIC_FIELDS[_quantity_prop] = (_kind, "quantity")


def catalog(*, refresh: bool = False) -> dict:
    global _catalog_cache
    with _catalog_lock:
        if refresh or _catalog_cache is None:
            _catalog_cache = build_index(GAME_ROOT, DATA_ROOT)
        return _catalog_cache


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_strings(child)


def data_payload(asset: str, *, vanilla: bool = False, language: str = "US") -> dict:
    package, source_sha, using_project = load_package(
        GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset, vanilla=vanilla)
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    referenced = {
        value
        for entry in package.entries
        for value in _walk_strings(entry.values)
        if value.startswith("$")
    }
    lookup: dict[str, str] = {}
    if referenced:
        try:
            resident = resident_text_map(
                GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), language=language)
            lookup = {key: resident[key] for key in referenced if key in resident}
        except Exception:
            lookup = {}
    payload["textLookup"] = lookup
    payload["textLanguage"] = language.upper()
    return payload


def text_payload(asset: str, *, vanilla: bool = False) -> dict:
    package, source_uasset_sha, source_uexp_sha, using_project = load_text_package(
        GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset, vanilla=vanilla)
    return package.api_payload(
        source_uasset_sha256=source_uasset_sha,
        source_uexp_sha256=source_uexp_sha,
        using_project=using_project,
    )


def data_map_payload() -> dict:
    rows = []
    for item in catalog().get("assets", []):
        asset_name = Path(item["asset"]).name.casefold()
        semantic = []
        if asset_name in ECONOMY_TABLE_NAMES:
            semantic.append("economy / prices when BuyValue/SaleValue fields exist")
        if asset_name == LOOT_TABLE_NAME:
            semantic.append("enemy normal/rare drops, chances and steal data")
        if asset_name == ENEMY_TERRITORY_TABLE_NAME:
            semantic.append("authored minimap forced-hide flags when HideNavimap is a scalar boolean")
        group = str(item.get("group", ""))
        if group == "Lexeditor ATB":
            semantic.append("reversible ATB tweak config materialized only when the ATB tweak is enabled")
        if group == "Lexeditor Encounters":
            semantic.append("reversible authored encounter edits materialized only when their tweak is enabled")
        if group == "Lexeditor Graphics":
            semantic.append("reversible Engine.ini graphics overrides applied only by explicit deployment")
        controls = (
            "Structured DataObject records; booleans, fixed-width numbers, floats "
            "and existing FNames are editable."
        )
        if semantic:
            controls += " Semantic surface: " + "; ".join(semantic) + "."
        rows.append({
            "filename": item["asset"] + ".uasset / .uexp",
            "target": item["asset"],
            "controls": controls,
            "notes": (
                "FString and arbitrary structural edits remain read-only; "
                "unknown bytes are preserved in the project overlay."
            ),
            "coverage": "structured",
            "status": "partial",
        })
    for item in catalog().get("textAssets", []):
        rows.append({
            "filename": item["asset"] + ".uasset / .uexp",
            "target": item["asset"],
            "controls": (
                "Localized menu, item, dialogue, subtitle and other text-resource "
                "strings, including existing sub-entry text."
            ),
            "notes": (
                "Text can change length and encoding. IDs, entry counts and "
                "sub-entry structure remain fixed."
            ),
            "coverage": "structured",
            "status": "partial",
        })
    rows.append({
        "filename": "runtime/LexeditorFF7RRuntime.json + LexeditorFF7RRuntime.dll",
        "target": "NativeMods runtime behavior",
        "controls": "Cutscene base-speed multiplier and tap/hold minimap behavior.",
        "notes": (
            "Native runtime behavior is separate from PAK edits. Deployment/readiness uses build/manifest validation; "
            "Runtime Active additionally requires a live DLL heartbeat from the current FF7R process."
        ),
        "coverage": "runtime-contract",
        "status": "partial",
    })
    return {"rows": rows}


def info_payload() -> dict:
    current = catalog()
    languages = sorted({
        str(row.get("language", ""))
        for row in current.get("textAssets", [])
        if row.get("language")
    })
    runtime = runtime_status(GAME_ROOT, PROJECT_ROOT)
    graphics = graphics_status(GAME_ROOT, PROJECT_ROOT)
    return {
        "gameRoot": str(GAME_ROOT),
        "dataRoot": str(DATA_ROOT),
        "projectRoot": str(PROJECT_ROOT),
        "dataObjects": len(current.get("assets", [])),
        "textResources": len(current.get("textAssets", [])),
        "textLanguages": languages,
        "helper": helper_status(),
        "runtime": runtime,
        "graphics": graphics,
        "engineIniPath": graphics["engineIniPath"],
        "pakVersion": preferred_pak_version(current),
        "pakMountPoint": FF7R_MOUNT_POINT,
        "buildPath": str(PROJECT_ROOT / "build" / "Lexeditor-FF7R_P.pak"),
        "deployPath": str(
            GAME_ROOT / "End" / "Content" / "Paks" / "~mods" / "Lexeditor-FF7R_P.pak"
        ),
    }


def _has_pak_edits() -> bool:
    content = PROJECT_ROOT / "content"
    has_content = content.is_dir() and any(path.is_file() for path in content.rglob("*"))
    return (
        has_content
        or has_enabled_data_overrides(PROJECT_ROOT)
        or has_enabled_encounter_tweaks(PROJECT_ROOT)
    )


def build_mod() -> dict:
    content = PROJECT_ROOT / "content"
    has_content = content.is_dir() and any(path.is_file() for path in content.rglob("*"))
    has_atb = has_enabled_data_overrides(PROJECT_ROOT)
    has_encounter = has_enabled_encounter_tweaks(PROJECT_ROOT)
    has_semantic_materialization = has_atb or has_encounter
    if not has_content and not has_semantic_materialization:
        raise RuntimeError("The FF7R project has no saved edits to build")

    target = PROJECT_ROOT / "build" / "Lexeditor-FF7R_P.pak"
    if not has_semantic_materialization:
        pack_directory(content, target, version=preferred_pak_version(catalog()))
        return {
            "path": str(target),
            "size": target.stat().st_size,
            "atbMaterialized": [],
            "encounterMaterialized": [],
        }

    # Semantic overrides never live permanently in project/content. Compose
    # them over any ordinary project edits in a temporary staging tree, pack the
    # result, and then discard the generated DataObjects.
    with TemporaryDirectory(prefix="lexeditor-ff7r-build-") as temp_name:
        staging = Path(temp_name) / "content"
        staging.mkdir(parents=True, exist_ok=True)
        if has_content:
            shutil.copytree(content, staging, dirs_exist_ok=True)
        atb_materialized = materialize_atb_overrides(
            GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), staging)
        encounter_materialized = materialize_encounter_tweaks(
            GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), staging)
        if not any(path.is_file() for path in staging.rglob("*")):
            raise RuntimeError("Enabled FF7R semantic tweaks produced no buildable DataObject edits")
        pack_directory(staging, target, version=preferred_pak_version(catalog()))
    return {
        "path": str(target),
        "size": target.stat().st_size,
        "atbMaterialized": atb_materialized,
        "encounterMaterialized": encounter_materialized,
    }


def deploy_mod() -> dict:
    built = Path(build_mod()["path"])
    target = GAME_ROOT / "End" / "Content" / "Paks" / "~mods" / "Lexeditor-FF7R_P.pak"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(built, temporary)
    temporary.replace(target)
    return {"path": str(target), "size": target.stat().st_size}


def deploy_project() -> dict:
    graphics = graphics_status(GAME_ROOT, PROJECT_ROOT)
    graphics_configured = graphics_config_path(PROJECT_ROOT).is_file() or graphics["managedOverridePresent"]
    if graphics["disableEyeAdaptationRequested"] and not graphics["deployReady"]:
        raise RuntimeError(graphics["notes"])
    has_pak = _has_pak_edits()
    if not has_pak and not graphics_configured:
        raise RuntimeError("The FF7R project has no saved edits to deploy")

    pak_result = deploy_mod() if has_pak else None
    graphics_result = (
        deploy_graphics_tweaks(GAME_ROOT, PROJECT_ROOT)
        if graphics_configured
        else None
    )
    path = pak_result["path"] if pak_result else graphics_result["path"]
    return {
        "path": path,
        "pak": pak_result,
        "graphics": graphics_result,
    }


def _semantic_save_from_generic(asset: str, *, source_sha256: str,
                                active_sha256: str, edits: list[dict]):
    """Route pure semantic edit sets through the stricter semantic validators."""
    asset_name = Path(asset).name.casefold()
    if asset_name in ECONOMY_TABLE_NAMES and edits and all(
        isinstance(edit, dict)
        and edit.get("property") in ECONOMY_GENERIC_FIELDS
        and "index" not in edit
        for edit in edits
    ):
        semantic_edits = [
            {
                "entry": edit.get("entry"),
                "field": ECONOMY_GENERIC_FIELDS[edit["property"]],
                "value": edit.get("value"),
            }
            for edit in edits
        ]
        return save_economy_edits(
            GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
            source_sha256=source_sha256,
            active_sha256=active_sha256,
            edits=semantic_edits,
        )

    if asset_name == LOOT_TABLE_NAME and edits and all(
        isinstance(edit, dict)
        and edit.get("property") in LOOT_GENERIC_FIELDS
        and "index" in edit
        for edit in edits
    ):
        semantic_edits = []
        for edit in edits:
            kind, field = LOOT_GENERIC_FIELDS[edit["property"]]
            semantic_edits.append({
                "entry": edit.get("entry"),
                "kind": kind,
                "index": edit.get("index"),
                "field": field,
                "value": edit.get("value"),
            })
        return save_loot_edits(
            GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
            source_sha256=source_sha256,
            active_sha256=active_sha256,
            edits=semantic_edits,
        )

    if asset_name == ENEMY_TERRITORY_TABLE_NAME and edits and all(
        isinstance(edit, dict)
        and edit.get("property") == HIDE_NAVIMAP_FIELD
        and "index" not in edit
        for edit in edits
    ):
        semantic_edits = [
            {"entry": edit.get("entry"), "hideNavimap": edit.get("value")}
            for edit in edits
        ]
        return save_minimap_visibility_edits(
            GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
            source_sha256=source_sha256,
            active_sha256=active_sha256,
            edits=semantic_edits,
        )
    return None


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
                    "capabilities": [
                        "data-map", "dataobject", "text-resource", "economy",
                        "enemy-loot", "minimap-visibility", "runtime-config", "native-probe",
                        "encounter-tweaks", "graphics-tweaks", "save", "economy-save",
                        "enemy-loot-save", "minimap-visibility-save", "text-save", "build",
                        "deploy", "runtime-deploy", "graphics-deploy",
                    ],
                })
            if path == "/api/catalog":
                return self.send_json(catalog(refresh=query.get("refresh") == ["1"]))
            if path == "/api/datamap":
                return self.send_json(data_map_payload())
            if path == "/api/info":
                return self.send_json(info_payload())
            if path == "/api/runtime":
                status = runtime_status(GAME_ROOT, PROJECT_ROOT)
                status["config"] = load_runtime_config(PROJECT_ROOT)
                return self.send_json(status)
            if path == "/api/runtime/probe":
                return self.send_json(probe_installed_exe(GAME_ROOT))
            if path == "/api/graphics":
                return self.send_json(graphics_status(GAME_ROOT, PROJECT_ROOT))
            if path == "/api/data":
                asset = (query.get("asset") or [""])[0]
                if not asset:
                    raise ValueError("asset is required")
                vanilla = (query.get("source") or [""])[0] == "vanilla"
                language = (query.get("language") or ["US"])[0]
                return self.send_json(data_payload(asset, vanilla=vanilla, language=language))
            if path == "/api/economy":
                vanilla = (query.get("source") or [""])[0] == "vanilla"
                language = (query.get("language") or ["US"])[0]
                return self.send_json(economy_payload(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(),
                    language=language, vanilla=vanilla,
                ))
            if path == "/api/loot":
                vanilla = (query.get("source") or [""])[0] == "vanilla"
                language = (query.get("language") or ["US"])[0]
                return self.send_json(loot_payload(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(),
                    language=language, vanilla=vanilla,
                ))
            if path == "/api/minimap-visibility":
                vanilla = (query.get("source") or [""])[0] == "vanilla"
                return self.send_json(minimap_visibility_payload(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), vanilla=vanilla,
                ))
            if path == "/api/text":
                asset = (query.get("asset") or [""])[0]
                if not asset:
                    raise ValueError("asset is required")
                vanilla = (query.get("source") or [""])[0] == "vanilla"
                return self.send_json(text_payload(asset, vanilla=vanilla))
            return self.send_json({"error": "Not found"}, 404)
        except (ValueError, KeyError, IndexError, FileNotFoundError) as error:
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
                source_sha256 = str(payload.get("sourceSha256", ""))
                active_sha256 = str(payload.get("activeSha256", ""))
                semantic = _semantic_save_from_generic(
                    asset,
                    source_sha256=source_sha256,
                    active_sha256=active_sha256,
                    edits=edits,
                )
                if semantic is not None:
                    return self.send_json(semantic)
                return self.send_json(save_edits(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
                    source_sha256=source_sha256,
                    active_sha256=active_sha256,
                    edits=edits,
                ))
            if path == "/api/economy/save":
                asset = str(payload.get("asset", ""))
                edits = payload.get("edits", [])
                if not asset or not isinstance(edits, list):
                    raise ValueError("asset and edits are required")
                return self.send_json(save_economy_edits(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
                    source_sha256=str(payload.get("sourceSha256", "")),
                    active_sha256=str(payload.get("activeSha256", "")),
                    edits=edits,
                ))
            if path == "/api/loot/save":
                asset = str(payload.get("asset", ""))
                edits = payload.get("edits", [])
                if not asset or not isinstance(edits, list):
                    raise ValueError("asset and edits are required")
                return self.send_json(save_loot_edits(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
                    source_sha256=str(payload.get("sourceSha256", "")),
                    active_sha256=str(payload.get("activeSha256", "")),
                    edits=edits,
                ))
            if path == "/api/minimap-visibility/save":
                asset = str(payload.get("asset", ""))
                edits = payload.get("edits", [])
                if not asset or not isinstance(edits, list):
                    raise ValueError("asset and edits are required")
                return self.send_json(save_minimap_visibility_edits(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
                    source_sha256=str(payload.get("sourceSha256", "")),
                    active_sha256=str(payload.get("activeSha256", "")),
                    edits=edits,
                ))
            if path == "/api/runtime/save":
                config = payload.get("config")
                if not isinstance(config, dict):
                    raise ValueError("config is required")
                return self.send_json({"config": save_runtime_config(PROJECT_ROOT, config)})
            if path == "/api/runtime/deploy":
                return self.send_json(deploy_runtime(GAME_ROOT, PROJECT_ROOT))
            if path == "/api/graphics/deploy":
                return self.send_json(deploy_graphics_tweaks(GAME_ROOT, PROJECT_ROOT))
            if path == "/api/text/save":
                asset = str(payload.get("asset", ""))
                edits = payload.get("edits", [])
                if not asset or not isinstance(edits, list):
                    raise ValueError("asset and edits are required")
                return self.send_json(save_text_edits(
                    GAME_ROOT, DATA_ROOT, PROJECT_ROOT, catalog(), asset,
                    source_uasset_sha256=str(payload.get("sourceUassetSha256", "")),
                    source_uexp_sha256=str(payload.get("sourceUexpSha256", "")),
                    active_uasset_sha256=str(payload.get("activeUassetSha256", "")),
                    active_uexp_sha256=str(payload.get("activeUexpSha256", "")),
                    edits=edits,
                ))
            if path == "/api/build":
                return self.send_json(build_mod())
            if path == "/api/deploy":
                return self.send_json(deploy_project())
            return self.send_json({"error": "Not found"}, 404)
        except (ValueError, KeyError, IndexError, TypeError, FileNotFoundError) as error:
            return self.send_json({"error": str(error)}, 400)
        except Exception as error:
            return self.send_json({"error": str(error)}, 500)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()