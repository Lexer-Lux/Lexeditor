"""ReShade presets that travel with a Lexeditor mod.

Three requirements pull against each other, so the shape is deliberate:

  * one ReShade managed by Lexeditor rather than a copy inside every mod,
  * each mod carrying its own preset and any shaders its author actually wrote,
  * and a published mod still working for someone who has never used Lexeditor.

The last one decides the format. A mod ships a plain ReShade preset and the
shaders it uses. The effects are Lexeditor's own (shaders), so
they may travel with a mod. Nothing here invents a container that only
Lexeditor can open.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import zipfile

MANIFEST_NAME = "reshade.json"
RESHADE_DIR = "reshade"
PRESET_SUFFIXES = (".ini",)
SHADER_SUFFIXES = (".fx", ".fxh")
# The loader DLL name depends on the renderer the game uses.
RENDERER_DLLS = {
    "dx9": "d3d9.dll", "dx10": "d3d10.dll", "dx11": "d3d11.dll",
    "dx12": "d3d12.dll", "dxgi": "dxgi.dll", "opengl": "opengl32.dll",
    "vulkan": "vulkan-1.dll",
}


def _reshade_root(project_root: Path) -> Path:
    return Path(project_root) / RESHADE_DIR


def manifest_path(project_root: Path) -> Path:
    return _reshade_root(project_root) / MANIFEST_NAME


def read_manifest(project_root: Path) -> dict:
    """Return the mod's ReShade manifest, defaulted when it has none yet."""
    path = manifest_path(project_root)
    payload: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, ValueError):
            payload = {}
    return {
        "enabled": bool(payload.get("enabled", False)),
        "preset": str(payload.get("preset", "") or ""),
        "renderer": str(payload.get("renderer", "") or ""),
    }


def write_manifest(project_root: Path, manifest: dict) -> dict:
    """Persist the manifest, creating the mod's reshade folder if needed."""
    root = _reshade_root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    clean = {
        "enabled": bool(manifest.get("enabled", False)),
        "preset": str(manifest.get("preset", "") or ""),
        "renderer": str(manifest.get("renderer", "") or ""),
    }
    manifest_path(project_root).write_text(
        json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    return clean


def _listing(root: Path, suffixes: tuple[str, ...]) -> list[str]:
    if not root.is_dir():
        return []
    found = []
    for folder, folders, files in os.walk(root):
        folders[:] = [name for name in folders if not name.startswith(".")]
        for name in sorted(files):
            if Path(name).suffix.lower() in suffixes:
                found.append(str(Path(folder, name).relative_to(root)).replace("\\", "/"))
    return sorted(found)


# ReShade's name as Windows stores it in a version resource. A DLL that merely
# mentions ReShade in ASCII - a wrapper, a loader, a game that credits it - has
# no reason to carry the wide form, and this decides whether Lexeditor is
# allowed to overwrite or delete a file inside someone's game.
RESHADE_MARKER = "ReShade".encode("utf-16-le")


def is_reshade(path: Path) -> bool:
    """Is this file ReShade's loader?

    Two things must hold: it is a Windows binary, and its version resource
    names ReShade. The whole file is searched, not a window at the front: in
    ReShade 6.8 the name first appears 4.3 MB in, so a two-megabyte read
    rejected the real loader.

    An ASCII match alone is not enough. Rebirth ships a d3d12.dll of its own,
    and the cost of being wrong here is a deleted or overwritten game file.
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return False
    return data[:2] == b"MZ" and RESHADE_MARKER in data


def occupied_loaders(game_root: Path | None) -> list[dict]:
    """Loader names already taken in this game by something that is not ReShade.

    A player who fixed their own game keeps a wrapper under one of these names
    - a DirectX 12 fix, a mod loader, a frame-rate patch. Lexeditor will not
    overwrite one, and saying which are taken beforehand is better than
    refusing after the choice is made.
    """
    if not game_root:
        return []
    root = Path(game_root)
    taken = []
    for renderer, dll in sorted(RENDERER_DLLS.items()):
        candidate = root / dll
        if candidate.is_file() and not is_reshade(candidate):
            taken.append({"renderer": renderer, "dll": dll,
                          "bytes": candidate.stat().st_size})
    return taken


def installed_renderer(game_root: Path | None) -> str:
    """Name the ReShade loader already present in the game folder, if any."""
    if not game_root:
        return ""
    root = Path(game_root)
    for renderer, dll in RENDERER_DLLS.items():
        candidate = root / dll
        if candidate.is_file() and is_reshade(candidate):
            return renderer
    return ""


# Lexeditor keeps ONE ReShade and installs it per game. The user supplies that
# copy once - ReShade is not vendored here, because which build to ship is their
# decision and not one a mod editor should make quietly on their behalf.
STORE = Path(os.environ.get("LOCALAPPDATA", "")) / "Lexeditor" / "reshade"
STORE_DLL = "ReShade64.dll"


# ReshadeEffectShaderToggler (MIT): an add-on that runs effects at a chosen
# point in the game's rendering, such as just before the HUD is drawn, so depth
# of field and friends leave the HUD alone. Pinned and bundled like ReShade.
HUD_ADDON_VERSION = "1.3.23.633"
HUD_ADDON_ARCHIVE = (Path(__file__).resolve().parents[1] / "tools" / "reshade" / "addons"
                     / f"REST-{HUD_ADDON_VERSION}" / f"ReshadeEffectShaderToggler-{HUD_ADDON_VERSION}.zip")
HUD_ADDON_SHA256 = "79aaf38002e103034527eeb09553cbc422b44989d22258e905652131904afa6d"
HUD_ADDON_FILES = {64: "ReshadeEffectShaderToggler.addon64", 32: "ReshadeEffectShaderToggler.addon32"}


def _hud_addon_bytes(bits: int) -> bytes:
    data = HUD_ADDON_ARCHIVE.read_bytes()
    if hashlib.sha256(data).hexdigest() != HUD_ADDON_SHA256:
        raise ValueError("The bundled Effect Shader Toggler add-on does not match its pinned build.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read(HUD_ADDON_FILES[bits])


def install_hud_addon(game_root: Path, bits: int) -> dict:
    """Put the add-on that matches ReShade's build beside it.

    It does nothing until a shader group is set up in its ReShade tab, so it is
    safe to install with every ReShade.
    """
    payload = _hud_addon_bytes(bits)
    target = Path(game_root) / HUD_ADDON_FILES[bits]
    if not (target.is_file() and target.read_bytes() == payload):
        target.write_bytes(payload)
    return {"installed": True, "path": str(target), "version": HUD_ADDON_VERSION}


def store_dll(bits: int = 64) -> Path:
    return STORE / (STORE_DLL32 if int(bits) == 32 else STORE_DLL)


# ReShade itself. The binary is BSD-3, so Lexeditor may fetch and keep a copy;
# what it must not do is fetch a different one than the user was told about,
# which is why the version, the variant and the file's hash are all recorded.
#
# The download is the ordinary setup program from reshade.me. That program is
# a small executable with a zip stuck on the end holding the two loader DLLs,
# so the DLL is taken straight out of it rather than running an installer.
LOADER_REPOSITORY = "crosire/reshade"
LOADER_TAGS = "https://api.github.com/repos/crosire/reshade/tags"
LOADER_SOURCE = "https://github.com/crosire/reshade"
LOADER_DOWNLOAD = "https://reshade.me/downloads/ReShade_Setup_{version}{variant}.exe"
LOADER_STATE = "loader.json"
LOADER_LICENCE = "BSD-3-Clause"
# The add-on build is the default: without it ReShade loads no .addon64, and a
# preset that runs its passes through an add-on renders nothing at all.
LOADER_VARIANTS = {"addon": "_Addon", "plain": ""}
DEFAULT_LOADER_VARIANT = "addon"

# The pinned build, and the exact bytes it must arrive as.
#
# Lexeditor pins its helpers: a version nobody chose is a version nobody
# tested, and a preset authored against one ReShade and played on another is
# the situation the pin exists to prevent. The panel still reports when
# upstream moves; moving is a decision, made here, with a new hash beside it.
PINNED_LOADER = "6.8.0"
PINNED_LOADER_SHA256 = {
    "addon": "0cee63f9c9f13f3ac909c5b4903f4dbb4b719a7ab3b4f13b0deaf83c814b94f7",
    "plain": "b2945c29e7095491a901746b400e58db9b1592ab092bacf2a888ce37f02d08da",
}
PINNED_LOADER32_SHA256 = {
    "addon": "da430e0a9c6eecefa0d1b27d05e16c426fb5d04e808b194d914eaac4b31bc0f8",
    "plain": "538998f66c0197adcdeadfe8e5ea19dd6ca3253e40399476d291f385ce518b88",
}
STORE_DLL32 = "ReShade32.dll"

# Vendored. Both pinned setup programs ship inside Lexeditor, so ReShade is
# installed without touching the network, and a release build carries them
# (tools/build_distribution.py names them explicitly). A setup is the exact
# file reshade.me publishes; its hash and each loader's inside it are pinned.
VENDORED_RESHADE = Path(__file__).resolve().parents[1] / "tools" / "reshade" / PINNED_LOADER
VENDORED_SETUPS = {
    "addon": f"ReShade_Setup_{PINNED_LOADER}_Addon.exe",
    "plain": f"ReShade_Setup_{PINNED_LOADER}.exe",
}
PINNED_SETUP_SHA256 = {
    "addon": "afe4c8f13048306307983b8b3d41d5bf00a86820440b0e57dea10950e1176445",
    "plain": "207aea16205fbf952bc8fe1879966672454cf04002e7ad34237c7990a5b3c0b4",
}
RESHADE_LICENSE = VENDORED_RESHADE / "LICENSE.md"


def loader_state() -> dict:
    """What this machine's copy of ReShade is, as recorded when it arrived."""
    path = STORE / LOADER_STATE
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def store_state() -> dict:
    dll = store_dll()
    dll32 = store_dll(32)
    recorded = loader_state()
    return {"path": str(dll), "present": dll.is_file(),
            "path32": str(dll32), "present32": dll32.is_file(),
            "bytes": dll.stat().st_size if dll.is_file() else 0,
            "version": str(recorded.get("version", "")),
            "variant": str(recorded.get("variant", "")),
            "sha256": str(recorded.get("sha256", "")),
            "installedAt": str(recorded.get("installedAt", "")),
            "source": LOADER_SOURCE, "licence": LOADER_LICENCE, "pinned": PINNED_LOADER}


def _version_key(version: str) -> tuple:
    parts = str(version or "").lstrip("vV").split(".")
    numbers = []
    for part in parts:
        digits = "".join(character for character in part if character.isdigit())
        numbers.append(int(digits) if digits else 0)
    return tuple(numbers)


def latest_loader(*, fetch=None) -> dict:
    """The newest ReShade upstream has tagged.

    Upstream publishes no GitHub release for the binary, so the tag list is
    the version and reshade.me is where the build comes from. Saying that out
    loud matters: the panel reports one source and downloads from another.
    """
    fetch = fetch or _fetch
    payload = json.loads(fetch(LOADER_TAGS).decode("utf-8"))
    names = [str(entry.get("name", "")) for entry in payload if isinstance(entry, dict)]
    names = [name for name in names if name]
    if not names:
        raise ValueError("Upstream listed no ReShade tags.")
    newest = max(names, key=_version_key)
    found = {"latest": newest.lstrip("vV"), "tag": newest, "source": LOADER_SOURCE}
    # The panel shows a date beside every other helper. A tag carries none, so
    # it comes from the commit the tag points at; failing to get it costs the
    # date, never the check.
    commit = next((entry.get("commit", {}).get("url", "") for entry in payload
                   if isinstance(entry, dict) and entry.get("name") == newest), "")
    if commit:
        try:
            detail = json.loads(fetch(commit).decode("utf-8"))
            found["published"] = str(
                detail.get("commit", {}).get("committer", {}).get("date", ""))
        except Exception:
            pass
    return found


def loader_upstream(*, fetch=None) -> dict:
    """One helper row for ReShade: what is here, what is out there."""
    mine = store_state()
    row = {"helper": "ReShade", "plugin": "Every game", "pluginId": "",
           "pinned": PINNED_LOADER, "licence": LOADER_LICENCE, "installable": True,
           "variant": mine["variant"] or DEFAULT_LOADER_VARIANT,
           "installed": mine["present"],
           "installedVersion": mine["version"],
           "installedStatus": ("installed" if mine["present"] else "not installed"),
           "source": LOADER_SOURCE}
    try:
        upstream = latest_loader(fetch=fetch)
    except Exception as error:
        return {**row, "error": str(error), "behind": False}
    row.update(upstream)
    row["releaseNotes"] = f"{LOADER_SOURCE}/releases/tag/{upstream['tag']}"
    # Behind the pin is this machine's problem and the button fixes it.
    row["behind"] = bool(mine["present"] and mine["version"] != PINNED_LOADER)
    # Upstream being ahead of the pin is a decision for whoever moves the pin.
    row["upstreamAhead"] = bool(
        _version_key(upstream["latest"]) > _version_key(PINNED_LOADER))
    if mine["present"] and not mine["version"]:
        # Adopted by hand: there is a DLL but nothing said which build it is.
        row["installedStatus"] = "installed, version unknown"
    return row


def install_loader(version: str = "", *, variant: str = DEFAULT_LOADER_VARIANT,
                   setup: Path | None = None) -> dict:
    """Make the pinned ReShade Lexeditor's copy, from the setup it ships with.

    Nothing is downloaded: both pinned setups are vendored beside this file. A
    setup is a small executable with a zip on the end holding the 64-bit and
    32-bit loaders, and both are read straight out of it. Nothing is run, and
    nothing is installed into a game here.

    The setup, and each loader inside it, must hash to the pin.
    """
    import hashlib
    import zipfile
    from datetime import datetime, timezone

    name = str(variant or "").lower()
    if name not in LOADER_VARIANTS:
        raise ValueError(f"Unknown ReShade variant: {variant}")
    wanted = str(version or "").lstrip("vV") or PINNED_LOADER
    if wanted != PINNED_LOADER:
        raise ValueError(
            f"Lexeditor pins ReShade {PINNED_LOADER}; it will not install {wanted}. "
            "Change the pin, with its hash, to move.")
    setup = Path(setup) if setup else VENDORED_RESHADE / VENDORED_SETUPS[name]
    if not setup.is_file():
        raise ValueError(f"The bundled ReShade setup is missing: {setup}")
    digest = hashlib.sha256(setup.read_bytes()).hexdigest()
    if digest != PINNED_SETUP_SHA256[name]:
        raise ValueError(
            f"{setup.name} is not the pinned ReShade {wanted} {name} setup. "
            f"Expected {PINNED_SETUP_SHA256[name]}, got {digest}. Nothing was installed.")
    loaders: dict[int, tuple[bytes, str]] = {}
    try:
        with zipfile.ZipFile(setup) as archive:
            for bits, member, pins in ((64, STORE_DLL, PINNED_LOADER_SHA256),
                                       (32, STORE_DLL32, PINNED_LOADER32_SHA256)):
                dll = archive.read(member)
                found = hashlib.sha256(dll).hexdigest()
                if found != pins[name]:
                    raise ValueError(
                        f"{member} inside {setup.name} is not the pinned {name} build. "
                        f"Expected {pins[name]}, got {found}. Nothing was installed.")
                loaders[bits] = (dll, found)
    except (zipfile.BadZipFile, KeyError) as error:
        raise ValueError(
            f"{setup.name} is not a ReShade setup carrying both loaders: {error}") from error
    STORE.mkdir(parents=True, exist_ok=True)
    for bits, (dll, _found) in loaders.items():
        store_dll(bits).write_bytes(dll)
    recorded = {
        "version": wanted,
        "variant": name,
        "sha256": loaders[64][1],
        "sha256_32": loaders[32][1],
        "bytes": len(loaders[64][0]),
        "setup": setup.name,
        "setupSha256": digest,
        "source": LOADER_SOURCE,
        "licence": LOADER_LICENCE,
        "installedAt": datetime.now(timezone.utc).isoformat(),
    }
    (STORE / LOADER_STATE).write_text(
        json.dumps(recorded, indent=2) + NEWLINE, encoding="utf-8")
    return {**store_state(), "installed": True}


NEWLINE = chr(10)

# Lexeditor's own effects, shipped with the app rather than downloaded.
BUNDLED_SHADERS = Path(__file__).resolve().parents[1] / "shaders"
# Where a mod keeps a copy of them, so a by-hand install has everything.
# Exported mods already carry this folder name; keep it stable.
BUNDLED_FOLDER_NAME = "Lexerian"


def _fetch(url: str, timeout: int = 120) -> bytes:
    import urllib.request
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


EXPORT_NOTE_NAME = "INSTALL-RESHADE.txt"


def export_note(project_root: Path, game_root: Path | None = None) -> str:
    """The text a person installing this mod by hand needs, and nothing else.

    It names the preset file, the loader DLL the game wants, and the shaders
    folder that travels with the mod. It does not describe Lexeditor, because
    the reader may never have used it.
    """
    state = snapshot(project_root, game_root)
    manifest = state["manifest"]
    preset = manifest["preset"] or "(no preset chosen)"
    renderer = manifest["renderer"] or state["installedRenderer"] or ""
    loader = RENDERER_DLLS.get(renderer, "") if renderer else ""
    lines = [
        "Installing this mod's ReShade preset by hand",
        "=" * 44,
        "",
        "You do not need Lexeditor for any of this.",
        "",
        "1. Install ReShade from https://reshade.me into the game folder.",
    ]
    lines.append(
        f"   This game loads it as {loader}." if loader
        else "   Pick the loader for the game's renderer when ReShade asks.")
    lines += [
        "",
        "2. Copy the shaders folder beside this note into ReShade's shaders",
        "   folder. It holds every effect the preset uses.",
    ]
    if state["shaders"]:
        lines += ["   This mod's own shaders in it:"]
        lines += [f"   - {name}" for name in state["shaders"]]
    lines += ["", f"3. Copy {preset} into the game's reshade-presets folder and",
              "   select it in ReShade's overlay."]
    lines.append("")
    return NEWLINE.join(lines)


def write_export_note(project_root: Path, game_root: Path | None = None) -> str:
    """Put the note beside the preset, where anyone unpacking the mod finds it."""
    root = _reshade_root(Path(project_root))
    root.mkdir(parents=True, exist_ok=True)
    # Lexeditor's effects are its own work, so the mod may carry them.
    copy = root / "shaders" / BUNDLED_FOLDER_NAME
    if BUNDLED_SHADERS.is_dir():
        shutil.copytree(BUNDLED_SHADERS, copy, dirs_exist_ok=True)
    path = root / EXPORT_NOTE_NAME
    path.write_text(export_note(project_root, game_root), encoding="utf-8")
    return str(path)


def adopt(source: Path) -> dict:
    """Take the user's ReShade DLL as Lexeditor's one copy."""
    source = Path(source)
    if not source.is_file():
        raise ValueError(f"No file at {source}")
    if not is_reshade(source):
        raise ValueError(f"{source.name} does not look like a ReShade DLL")
    STORE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, store_dll())
    return store_state()


RESHADE_INI = "ReShade.ini"


def shader_paths(project_root: Path | None) -> tuple[list[Path], list[Path]]:
    """Every folder ReShade should search for effects and for textures.

    Lexeditor's own effects, plus the shaders the mod's own author wrote. The
    copy of Lexeditor's effects a mod carries for by-hand installs sits one
    folder down and is not searched, so no effect is compiled twice.
    """
    effects: list[Path] = []
    textures: list[Path] = []
    if BUNDLED_SHADERS.is_dir():
        effects.append(BUNDLED_SHADERS)
    if project_root:
        authored = Path(project_root) / RESHADE_DIR / "shaders"
        if authored.is_dir():
            effects.append(authored)
    return effects, textures


def configure(game_root: Path, project_root: Path | None = None) -> dict:
    """Tell ReShade where the shaders are and which preset to load.

    Installing the loader is not enough: ReShade reads its own ReShade.ini
    beside the game and, with no search paths in it, compiles nothing and shows
    an empty effect list. Only the keys Lexeditor owns are written; anything
    else already in the file is left alone.
    """
    game_root = Path(game_root)
    if not game_root.is_dir():
        raise ValueError(f"No game folder at {game_root}")
    effects, textures = shader_paths(project_root)
    manifest = read_manifest(project_root) if project_root else {}
    preset = ""
    named = str(manifest.get("preset", "") or "")
    if named and project_root:
        candidate = Path(project_root) / RESHADE_DIR / named
        if candidate.is_file():
            preset = str(candidate)
    wanted = {
        "EffectSearchPaths": ",".join(str(path) for path in effects),
        "TextureSearchPaths": ",".join(str(path) for path in textures or effects),
    }
    if preset:
        wanted["PresetPath"] = preset
    target = game_root / RESHADE_INI
    lines = (target.read_text(encoding="utf-8", errors="replace").splitlines()
             if target.is_file() else [])
    if "[GENERAL]" not in [line.strip().upper() for line in lines]:
        lines = (lines + [""] if lines else []) + ["[GENERAL]"]
    written = set()
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in wanted:
            lines[index] = f"{key}={wanted[key]}"
            written.add(key)
    if written != set(wanted):
        insert = next(index for index, line in enumerate(lines)
                      if line.strip().upper() == "[GENERAL]") + 1
        for key, value in wanted.items():
            if key not in written:
                lines.insert(insert, f"{key}={value}")
                insert += 1
    target.write_text(NEWLINE.join(lines) + NEWLINE, encoding="utf-8")
    return {
        "path": str(target),
        "effectPaths": [str(path) for path in effects],
        "preset": preset,
        # The reason nothing happens when this is empty, said plainly.
        "ready": bool(effects) and bool(preset),
        "reason": ("" if effects and preset else
                   "No shader folder was found."
                   if not effects else
                   "This mod names no preset that is present."),
    }


PE_MACHINES = {0x014C: 32, 0x8664: 64}


def executable_bits(path: Path) -> int | None:
    """32 or 64, read from a Windows executable's own header."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(0x40)
            if len(head) < 0x40 or head[:2] != b"MZ":
                return None
            handle.seek(int.from_bytes(head[0x3C:0x40], "little"))
            signature = handle.read(6)
    except OSError:
        return None
    if len(signature) < 6 or signature[:4] != b"PE\0\0":
        return None
    return PE_MACHINES.get(int.from_bytes(signature[4:6], "little"))


GRAPHICS_IMPORTS = frozenset({
    "d3d8.dll", "d3d9.dll", "d3d10.dll", "d3d10_1.dll", "d3d11.dll", "d3d12.dll",
    "dxgi.dll", "ddraw.dll", "opengl32.dll", "vulkan-1.dll",
})


def executable_imports(path: Path) -> set[str]:
    """The DLL names a Windows executable imports, from its own import table."""
    import mmap

    def u16(at):
        return int.from_bytes(data[at:at + 2], "little")

    def u32(at):
        return int.from_bytes(data[at:at + 4], "little")

    try:
        with open(path, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
            if data[:2] != b"MZ":
                return set()
            header = u32(0x3C)
            if data[header:header + 4] != b"PE\0\0":
                return set()
            coff = header + 4
            optional = coff + 20
            magic = u16(optional)
            if magic not in (0x10B, 0x20B):
                return set()
            directory = optional + (96 if magic == 0x10B else 112) + 8
            imports = u32(directory)
            if not imports:
                return set()
            table = optional + u16(coff + 16)
            spans = []
            for index in range(u16(coff + 2)):
                entry = table + 40 * index
                spans.append((u32(entry + 12), max(u32(entry + 8), u32(entry + 16)), u32(entry + 20)))

            def offset(rva):
                for start, size, raw in spans:
                    if start <= rva < start + size:
                        return raw + (rva - start)
                return None

            names: set[str] = set()
            cursor = offset(imports)
            while cursor is not None and cursor + 20 <= len(data) and any(data[cursor:cursor + 20]):
                at = offset(u32(cursor + 12))
                if at is not None:
                    end = data.find(b"\0", at, at + 260)
                    if end > at:
                        names.add(bytes(data[at:end]).decode("ascii", "replace").lower())
                cursor += 20
                if len(names) > 1024:
                    break
            return names
    except (OSError, ValueError, IndexError):
        return set()


def renders(path: Path) -> bool:
    """Does this executable draw anything? A launcher imports no graphics API."""
    return bool(executable_imports(path) & GRAPHICS_IMPORTS)


def loader_bits(folder: Path, executable: Path | None = None) -> int:
    """Which ReShade build this game loads, from what the player's install runs.

    A 32-bit game cannot load ReShade64 and a 64-bit one cannot load
    ReShade32, so the build follows the executable that actually renders:

    1. the executable Play starts, when it is in this folder and renders;
    2. otherwise the executables here that render, when they agree - FF7's
       launcher draws nothing and hands off to a 64-bit game beside it;
    3. otherwise, with no import table readable, the executable Play starts,
       or every executable here if they agree.

    Only a folder whose rendering executables disagree, where Play starts none
    of them, is refused.
    """
    folder = Path(folder).resolve()
    play = Path(executable).resolve() if executable else None
    if play is not None and play.parent == folder and play.is_file():
        bits = executable_bits(play)
        if bits and renders(play):
            return bits
    executables = sorted(folder.glob("*.exe"))
    drawing = {executable_bits(path) for path in executables if renders(path)} - {None}
    if len(drawing) == 1:
        return drawing.pop()
    if not drawing:
        if play is not None and play.is_file() and executable_bits(play):
            return executable_bits(play)
        found = {executable_bits(path) for path in executables} - {None}
        if len(found) == 1:
            return found.pop()
        if not found:
            raise ValueError(
                f"There is no Windows executable in {folder} to tell 32-bit from 64-bit ReShade.")
    raise ValueError(
        f"{folder} holds 32-bit and 64-bit executables, and the one Play starts does not "
        "decide between them.")


def install(game_root: Path, renderer: str, executable: Path | None = None) -> dict:
    """Place Lexeditor's ReShade in one game, under the loader name it needs.

    The build matches the game's executable, and comes out of the bundled
    setup the first time it is needed, so there is no separate download step.
    """
    game_root = Path(game_root)
    dll_name = RENDERER_DLLS.get(str(renderer).lower())
    if not dll_name:
        raise ValueError(f"Unknown renderer: {renderer}")
    if not game_root.is_dir():
        raise ValueError(f"No game folder at {game_root}")
    bits = loader_bits(game_root, executable)
    source = store_dll(bits)
    if not source.is_file():
        install_loader()
    if not source.is_file():
        raise ValueError(f"Lexeditor could not prepare the {bits}-bit ReShade loader.")
    target = game_root / dll_name
    # A game's own d3d11.dll is not ours to replace. Only an existing ReShade
    # may be overwritten, and only by another ReShade.
    if target.is_file():
        if not is_reshade(target):
            raise ValueError(
                f"{dll_name} already exists in this game and is not ReShade. "
                "Lexeditor will not overwrite it.")
    shutil.copy2(source, target)
    result = {"installed": True, "renderer": str(renderer).lower(), "path": str(target),
              "bits": bits}
    try:
        result["hudAddon"] = install_hud_addon(game_root, bits)
    except Exception as error:
        result["hudAddon"] = {"installed": False, "reason": str(error)}
    # A loader with no search paths compiles nothing, so the two steps are one.
    try:
        result["configured"] = configure(game_root)
    except Exception as error:
        result["configured"] = {"ready": False, "reason": str(error)}
    return result


def uninstall(game_root: Path) -> dict:
    """Remove ReShade from one game. Only a DLL that IS ReShade is deleted."""
    game_root = Path(game_root)
    removed = []
    for renderer, dll_name in RENDERER_DLLS.items():
        target = game_root / dll_name
        if not target.is_file():
            continue
        if not is_reshade(target):
            continue
        try:
            target.unlink()
        except OSError:
            continue
        removed.append({"renderer": renderer, "path": str(target)})
    # The add-on goes with ReShade, but only a copy that is still ours; its
    # saved shader groups (the .ini) are the player's and stay.
    addons = []
    for bits, name in HUD_ADDON_FILES.items():
        target = game_root / name
        if target.is_file() and target.read_bytes() == _hud_addon_bytes(bits):
            try:
                target.unlink()
            except OSError:
                continue
            addons.append({"addon": name, "path": str(target)})
    return {"removed": removed, "removedAddons": addons}


def snapshot(project_root: Path, game_root: Path | None = None) -> dict:
    """Everything the Tweaks page needs to describe this mod's ReShade state."""
    root = _reshade_root(project_root)
    manifest = read_manifest(project_root)
    presets = _listing(root, PRESET_SUFFIXES)
    presets = [name for name in presets if Path(name).name != MANIFEST_NAME]
    shaders = [name for name in _listing(root / "shaders", SHADER_SUFFIXES)
               if not name.startswith(BUNDLED_FOLDER_NAME + "/")]
    renderer = installed_renderer(game_root)
    return {
        "path": str(root),
        "hasFolder": root.is_dir(),
        "manifest": manifest,
        "presets": presets,
        "shaders": shaders,
        "installedRenderer": renderer,
        "reshadeInstalled": bool(renderer),
        "occupiedLoaders": occupied_loaders(game_root),
        "store": store_state(),
        "renderers": sorted(RENDERER_DLLS),
        "exportNote": EXPORT_NOTE_NAME,
        # A preset that names no file, or names one that is not there, would
        # silently do nothing at play time. Say so instead.
        "ready": bool(manifest["enabled"] and manifest["preset"]
                      and manifest["preset"] in presets and renderer),
    }
