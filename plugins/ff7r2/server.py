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

from plugins.ff7r2 import packaging, shader_injector
from plugins.ff7r2.dataobject import DataObjectError, DataObjectPackage
from core.plugin_http import PluginRequestHandler
from core import unreal_config  # shared Unreal Engine config editor (issue 478)


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY_BYTES = 512 * 1024
PROJECT_ENV = "LEXEDITOR_FF7R2_PROJECT"
PLAYER_PARAMETER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")
BATTLE_PLAYER_PARAMETER = Path("End/Content/DataObject/Resident/BattlePlayerParameter.uasset")
BATTLE_ITEM_POSSESSION = Path("End/Content/DataObject/Resident/BattleItemPossession.uasset")


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


def unreal_state_root() -> Path:
    """Project sidecar root for Unreal config state (issue 478)."""
    root = project_root()
    if root is not None:
        return root
    return (Path(os.environ.get("LOCALAPPDATA", str(ROOT / "out")))
            / "Lexeditor" / "FF7R2")


def unreal_status_payload() -> dict:
    """Shared-editor status for the Rebirth Engine.ini (issue 478)."""
    return unreal_config.status("ff7r2", unreal_state_root())


def source_path() -> Path | None:
    root = project_root()
    return root / "source" / PLAYER_PARAMETER if root else None


def output_path() -> Path | None:
    root = project_root()
    return root / "content" / PLAYER_PARAMETER if root else None


def battle_player_source_path() -> Path | None:
    root = project_root()
    return root / "source" / BATTLE_PLAYER_PARAMETER if root else None


def battle_item_source_path() -> Path | None:
    root = project_root()
    return root / "source" / BATTLE_ITEM_POSSESSION if root else None


_BATTLE_PLAYER_SCHEMA = {
    "CommandAbilityID_Array": ("array", "NameProperty"),
    "EnableAerialShortCut": ("uint8", "ByteProperty"),
    "UniqueAbilityType0": ("uint8", "ByteProperty"),
    "UniqueAbilityParameterValue_Array": ("array", "FloatProperty"),
    "KeyDownTime": ("float", "FloatProperty"),
    "KeyDownEffectCreateTime": ("float", "FloatProperty"),
    "GuardParameterValue_Array": ("array", "FloatProperty"),
    "DodgeType_Array": ("array", "ByteProperty"),
    "LimitAbilityID_Array": ("array", "NameProperty"),
}


_BATTLE_ITEM_SCHEMA = {
    "NormalItemName_Array": ("array", "NameProperty"),
    "NormalItemPercent_Array": ("array", "ByteProperty"),
    "RareItemName_Array": ("array", "NameProperty"),
    "RareItemPercent_Array": ("array", "ByteProperty"),
    "StealItemName_Array": ("array", "NameProperty"),
    "StealItemQuantity_Array": ("array", "ByteProperty"),
    "StealFaildCountArrayIndex": ("int32", "IntProperty"),
}


def _validate_schema(package: DataObjectPackage, table: str,
                     schema: dict[str, tuple[str, str]]) -> None:
    if not package.records:
        raise DataObjectError(f"{table} contains no rows to validate")
    fields = {field.name: field for field in package.records[0].fields}
    for name, (kind, type_name) in schema.items():
        field = fields.get(name)
        if field is None:
            raise DataObjectError(f"{table} schema is missing proved field {name}")
        if field.kind != kind or field.type_name != type_name:
            raise DataObjectError(
                f"{table} field {name} has {field.kind}/{field.type_name}; "
                f"expected {kind}/{type_name}"
            )


def _source_only_payload(package: DataObjectPackage, reason: str) -> dict:
    payload = package.payload()
    for record in payload.get("records", []):
        for field in record.get("fields", []):
            field["editable"] = False
            field["note"] = reason
    return payload


def battle_player_payload() -> dict:
    root = project_root()
    path = battle_player_source_path()
    if root is None:
        raise DataObjectError("No FF7 Rebirth project is selected.")
    if path is None or not path.is_file():
        raise DataObjectError(
            "BattlePlayerParameter source is missing. Place the extracted IoStore-state "
            f"asset at source/{BATTLE_PLAYER_PARAMETER.as_posix()} inside this project."
        )
    package = DataObjectPackage.from_bytes(path.read_bytes())
    _validate_schema(package, "BattlePlayerParameter", _BATTLE_PLAYER_SCHEMA)
    payload = _source_only_payload(
        package,
        "Decoded source value; BattlePlayerParameter editing is disabled until "
        "gameplay semantics and safe ranges are proved.",
    )
    payload.update({
        "source": "source",
        "path": str(path),
        "projectRelativePath": str(path.relative_to(root)).replace("\\", "/"),
        "readOnly": True,
        "purpose": (
            "Public generated declarations prove these storage types, but not enough "
            "gameplay semantics or safe ranges to expose edits."
        ),
    })
    return payload


def battle_item_payload() -> dict:
    root = project_root()
    path = battle_item_source_path()
    if root is None:
        raise DataObjectError("No FF7 Rebirth project is selected.")
    if path is None or not path.is_file():
        raise DataObjectError(
            "BattleItemPossession source is missing. Place the extracted IoStore-state "
            f"asset at source/{BATTLE_ITEM_POSSESSION.as_posix()} inside this project."
        )
    package = DataObjectPackage.from_bytes(path.read_bytes())
    _validate_schema(package, "BattleItemPossession", _BATTLE_ITEM_SCHEMA)
    payload = _source_only_payload(
        package,
        "Decoded source value; BattleItemPossession editing is disabled until "
        "the Steal/drop semantics and array-write acceptance are proved.",
    )
    payload.update({
        "source": "source",
        "path": str(path),
        "projectRelativePath": str(path.relative_to(root)).replace("\\", "/"),
        "readOnly": True,
        "purpose": "Steal/drop source data; the Steal formula is not yet reconstructed.",
    })
    return payload


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
    battle_player = battle_player_source_path()
    battle_item = battle_item_source_path()
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
        "battlePlayerParameter": {
            "relative": BATTLE_PLAYER_PARAMETER.as_posix(),
            "sourceRelative": f"source/{BATTLE_PLAYER_PARAMETER.as_posix()}",
            "sourcePresent": bool(battle_player and battle_player.is_file()),
            "readOnly": True,
        },
        "battleItemPossession": {
            "relative": BATTLE_ITEM_POSSESSION.as_posix(),
            "sourceRelative": f"source/{BATTLE_ITEM_POSSESSION.as_posix()}",
            "sourcePresent": bool(battle_item and battle_item.is_file()),
            "readOnly": True,
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
            "filename": BATTLE_PLAYER_PARAMETER.as_posix(),
            "controls": "Battle Params — read-only structured rows and decoded arrays",
            "coverage": "view",
            "notes": (
                "Public generated declarations and Synthlight's public property list independently "
                "identify the BattlePlayerParameter storage schema. Lexeditor validates a distinctive "
                "typed signature before displaying rows and arrays. Gameplay meanings, enum domains "
                "and safe edit ranges remain unproved, so no staging or save route is exposed."
            ), "status": "partial", "target": "battleparams",
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
            "controls": "Information — Build isolated candidate", "coverage": "structured",
            "notes": (
                "The dependency-explicit UnrealReZen route audits every staged regular file, "
                "rejects symlinks, records input/tool/output hashes and writes only under the project. "
                "It requires the local tool plus adjacent explicit Oodle and never installs the result; "
                "shared-helper ownership and real-game load/removal acceptance are still pending."
            ), "status": "partial",
        },
        {
            "filename": "End/Content/DataObject/Resident/ResidentParameter.uasset (#470)",
            "controls": "None — Chocobo whistle research target", "coverage": "unavailable",
            "notes": (
                "Public constants identify CallChocoboAtFieldActionDistanceParamRatio0/1 and the "
                "whistle/chocobo identities. The public generated Rebirth SDK further exposes "
                "AEndLocationVolume.bDisableChocoboRide, UEndEnvQueryTest_IsDisabledChocoboRide, "
                "UEndEnvQueryContext_LastEnableChocoboRideLocation and a "
                "FEndBehaviorChocoboRideOnExtraAction type. This proves ride-legality/location/action "
                "seams exist, but not the callable sequence for safe teleport + immediate mount, "
                "nor the distance-ratio semantics/ranges or vanilla fallback."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/BattleItemPossession.uasset (#471)",
            "controls": "Formulae — read-only row and array-element view", "coverage": "view",
            "notes": (
                "Public format evidence proves _Array headers point to elements of the property's "
                "underlying type, so Lexeditor can decode supplied BattleItemPossession rows and "
                "array elements read-only. Public constants identify NormalItemPercent_Array, "
                "RareItemPercent_Array, StealItemName_Array, StealItemQuantity_Array and "
                "StealFaildCountArrayIndex; public mod evidence says the 25% rate data is shared "
                "between steal/drop. Generated runtime enums separately identify StealFailed, "
                "AlreadyStolen and NothingToSteal messages plus a StealSuccessRateAdd skill effect, "
                "but do not expose the condition/arithmetic connecting them. Writes and the complete "
                "formula remain unproved."
            ), "status": "partial", "target": "formulae",
        },
        {
            "filename": "End/Content/DataObject/Resident/StateChange.uasset + StateTrigger.uasset + ActionGroup.uasset (#472)",
            "controls": "None — restable-bench/cushion research family", "coverage": "unavailable",
            "notes": (
                "Public constants identify the bench rest trigger/action rows and the consumed-cushion "
                "resource. The public generated SDK exposes AEndFieldActionActorBenchBreak with both "
                "BenchMeshComponent and ZabutonActorClass, directly narrowing the model/cushion actor seam; "
                "public mesh work also confirms multiple bench models. Public gameplay documentation independently "
                "confirms vanilla blue benches and Chocobo-stop benches are distinct: ordinary blue benches do not "
                "consume a cushion, while Chocobo stops do. Missing evidence is the complete restable-placement -> "
                "desired blue-mesh mapping and the inventory/state transition that must consume a cushion for every "
                "valid rest without changing unusable benches."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/MapIconInfo.uasset + HUD package assets (#473)",
            "controls": "None — world-minimap zoom research family", "coverage": "unavailable",
            "notes": (
                "The public generated Rebirth SDK explicitly defines option categories AreaNaviMapScale, "
                "LocationNaviMapScale and ZackNaviMapScale; UEndNaviMap also exposes PixelPerCm, and the option "
                "model supports Range entries with integer MinValue/MaxValue. Independent player-facing documentation "
                "confirms Rebirth already exposes separate world-navigation and specific-location minimap scale controls, "
                "with larger numeric choices showing a wider area. Public sources still do not prove which generated "
                "category maps to which persisted setting, its exact stored range/default, or the save/config location, "
                "so Lexeditor does not invent a slider contract."
            ), "status": "not-integrated",
        },
        {
            "filename": "End/Content/DataObject/Resident/CardGameCommonParameter.uasset + CardGameAIParam.uasset (#477)",
            "controls": "None — Queen's Blood turn-flow research family", "coverage": "unavailable",
            "notes": (
                "Public CardGame data exposes EffectWaitTime, NeedCanPutCount and player/enemy prediction fields. "
                "The generated SDK additionally exposes UEndCardGameMenu._PassClass with OnYesButtonPressed/OnNoButtonPressed, "
                "and AEndCardGame3DManager player/enemy turn visibility plus CardPlacementActor state. These are real "
                "pass/turn/board seams, but they still do not prove the legal-move predicate, automatic pass transition, "
                "both-sides-no-moves match termination or intro first-skippable-input hook."
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
        {"filename": "Documents/My Games/FINAL FANTASY VII REBIRTH/Saved/Config/WindowsNoEditor/Engine.ini",
         "controls": "Shared Unreal Engine config settings as typed controls, with Use game default and reset-all.",
         "notes": ("File location verified against an installed game; every setting stays marked unverified "
                   "until in-game effect proof. Values read from the file are observed values, never effective game values. (#478)"),
         "coverage": "structured", "status": "partial", "target": "tweaks"},
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
                            "player-parameter", "unreal-config", "battle-player-parameter-view",
                            "battle-item-possession-view", "fixed-width-edit",
                            "project-staging", "package-candidate"]})
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
        elif path == "/api/battle-player-parameter":
            try:
                self.send_json(battle_player_payload())
            except (OSError, DataObjectError) as error:
                self.send_json({"error": str(error), "workspace": workspace_payload()}, 404)
        elif path == "/api/battle-item-possession":
            try:
                self.send_json(battle_item_payload())
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
        elif path == "/api/unreal-config":
            try:
                self.send_json(unreal_status_payload())
            except (OSError, ValueError) as error:
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
            "/api/unreal-config/apply", "/api/unreal-config/default",
            "/api/unreal-config/reset", "/api/unreal-config/refresh",
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
            if path.startswith("/api/unreal-config/"):
                if project_read_only():
                    raise ValueError("This project is read-only.")
                state_root = unreal_state_root()
                if path == "/api/unreal-config/apply":
                    values = body.get("values")
                    if not isinstance(values, dict):
                        raise ValueError("values must be an object")
                    self.send_json({"result": unreal_config.apply_settings(
                        "ff7r2", state_root, values)})
                    return
                if path == "/api/unreal-config/default":
                    key = body.get("key")
                    if not isinstance(key, str) or not key:
                        raise ValueError("key must be a non-empty string")
                    self.send_json({"result": unreal_config.use_game_default(
                        "ff7r2", state_root, key)})
                    return
                if path == "/api/unreal-config/reset":
                    self.send_json({"result": unreal_config.reset_all(
                        "ff7r2", state_root)})
                    return
                if path == "/api/unreal-config/refresh":
                    self.send_json({"result": unreal_config.refresh_snapshot(
                        "ff7r2", state_root)})
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
        except (OSError, ValueError, unreal_config.ExternalEditError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
