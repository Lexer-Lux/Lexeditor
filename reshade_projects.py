"""ReShade presets that travel with a Lexeditor mod.

Three requirements pull against each other, so the shape is deliberate:

  * one ReShade managed by Lexeditor rather than a copy inside every mod,
  * each mod carrying its own preset and any shaders its author actually wrote,
  * and a published mod still working for someone who has never used Lexeditor.

The last one decides the format. A mod ships a plain ReShade preset plus a
manifest naming the shader repositories it needs. Anyone with ReShade already
installed can drop the preset in and install those repositories by hand. Nothing
here invents a container that only Lexeditor can open.

Shader repositories are named, never copied: several common ones forbid
redistribution, so a mod that bundled them would not be safe to publish.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

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
        "repositories": [
            {"name": str(entry.get("name", "")), "version": str(entry.get("version", ""))}
            for entry in payload.get("repositories", [])
            if isinstance(entry, dict) and entry.get("name")
        ],
    }


def write_manifest(project_root: Path, manifest: dict) -> dict:
    """Persist the manifest, creating the mod's reshade folder if needed."""
    root = _reshade_root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    clean = {
        "enabled": bool(manifest.get("enabled", False)),
        "preset": str(manifest.get("preset", "") or ""),
        "renderer": str(manifest.get("renderer", "") or ""),
        "repositories": [
            {"name": str(entry.get("name", "")), "version": str(entry.get("version", ""))}
            for entry in manifest.get("repositories", [])
            if isinstance(entry, dict) and entry.get("name")
        ],
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


def is_reshade(path: Path) -> bool:
    """Is this file ReShade's loader?

    ReShade's own DLL carries its name; a game's real d3d11.dll does not. The
    whole file is searched, not a window at the front: in ReShade 6.8 the name
    first appears 4.3 MB in, so a two-megabyte read rejected the real loader.
    """
    try:
        return b"ReShade" in Path(path).read_bytes()
    except OSError:
        return False


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


def store_dll() -> Path:
    return STORE / STORE_DLL


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
    recorded = loader_state()
    return {"path": str(dll), "present": dll.is_file(),
            "bytes": dll.stat().st_size if dll.is_file() else 0,
            "version": str(recorded.get("version", "")),
            "variant": str(recorded.get("variant", "")),
            "sha256": str(recorded.get("sha256", "")),
            "installedAt": str(recorded.get("installedAt", "")),
            "source": LOADER_SOURCE, "licence": LOADER_LICENCE}


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
           "pinned": "", "licence": LOADER_LICENCE, "installable": True,
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
    row["behind"] = bool(mine["present"] and mine["version"]
                         and _version_key(mine["version"]) < _version_key(upstream["latest"]))
    if mine["present"] and not mine["version"]:
        # Adopted by hand: there is a DLL but nothing said which build it is.
        row["installedStatus"] = "installed, version unknown"
    return row


def install_loader(version: str = "", *, variant: str = DEFAULT_LOADER_VARIANT,
                   fetch=None) -> dict:
    """Fetch one ReShade build and make it Lexeditor's copy.

    The setup program is a zip with an executable header, so the loader DLL is
    read straight out of it. Nothing is run, and nothing is installed into a
    game here: this only fills the store that install() copies from.
    """
    import hashlib
    import io as _io
    import zipfile
    from datetime import datetime, timezone

    fetch = fetch or _fetch
    suffix = LOADER_VARIANTS.get(str(variant or "").lower())
    if suffix is None:
        raise ValueError(f"Unknown ReShade variant: {variant}")
    wanted = str(version or "").lstrip("vV") or latest_loader(fetch=fetch)["latest"]
    url = LOADER_DOWNLOAD.format(version=wanted, variant=suffix)
    payload = fetch(url)
    try:
        with zipfile.ZipFile(_io.BytesIO(payload)) as archive:
            dll = archive.read(STORE_DLL)
    except (zipfile.BadZipFile, KeyError) as error:
        raise ValueError(
            f"{url} is not a ReShade setup carrying {STORE_DLL}: {error}") from error
    if b"ReShade" not in dll:
        raise ValueError(f"The file taken from {url} is not ReShade.")
    STORE.mkdir(parents=True, exist_ok=True)
    store_dll().write_bytes(dll)
    recorded = {
        "version": wanted,
        "variant": str(variant).lower(),
        "sha256": hashlib.sha256(dll).hexdigest(),
        "bytes": len(dll),
        "download": url,
        "source": LOADER_SOURCE,
        "licence": LOADER_LICENCE,
        "installedAt": datetime.now(timezone.utc).isoformat(),
    }
    (STORE / LOADER_STATE).write_text(
        json.dumps(recorded, indent=2) + NEWLINE, encoding="utf-8")
    return {**store_state(), "installed": True}


NEWLINE = chr(10)
REPOSITORIES_NAME = "repositories.json"


def repositories_path() -> Path:
    return STORE / REPOSITORIES_NAME


def _clean_repository(entry: dict) -> dict | None:
    name = str(entry.get("name", "") or "").strip()
    if not name:
        return None
    return {
        "name": name,
        "version": str(entry.get("version", "") or "").strip(),
        "url": str(entry.get("url", "") or "").strip(),
        # Where this machine keeps the repository's .fx files. Naming a
        # repository is what a mod does; having the shaders on disk is what
        # this machine does, and without it ReShade loads with nothing to run.
        "path": str(entry.get("path", "") or "").strip(),
    }


def repositories() -> list[dict]:
    """The shader repositories this machine has, shared by every project.

    One list per machine, not per mod. A mod's manifest names a repository and
    a version; it never carries the shaders, because several of the common
    repositories forbid redistribution.
    """
    path = repositories_path()
    if not path.is_file():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(loaded, list):
        return []
    found = [_clean_repository(entry) for entry in loaded if isinstance(entry, dict)]
    return sorted((entry for entry in found if entry), key=lambda entry: entry["name"].lower())


def write_repositories(entries: list[dict]) -> list[dict]:
    """Replace the machine's repository list. Last name written wins."""
    by_name: dict[str, dict] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        clean = _clean_repository(entry)
        if clean:
            by_name[clean["name"].lower()] = clean
    ordered = sorted(by_name.values(), key=lambda entry: entry["name"].lower())
    STORE.mkdir(parents=True, exist_ok=True)
    repositories_path().write_text(
        json.dumps(ordered, indent=2) + NEWLINE, encoding="utf-8")
    return ordered


def add_repository(name: str, version: str = "", url: str = "") -> list[dict]:
    """Add or update one repository by name."""
    if not str(name or "").strip():
        raise ValueError("A repository needs a name.")
    return write_repositories(
        [*repositories(), {"name": name, "version": version, "url": url}])


def remove_repository(name: str) -> list[dict]:
    """Forget one repository. The mods that name it still name it."""
    wanted = str(name or "").strip().lower()
    return write_repositories(
        [entry for entry in repositories() if entry["name"].lower() != wanted])


def repository_status(manifest: dict) -> list[dict]:
    """Say, per repository the mod needs, whether this machine has it.

    A version the mod names and the machine does not match is reported as a
    mismatch rather than as missing, because the shaders are there but may not
    be the ones the preset was authored against.
    """
    have = {entry["name"].lower(): entry for entry in repositories()}
    status = []
    for needed in manifest.get("repositories", []):
        name = str(needed.get("name", "") or "")
        wanted = str(needed.get("version", "") or "")
        mine = have.get(name.lower())
        if mine is None:
            state = "missing"
        elif wanted and mine["version"] and wanted != mine["version"]:
            state = "version-mismatch"
        else:
            state = "present"
        status.append({"name": name, "version": wanted,
                       "installedVersion": mine["version"] if mine else "",
                       "url": mine["url"] if mine else "",
                       "state": state})
    return status


# The shader collection Lexeditor knows how to fetch.
#
# Every package here is redistributable: MIT, BSD or CC0. That rules out the
# three the community reaches for first - qUINT, Depth3D and iMMERSE carry no
# licence or forbid it outright - so an equivalent was found for each effect
# rather than naming something we have no right to fetch. The roles below are
# what a preset author actually needs; nothing is here to pad the list out.
EFFECT_ROLES = [
    ("color-grading", "Color grading", "Tune colours, contrast, exposure and black levels"),
    ("sharpening", "Sharpening", "Reduce softness"),
    ("debanding", "Debanding", "Smooth visible bands in skies and shadows"),
    ("smaa", "SMAA", "Reduce jagged edges"),
    ("bloom", "Bloom", "Add glow around bright areas"),
    ("ambient-occlusion", "Ambient occlusion", "Add contact shadows and depth"),
    ("depth-of-field", "Depth of field", "Optional focus and background blur"),
    ("film-grain", "Film grain", "Optional film texture"),
    ("vignette", "Vignette", "Optional darkening toward the edges"),
    ("before-after", "Before/after split", "Compare the preset against the raw frame"),
    ("depth-viewer", "Depth buffer viewer", "Set up ambient occlusion and depth of field"),
]

CATALOGUE = [
    {
        "name": "Standard effects",
        "url": "https://github.com/crosire/reshade-shaders/tree/slim",
        "download": "https://github.com/crosire/reshade-shaders/archive/slim.zip",
        "repository": "crosire/reshade-shaders",
        "branch": "slim",
        "licence": "MIT (per file)",
        "effects": {"debanding": "Deband.fx", "depth-viewer": "DisplayDepth.fx"},
    },
    {
        "name": "SweetFX",
        "url": "https://github.com/CeeJayDK/SweetFX",
        "download": "https://github.com/CeeJayDK/SweetFX/archive/master.zip",
        "repository": "CeeJayDK/SweetFX",
        "branch": "master",
        "licence": "MIT",
        "effects": {
            "color-grading": "Curves.fx, Levels.fx, LiftGammaGain.fx, Tonemap.fx, Vibrance.fx",
            "sharpening": "LumaSharpen.fx, CAS.fx",
            "smaa": "SMAA.fx",
            "film-grain": "FilmGrain.fx",
            "vignette": "Vignette.fx",
            "before-after": "Splitscreen.fx, Compare.fx",
        },
    },
    {
        "name": "FXShaders",
        "url": "https://github.com/luluco250/FXShaders",
        "download": "https://github.com/luluco250/FXShaders/archive/master.zip",
        "repository": "luluco250/FXShaders",
        "branch": "master",
        "licence": "MIT",
        "effects": {"bloom": "NeoBloom.fx", "depth-of-field": "FocalDOF.fx"},
    },
    {
        # The one hard role. Every well known ambient occlusion shader for
        # ReShade is unlicensed; this one is CC0, and does screen-space
        # occlusion and lighting together.
        "name": "NiceGuy Shaders",
        "url": "https://github.com/mj-ehsan/NiceGuy-Shaders",
        "download": "https://github.com/mj-ehsan/NiceGuy-Shaders/archive/main.zip",
        "repository": "mj-ehsan/NiceGuy-Shaders",
        "branch": "main",
        "licence": "CC0-1.0",
        "effects": {"ambient-occlusion": "NGLighting.fx"},
    },
    {
        # Not needed for any role: colour grading is covered above. This is the
        # deep set, for an author who wants per-channel control.
        "name": "prod80 colour effects",
        "url": "https://github.com/prod80/prod80-ReShade-Repository",
        "download": "https://github.com/prod80/prod80-ReShade-Repository/archive/master.zip",
        "repository": "prod80/prod80-ReShade-Repository",
        "branch": "master",
        "licence": "MIT",
        "optional": True,
        "effects": {"color-grading": "PD80_*.fx, an extensive set"},
    },
]

ARCHIVE_SUFFIXES = (".fx", ".fxh", ".png", ".jpg", ".jpeg", ".bmp", ".dds", ".txt", ".md")


def _slug(name: str) -> str:
    return "".join(character if character.isalnum() else "-"
                   for character in str(name).lower()).strip("-")


def shaders_root() -> Path:
    """Where installed shader repositories live. One per machine, not per mod."""
    return STORE / "shaders"


def catalogue() -> list[dict]:
    """The collection, each package saying whether this machine has it."""
    have = {entry["name"].lower(): entry for entry in repositories()}
    listed = []
    for package in CATALOGUE:
        mine = have.get(package["name"].lower())
        folder = Path(mine["path"]) if mine and mine.get("path") else None
        listed.append({
            **{key: value for key, value in package.items() if key != "effects"},
            "optional": bool(package.get("optional")),
            "effects": dict(package["effects"]),
            "installed": bool(folder and folder.is_dir()),
            "path": str(folder) if folder else "",
            "version": mine["version"] if mine else "",
        })
    return listed


def coverage() -> list[dict]:
    """Per effect the collection promises: which shader, and is it here yet.

    A role with no installed package is the reason ReShade can load and do
    nothing, so it gets its own line rather than being left to be inferred
    from the repository list.
    """
    installed = {package["name"]: package["installed"] for package in catalogue()}
    rows = []
    for role, label, purpose in EFFECT_ROLES:
        providers = [package for package in CATALOGUE
                     if role in package["effects"] and not package.get("optional")]
        extra = [package for package in CATALOGUE
                 if role in package["effects"] and package.get("optional")]
        rows.append({
            "role": role,
            "label": label,
            "purpose": purpose,
            "shaders": "; ".join(package["effects"][role] for package in providers),
            "packages": [package["name"] for package in providers],
            "alsoIn": [package["name"] for package in extra],
            "installed": any(installed.get(package["name"]) for package in providers),
        })
    return rows


def _fetch(url: str, timeout: int = 120) -> bytes:
    import urllib.request
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def install_repository(name: str, *, fetch=_fetch) -> dict:
    """Download one catalogued package and register where its shaders landed.

    Naming a repository was never enough: ReShade needs a folder to search, and
    a name with no folder is exactly the state that produces a loader with an
    empty effect list. This puts the files on disk and writes the path into the
    machine's repository list in one step.
    """
    import io as _io
    import zipfile

    wanted = str(name or "").strip().lower()
    package = next((entry for entry in CATALOGUE
                    if entry["name"].lower() == wanted), None)
    if package is None:
        raise ValueError(f"No catalogued shader package called {name!r}")
    payload = fetch(package["download"])
    target = shaders_root() / _slug(package["name"])
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(_io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            parts = Path(member.filename).parts
            if len(parts) < 2:
                continue
            # Drop the archive's own top folder and keep the rest of the tree,
            # so Shaders/ and Textures/ land where configure() looks for them.
            relative = Path(*parts[1:])
            if relative.suffix.lower() not in ARCHIVE_SUFFIXES:
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))
    write_repositories([*repositories(), {
        "name": package["name"],
        "version": package.get("branch", ""),
        "url": package["url"],
        "path": str(target),
    }])
    return {"name": package["name"], "path": str(target),
            "shaders": len(_listing(target, SHADER_SUFFIXES))}


def install_collection(*, fetch=_fetch, include_optional: bool = False) -> list[dict]:
    """Install every package a listed effect depends on."""
    done = []
    for package in CATALOGUE:
        if package.get("optional") and not include_optional:
            continue
        done.append(install_repository(package["name"], fetch=fetch))
    return done


EXPORT_NOTE_NAME = "INSTALL-RESHADE.txt"


def export_note(project_root: Path, game_root: Path | None = None) -> str:
    """The text a person installing this mod by hand needs, and nothing else.

    It names the preset file, the loader DLL the game wants, and every shader
    repository with the version the preset was authored against. It does not
    describe Lexeditor, because the reader may never have used it.
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
        "2. Install these shader repositories in ReShade's setup. They are not",
        "   included here, because their licences do not all allow it.",
    ]
    needed = manifest["repositories"]
    if needed:
        for entry in needed:
            version = f" (version {entry['version']})" if entry.get("version") else ""
            lines.append(f"   - {entry['name']}{version}")
    else:
        lines.append("   - none; this preset uses only the shaders below.")
    lines += ["", f"3. Copy {preset} into the game's reshade-presets folder and",
              "   select it in ReShade's overlay."]
    if state["shaders"]:
        lines += ["",
                  "4. Copy these shaders, which are this mod's own work, into",
                  "   ReShade's shaders folder:"]
        lines += [f"   - {name}" for name in state["shaders"]]
    lines.append("")
    return NEWLINE.join(lines)


def write_export_note(project_root: Path, game_root: Path | None = None) -> str:
    """Put the note beside the preset, where anyone unpacking the mod finds it."""
    root = _reshade_root(Path(project_root))
    root.mkdir(parents=True, exist_ok=True)
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

    The repositories this machine has, plus the shaders the mod's own author
    wrote. A repository entry with no folder contributes nothing, which is
    exactly the state that makes ReShade start with an empty effect list.
    """
    effects: list[Path] = []
    textures: list[Path] = []
    for entry in repositories():
        folder = entry.get("path") or ""
        if not folder:
            continue
        root = Path(folder)
        if not root.is_dir():
            continue
        effects.append(root)
        for name in ("Shaders", "Textures"):
            child = root / name
            if child.is_dir():
                (effects if name == "Shaders" else textures).append(child)
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
                   "No shader folder is registered for any repository."
                   if not effects else
                   "This mod names no preset that is present."),
    }


def install(game_root: Path, renderer: str) -> dict:
    """Place Lexeditor's ReShade in one game, under the loader name it needs."""
    game_root = Path(game_root)
    dll_name = RENDERER_DLLS.get(str(renderer).lower())
    if not dll_name:
        raise ValueError(f"Unknown renderer: {renderer}")
    if not game_root.is_dir():
        raise ValueError(f"No game folder at {game_root}")
    source = store_dll()
    if not source.is_file():
        raise ValueError("Lexeditor has no ReShade to install yet")
    target = game_root / dll_name
    # A game's own d3d11.dll is not ours to replace. Only an existing ReShade
    # may be overwritten, and only by another ReShade.
    if target.is_file():
        if not is_reshade(target):
            raise ValueError(
                f"{dll_name} already exists in this game and is not ReShade. "
                "Lexeditor will not overwrite it.")
    shutil.copy2(source, target)
    result = {"installed": True, "renderer": str(renderer).lower(), "path": str(target)}
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
    return {"removed": removed}


def snapshot(project_root: Path, game_root: Path | None = None) -> dict:
    """Everything the Tweaks page needs to describe this mod's ReShade state."""
    root = _reshade_root(project_root)
    manifest = read_manifest(project_root)
    presets = _listing(root, PRESET_SUFFIXES)
    presets = [name for name in presets if Path(name).name != MANIFEST_NAME]
    shaders = _listing(root / "shaders", SHADER_SUFFIXES)
    renderer = installed_renderer(game_root)
    return {
        "path": str(root),
        "hasFolder": root.is_dir(),
        "manifest": manifest,
        "presets": presets,
        "shaders": shaders,
        "installedRenderer": renderer,
        "reshadeInstalled": bool(renderer),
        "store": store_state(),
        "renderers": sorted(RENDERER_DLLS),
        "repositories": repositories(),
        "repositoryStatus": repository_status(manifest),
        "catalogue": catalogue(),
        "coverage": coverage(),
        "exportNote": EXPORT_NOTE_NAME,
        # A preset that names no file, or names one that is not there, would
        # silently do nothing at play time. Say so instead.
        "ready": bool(manifest["enabled"] and manifest["preset"]
                      and manifest["preset"] in presets and renderer),
    }
