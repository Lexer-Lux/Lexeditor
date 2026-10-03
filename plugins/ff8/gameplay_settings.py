"""FF8 gameplay tweaks: library tweak mods plus the runtime files they switch.

Every gameplay tweak is a tweak mod in the mod library (plugins/ff8/
tweak_mods.py builds them), including Shared Party Magic Inventory and GF
Spellbooks: enabling the mod is the switch. What stays here is what a mod's
own files cannot carry:

- direct/lexeditor/gameplay.toml, which combines Shared Party Magic
  Inventory with Max Spell's cap;
- the Lexeditor FFNx derivative several tweaks run on, and the FFNx.toml
  keys enabled tweaks ask for;
- the one transaction that applies all of that, then composes the runtime.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import time

from core import script_mods

from . import paths, formats
from . import ffnx_manager
from . import runtime_layout
from . import tweak_mods
from .ffnx_issue_51 import runtime_config as shared_magic_runtime_config


DEFAULT_SHARED_MAGIC_INVENTORY = False
DEFAULT_MAX_SPELL = 100
# Tweak mods other features of the editor ask about.
SHARED_MAGIC_MOD = "shared-party-magic-inventory"
SPELLBOOKS_MOD = "gf-spellbooks"
SINGLE_GF_MOD = "monogamy"
DEFAULT_CAMERA_SPEED = 1.0
SUPPORTED_EXE_SHA256 = tweak_mods.SUPPORTED_EXE_SHA256
# The single combined patch every gameplay tweak used to share. Saving
# removes it, because each tweak mod now ships its own patch.
PATCH_NAME = "Lexeditor.FLYING_EVA.txt"
FFNX_HEXT_SUFFIX = Path("ff8") / "en_nv"
# Driver switches Lexeditor owns in FFNx.toml. A tweak mod turns one on; every
# switch no enabled mod asks for is written off, so disabling a mod disables
# its driver feature.
FFNX_DEFAULTS = {
    "enable_ff8_xp_bars": False,
    "enable_ff8_hp_bars": False,
    "enable_ff8_better_hp_colors": False,
    "enable_ff8_gf_hp_bars": False,
    "enable_ff8_ingame_time": False,
    "enable_ff8_interaction_indicators": False,
    "enable_ff8_better_targeting": False,
    "enable_ff8_fast_start": False,
    "enable_ff8_modern_controls": False,
    "enable_ff8_party_switch": False,
    # No Magic Consumption is a Hext patch; the driver's copy stays off so only
    # one of them ever hooks the debit.
    "enable_ff8_no_magic_consumption": False,
    "ff8_modern_controls_camera_speed": DEFAULT_CAMERA_SPEED,
}
FFNX_KEY = re.compile(r"^(?:enable_ff8|ff8)_[a-z0-9_]+$")
_last_activation_ns = 0
_last_patches: list[Path] = []


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _boolean(value, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be true or false")
    return value


def patch_path(project_root: Path | None = None) -> Path:
    """Where the retired combined patch lived, so saving can remove it."""
    return (project_root or paths.PROJECT_ROOT) / "hext" / FFNX_HEXT_SUFFIX / PATCH_NAME


def legacy_patch_path(project_root: Path | None = None) -> Path:
    """Return the old base-directory file that FFNx never scanned."""
    return (project_root or paths.PROJECT_ROOT) / "hext" / PATCH_NAME


def obsolete_english_patch_path(project_root: Path | None = None) -> Path:
    """Return the wrong non-Nvidia path used by an older contract."""
    return (project_root or paths.PROJECT_ROOT) / "hext" / "ff8" / "en" / PATCH_NAME


def _runtime_root(value: Path | None = None,
                  project_root: Path | None = None) -> Path:
    if value is not None:
        return Path(value).resolve()
    if project_root is not None:
        project = Path(project_root).resolve()
        if project != paths.PROJECT_ROOT.resolve():
            # Explicit temporary/test projects must never compose into the
            # player's real active runtime.
            return project / ".lexeditor-runtime"
    return paths.RUNTIME_ROOT.resolve()


def _mods_root(project: Path) -> Path:
    # A temporary project brings its own library when it has one, so a test
    # never builds or enables the reader's real mods.
    private = project / ".lexeditor-mods"
    return private if private.is_dir() else paths.MODS_ROOT


def _shared_magic_payload(project: Path, game: Path, enabled: bool,
                          runtime_root: Path | None = None) -> dict:
    runtime_direct = _runtime_root(runtime_root, project) / "direct"
    runtime = ffnx_manager.status(
        game, ffnx_manager.STATE_PATH, direct_root=runtime_direct,
    )
    try:
        shared_magic_runtime_config.load(project)
        config_error = ""
    except shared_magic_runtime_config.RuntimeConfigError as error:
        config_error = str(error)
    configured = enabled
    # A verified package makes the request selectable. Launch then installs
    # and verifies that package before FF8 starts.
    package_available = bool(runtime.get("sharedMagicInventoryPackageAvailable"))
    installed = bool(runtime.get("sharedMagicInventoryRuntime"))
    return {
        "sharedMagicInventory": bool(configured),
        "sharedMagicInventoryConfigured": bool(configured),
        "sharedMagicInventoryAvailable": package_available,
        "sharedMagicInventoryRuntimeInstalled": installed,
        "sharedMagicInventoryMessage": (
            config_error or runtime.get("sharedMagicInventoryRuntimeMessage", "")
        ),
    }


def _validate_shared_magic_launch(project: Path, game: Path,
                                  runtime_root: Path | None = None) -> bool:
    try:
        enabled = shared_magic_runtime_config.load(project)["sharedMagicInventory"]
    except shared_magic_runtime_config.RuntimeConfigError as error:
        raise RuntimeError(
            "The Shared Party Magic Inventory configuration is invalid. "
            "Save Tweaks with the setting off before launch."
        ) from error
    if enabled and not ffnx_manager.status(
        game, ffnx_manager.STATE_PATH,
        direct_root=_runtime_root(runtime_root, project) / "direct",
    ).get("sharedMagicInventoryRuntime"):
        raise RuntimeError(
            "Shared Party Magic Inventory is selected, but the complete verified "
            "Lexeditor FFNx runtime is not installed. The game was not launched."
        )
    return enabled


def _tweak_payload(project: Path, game: Path) -> list[dict]:
    """Every tweak mod as the Tweaks page shows it; trusted ones may describe more."""
    rows = []
    for row in tweak_mods.tweak_rows(project, _mods_root(project)):
        entry = {key: row.get(key) for key in (
            "id", "name", "order", "enabled", "trust", "error", "schema", "values", "path")}
        entry["describe"] = {}
        if row.get("trust") == "trusted" and not row.get("error"):
            try:
                context = tweak_mods.BuildContext(game, paths.BASELINE_ROOT, {})
                entry["describe"] = script_mods.describe(Path(row["path"]), context)
            except Exception as error:  # A broken describe() must not hide the page.
                entry["error"] = f"describe(): {error}"
        rows.append(entry)
    return rows


def load(project_root: Path | None = None, game_root: Path | None = None,
         runtime_root: Path | None = None) -> dict:
    project = (project_root or paths.PROJECT_ROOT).resolve()
    game = (game_root or paths.GAME_ROOT).resolve()
    tweaks = _tweak_payload(project, game)
    enabled = {row["id"] for row in tweaks if row["enabled"]}
    return {
        "tweaks": tweaks,
        # Features outside the library ask whether these tweak mods are on.
        "gfSpellbooksEnabled": SPELLBOOKS_MOD in enabled,
        "singleGf": SINGLE_GF_MOD in enabled,
        **_shared_magic_payload(project, game, SHARED_MAGIC_MOD in enabled, runtime_root),
    }


def _atomic_text(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(target)


def _set_ffnx_keys(config: Path, values: dict) -> None:
    """Set Lexeditor's driver keys without changing unrelated FFNx settings."""
    text = config.read_text(encoding="utf-8", errors="strict")
    for key, value in values.items():
        if not FFNX_KEY.match(key):
            raise ValueError(f"A tweak asked for an FFNx key Lexeditor does not manage: {key}")
        if isinstance(value, bool):
            rendered, pattern = ("true" if value else "false"), r"(?:true|false)"
        elif isinstance(value, (int, float)):
            rendered, pattern = f"{value:g}", r"[-+0-9.eE]+"
        else:
            raise ValueError(f"FFNx key {key} needs a switch or a number")
        line = f"{key} = {rendered}"
        existing = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=\s*{pattern}\s*$")
        text = existing.sub(line, text, count=1) if existing.search(text) else text.rstrip() + f"\n\n{line}\n"
    _atomic_text(config, text)


def _snapshot_files(targets: list[Path]) -> list[tuple[Path, bool, bytes]]:
    snapshots = []
    for target in targets:
        path = Path(target)
        existed = path.is_file()
        snapshots.append((path, existed, path.read_bytes() if existed else b""))
    return snapshots


def _restore_files(snapshots: list[tuple[Path, bool, bytes]]) -> None:
    for path, existed, content in reversed(snapshots):
        if not existed:
            path.unlink(missing_ok=True)
            continue
        # A loaded FFNx driver is locked by Windows. Do not stage or replace it
        # when the failed transaction did not change its bytes.
        if path.is_file():
            try:
                if path.read_bytes() == content:
                    path.with_suffix(path.suffix + ".lexeditor.rollback.tmp").unlink(missing_ok=True)
                    continue
            except OSError:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".lexeditor.rollback.tmp")
        temporary.write_bytes(content)
        temporary.replace(path)


def initialize_project(project_root: Path) -> None:
    """A new mod starts with the runtime file sharing reads, sharing off until
    the first save writes what the enabled tweak mods ask for."""
    project = project_root.resolve()
    shared_magic_runtime_config.write(
        project, shared_magic_inventory=DEFAULT_SHARED_MAGIC_INVENTORY,
        magic_stock_limit=DEFAULT_MAX_SPELL,
    )
    for old_patch in (patch_path(project), legacy_patch_path(project), obsolete_english_patch_path(project)):
        old_patch.unlink(missing_ok=True)


def _tweak_changes(data: dict, rows: dict[str, dict]) -> tuple[dict, dict]:
    """Validate requested enable switches and values before anything is written."""
    requested = data.get("tweaks", {})
    if not isinstance(requested, dict):
        raise ValueError("tweaks must map tweak ids to their changes")
    enabled, values = {}, {}
    for mod_id, change in requested.items():
        if mod_id not in rows:
            raise ValueError(f"There is no tweak mod {mod_id}")
        if not isinstance(change, dict) or set(change) - {"enabled", "values"}:
            raise ValueError(f"{mod_id}: send enabled and values only")
        if "enabled" in change:
            enabled[mod_id] = _boolean(change["enabled"], rows[mod_id]["name"])
        if "values" in change:
            values[mod_id] = change["values"]
    return enabled, values


def save(data: dict, game_root: Path | None = None,
         project_root: Path | None = None, *, install_runtime: bool = False,
         runtime_root: Path | None = None) -> dict:
    game = (game_root or paths.GAME_ROOT).resolve()
    project = (project_root or paths.PROJECT_ROOT).resolve()
    mods_root = _mods_root(project)
    if not isinstance(data, dict):
        raise ValueError("Settings must be an object")
    # GF Spellbooks and Shared Party Magic Inventory were switches here; they
    # are tweak mods now, so an old request for them must not pass silently.
    if set(data) - {"tweaks"}:
        raise ValueError(f"Unknown settings: {', '.join(sorted(set(data) - {'tweaks'}))}. "
                         "Every gameplay switch is a tweak mod; enable it in the Mods tab.")
    catalog = runtime_layout.catalog(project, mods_root)
    tweak_rows = {row["id"]: row for row in tweak_mods.tweak_rows(project, mods_root)}
    enabled_changes, value_changes = _tweak_changes(data, tweak_rows)
    # Metadata must be valid before switches, values or runtime files change.
    # Prepare the spellbook snapshot before composition so the active runtime
    # receives the snapshot for the requested switches in this transaction.
    from . import gf_spellbooks, reptile_atb
    reptile_atb.load(project)
    planned_enabled = {mod_id for mod_id, row in tweak_rows.items()
                       if enabled_changes.get(mod_id, row["enabled"])}
    spellbooks_active = (SPELLBOOKS_MOD in planned_enabled and SINGLE_GF_MOD in planned_enabled
                         and SHARED_MAGIC_MOD not in planned_enabled)
    spellbooks = (gf_spellbooks.load(project) if spellbooks_active
                  else {"schemaVersion": gf_spellbooks.SCHEMA_VERSION, "books": []})
    spellbook_runtime = gf_spellbooks.runtime_bytes(spellbooks)
    spellbook_target = project / gf_spellbooks.RUNTIME_RELATIVE
    active_root = _runtime_root(runtime_root, project)
    direct_root = active_root / "direct"

    changed_files = [
        patch_path(project), legacy_patch_path(project), obsolete_english_patch_path(project),
        shared_magic_runtime_config.path(project),
        spellbook_target,
        *(runtime_layout._metadata_path(Path(row["path"])) for row in catalog if not row["selected"]),
        *(Path(tweak_rows[mod_id]["path"]) / script_mods.VALUES_FILE for mod_id in value_changes),
    ]
    if install_runtime:
        changed_files.append(game / "FFNx.toml")
    snapshots = _snapshot_files(changed_files)
    runtime_link_snapshots = ffnx_manager._snapshot_runtime_links(game) if install_runtime else None
    try:
        for mod_id, changes in value_changes.items():
            script_mods.save_values(Path(tweak_rows[mod_id]["path"]), changes)
        if enabled_changes:
            order = [row["id"] for row in catalog]
            runtime_layout.configure(project, mods_root, order, {
                row["id"]: enabled_changes.get(row["id"], row["enabled"]) for row in catalog})
        built = tweak_mods.build_enabled(project, mods_root, game, paths.BASELINE_ROOT)
        for old_patch in (patch_path(project), legacy_patch_path(project), obsolete_english_patch_path(project)):
            old_patch.unlink(missing_ok=True)
        # Every switch that used to live here is a tweak mod now.
        enabled_now = {row["id"]: row for row in tweak_mods.tweak_rows(project, mods_root) if row["enabled"]}
        shared_magic = SHARED_MAGIC_MOD in enabled_now
        stock_limit = (enabled_now["max-spell"]["values"]["limit"]
                       if "max-spell" in enabled_now else DEFAULT_MAX_SPELL)
        _atomic_text(shared_magic_runtime_config.path(project), shared_magic_runtime_config.build(
            shared_magic_inventory=shared_magic, magic_stock_limit=stock_limit))
        gf_spellbooks._atomic(spellbook_target, spellbook_runtime)
        runtime_layout.compose(
            project, active_root, runtime_layout.catalog(project, mods_root),
            paths.BASELINE_ROOT, formats.SECTIONS,
            runtime_layout.prelaunch_condition_state(game / "FFNx.toml"),
        )
        if install_runtime:
            status = ffnx_manager.status(game, ffnx_manager.STATE_PATH, direct_root=direct_root)
            if (built["driver"] or shared_magic) and not status.get("sharedMagicInventoryRuntime"):
                # A later configuration failure must undo the driver install
                # too, not only the selected settings and FFNx.toml.
                package = ffnx_manager.runtime_package.verify()
                snapshots.extend(_snapshot_files([
                    game / ffnx_manager.runtime_package.DRIVER_NAME,
                    game / package["steamApiName"],
                    game / "steam_appid.txt",
                    ffnx_manager.STATE_PATH,
                    *(game / package["shaderDirName"] / shader.name
                      for shader in Path(package["packagedShaderRoot"]).glob("*") if shader.is_file()),
                ]))
                ffnx_manager.install_derivative(
                    game, state_path=ffnx_manager.STATE_PATH, direct_root=direct_root,
                    game_running=ffnx_manager._game_running,
                )
                if not ffnx_manager.status(
                    game, ffnx_manager.STATE_PATH, direct_root=direct_root,
                ).get("sharedMagicInventoryRuntime"):
                    raise RuntimeError(
                        "The Lexeditor FFNx derivative did not verify after installation. "
                        "No enabled runtime configuration was written."
                    )
            else:
                config = game / "FFNx.toml"
                if not config.is_file():
                    raise RuntimeError("FFNx.toml is missing. FFNx cannot use the active runtime.")
                ffnx_manager._set_project_paths(config, direct_root)
                ffnx_manager._verify_project_path(config, direct_root)
            _set_ffnx_keys(game / "FFNx.toml", {**FFNX_DEFAULTS, **built["ffnx"]})
    except Exception:
        _restore_files(snapshots)
        if runtime_link_snapshots is not None:
            ffnx_manager._restore_runtime_links(game, runtime_link_snapshots)
        try:
            # Rebuild from the restored switches and values so the runtime
            # matches them again, not the half-applied request.
            tweak_mods.build_enabled(project, mods_root, game, paths.BASELINE_ROOT)
            runtime_layout.compose(
                project, active_root, runtime_layout.catalog(project, mods_root),
                paths.BASELINE_ROOT, formats.SECTIONS,
                runtime_layout.prelaunch_condition_state(game / "FFNx.toml"),
            )
        except Exception:
            pass
        raise
    return payload(project, saved=1, game_root=game, runtime_root=active_root)


def ensure(game_root: Path | None = None, project_root: Path | None = None,
           *, install_runtime: bool = False,
           runtime_root: Path | None = None) -> dict:
    """Rebuild and recompose with the current switches and values."""
    return save({}, game_root, project_root, install_runtime=install_runtime,
                runtime_root=runtime_root)


def trust(mod_id: str, trusted: bool, project_root: Path | None = None,
          game_root: Path | None = None) -> dict:
    """Let a tweak mod run its script, or stop it; the reader decides."""
    project = (project_root or paths.PROJECT_ROOT).resolve()
    rows = {row["id"]: row for row in tweak_mods.tweak_rows(project, _mods_root(project))}
    if mod_id not in rows:
        raise ValueError(f"There is no tweak mod {mod_id}")
    script_mods.set_trusted(Path(rows[mod_id]["path"]), _boolean(trusted, "Trusted"))
    return payload(project, game_root=game_root)


def keep_previous_log(game: Path) -> Path | None:
    """Copy the last session's FFNx.log aside before the game starts again.

    FFNx rewrites FFNx.log on every start, so the session in which something
    went wrong was gone the moment the game was relaunched. One previous copy
    is kept and replaced each launch.
    """
    log = game / "FFNx.log"
    previous = game / "FFNx.previous.log"
    try:
        if log.is_file() and log.stat().st_size:
            previous.write_bytes(log.read_bytes())
            return previous
    except OSError:
        pass  # a log that cannot be copied must never stop the game starting
    return None


def materialized_tweak_patches(runtime_root: Path, tweak_ids: set[str]) -> list[Path]:
    """The composed Hext files that came from enabled tweak mods."""
    active = Path(runtime_root).resolve()
    patches = []
    for row in runtime_layout.read(active).get("files", []):
        path = str(row.get("path", ""))
        if str(row.get("winner")) not in tweak_ids or not path.replace("\\", "/").startswith("hext/"):
            continue
        candidate = (active / path).resolve()
        if candidate == active or active not in candidate.parents:
            raise RuntimeError("A composed tweak patch path escapes the FF8 runtime")
        patches.append(candidate)
    return sorted(patches)


def activate(game_root: Path | None = None,
             project_root: Path | None = None,
             runtime_root: Path | None = None) -> dict:
    """Build, compose and verify exactly the patches FFNx will read before launch."""
    global _last_activation_ns, _last_patches
    game = (game_root or paths.GAME_ROOT).resolve()
    project = (project_root or paths.PROJECT_ROOT).resolve()
    active_root = _runtime_root(runtime_root, project)
    keep_previous_log(game)
    result = ensure(game, project, install_runtime=True, runtime_root=active_root)
    _validate_shared_magic_launch(project, game, active_root)
    config = game / "FFNx.toml"
    if not config.is_file():
        raise RuntimeError("FFNx.toml is missing. FFNx cannot load the gameplay patches.")
    text = config.read_text(encoding="utf-8", errors="strict")
    match = re.search(r'(?m)^\s*hext_patching_path\s*=\s*"([^"]+)"\s*$', text)
    configured_root = (active_root / "hext").resolve()
    if not match or Path(match.group(1)).resolve() != configured_root:
        actual = match.group(1) if match else "not configured"
        raise RuntimeError(f"FFNx uses {actual} as its Hext base, not {configured_root}.")
    effective_root = configured_root / FFNX_HEXT_SUFFIX
    enabled = {row["id"] for row in result["tweaks"] if row["enabled"]}
    patches = materialized_tweak_patches(active_root, enabled)
    for patch in patches:
        if patch.parent != effective_root:
            raise RuntimeError(f"The tweak patch {patch.name} is in {patch.parent}, but FFNx scans {effective_root}.")
        if patch.stat().st_size == 0:
            raise RuntimeError(f"The tweak patch is empty: {patch}")
    _last_patches = patches
    _last_activation_ns = time.time_ns()
    return {
        **result,
        "ready": True,
        "patches": [{"path": str(patch), "sha256": _sha256(patch), "bytes": patch.stat().st_size}
                    for patch in patches],
        "activatedAtNs": _last_activation_ns,
        "hextBase": str(configured_root),
        "hextRoot": str(effective_root),
    }


def _log_has_loaded_patch(text: str, target: Path) -> bool:
    expected = str(target.resolve()).replace("/", "\\").casefold()
    marker = "Applied Hext patch:"
    for line in text.splitlines():
        if marker.casefold() not in line.casefold():
            continue
        if expected in line.replace("/", "\\").casefold():
            return True
    return False


def runtime_status(game_root: Path | None = None,
                   project_root: Path | None = None,
                   runtime_root: Path | None = None,
                   game_running=ffnx_manager._game_running,
                   game_started=ffnx_manager._game_started) -> dict:
    """Report whether FFNx loaded every tweak patch from the latest launch."""
    game = (game_root or paths.GAME_ROOT).resolve()
    log = game / "FFNx.log"
    # The launcher can stay open for as long as the player likes; FFNx only
    # starts with the game, so the editor times its check from this.
    started = bool(game_started())
    if not log.is_file():
        return {"loaded": False, "logReady": False, "gameStarted": started,
                "message": "FFNx.log is not ready."}
    text = log.read_text(encoding="utf-8", errors="replace")
    log_is_current = bool(_last_activation_ns) and log.stat().st_mtime_ns >= _last_activation_ns - 1_000_000_000
    missing = [patch for patch in _last_patches if not _log_has_loaded_patch(text, patch)]
    loaded = log_is_current and not missing
    hext_was_reached = log_is_current and "applied hext patch:" in text.casefold()
    running = bool(game_running())
    # FFNx writes its log before it scans Hext files. Keep waiting while the
    # game process is alive, and report a failure only after it stops.
    log_ready = loaded or (log_is_current and not running)
    last_line = next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")
    return {
        "loaded": loaded,
        "logReady": log_ready,
        "startupIncomplete": log_is_current and not log_ready,
        "gameRunning": running,
        "gameStarted": started,
        "log": str(log),
        "missing": [patch.name for patch in missing],
        "message": (
            ("FFNx loaded every gameplay tweak patch." if _last_patches else "No gameplay tweak is enabled.")
            if loaded else
            f"FFNx stopped after it applied other Hext files, but it did not apply {', '.join(p.name for p in missing)}."
            if hext_was_reached and not running else
            f"The game stopped before FFNx reached Hext. Its last log entry was: {last_line or 'none'}."
            if log_is_current and not running else
            f"FFNx is still starting. Its last log entry is: {last_line or 'none'}."
            if log_is_current else
            "Waiting for FFNx to write a new log."
        ),
    }


def payload(project_root: Path | None = None, saved: int = 0,
            game_root: Path | None = None,
            runtime_root: Path | None = None) -> dict:
    project = (project_root or paths.PROJECT_ROOT).resolve()
    active_root = _runtime_root(runtime_root, project)
    current = load(project, game_root, active_root)
    return {**current, "runtimeRoot": str(active_root), "modsRoot": str(_mods_root(project)), "saved": saved}
