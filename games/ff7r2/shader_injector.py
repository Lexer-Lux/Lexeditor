"""Shader Injector for Final Fantasy VII Rebirth, vendored and managed here.

Shader Injector is David Matos's D3D12 mod (github.com/frostbone25/ShaderInjector,
MIT). It loads as dsound.dll beside the game's executable and swaps the game's
own lighting, shadow, water and post-process shaders for rewritten ones while
the game runs.

The pinned release archive ships with Lexeditor, byte for byte the asset on the
upstream release page, and nothing is installed unless it hashes to that. It is
installed, switched on and off, removed, and configured from here:

  * on and off renames dsound.dll, so "off" means the game never loads it, and
    the ShaderInjector folder - with any shader edits in it - is left alone;
  * a file in that folder the player has changed is never overwritten or
    deleted, because the folder is where the mod expects people to edit;
  * a dsound.dll that is not this release is never touched at all.

ShaderInjector.ini is written by the injector on first start. Lexeditor reads
and writes the same keys, with the same defaults as the pinned source.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
from pathlib import Path, PurePosixPath
import zipfile


PLUGIN_ROOT = Path(__file__).resolve().parent
RUNTIME = PLUGIN_ROOT / "runtime"

VERSION = "2.2.1"
VARIANT = "Maximum quality"
ARCHIVE = RUNTIME / "shader-injector-2-2-1-maximum-dood.zip"
# The digest GitHub publishes for the release asset. The vendored copy must
# match it exactly, which is what makes "vendored" mean "upstream's release".
ARCHIVE_SHA256 = "ced1790992265e203e0db418203881d5570a58c5af0663e5f50c05a7996cd119"
ARCHIVE_TOP = "shader-injector-2-2-1-maximum-dood/"
LICENSE = RUNTIME / "SHADER-INJECTOR-LICENSE.txt"
SOURCE = "https://github.com/frostbone25/ShaderInjector"
RELEASE = SOURCE + "/releases/tag/" + VERSION

# Where Rebirth loads it from: beside ff7rebirth_.exe. Declared, not inferred,
# for the same reason the ReShade folder is.
INSTALL_FOLDER = "End/Binaries/Win64"

DLL = "dsound.dll"
DISABLED_DLL = "dsound.dll.lexeditor-off"
FOLDER = "ShaderInjector"
INI = "ShaderInjector.ini"
MANIFEST = FOLDER + "/.lexeditor-install.json"

# The game's own compiled-shader cache. Upstream's install guide makes deleting
# it the first step: the injector can only replace shaders it watches the game
# create, and a cached game creates almost none.
CACHE_FOLDER = ("My Games", "FINAL FANTASY VII REBIRTH", "Saved")
CACHE_PATTERN = "D3DDriverByteCodeBlob*.ushaderprecache"


# --------------------------------------------------------------------------
# The package


@dataclass(frozen=True)
class Package:
    files: dict[str, bytes]
    directories: tuple[str, ...]
    hashes: dict[str, str]
    archive_sha256: str


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(Path(path).read_bytes())


def load_package(archive: Path = ARCHIVE, expected: str = ARCHIVE_SHA256,
                 top: str = ARCHIVE_TOP) -> Package:
    """Read the archive, refusing anything but the pinned bytes."""
    data = Path(archive).read_bytes()
    digest = _sha(data)
    if digest != expected:
        raise ValueError(
            f"The Shader Injector archive is not the pinned {VERSION} release "
            f"(expected {expected}, got {digest}). Nothing was installed.")
    files: dict[str, bytes] = {}
    directories: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        for member in bundle.infolist():
            if not member.filename.startswith(top):
                raise ValueError(f"Unexpected entry in the Shader Injector archive: {member.filename}")
            relative = member.filename[len(top):]
            if not relative:
                continue
            path = PurePosixPath(relative.rstrip("/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe entry in the Shader Injector archive: {member.filename}")
            if member.is_dir():
                directories.append(str(path))
            else:
                files[str(path)] = bundle.read(member)
    if DLL not in files:
        raise ValueError(f"The Shader Injector archive has no {DLL}.")
    return Package(files, tuple(sorted(directories)),
                   {name: _sha(content) for name, content in files.items()}, digest)


_DEFAULT_PACKAGE: Package | None = None


def default_package() -> Package:
    global _DEFAULT_PACKAGE
    if _DEFAULT_PACKAGE is None:
        _DEFAULT_PACKAGE = load_package()
    return _DEFAULT_PACKAGE


# --------------------------------------------------------------------------
# Install, switch, remove


def _is_ours(path: Path, package: Package) -> bool:
    return path.is_file() and _file_sha(path) == package.hashes[DLL]


def install(root: Path, package: Package | None = None) -> dict:
    """Put the pinned release beside the executable.

    Files already present and identical are left as they are, so this adopts an
    install made by hand from the same archive. Files the player has changed
    are kept. A disabled install stays disabled.
    """
    package = package or default_package()
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"No game folder at {root}")
    active, parked = root / DLL, root / DISABLED_DLL
    if active.is_file() and not _is_ours(active, package):
        raise ValueError(
            f"{DLL} already exists here and is not Shader Injector {VERSION}. "
            "Lexeditor will not overwrite it.")
    if parked.is_file() and not _is_ours(parked, package):
        raise ValueError(f"{DISABLED_DLL} is here and is not Shader Injector {VERSION}.")
    for directory in package.directories:
        (root / directory).mkdir(parents=True, exist_ok=True)
    written, kept = [], []
    for name, content in package.files.items():
        if name == DLL:
            continue
        target = root / name
        if target.is_file():
            if _file_sha(target) != package.hashes[name]:
                kept.append(name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(name)
    if not active.is_file() and not parked.is_file():
        active.write_bytes(package.files[DLL])
        written.append(DLL)
    # The first install's time is kept: it is what "the cache predates the
    # install" is measured against, and a repair should not reset it.
    installed_at = _manifest(root).get("installedAt") or datetime.now(timezone.utc).isoformat()
    (root / MANIFEST).write_text(json.dumps({
        "name": "Shader Injector", "version": VERSION, "variant": VARIANT,
        "source": SOURCE, "archiveSha256": package.archive_sha256,
        "installedAt": installed_at,
        "files": package.hashes,
    }, indent=2) + "\n", encoding="utf-8")
    return {"written": sorted(written), "kept": sorted(kept)}


def set_enabled(root: Path, enabled: bool, package: Package | None = None) -> None:
    """Load it or not. Off parks the DLL under a name Windows will not load."""
    package = package or default_package()
    root = Path(root)
    active, parked = root / DLL, root / DISABLED_DLL
    if enabled:
        if _is_ours(active, package):
            return
        if not _is_ours(parked, package):
            raise ValueError("Shader Injector is not installed in this game.")
        if active.is_file():
            raise ValueError(f"{DLL} already exists here and is not Shader Injector.")
        parked.rename(active)
        return
    if _is_ours(active, package):
        if parked.is_file():
            parked.unlink()
        active.rename(parked)
    elif not _is_ours(parked, package):
        raise ValueError("Shader Injector is not installed in this game.")


def uninstall(root: Path, package: Package | None = None) -> dict:
    """Remove what the release put here and nothing the player changed."""
    package = package or default_package()
    root = Path(root)
    removed, kept = [], []
    for dll in (root / DLL, root / DISABLED_DLL):
        if _is_ours(dll, package):
            dll.unlink()
            removed.append(dll.name)
    for name in package.files:
        if name == DLL:
            continue
        target = root / name
        if not target.is_file():
            continue
        if _file_sha(target) == package.hashes[name]:
            target.unlink()
            removed.append(name)
        else:
            kept.append(name)
    manifest = root / MANIFEST
    if manifest.is_file():
        manifest.unlink()
    folder = root / FOLDER
    if folder.is_dir():
        for directory in sorted((path for path in folder.rglob("*") if path.is_dir()),
                                key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            folder.rmdir()
        except OSError:
            pass
    leftovers = sorted(str(path.relative_to(root)).replace("\\", "/")
                       for path in folder.rglob("*") if path.is_file()) if folder.is_dir() else []
    return {"removed": sorted(removed), "kept": sorted(kept), "leftovers": leftovers}


# --------------------------------------------------------------------------
# ShaderInjector.ini


@dataclass(frozen=True)
class Setting:
    section: str
    key: str
    label: str
    kind: str                 # bool, int, float, key, choice
    default: object
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[tuple[int, str], ...] = ()
    help: str = ""


# Keys, sections and defaults are the ones ShaderInjectorIO.cpp and Globals.cpp
# read at the 2.2.1 tag. Only MenuScale has a documented range; the other
# bounds are sanity limits so a typo cannot write something absurd.
SETTINGS: tuple[Setting, ...] = (
    Setting("InjectorSettings", "InjectorEnabled", "Active at startup", "bool", True,
            help="Whether shaders are replaced from the moment the game starts. The toggle key still switches it while playing."),
    Setting("InjectorSettings", "MenuOpen", "Menu open at startup", "bool", True,
            help="Whether the injector's in-game menu is showing when the game starts."),
    Setting("InjectorSettings", "MenuScale", "Menu scale", "float", 1.0, 0.5, 4.0,
            help="Size of the in-game menu. It ignores Windows scaling, so 2.0 suits a 4K display. Read when the menu is created: set it before starting the game."),
    Setting("InjectorSettings", "OpenMenuKey", "Open menu key", "key", 45,
            help="Opens and closes the injector's menu."),
    Setting("InjectorSettings", "ToggleInjectorKey", "Toggle key", "key", 46,
            help="Switches shader replacement on and off while playing, to compare against the game's own lighting."),
    Setting("RenderDoc", "Enabled", "Integration", "bool", False,
            help="For shader development with RenderDoc. Leave off to play."),
    Setting("RenderDoc", "AutoAttach", "Auto-attach", "bool", False,
            help="Attaches RenderDoc at startup when the integration is on."),
    Setting("ShaderDiscovery", "Mode", "Discovery mode", "choice", 0,
            choices=((0, "Hash lookup"), (1, "Shader analysis")),
            help="How the injector recognises the game's shaders. Hash lookup matches known versions; analysis compares shader structure, which survives game patches but costs more."),
    Setting("ShaderDiscovery", "WorkerThreads", "Worker threads", "int", 0, 0, 64,
            help="Threads used to analyse shaders. 0 lets the injector decide."),
    Setting("ShaderDiscovery", "WorkerThreadPriority", "Worker priority", "choice", -1,
            choices=((-2, "Lowest"), (-1, "Below normal"), (0, "Normal"), (1, "Above normal"), (2, "Highest")),
            help="Windows thread priority for that analysis."),
    Setting("ShaderDiscovery", "FrameJobBudget", "Jobs per frame", "int", 8192, 1, 1_000_000,
            help="How much discovery work may happen in one frame."),
    Setting("ShaderDiscovery", "PendingAnalysisLimit", "Analysis limit", "int", 64, 1, 100_000,
            help="Shaders waiting for analysis before new ones are held back."),
    Setting("ShaderDiscovery", "QueuedShaderLimit", "Queue limit", "int", 8192, 1, 1_000_000,
            help="Shaders queued for discovery before the oldest are dropped."),
    Setting("ShaderDiscovery", "MinimumSimilarityScore", "Minimum similarity", "float", 0.90, 0.0, 1.0,
            help="How closely a shader must match a known one in analysis mode."),
    Setting("ShaderDiscovery", "SimilarityAmbiguityMargin", "Ambiguity margin", "float", 0.02, 0.0, 1.0,
            help="How far ahead the best match must be before it is trusted."),
)

# Virtual-key codes, named the way upstream's settings guide names them.
KEY_NAMES: dict[int, str] = {
    **{112 + index: f"F{index + 1}" for index in range(12)},
    8: "Backspace", 9: "Tab", 13: "Enter", 19: "Pause", 20: "Caps Lock", 27: "Escape",
    32: "Space", 33: "Page Up", 34: "Page Down", 35: "End", 36: "Home",
    37: "Left", 38: "Up", 39: "Right", 40: "Down", 44: "Print Screen",
    45: "Insert", 46: "Delete", 145: "Scroll Lock",
    **{48 + digit: str(digit) for digit in range(10)},
    **{65 + letter: chr(65 + letter) for letter in range(26)},
    **{96 + digit: f"Numpad {digit}" for digit in range(10)},
    106: "Numpad *", 107: "Numpad +", 109: "Numpad -", 110: "Numpad .", 111: "Numpad /",
}


def key_name(code: int) -> str:
    return KEY_NAMES.get(int(code), f"Key code {int(code)}")


def schema() -> list[dict]:
    return [{
        "section": item.section, "key": item.key, "label": item.label, "kind": item.kind,
        "default": item.default, "minimum": item.minimum, "maximum": item.maximum,
        "choices": [{"value": value, "label": label} for value, label in item.choices],
        "help": item.help,
    } for item in SETTINGS]


def _parse_ini(text: str) -> tuple[list[tuple[str, list[tuple[str, str]]]], list[str]]:
    """Sections in order, and the problems the injector's own parser would hit."""
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    problems: list[str] = []
    current: list[tuple[str, str]] | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                problems.append(f"Line {number}: section not closed.")
                continue
            name = line[1:-1].strip()
            existing = next((fields for title, fields in sections if title == name), None)
            if existing is None:
                current = []
                sections.append((name, current))
            else:
                current = existing
            continue
        if "=" not in line:
            problems.append(f"Line {number}: no '=' in \"{line}\".")
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if current is None:
            problems.append(f"Line {number}: {key} has no section.")
            continue
        if any(existing == key for existing, _ in current):
            problems.append(f"Line {number}: {key} appears twice, so the injector would ignore the whole file.")
            continue
        current.append((key, value))
    return sections, problems


def _coerce(setting: Setting, value: object) -> object:
    if setting.kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1"):
            return True
        if text in ("false", "0"):
            return False
        raise ValueError(f"{setting.label} must be true or false.")
    if isinstance(value, bool):
        raise ValueError(f"{setting.label} must be a number.")
    try:
        number = float(value) if setting.kind == "float" else int(str(value).strip(), 10)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{setting.label} must be a number.") from error
    if setting.kind in ("int", "key", "choice") and isinstance(value, float) and not float(value).is_integer():
        raise ValueError(f"{setting.label} must be a whole number.")
    if setting.kind == "key" and not 1 <= number <= 254:
        raise ValueError(f"{setting.label} must be a key code from 1 to 254.")
    if setting.kind == "choice" and number not in {choice for choice, _ in setting.choices}:
        raise ValueError(f"{setting.label} is not one of its choices.")
    if setting.minimum is not None and number < setting.minimum:
        raise ValueError(f"{setting.label} must be at least {setting.minimum:g}.")
    if setting.maximum is not None and number > setting.maximum:
        raise ValueError(f"{setting.label} must be at most {setting.maximum:g}.")
    return number


def _format(setting: Setting, value: object) -> str:
    if setting.kind == "bool":
        return "true" if value else "false"
    if setting.kind == "float":
        return repr(float(value))
    return str(int(value))


def read_settings(root: Path) -> dict:
    """The injector's settings as it would read them, defaults included."""
    path = Path(root) / INI
    exists = path.is_file()
    sections, problems = _parse_ini(path.read_text(encoding="utf-8", errors="replace")) if exists else ([], [])
    found = {name: dict(fields) for name, fields in sections}
    values: dict[str, dict[str, object]] = {}
    for setting in SETTINGS:
        raw = found.get(setting.section, {}).get(setting.key)
        value = setting.default
        if raw is not None:
            try:
                value = _coerce(setting, raw)
            except ValueError as error:
                problems.append(f"{error} Using the default, {_format(setting, setting.default)}.")
        values.setdefault(setting.section, {})[setting.key] = value
    return {"path": str(path), "exists": exists, "values": values, "problems": problems}


def write_settings(root: Path, changes: dict) -> dict:
    """Validate and write. Every known key is written; unknown ones are kept."""
    path = Path(root) / INI
    if not Path(root).is_dir():
        raise ValueError(f"No game folder at {root}")
    known = {(setting.section, setting.key): setting for setting in SETTINGS}
    current = read_settings(root)["values"]
    for section, fields in (changes or {}).items():
        if not isinstance(fields, dict):
            raise ValueError(f"Settings for {section} must be a set of keys.")
        for key, value in fields.items():
            setting = known.get((section, key))
            if setting is None:
                raise ValueError(f"{section}.{key} is not a Shader Injector setting.")
            current[section][key] = _coerce(setting, value)
    existing, _ = _parse_ini(path.read_text(encoding="utf-8", errors="replace")) if path.is_file() else ([], [])
    order = []
    for setting in SETTINGS:
        if setting.section not in order:
            order.append(setting.section)
    lines: list[str] = []
    for section in order:
        lines.append(f"[{section}]")
        for setting in SETTINGS:
            if setting.section == section:
                lines.append(f"{setting.key}={_format(setting, current[section][setting.key])}")
        extras = next((fields for name, fields in existing if name == section), [])
        lines.extend(f"{key}={value}" for key, value in extras if (section, key) not in known)
        lines.append("")
    for name, fields in existing:
        if name in order:
            continue
        lines.append(f"[{name}]")
        lines.extend(f"{key}={value}" for key, value in fields)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return read_settings(root)


# --------------------------------------------------------------------------
# Neighbours: ReShade's keys, and the game's shader cache

RESHADE_KEYS = {
    "KeyOverlay": "opens the ReShade overlay",
    "KeyEffects": "toggles ReShade's effects",
    "KeyReload": "reloads ReShade's effects",
    "KeyScreenshot": "takes a ReShade screenshot",
    "KeyNextPreset": "switches to ReShade's next preset",
    "KeyPreviousPreset": "switches to ReShade's previous preset",
}


def hotkey_conflicts(root: Path, values: dict | None = None) -> list[dict]:
    """Injector keys that ReShade, installed in the same folder, also answers.

    Only a ReShade binding with no modifier counts: Ctrl+Insert does not fire
    when Insert alone is pressed.
    """
    reshade = Path(root) / "ReShade.ini"
    if not reshade.is_file():
        return []
    values = values or read_settings(root)["values"]
    sections, _ = _parse_ini(reshade.read_text(encoding="utf-8", errors="replace"))
    bindings = dict(next((fields for name, fields in sections if name.upper() == "INPUT"), []))
    conflicts = []
    injector_keys = {"OpenMenuKey": "opens the Shader Injector menu",
                     "ToggleInjectorKey": "toggles Shader Injector"}
    for key, what in injector_keys.items():
        code = int(values["InjectorSettings"][key])
        for binding, does in RESHADE_KEYS.items():
            parts = [part.strip() for part in bindings.get(binding, "").split(",")]
            if not parts or not parts[0].isdigit():
                continue
            if int(parts[0]) == code and all(part in ("", "0") for part in parts[1:]):
                conflicts.append({"injectorKey": key, "reshadeKey": binding, "code": code,
                                  "message": f"{key_name(code)} {what} and also {does}."})
    return conflicts


def documents_folder() -> Path:
    """The player's Documents, wherever Windows has put it."""
    if os.name == "nt":
        import ctypes
        buffer = ctypes.create_unicode_buffer(260)
        # CSIDL_PERSONAL. Documents is often moved off C:, as it is here.
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0 and buffer.value:
            return Path(buffer.value)
    return Path.home() / "Documents"


def shader_cache(documents: Path | None = None) -> dict:
    folder = Path(documents or documents_folder()).joinpath(*CACHE_FOLDER)
    files = sorted(folder.glob(CACHE_PATTERN)) if folder.is_dir() else []
    return {"folder": str(folder),
            "files": [{"name": path.name, "bytes": path.stat().st_size} for path in files],
            "bytes": sum(path.stat().st_size for path in files)}


def clear_shader_cache(documents: Path | None = None) -> dict:
    """Delete the game's compiled-shader cache, and only that."""
    folder = Path(documents or documents_folder()).joinpath(*CACHE_FOLDER)
    removed, failed = [], []
    if folder.is_dir():
        for path in sorted(folder.glob(CACHE_PATTERN)):
            if not path.is_file():
                continue
            try:
                path.unlink()
                removed.append(path.name)
            except OSError as error:
                failed.append({"name": path.name, "error": str(error)})
    return {"removed": removed, "failed": failed}


def _manifest(root: Path) -> dict:
    try:
        value = json.loads((Path(root) / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def install_time(root: Path) -> float | None:
    """When Shader Injector went into this folder, as an epoch time.

    The install record when Lexeditor made one; otherwise the DLL's own date,
    which is when a hand install from the archive put it there.
    """
    stamp = _manifest(root).get("installedAt")
    if stamp:
        try:
            return datetime.fromisoformat(str(stamp)).timestamp()
        except ValueError:
            pass
    for name in (DLL, DISABLED_DLL):
        path = Path(root) / name
        if path.is_file():
            return path.stat().st_mtime
    return None


def setup_notice(root: Path, installed: bool, documents: Path | None = None) -> dict | None:
    """What first-time setup still needs after the install: a fresh shader cache.

    A cache older than the install was compiled by a game that never had the
    injector in it. Rebirth then loads nearly every shader from that cache, so
    the injector sees almost nothing compiled and replaces almost nothing. The
    game rebuilds the cache on the next start after it is cleared; once it is
    newer than the install, this goes quiet on its own.
    """
    if not installed:
        return None
    since = install_time(root)
    cache = shader_cache(documents)
    if since is None or not cache["files"]:
        return None
    folder = Path(cache["folder"])
    newest = max((folder / item["name"]).stat().st_mtime for item in cache["files"])
    if newest >= since:
        return None
    size = f"{cache['bytes'] / 1048576:,.0f} MB"
    return {
        "title": "Purge the shader cache first",
        "message": ("Shader Injector can only replace shaders it watches the game compile, and "
                    f"Rebirth's {size} shader cache was built before it was installed, so the game "
                    "would skip compiling almost all of them. Clear the cache with the game closed; "
                    "Rebirth rebuilds it the next time it starts."),
        "action": "clear_shader_cache",
        "actionLabel": "Clear shader cache",
        "bytes": cache["bytes"],
        "folder": cache["folder"],
    }


def status(root: Path, package: Package | None = None, documents: Path | None = None) -> dict:
    """Everything the Shader Injector subtab shows."""
    package = package or default_package()
    root = Path(root)
    active, parked = root / DLL, root / DISABLED_DLL
    enabled = _is_ours(active, package)
    installed = enabled or _is_ours(parked, package)
    missing, modified = [], []
    if installed:
        for name, digest in package.hashes.items():
            if name == DLL:
                continue
            target = root / name
            if not target.is_file():
                missing.append(name)
            elif _file_sha(target) != digest:
                modified.append(name)
    settings = read_settings(root)
    return {
        "name": "Shader Injector", "version": VERSION, "variant": VARIANT,
        "author": "David Matos", "source": SOURCE, "release": RELEASE, "license": "MIT",
        "folder": str(root), "folderExists": root.is_dir(),
        "installed": installed, "enabled": enabled,
        "foreignDll": active.is_file() and not enabled,
        "missingFiles": missing, "modifiedFiles": modified,
        "settings": settings, "schema": schema(),
        "keyNames": {str(code): name for code, name in sorted(KEY_NAMES.items())},
        "conflicts": hotkey_conflicts(root, settings["values"]) if root.is_dir() else [],
        "shaderCache": shader_cache(documents),
        "setupNotice": setup_notice(root, installed, documents),
    }


# --------------------------------------------------------------------------
# The shell's helper contract: first-time setup, the Updates drawer, and the
# one setup step this helper can ask for.

LATEST_RELEASE_API = "https://api.github.com/repos/frostbone25/ShaderInjector/releases/latest"


def _game_folder(game_root: Path | None) -> Path | None:
    if game_root is None:
        return None
    folder = Path(game_root) / INSTALL_FOLDER
    return folder if folder.is_dir() else None


def helper_status(game_root: Path | None, package: Package | None = None,
                  documents: Path | None = None) -> dict:
    """What the shell reads to decide whether Rebirth is set up."""
    base = {"runtime": "Shader Injector", "pinned": VERSION, "packageVersion": VERSION,
            "source": SOURCE, "releaseNotes": RELEASE, "installed": False, "version": "",
            "autoUpdate": False}
    folder = _game_folder(game_root)
    if folder is None:
        return {**base, "message": "Final Fantasy VII Rebirth has not been located."}
    try:
        state = status(folder, package, documents)
    except (OSError, ValueError) as error:
        return {**base, "message": f"Shader Injector could not be verified: {error}", "error": str(error)}
    ready = state["installed"] and not state["missingFiles"]
    if state["foreignDll"]:
        message = ("dsound.dll in the game folder belongs to another mod, so Shader Injector cannot "
                   "be installed. Move that file out of the way, then Install/Repair.")
    elif not state["installed"]:
        message = f"Install the bundled Shader Injector {VERSION} to finish setting up this game."
    elif state["missingFiles"]:
        message = (f"{len(state['missingFiles'])} Shader Injector files are missing. "
                   "Use Install/Repair to restore them.")
    else:
        message = f"Pinned Shader Injector {VERSION} verified{'' if state['enabled'] else ', switched off'}."
    return {**base, "installed": ready, "version": VERSION if state["installed"] else "",
            "integrity": "verified" if ready else "mismatch" if state["installed"] else "missing",
            "enabled": state["enabled"], "gameRoot": str(folder), "message": message,
            "setupNotice": state["setupNotice"]}


def helper_install(game_root: Path, package: Package | None = None) -> dict:
    folder = _game_folder(game_root)
    if folder is None:
        raise ValueError("Locate Final Fantasy VII Rebirth before installing Shader Injector.")
    result = install(folder, package)
    return {**helper_status(game_root, package), **result, "changed": bool(result["written"])}


def clear_cache_action(game_root: Path | None) -> dict:
    """The setup step first-time setup offers beside the game."""
    result = clear_shader_cache()
    if result["failed"]:
        first = result["failed"][0]
        raise ValueError(f"Could not delete {first['name']}: {first['error']}. Close the game first.")
    return {**result, "message": "Cleared the shader cache. Rebirth rebuilds it the next time it starts."}


def _version_tuple(text: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?", str(text).strip())
    if not match:
        return None
    parts = [int(part) for part in match.groups() if part is not None]
    return tuple(parts + [0] * (4 - len(parts)))


def _fetch_json(url: str) -> dict:
    import urllib.request
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor-ShaderInjector/1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("Shader Injector release metadata is too large.")
    return json.loads(raw)


def upstream_release(fetch_json=None) -> dict:
    """Latest is information, never an install target or a moving pin."""
    base = {"runtime": "Shader Injector", "pinned": VERSION, "packageVersion": VERSION, "source": SOURCE}
    try:
        payload = (fetch_json or _fetch_json)(LATEST_RELEASE_API)
        latest = str(payload.get("tag_name", ""))
        parsed = _version_tuple(latest)
        if parsed is None or payload.get("draft") or payload.get("prerelease"):
            raise RuntimeError("Upstream did not return a stable Shader Injector release.")
        return {**base, "latest": latest, "published": str(payload.get("published_at", "")),
                "releaseNotes": SOURCE + "/releases/tag/" + latest,
                "behind": parsed > _version_tuple(VERSION)}
    except Exception as error:
        return {**base, "error": str(error), "behind": False}
