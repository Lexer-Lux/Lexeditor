"""Lexer's Mod for a game: a GitHub repository whose modules are mods.

The repository a game uses is declared in its plugin.json (`lexmod`), never by
anything downloaded.

Repository contract
- README.md has a `## Features` section: a bullet list whose last bullet is
  FINAL_FEATURE. The first-run screen shows that list.
- Every top-level folder holding a mod.json is one module (core/mod_metadata).
  Its mod.json `enabled` is the module's default state and its settings.json,
  when it has one, holds the default settings.

Installed modules keep a `.lexmod.json` marker naming the repository, the
version they came from and the files it shipped. Updating replaces those
files with the latest version's, keeps the reader's settings.json and on/off
state, and never touches a mod the repository did not install.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile

from core import mod_metadata, script_mods
from core.mod_library import relative_path

FEATURES_HEADING = "Features"
FINAL_FEATURE = "Fully customizable -- pick and choose which modules you want!"
MARKER = ".lexmod.json"
# The reader's choices survive every update.
KEPT_ON_UPDATE = frozenset({script_mods.VALUES_FILE})
MAX_DOWNLOAD = 2 * 1024 ** 3
TOKEN_ENV = "LEXEDITOR_GITHUB_TOKEN"


class LexmodError(ValueError):
    """The Lexmod could not be read, downloaded or installed."""


class Cancelled(LexmodError):
    """The reader cancelled the download before anything was installed."""


# --- README contract -------------------------------------------------------

def features(readme: str) -> list[str]:
    """The bullets of the README's Features section, in order."""
    lines = readme.splitlines()
    heading = re.compile(rf"^#{{1,6}}\s+{re.escape(FEATURES_HEADING)}\s*#*\s*$", re.I)
    start = next((index for index, line in enumerate(lines) if heading.match(line.strip())), None)
    if start is None:
        return []
    bullets: list[str] = []
    for line in lines[start + 1:]:
        stripped = line.strip()
        if re.match(r"^#{1,6}\s", stripped):
            break
        match = re.match(r"^[-*+]\s+(.*\S)\s*$", stripped)
        if match and not line.startswith((" ", "\t")):
            bullets.append(match.group(1))
        elif match and bullets:
            bullets[-1] += " " + match.group(1)
        elif stripped and bullets and line.startswith((" ", "\t")):
            bullets[-1] += " " + stripped
    return bullets


def readme_problems(readme: str) -> list[str]:
    """What keeps a Lexmod README from meeting the contract."""
    bullets = features(readme)
    if not bullets:
        return [f"README.md needs a '## {FEATURES_HEADING}' section with a bullet list"]
    problems = []
    if bullets[-1] != FINAL_FEATURE:
        problems.append(f"The last Features bullet must be: {FINAL_FEATURE}")
    if len(bullets) < 2:
        problems.append("Features needs at least one bullet before the closing one")
    return problems


# --- GitHub ----------------------------------------------------------------

def _request(url: str, accept: str = "application/vnd.github+json"):
    headers = {"User-Agent": "Lexeditor", "Accept": accept}
    token = os.environ.get(TOKEN_ENV)
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)


def _json(url: str):
    try:
        with _request(url) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise LexmodError("Lexer's mod for this game is not published yet") from error
        raise LexmodError(f"GitHub answered {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise LexmodError("GitHub could not be reached") from error


def latest(repository: str) -> dict:
    """The newest version: the latest stable release, or the default branch."""
    base = f"https://api.github.com/repos/{repository}"
    try:
        release = _json(f"{base}/releases/latest")
        if not release.get("draft") and not release.get("prerelease"):
            tag = str(release["tag_name"])
            return {"version": tag, "ref": tag, "zip": f"{base}/zipball/{tag}"}
    except LexmodError:
        pass
    info = _json(base)
    branch = info["default_branch"]
    commit = _json(f"{base}/commits/{branch}")["sha"]
    return {"version": commit[:12], "ref": commit, "zip": f"{base}/zipball/{commit}"}


def _raw(repository: str, ref: str, path: str) -> bytes:
    url = f"https://api.github.com/repos/{repository}/contents/{path}?ref={ref}"
    try:
        with _request(url, "application/vnd.github.raw") as response:
            return response.read(4 * 1024 * 1024)
    except urllib.error.HTTPError as error:
        # GitHub answers a private repository the same as a missing file.
        raise LexmodError(f"{path} is not published (missing, or the repository is private)") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise LexmodError("GitHub could not be reached") from error


def catalog(repository: str) -> dict:
    """The latest version's feature list and modules, without downloading it."""
    version = latest(repository)
    readme = _raw(repository, version["ref"], "README.md").decode("utf-8", "replace")
    tree = _json(f"https://api.github.com/repos/{repository}/git/trees/{version['ref']}?recursive=1")
    manifests = sorted({item["path"] for item in tree.get("tree", [])
                        if item.get("type") == "blob" and _module_path(PurePosixPath(item["path"]).parts)})
    modules = []
    for manifest in manifests:
        folder = PurePosixPath(manifest).parent.name
        try:
            relative_path(manifest)
            info = json.loads(_raw(repository, version["ref"], manifest))
        except (LexmodError, ValueError):
            continue
        if not isinstance(info, dict):
            continue
        modules.append({"folder": folder, "name": str(info.get("name") or folder),
                        "author": str(info.get("author") or ""), "description": str(info.get("description") or ""),
                        "enabled": info.get("enabled") is not False,
                        "id": str(info.get("id") or folder), "version": str(info.get("version") or version["version"])})
    if not modules:
        raise LexmodError("Lexer's mod has no published modules yet")
    return {**version, "repository": repository, "url": f"https://github.com/{repository}",
            "features": features(readme), "readmeProblems": readme_problems(readme), "modules": modules}


# --- install, update, remove -------------------------------------------------

def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def installed(library: Path, repository: str) -> dict[str, dict]:
    """Modules of this Lexmod in the game's library, by folder name."""
    result = {}
    library = Path(library)
    if not library.is_dir():
        return result
    for folder in library.iterdir():
        marker = folder / MARKER
        if not marker.is_file():
            continue
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(info, dict) and info.get("repository") == repository:
            result[folder.name] = info
    return result


def _download(url: str, progress, cancel: threading.Event | None) -> bytes:
    try:
        with _request(url, "application/vnd.github+json") as response:
            total = int(response.headers.get("Content-Length") or 0)
            buffer = io.BytesIO()
            while True:
                if cancel is not None and cancel.is_set():
                    raise Cancelled("The download was cancelled")
                block = response.read(256 * 1024)
                if not block:
                    break
                buffer.write(block)
                if buffer.tell() > MAX_DOWNLOAD:
                    raise LexmodError("Lexer's mod is larger than Lexeditor will download")
                if progress:
                    progress("download", buffer.tell(), total)
            return buffer.getvalue()
    except urllib.error.HTTPError as error:
        raise LexmodError(f"GitHub answered {error.code} to the download") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise LexmodError("GitHub could not be reached") from error


def _module_path(parts: tuple[str, ...]) -> bool:
    return (len(parts) == 2 or (len(parts) == 3 and parts[0] == "mods")) and parts[-1] == mod_metadata.FILE


def _modules_in(archive: zipfile.ZipFile) -> dict[str, dict[str, bytes]]:
    """Read module folders from the repository root or its mods directory."""
    names = [info for info in archive.infolist() if not info.is_dir()]
    if not names:
        raise LexmodError("The download is empty")
    top = PurePosixPath(names[0].filename).parts[0]
    roots = {}
    for info in names:
        parts = PurePosixPath(info.filename).parts
        if parts[0] == top and _module_path(parts[1:]):
            relative_path("/".join(parts[1:]))
            key = parts[-2]
            if key.casefold() in roots:
                raise LexmodError(f"Duplicate module folder {key}")
            roots[key.casefold()] = (key, parts[:-1])
    files = {folder: {} for folder, _ in roots.values()}
    for info in names:
        parts = PurePosixPath(info.filename).parts
        for depth in (2, 3):
            if len(parts) <= depth:
                continue
            entry = roots.get(parts[depth - 1].casefold())
            if entry is None or parts[:depth] != entry[1]:
                continue
            relative = "/".join(parts[depth:])
            relative_path(relative)
            files[entry[0]][relative] = archive.read(info)
            break
    return files


def install(repository: str, library: Path, *, modules: list[str] | None = None,
            progress=None, cancel: threading.Event | None = None, fetch=None, install_only=False) -> dict:
    """Download the latest version and install or update its modules.

    `modules` limits a fresh install to those folders (one module's Download
    button); modules already installed from this Lexmod are always updated.
    With install_only, preserve all installed folders and add only the requested modules.
    Everything is staged before anything is installed, so a cancelled or
    failed download leaves the library exactly as it was.
    """
    library = Path(library)
    version = latest(repository) if fetch is None else fetch["version"]
    data = _download(version["zip"], progress, cancel) if fetch is None else fetch["zip"]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        upstream = _modules_in(archive)
    if not upstream:
        raise LexmodError("Lexer's mod has no published modules yet")
    present = installed(library, repository)
    wanted = set(upstream) if modules is None else set(modules)
    if not install_only:
        wanted.update(present)
    unknown = (set(modules or ()) - set(upstream))
    if unknown:
        raise LexmodError("Lexer's mod has no module " + ", ".join(sorted(unknown)))
    library.mkdir(parents=True, exist_ok=True)
    plans = []
    for folder in sorted(wanted & set(upstream)):
        target = library / folder
        if target.exists() and (install_only or folder not in present):
            raise LexmodError(f"A mod named {folder} is already in the library and did not come from Lexer's mod")
        plans.append((folder, target, upstream[folder]))
    if cancel is not None and cancel.is_set():
        raise Cancelled("The download was cancelled")
    if progress:
        progress("install", 0, len(plans))
    done = []
    with tempfile.TemporaryDirectory(prefix=".lexmod-", dir=library) as temp:
        staged_root = Path(temp)
        for folder, target, files in plans:
            staged = staged_root / folder
            for relative, content in files.items():
                path = staged / Path(*PurePosixPath(relative).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            if target.exists():
                # The reader's settings and on/off state outlive the update.
                for kept in KEPT_ON_UPDATE:
                    if (target / kept).is_file():
                        shutil.copyfile(target / kept, staged / kept)
                enabled = mod_metadata._stored(target).get("enabled")
                if enabled is not None:
                    stored = json.loads((staged / mod_metadata.FILE).read_text(encoding="utf-8-sig"))
                    stored["enabled"] = enabled
                    (staged / mod_metadata.FILE).write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")
                for generated in (script_mods.MANIFEST_FILE,):
                    if (target / generated).is_file():
                        (staged / generated).unlink(missing_ok=True)
            (staged / MARKER).write_text(json.dumps({"repository": repository, "version": version["version"],
                                                     "ref": version["ref"],
                                                     "files": {k: _digest(v) for k, v in files.items()}},
                                                    indent=2) + "\n", encoding="utf-8")
        if cancel is not None and cancel.is_set():
            raise Cancelled("The download was cancelled")
        for folder, target, _files in plans:
            if not install_only and target.exists():
                retired = staged_root / f"{folder}.previous"
                target.rename(retired)
            (staged_root / folder).rename(target)
            done.append(folder)
            if progress:
                progress("install", len(done), len(plans))
    return {"version": version["version"], "installed": done}


def remove(library: Path, repository: str, folders: list[str]) -> list[str]:
    """Delete modules this Lexmod installed; anything else is left alone."""
    present = installed(library, repository)
    removed = []
    for folder in folders:
        if folder not in present:
            continue
        target = Path(library) / folder
        shutil.rmtree(target)
        removed.append(folder)
    return removed
