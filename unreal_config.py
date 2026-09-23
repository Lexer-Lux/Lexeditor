"""Shared Unreal Engine configuration editor and settings catalogue.

One config editor and one CVar catalogue serve every Unreal game. Each game
supplies its config locations, supported settings, exceptions, and
verification results. Game modules never copy this file.

Design rules this module enforces:
- Overrides live in one Lexeditor managed block at the end of the file, so
  the block wins over earlier values while unrelated lines, comments, and
  settings stay byte-identical.
- A value read from an INI file is reported as an observed override, never
  as the game's effective current value.
- "Use game default" removes the override so the game configuration applies
  again. It does not establish a known numeric default.
- Reset restores pre-existing user overrides from the journal instead of
  deleting them.
- A file that changed outside Lexeditor (user edit or game rewrite) blocks
  saving until status is reloaded. This module never makes config files
  read-only and never silently overwrites external changes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any


ENGINE_UE4 = "UE4"

STATE_DIR_NAME = "UnrealConfig"
SNAPSHOT_NAME = "unreal_config_state.json"
BACKUP_KEEP = 5


class ConfigError(ValueError):
    """The config file or a setting value cannot be handled safely."""


class ExternalEditError(RuntimeError):
    """The file changed outside Lexeditor after the last snapshot."""


# ---------------------------------------------------------------------------
# CVar catalogue (common definitions by engine version)
# ---------------------------------------------------------------------------
# Ranges below are conservative editor bounds, not engine guarantees.
# Per-game evidence (defined by the engine, accepted by the game,
# demonstrated to have the intended effect) lives in each entry's
# "verification" map. An entry without a demonstrated effect for a game
# stays out of that game's normal view and recommended presets.

def _pending() -> dict[str, Any]:
    return {"defined": True, "accepted": False, "demonstrated": False,
            "tested_version": ""}


CATALOGUE: tuple[dict[str, Any], ...] = (
    {
        "key": "r.EyeAdaptationQuality", "name": "Eye adaptation",
        "description": ("Automatic brightness adjustment when moving between "
                        "dark and bright areas. 0 turns the adjustment off for "
                        "a steadier image; 1 keeps the game's adjustment. "
                        "Restart the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 1,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {
            "ff7r": {"defined": True, "accepted": True,
                     "demonstrated": False, "tested_version": ""},
            "ff7r2": _pending(),
        },
    },
    {
        "key": "r.MotionBlurQuality", "name": "Motion blur",
        "description": ("Softens fast movement. Lower values give a sharper "
                        "image in motion and can help performance; higher "
                        "values look smoother but blur detail. Restart the "
                        "game after changing it."),
        "type": "int", "minimum": 0, "maximum": 4,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.DepthOfFieldQuality", "name": "Depth of field",
        "description": ("Background blur in cutscenes and photo-like shots. "
                        "Lower values keep more of the scene sharp and can "
                        "help performance. Restart the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 4,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.BloomQuality", "name": "Bloom",
        "description": ("Glow around bright lights. Lower values reduce the "
                        "glow and can help performance; 0 turns it off. "
                        "Restart the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 5,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.SceneColorFringeQuality", "name": "Chromatic aberration",
        "description": ("Color fringing at screen edges, a lens effect. 0 "
                        "removes it for a cleaner image; 1 keeps it. Restart "
                        "the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 1,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.Tonemapper.Sharpen", "name": "Sharpening",
        "description": ("Image sharpness filter strength. 0 disables extra "
                        "sharpening; higher values sharpen more but can add "
                        "edge shimmer. Restart the game after changing it."),
        "type": "float", "minimum": 0.0, "maximum": 4.0,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.PostProcessAAQuality", "name": "Anti-aliasing",
        "description": ("Smoothing of jagged edges. Higher values smooth "
                        "more but cost performance; 0 turns it off. Restart "
                        "the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 6,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.Shadow.MaxResolution", "name": "Shadow resolution",
        "description": ("Maximum shadow map size. Higher values give crisper "
                        "shadows but cost video memory and performance. "
                        "Restart the game after changing it."),
        "type": "choice", "minimum": None, "maximum": None,
        "choices": [512, 1024, 2048, 4096], "dependencies": [],
        "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.SSR.Quality", "name": "Reflections",
        "description": ("Quality of on-screen reflections on wet and shiny "
                        "surfaces. Lower values run faster with rougher "
                        "reflections. Restart the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 4,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.VolumetricFog", "name": "Volumetric fog",
        "description": ("Light shafts through fog and dust. 0 turns them off "
                        "for performance; 1 keeps them. Restart the game "
                        "after changing it."),
        "type": "int", "minimum": 0, "maximum": 1,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.ViewDistanceScale", "name": "Draw distance",
        "description": ("How far away objects and detail stay visible. Higher "
                        "values show more at distance but cost performance; "
                        "values below 1 hide distant detail. Restart the game "
                        "after changing it."),
        "type": "float", "minimum": 0.1, "maximum": 10.0,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.Foliage.DensityScale", "name": "Foliage density",
        "description": ("Amount of grass and small plants. Lower values thin "
                        "vegetation out and can help performance. Restart the "
                        "game after changing it."),
        "type": "float", "minimum": 0.0, "maximum": 1.0,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.MaxAnisotropy", "name": "Texture filtering",
        "description": ("Sharpness of ground and wall textures seen at an "
                        "angle. Higher values look better at a small cost. "
                        "Restart the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 16,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.Streaming.PoolSize", "name": "Texture streaming budget",
        "description": ("Video memory reserved for streamed textures, in "
                        "megabytes. Too low causes blurry textures; too high "
                        "can starve the rest of the game. Restart the game "
                        "after changing it."),
        "type": "int", "minimum": 128, "maximum": 8192,
        "choices": None, "dependencies": ["r.Streaming.*"],
        "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "t.MaxFPS", "name": "Frame rate limit",
        "description": ("Maximum frames per second. 0 means no limit. A limit "
                        "can smooth pacing and reduce heat and noise. Takes "
                        "effect without a restart on most builds."),
        "type": "int", "minimum": 0, "maximum": 480,
        "choices": None, "dependencies": [], "restart_required": False,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
    {
        "key": "r.VSync", "name": "Vertical sync",
        "description": ("Locks frames to the display refresh to stop screen "
                        "tearing. 1 enables it (adds input delay); 0 "
                        "disables it. Restart the game after changing it."),
        "type": "int", "minimum": 0, "maximum": 1,
        "choices": None, "dependencies": [], "restart_required": True,
        "verification": {"ff7r": _pending(), "ff7r2": _pending()},
    },
)


def catalogue(*, engine: str = ENGINE_UE4) -> list[dict[str, Any]]:
    """Return the shared CVar catalogue for one engine version."""
    if engine != ENGINE_UE4:
        raise ConfigError(f"Unsupported engine version: {engine}")
    return [dict(entry, verification=dict(entry["verification"]))
            for entry in CATALOGUE]


def setting(key: str) -> dict[str, Any]:
    """Return one catalogue entry by CVar key."""
    for entry in CATALOGUE:
        if entry["key"] == key:
            return dict(entry, verification=dict(entry["verification"]))
    raise ConfigError(f"Unknown Unreal setting: {key}")


# ---------------------------------------------------------------------------
# Per-game registry (locations, supported settings, exceptions)
# ---------------------------------------------------------------------------
# FF7R managed markers intentionally match plugins/ff7r/graphics_tweaks.py so
# both editors read one block format. A test pins that equality.

FF7R_MANAGED_BEGIN = "; BEGIN LEXEDITOR FF7R EYE ADAPTATION"
FF7R_MANAGED_END = "; END LEXEDITOR FF7R EYE ADAPTATION"

MANAGED_BEGIN_TEMPLATE = "; BEGIN LEXEDITOR UNREAL CONFIG ({game})"
MANAGED_END_TEMPLATE = "; END LEXEDITOR UNREAL CONFIG ({game})"


def _documents() -> Path:
    return Path.home() / "Documents"


GAMES: dict[str, dict[str, Any]] = {
    "ff7r": {
        "name": "FINAL FANTASY VII REMAKE",
        "engine": ENGINE_UE4,
        "env_override": "LEXEDITOR_FF7R_ENGINE_INI",
        "config_candidates": (
            "Documents/My Games/FINAL FANTASY VII REMAKE/Saved/Config/WindowsNoEditor/Engine.ini",
        ),
        "config_verified": True,
        "supported": [entry["key"] for entry in CATALOGUE],
        "legacy_managed_keys": ("r.EyeAdaptationQuality",),
        "legacy_note": ("Eye adaptation is managed by the existing FF7R "
                        "Graphics Tweaks group; the shared editor reads it "
                        "but writes the remaining settings."),
        "exceptions": ("Engine.ini loading needs a verified INI unlocker "
                       "next to ff7remake_.exe; see the Graphics Tweaks "
                       "group status."),
    },
    "ff7r2": {
        "name": "FINAL FANTASY VII REBIRTH",
        "engine": ENGINE_UE4,
        "env_override": "LEXEDITOR_FF7R2_ENGINE_INI",
        "config_candidates": (
            "Documents/My Games/FINAL FANTASY VII REBIRTH/Saved/Config/WindowsNoEditor/Engine.ini",
        ),
        "config_verified": False,
        "supported": [entry["key"] for entry in CATALOGUE
                      if entry["key"] != "r.EyeAdaptationQuality"],
        "legacy_managed_keys": (),
        "legacy_note": "",
        "exceptions": ("Rebirth config locations are undiscovered: the "
                       "candidate above is unchecked against an installed "
                       "game, so every setting stays in the advanced view "
                       "until discovery and in-game verification."),
    },
}


def game_ids() -> list[str]:
    """Return registered game ids."""
    return sorted(GAMES)


def game_definition(game_id: str) -> dict[str, Any]:
    """Return one game's config locations and support data."""
    try:
        definition = GAMES[game_id]
    except KeyError:
        raise ConfigError(f"Unknown game for Unreal config: {game_id}") from None
    return dict(definition)


def settings_for_game(game_id: str, *,
                      include_unverified: bool = False) -> list[dict[str, Any]]:
    """Return settings for one game split into normal and advanced views.

    The normal view holds only settings with a demonstrated effect for the
    tested game version. The advanced view holds accepted or engine-defined
    settings, clearly marked, and never feeds recommended presets.
    """
    definition = game_definition(game_id)
    supported = set(definition["supported"])
    normal, advanced = [], []
    for entry in CATALOGUE:
        if entry["key"] not in supported:
            continue
        evidence = entry["verification"].get(game_id, {})
        item = dict(entry, verification=dict(evidence),
                    managed_by=("legacy-graphics-tweaks"
                                if entry["key"] in definition["legacy_managed_keys"]
                                else "unreal-config"))
        if evidence.get("demonstrated") and evidence.get("tested_version"):
            normal.append(item)
        else:
            item["unverified_note"] = (
                "Effect in this game is not verified. Accepted values alone "
                "do not prove an effect.")
            advanced.append(item)
    if include_unverified:
        return normal + advanced
    return normal


# ---------------------------------------------------------------------------
# Config file discovery
# ---------------------------------------------------------------------------

def discover_config_file(game_id: str) -> Path | None:
    """Return the first existing config file for a game, if any.

    Never assumes one universal Unreal config path: the environment override
    wins, then per-game candidates are probed in order.
    """
    definition = game_definition(game_id)
    override = os.environ.get(definition["env_override"], "")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.is_file() else None
    for relative in definition["config_candidates"]:
        candidate = _documents() / relative.split("Documents/", 1)[-1] \
            if relative.startswith("Documents/") else Path(relative)
        if candidate.is_file():
            return candidate
    return None


def default_config_path(game_id: str) -> Path:
    """Return where the config file should live, existing or not."""
    definition = game_definition(game_id)
    override = os.environ.get(definition["env_override"], "")
    if override:
        return Path(override).expanduser()
    relative = definition["config_candidates"][0]
    tail = relative.split("Documents/", 1)[-1] if relative.startswith("Documents/") else relative
    return _documents() / tail


# ---------------------------------------------------------------------------
# Line-preserving INI model
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^\s*\[(?P<section>[^\]]+)\]\s*$")
_SETTING_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_.]+)\s*=\s*(?P<value>.*?)\s*$")


class IniDocument:
    """An INI file as content lines with per-line endings preserved."""

    def __init__(self, lines: list[str], endings: list[str], *,
                 bom: bool, newline: str):
        self.lines = lines
        self.endings = endings
        self.bom = bom
        self.newline = newline

    def text(self) -> str:
        return "".join(line + ending
                       for line, ending in zip(self.lines, self.endings))

    def append_line(self, line: str) -> None:
        """Append a new line using the document's dominant newline."""
        self.lines.append(line)
        self.endings.append(self.newline)


def read_document(path: Path) -> IniDocument:
    """Read an INI file without normalizing its layout."""
    if not path.is_file():
        return IniDocument([], [], bom=False, newline="\n")
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig" if bom else "utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(
            f"Unreal config is not valid UTF-8 and cannot be safely edited: {path}"
        ) from error
    lines, endings = [], []
    for chunk in text.splitlines(keepends=True):
        stripped = chunk.rstrip("\r\n")
        endings.append(chunk[len(stripped):] or "\n")
        lines.append(stripped)
    crlf = sum(ending == "\r\n" for ending in endings)
    newline = "\r\n" if crlf > len(endings) - crlf else "\n"
    return IniDocument(lines, endings, bom=bom, newline=newline)


def write_document(path: Path, document: IniDocument) -> None:
    """Write an INI file atomically and verify the readback."""
    payload = document.text().encode("utf-8-sig" if document.bom else "utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)
    if path.read_bytes() != payload:
        raise ConfigError(f"Unreal config failed atomic readback: {path}")


def _managed_markers(game_id: str) -> tuple[str, str]:
    if game_id == "ff7r":
        return FF7R_MANAGED_BEGIN, FF7R_MANAGED_END
    return (MANAGED_BEGIN_TEMPLATE.format(game=game_id),
            MANAGED_END_TEMPLATE.format(game=game_id))


def managed_span(document: IniDocument, game_id: str) -> tuple[int, int] | None:
    """Return the managed block line span, or None when absent."""
    begin, end = _managed_markers(game_id)
    begins = [i for i, line in enumerate(document.lines) if begin in line]
    ends = [i for i, line in enumerate(document.lines) if end in line]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise ConfigError(
            "Unreal config contains malformed or duplicate Lexeditor managed markers")
    end = ends[0] + 1
    return begins[0], end


def managed_overrides(document: IniDocument, game_id: str) -> dict[str, str]:
    """Return key/value pairs inside the managed block (Lexeditor overrides)."""
    span = managed_span(document, game_id)
    if span is None:
        return {}
    values: dict[str, str] = {}
    for line in document.lines[span[0]:span[1]]:
        match = _SETTING_RE.match(line)
        if match:
            values[match.group("key")] = match.group("value")
    return values


def observed_values(document: IniDocument, game_id: str) -> dict[str, str]:
    """Return known CVar values set outside the managed block.

    These are observed file contents, not the game's effective values.
    """
    span = managed_span(document, game_id)
    known = {entry["key"] for entry in CATALOGUE}
    values: dict[str, str] = {}
    for index, line in enumerate(document.lines):
        if span is not None and span[0] <= index < span[1]:
            continue
        match = _SETTING_RE.match(line)
        if match and match.group("key") in known:
            values[match.group("key")] = match.group("value")
    return values


def remove_managed_block(document: IniDocument, game_id: str) -> bool:
    """Remove the managed block, preserving everything else."""
    span = managed_span(document, game_id)
    if span is None:
        return False
    start, end = span
    while start > 0 and not document.lines[start - 1].strip():
        start -= 1
    del document.lines[start:end]
    del document.endings[start:end]
    while document.lines and not document.lines[-1].strip():
        document.lines.pop()
        document.endings.pop()
    return True


def apply_managed_block(document: IniDocument, game_id: str,
                        values: dict[str, str]) -> None:
    """Replace the managed block with new overrides, last in file."""
    remove_managed_block(document, game_id)
    if document.lines and document.lines[-1].strip():
        document.append_line("")
    begin, end = _managed_markers(game_id)
    document.append_line(begin)
    document.append_line("[SystemSettings]")
    for key in sorted(values):
        document.append_line(f"{key}={values[key]}")
    document.append_line(end)


# ---------------------------------------------------------------------------
# Validation (bounded controls, known enums)
# ---------------------------------------------------------------------------

def validate_value(key: str, value: Any) -> str:
    """Validate one setting and return its canonical INI text."""
    entry = setting(key)
    name = entry["name"]
    kind = entry["type"]
    if kind == "choice":
        choices = entry["choices"] or []
        if value not in choices:
            raise ConfigError(
                f"{name} must be one of {choices}; got {value!r}.")
        return str(value)
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{name} must be a whole number.")
        minimum, maximum = entry["minimum"], entry["maximum"]
        if (minimum is not None and value < minimum) or \
                (maximum is not None and value > maximum):
            raise ConfigError(
                f"{name} must be a whole number from {minimum} to {maximum}.")
        return str(value)
    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{name} must be a number.")
        number = float(value)
        minimum, maximum = entry["minimum"], entry["maximum"]
        if (minimum is not None and number < minimum) or \
                (maximum is not None and number > maximum):
            raise ConfigError(
                f"{name} must be a number from {minimum} to {maximum}.")
        return str(number) if "." in str(value) or isinstance(value, float) else str(value)
    raise ConfigError(f"{name} has an unsupported type: {kind}")


def validate_settings(game_id: str, values: dict[str, Any]) -> dict[str, str]:
    """Validate a settings map for one game, rejecting legacy-owned keys."""
    definition = game_definition(game_id)
    supported = set(definition["supported"])
    legacy = set(definition["legacy_managed_keys"])
    canonical: dict[str, str] = {}
    for key, value in values.items():
        if key not in supported:
            raise ConfigError(
                f"{key} is not a supported Unreal setting for {definition['name']}.")
        if key in legacy:
            raise ConfigError(
                f"{setting(key)['name']} is managed by the existing game "
                f"tweaks group ({definition['legacy_note']})")
        canonical[key] = validate_value(key, value)
    return canonical


# ---------------------------------------------------------------------------
# State sidecar: journal, snapshots, backups
# ---------------------------------------------------------------------------

def state_path(project_root: Path, game_id: str) -> Path:
    """Return the journal/snapshot file for one game project."""
    return Path(project_root) / "runtime" / STATE_DIR_NAME / f"{game_id}.json"


def load_state(project_root: Path, game_id: str) -> dict[str, Any]:
    """Load journal and snapshot state, defaulting to empty."""
    target = state_path(project_root, game_id)
    if not target.is_file():
        return {"journal": {}, "snapshot": None}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(
            f"Could not read Unreal config state: {error}") from error
    if not isinstance(payload, dict):
        raise ConfigError("Unreal config state is corrupt.")
    payload.setdefault("journal", {})
    payload.setdefault("snapshot", None)
    return payload


def save_state(project_root: Path, game_id: str, state: dict[str, Any]) -> None:
    """Persist journal and snapshot state atomically."""
    target = state_path(project_root, game_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def snapshot_of(path: Path) -> dict[str, Any] | None:
    """Return hash/size/mtime for an existing file, else None."""
    if not path.is_file():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    stat = path.stat()
    return {"path": str(path), "sha256": digest, "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns}


def check_snapshot(path: Path, snapshot: dict[str, Any] | None) -> None:
    """Raise ExternalEditError when the file changed since the snapshot."""
    if not snapshot:
        return
    if snapshot.get("path") != str(path):
        return
    current = snapshot_of(path)
    if current is None and snapshot is not None:
        raise ExternalEditError(
            f"{path} was deleted outside Lexeditor. Reload status before saving.")
    if current != snapshot:
        raise ExternalEditError(
            f"{path} changed outside Lexeditor (user edit or game rewrite). "
            f"Reload status before saving so nothing is silently overwritten.")


def backup_config(path: Path) -> Path | None:
    """Copy the config file to a timestamped backup, keeping newest few."""
    if not path.is_file():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.lexeditor-{stamp}.bak")
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = path.with_name(f"{path.name}.lexeditor-{stamp}-{counter}.bak")
    candidate.write_bytes(path.read_bytes())
    backups = sorted(path.parent.glob(f"{path.name}.lexeditor-*.bak"),
                     key=lambda item: item.name)
    for stale in backups[:-BACKUP_KEEP]:
        try:
            stale.unlink()
        except OSError:
            pass
    return candidate


# ---------------------------------------------------------------------------
# Apply, defaults, reset, status
# ---------------------------------------------------------------------------

def _record_journal(state: dict[str, Any], observed: dict[str, str],
                    keys: set[str]) -> None:
    journal = state["journal"]
    for key in keys:
        if key not in journal:
            journal[key] = {"had": key in observed, "value": observed.get(key)}


def apply_settings(game_id: str, project_root: Path,
                   values: dict[str, Any]) -> dict[str, Any]:
    """Validate, journal originals, back up, and write managed overrides."""
    game_definition(game_id)
    canonical = validate_settings(game_id, values)
    path = default_config_path(game_id)
    state = load_state(project_root, game_id)
    check_snapshot(path, state["snapshot"])
    document = read_document(path)
    _record_journal(state, observed_values(document, game_id), set(canonical))
    current = managed_overrides(document, game_id)
    merged = dict(current)
    merged.update(canonical)
    backup = backup_config(path)
    apply_managed_block(document, game_id, merged)
    write_document(path, document)
    save_state(project_root, game_id,
               {"journal": state["journal"], "snapshot": snapshot_of(path)})
    return status(game_id, project_root, backup=str(backup) if backup else "")


def use_game_default(game_id: str, project_root: Path, key: str) -> dict[str, Any]:
    """Remove one override so the game's own configuration applies again."""
    game_definition(game_id)
    setting(key)
    path = default_config_path(game_id)
    state = load_state(project_root, game_id)
    check_snapshot(path, state["snapshot"])
    document = read_document(path)
    current = managed_overrides(document, game_id)
    if key not in current:
        return status(game_id, project_root)
    backup = backup_config(path)
    del current[key]
    if current:
        apply_managed_block(document, game_id, current)
    else:
        remove_managed_block(document, game_id)
    write_document(path, document)
    save_state(project_root, game_id,
               {"journal": state["journal"], "snapshot": snapshot_of(path)})
    return status(game_id, project_root, backup=str(backup) if backup else "")


def reset_all(game_id: str, project_root: Path) -> dict[str, Any]:
    """Remove every managed override and restore journaled user values."""
    definition = game_definition(game_id)
    path = default_config_path(game_id)
    state = load_state(project_root, game_id)
    check_snapshot(path, state["snapshot"])
    document = read_document(path)
    backup = backup_config(path)
    remove_managed_block(document, game_id)
    remaining = observed_values(document, game_id)
    restored: list[str] = []
    missing = {key: record for key, record in state["journal"].items()
               if record.get("had") and key not in remaining}
    if missing:
        if document.lines and document.lines[-1].strip():
            document.append_line("")
        document.append_line("; Restored by Lexeditor: values present before "
                             "the managed block overrode them")
        document.append_line("[SystemSettings]")
        for key in sorted(missing):
            document.append_line(f"{key}={missing[key]['value']}")
            restored.append(key)
    write_document(path, document)
    save_state(project_root, game_id,
               {"journal": {}, "snapshot": snapshot_of(path)})
    result = status(game_id, project_root, backup=str(backup) if backup else "")
    result["restored"] = restored
    return result


def refresh_snapshot(game_id: str, project_root: Path) -> dict[str, Any]:
    """Accept the current file as the new baseline after an external change.

    Use after reviewing status: it records the file as-is without writing to
    it, so the next save guards against newer changes only.
    """
    game_definition(game_id)
    path = default_config_path(game_id)
    state = load_state(project_root, game_id)
    state["snapshot"] = snapshot_of(path)
    save_state(project_root, game_id, state)
    return status(game_id, project_root)


def status(game_id: str, project_root: Path, backup: str = "") -> dict[str, Any]:
    """Report overrides separately from observed file values plus drift."""
    definition = game_definition(game_id)
    path = default_config_path(game_id)
    document = read_document(path)
    try:
        span = managed_span(document, game_id)
        markers_error = ""
    except ConfigError as error:
        span = None
        markers_error = str(error)
    overrides = {} if span is None and markers_error else managed_overrides(document, game_id)
    observed = observed_values(document, game_id)
    effective_at_end = False
    if span is not None:
        tail = "".join(line + ending for line, ending in
                       zip(document.lines[span[1]:], document.endings[span[1]:])).strip()
        effective_at_end = not tail
    state = load_state(project_root, game_id)
    drift = False
    drift_note = ""
    if state["snapshot"] and state["snapshot"].get("path") == str(path):
        if snapshot_of(path) != state["snapshot"]:
            drift = True
            drift_note = ("The file changed outside Lexeditor (user edit or "
                          "game rewrite). Reload before saving.")
    notes = []
    if markers_error:
        notes.append(markers_error)
    if drift:
        notes.append(drift_note)
    if overrides and not effective_at_end:
        notes.append("The managed block is not last; content after it may "
                     "take precedence. Re-apply to restore override order.")
    if not definition["config_verified"]:
        notes.append(definition["exceptions"])
    restart = any(setting(key)["restart_required"] for key in overrides)
    return {
        "game": game_id,
        "engine": definition["engine"],
        "configPath": str(path),
        "configExists": path.is_file(),
        "configDiscovered": discover_config_file(game_id) is not None,
        "overrides": overrides,
        "observed": observed,
        "managedPresent": bool(overrides) and span is not None,
        "managedEffectiveAtEnd": effective_at_end,
        "externalChange": drift,
        "restartRequired": restart,
        "normal": settings_for_game(game_id),
        "advanced": settings_for_game(game_id, include_unverified=True),
        "backup": backup,
        "notes": " ".join(notes),
    }
