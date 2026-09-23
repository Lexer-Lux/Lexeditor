"""Loopback service for the Final Fantasy VII Rebirth plugin.

It serves the page and the shared UI, answers where the game is, and runs
Shader Injector: install, switch on and off, remove, settings, and clearing the
game's shader cache. Every ReShade action goes through the desktop host, which
owns the one copy of ReShade and Lexeditor's effects.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from games.ff7r2 import packaging, shader_injector
from games.ff7r2.dataobject import DataObjectError, DataObjectPackage
from plugin_http import PluginRequestHandler


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY_BYTES = 512 * 1024
PROJECT_ENV = "LEXEDITOR_FF7R2_PROJECT"
PLAYER_PARAMETER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")


def game_root() -> Path | None:
    value = os.environ.get("LEXEDITOR_FF7R2_ROOT", "").strip()
    if not value:
        return None
    root = Path(value)
    return root if root.is_dir() else None



def project_root() -> Path | None:
    value = os.environ.get(PROJECT_ENV, "").strip()
    if not value:
        return None
    root = Path(value)
    return root if root.is_dir() else None


def project_read_only() -> bool:
    return os.environ.get("LEXEDITOR_MOD_READ_ONLY", "0") == "1"


def source_path() -> Path | None:
    root = project_root()
    return root / "source" / PLAYER_PARAMETER if root else None


def output_path() -> Path | None:
    root = project_root()
    return root / "content" / PLAYER_PARAMETER if root else None


def active_player_path(source: str = "mine") -> tuple[Path, str]:
    baseline = source_path()
    candidate = output_path()
    if baseline is None:
        raise DataObjectError("No FF7 Rebirth project is selected.")
    if not baseline.is_file():
        raise DataObjectError(
            "PlayerParameter source is missing. Place the extracted IoStore-state "
            f"asset at source/{PLAYER_PARAMETER.as_posix()} inside this project."
        )
    if source == "vanilla":
        return baseline, "source"
    if source != "mine":
        raise DataObjectError("source must be mine or vanilla")
    if candidate is not None and candidate.is_file():
        return candidate, "project"
    return baseline, "source"


def player_payload(source: str = "mine") -> dict:
    path, origin = active_player_path(source)
    package = DataObjectPackage.from_bytes(path.read_bytes())
    payload = package.payload()
    root = project_root()
    payload.update({
        "source": origin,
        "path": str(path),
        "projectRelativePath": str(path.relative_to(root)).replace("\\", "/") if root else "",
        "readOnly": project_read_only() or source == "vanilla",
    })
    return payload


def workspace_payload() -> dict:
    root = project_root()
    baseline = source_path()
    candidate = output_path()
    game = game_root()
    package = packaging.status(root, game)
    return {
        "projectRoot": str(root) if root else "",
        "projectName": root.name if root else "",
        "readOnly": project_read_only(),
        "game": {
            "root": str(game) if game else "",
            "found": game is not None,
            "renderer": "dxgi",
            "binaries": str(game / "End/Binaries/Win64") if game else "",
        },
        "playerParameter": {
            "relative": PLAYER_PARAMETER.as_posix(),
            "sourceRelative": f"source/{PLAYER_PARAMETER.as_posix()}",
            "outputRelative": f"content/{PLAYER_PARAMETER.as_posix()}",
            "sourcePresent": bool(baseline and baseline.is_file()),
            "outputPresent": bool(candidate and candidate.is_file()),
        },
        "delivery": {
            "staged": package["stagedPresent"],
            "stagedFileCount": package["stagedFileCount"],
            "stagedFiles": package["stagedFiles"],
            "path": str(candidate) if candidate and candidate.is_file() else "",
            "packaged": package["candidateCount"] > 0,
            "installed": False,
            "packaging": package,
            "reason": (
                "Lexeditor stages proved project outputs without touching the game. "
                "The candidate builder audits every regular file under content/End/Content, "
                "rejects symlinks and rechecks the full staged file set and hashes after packing. "
                "UnrealReZen and Oodle must be explicitly supplied; candidates are never installed "
                "automatically and remain unaccepted until verified in the real game."
            ),
        },
        "tooling": {
            "shaderInjector": {"pinned": shader_injector.VERSION, "managedBySharedUpdates": True},
            "retoc": {
                "pinned": "v0.1.5",
                "license": "MIT",
                "integrated": False,
                "reason": (
                    "The public release can acquire Oodle when the DLL is absent; "
                    "Lexeditor will not trigger that silent network dependency."
                ),
            },
            "unrealReZen": {
                "reference": "matyamod/UnrealReZen ff7r",
                "license": "GPL-3.0",
                "integrated": False,
                "candidateBuilder": True,
                "reason": (
                    "The FF7R2 fork documents UE4.26 packaging. Lexeditor's candidate "
                    "builder refuses to run without explicit local UnrealReZen and Oodle "
                    "paths plus the known CUE4Parse/1.1.1 dependency manifest; the supplied Oodle "
                    "must already be oo2core_9_win64.dll beside UnrealReZen before process start. "
                    "Output stays under the project and still needs real-game acceptance/shared ownership."
                ),
            },
        },
    }


def _write_player_candidate(body: dict) -> dict:
    if project_read_only():
        raise DataObjectError("This project is read-only.")
    current, _origin = active_player_path("mine")
    package = DataObjectPackage.from_bytes(current.read_bytes())
    expected = str(body.get("sha256") or "")
    if expected and expected != package.payload()["activeSha256"]:
        raise DataObjectError("PlayerParameter changed on disk. Reopen it before saving.")
    edits = body.get("changes")
    if not isinstance(edits, list):
        raise DataObjectError("changes must be an array")
    changed = package.apply_edits(edits)
    target = output_path()
    if target is None:
        raise DataObjectError("No FF7 Rebirth project is selected.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(package.to_bytes())
    temporary.replace(target)
    payload = player_payload("mine")
    payload["changedFields"] = changed
    return payload


def _reset_player_candidate() -> dict:
    if project_read_only():
        raise DataObjectError("This project is read-only.")
    target = output_path()
    if target and target.is_file():
        target.unlink()
    return player_payload("mine")

def injector_folder() -> Path | None:
    """The folder Shader Injector is declared to live in, if the game has it."""
    root = game_root()
    if root is None:
        return None
    folder = root / shader_injector.INSTALL_FOLDER
    return folder if folder.is_dir() else None


def injector_state() -> dict:
    folder = injector_folder()
    if folder is None:
        return {"available": False,
                "reason": "Locate Final Fantasy VII Rebirth first. Shader Injector goes in its End/Binaries/Win64 folder."}
    return {"available": True, **shader_injector.status(folder)}


def data_map_payload() -> dict:
    binaries = f"{shader_injector.INSTALL_FOLDER}/"
    cache = "Documents/" + "/".join(shader_injector.CACHE_FOLDER) + "/"
    rows = [
        {
            "filename": PLAYER_PARAMETER.as_posix(),
            "controls": "Characters — real row FName identity and fixed-width scalar controls",
            "coverage": "structured",
            "notes": (
                "Implemented from public Rebirth format evidence and synthetic structural "
                "fixtures. Real installed-game acceptance is still pending."
            ),
            "status": "partial", "target": "characters",
        },
        {
            "filename": "End/Content/DataObject/Resident/BattlePlayerParameter.uasset",
            "controls": "None", "coverage": "unavailable",
            "notes": (
                "Known table includes arrays and behavior-linked fields. Array resizing "
                "and semantics have not been proved in Lexeditor."
            ), "status": "not-integrated",
        },
        {
            "filename": "pakchunk3-WindowsNoEditor.utoc / .ucas",
            "controls": "None", "coverage": "unavailable",
            "notes": (
                "retoc v0.1.5 can address DirectoryIndex containers, but its Oodle "
                "dependency must be supplied explicitly before Lexeditor may invoke it."
            ), "status": "not-integrated",
        },
        {
            "filename": "FF7R2 IoStore patch package (.utoc/.ucas/.pak)",
            "controls": "None", "coverage": "unavailable",
            "notes": (
                "A dependency-explicit UnrealReZen candidate builder is available only when "
                "the local tool and its adjacent explicit Oodle path are supplied. It writes under the project and never "
                "installs; shared-helper ownership and real-game load acceptance are still pending."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/ResidentParameter.uasset (#470)",
            "controls": "None — Chocobo whistle research target", "coverage": "unavailable",
            "notes": (
                "Public Rebirth constants identify CallChocoboAtFieldActionDistanceParamRatio0/1; "
                "Item also identifies key_ChocoboWhistle, CharaSpec identifies "
                "FA0407_00_ChocoboWhistle_Standard, and CameraModule identifies ChocoboRide. "
                "Those names do not prove a teleport/mount hook, safe-placement rule, ride-legality "
                "predicate or vanilla fallback, and the distance-ratio semantics/ranges are unproved."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/BattleItemPossession.uasset (#471)",
            "controls": "None — Steal/drop formula research target", "coverage": "unavailable",
            "notes": (
                "Public constants identify NormalItemPercent_Array, RareItemPercent_Array, "
                "StealItemName_Array, StealItemQuantity_Array and StealFaildCountArrayIndex. "
                "The public 100% Steal/Drop mod author reports Rebirth shares the 25% rate data "
                "between steals and drops. Lexeditor intentionally cannot write arrays yet, and "
                "no source proves the complete Steal formula, roll-vs-no-item failure branch or message hook."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/StateChange.uasset + StateTrigger.uasset + ActionGroup.uasset (#472)",
            "controls": "None — restable-bench/cushion research family", "coverage": "unavailable",
            "notes": (
                "Public constants identify scgCmn_Tmp_Bench_Init/Rest, trgCmn_Bench_Rest and "
                "acgCmn_RecoverAll_ForBench; CharaSpec also identifies UI7033_00_ConsumedItem_Cushion. "
                "Public mesh work confirms the blue bench and Chocobo-rest benches are separate models. "
                "No public mapping yet proves every restable bench identity or the universal cushion-consumption gate."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/MapIconInfo.uasset + HUD package assets (#473)",
            "controls": "None — world-minimap zoom research family", "coverage": "unavailable",
            "notes": (
                "MapIconInfo publicly exposes navimap visibility/layer, offsets and view-distance fields, "
                "but no minimap zoom field. A 2026 accessibility mod proves minimap position/size can live "
                "in packaged HUD data, while its runtime HUD mover is separate UE4SS code. No proved world-minimap "
                "zoom scalar, valid range or persistence path has been found, so size/position is not relabeled as zoom."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/CardGameCommonParameter.uasset + CardGameAIParam.uasset (#477)",
            "controls": "None — Queen's Blood turn-flow research family", "coverage": "unavailable",
            "notes": (
                "Public constants expose CardGameCommonParameter rows such as EffectWaitTime and "
                "CardGameAIParam fields including NeedCanPutCount and Player/EnemyPredictionTurn. "
                "They do not establish the game's legal-move predicate, auto-pass transition, both-sides-no-moves "
                "end condition or the intro's first skippable input state. Lexeditor does not infer those rules from names."
            ), "status": "not-integrated",
        },
        {"filename": binaries + shader_injector.DLL,
         "controls": "Shader Injector's loader. Installed, switched on and off by renaming it to "
                     + shader_injector.DISABLED_DLL + ", and removed.",
         "notes": "Only the pinned release (" + shader_injector.VERSION + ", "
                  + shader_injector.VARIANT + ") is installed, checked by its SHA-256 before use.",
         "coverage": "structured", "status": "integrated", "target": "tweaks"},
        {"filename": binaries + shader_injector.INI,
         "controls": "Every Shader Injector setting, as a typed control: switches, numbers and key bindings.",
         "notes": "Written back in place; settings the plugin does not know are preserved.",
         "coverage": "structured", "status": "integrated", "target": "tweaks"},
        {"filename": binaries + shader_injector.FOLDER + "/",
         "controls": "The shader replacements Shader Injector loads.",
         "notes": "Installed with the release and removed with it; not edited.",
         "coverage": "source", "status": "partial", "target": "tweaks"},
        {"filename": cache + shader_injector.CACHE_PATTERN,
         "controls": "The game's compiled shader cache. Cleared on request so the injector sees shaders being created.",
         "notes": "Deleted files go to the Recycle Bin; the game rebuilds them on its next start.",
         "coverage": "view", "status": "partial", "target": "tweaks"},
        {"filename": binaries + "dxgi.dll / ReShade.ini / ReShadePreset.ini",
         "controls": "ReShade and Lexeditor's effects: the master switch, each effect and its values.",
         "notes": "Installed and configured by the desktop host, which owns the one copy of ReShade.",
         "coverage": "structured", "status": "integrated", "target": "tweaks"},
    ]
    for index, row in enumerate(rows):
        row["id"] = str(index)
    return {"rows": rows}


class Handler(PluginRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
        elif self.send_page_module(PLUGIN_ROOT, path):
            return
        elif path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Shared UI asset not found"}, 404)
        elif path == "/api/plugin":
            self.send_json({"apiVersion": 1, "pluginId": "ff7r2",
                            "name": "Final Fantasy VII Rebirth",
                            "hosted": True, "windowHost": "webview2",
                            "capabilities": ["reshade", "shader-injector", "data-map",
                            "player-parameter", "fixed-width-edit", "project-staging",
                            "package-candidate"]})
        elif path == "/api/datamap":
            self.send_json(data_map_payload())
        elif path == "/api/workspace":
            self.send_json(workspace_payload())
        elif path == "/api/player-parameter":
            try:
                source = parse_qs(urlparse(self.path).query).get("source", ["mine"])[0]
                self.send_json(player_payload(source))
            except (OSError, DataObjectError) as error:
                self.send_json({"error": str(error), "workspace": workspace_payload()}, 404)
        elif path == "/api/game":
            root = game_root()
            binaries = root / "End/Binaries/Win64" if root else None
            self.send_json({
                "root": str(root) if root else "",
                "found": root is not None,
                # Rebirth ships its own d3d12.dll, so dxgi is the loader.
                "renderer": "dxgi",
                "binaries": str(binaries) if binaries else "",
            })
        elif path == "/api/shader-injector":
            try:
                self.send_json(injector_state())
            except (OSError, ValueError, DataObjectError) as error:
                self.send_json({"error": str(error)}, 500)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        # Reject browser cross-origin writes to this loopback service: these
        # routes change files inside the game folder.
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            self.send_json({"error": "Cross-origin writes are not permitted"}, 403)
            return
        actions = {
            "/api/player-parameter/save", "/api/player-parameter/reset",
            "/api/package/build",
            "/api/shader-injector/install", "/api/shader-injector/uninstall",
            "/api/shader-injector/enabled", "/api/shader-injector/settings",
            "/api/shader-injector/clear-cache",
        }
        if path not in actions:
            self.send_json({"error": "Not found"}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0") or 0)
            if not 0 <= size <= MAX_BODY_BYTES:
                raise ValueError("Request size is invalid or too large")
            body = json.loads(self.rfile.read(size) or b"{}") if size else {}
            if not isinstance(body, dict):
                raise ValueError("Request must be a JSON object")
            if path == "/api/player-parameter/save":
                self.send_json(_write_player_candidate(body))
                return
            if path == "/api/player-parameter/reset":
                self.send_json(_reset_player_candidate())
                return
            if path == "/api/package/build":
                if project_read_only():
                    raise ValueError("This project is read-only.")
                root = project_root()
                game = game_root()
                self.send_json({
                    "result": packaging.build_candidate(root, game),
                    "workspace": workspace_payload(),
                })
                return
            folder = injector_folder()
            if folder is None:
                raise ValueError("Locate Final Fantasy VII Rebirth before changing Shader Injector.")
            result = {}
            if path.endswith("/install"):
                result = shader_injector.install(folder)
            elif path.endswith("/uninstall"):
                result = shader_injector.uninstall(folder)
            elif path.endswith("/enabled"):
                if not isinstance(body.get("enabled"), bool):
                    raise ValueError("enabled must be true or false")
                shader_injector.set_enabled(folder, body["enabled"])
            elif path.endswith("/settings"):
                shader_injector.write_settings(folder, body.get("changes") or {})
            elif path.endswith("/clear-cache"):
                result = shader_injector.clear_shader_cache()
            self.send_json({"result": result, "status": injector_state()})
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
