"""Verified installation and update management for the Memoria FF9 helper.

Memoria publishes one asset per release, `Memoria.Patcher.exe`, together with a
SHA-256 digest. Unlike FFNx, which Lexeditor unpacks itself, Memoria ships a
patcher that rewrites the game's managed assemblies, so this module verifies and
stages the download and then runs the publisher's own patcher. Nothing is
downloaded or run without an explicit request from the editor.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request
from typing import Callable


LOCAL_DATA = Path(os.environ.get(
    "LOCALAPPDATA", Path(__file__).resolve().parents[2] / "out")) / "Lexeditor"
STATE_PATH = LOCAL_DATA / "helpers" / "memoria.json"
CACHE_ROOT = LOCAL_DATA / "helpers" / "downloads"
# Pinned, for the same reason as FFNx: Lexeditor installs the Memoria release
# it was built against. Moving this is a deliberate edit after testing.
PINNED_RELEASE = "v2025.07.04"
RELEASES_API = "https://api.github.com/repos/Albeoris/Memoria/releases"
RELEASE_API = f"{RELEASES_API}/tags/{PINNED_RELEASE}"
LATEST_RELEASE_API = f"{RELEASES_API}/latest"
REPOSITORY = "https://github.com/Albeoris/Memoria"
ASSET_NAME = "Memoria.Patcher.exe"
MAX_ASSET_BYTES = 120 * 1024 * 1024
MANAGED_RELATIVE = Path("x64") / "FF9_Data" / "Managed"
CONFIG_NAME = "Memoria.ini"

Progress = Callable[[int, int, str], None]
JsonFetcher = Callable[[str], dict]
FileFetcher = Callable[[str, Path, "Progress | None"], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_state(path: Path = STATE_PATH) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(state: dict, path: Path = STATE_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_file(url: str, target: Path, progress: Progress | None = None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as stream:
        total = int(response.headers.get("Content-Length") or 0)
        if total > MAX_ASSET_BYTES:
            raise RuntimeError("The Memoria download is larger than the allowed limit")
        current = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            current += len(block)
            if current > MAX_ASSET_BYTES:
                raise RuntimeError("The Memoria download is larger than the allowed limit")
            stream.write(block)
            if progress:
                progress(current, total, "Downloading Memoria…")


def release(fetch_json: JsonFetcher = _fetch_json) -> dict:
    """Describe the published release, refusing anything unverifiable."""
    payload = fetch_json(RELEASE_API)
    candidates = [
        asset for asset in payload.get("assets", [])
        if str(asset.get("name", "")) == ASSET_NAME
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"The latest Memoria release has no unique {ASSET_NAME}")
    asset = candidates[0]
    digest = str(asset.get("digest", ""))
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise RuntimeError("The Memoria release does not publish a valid SHA-256 digest")
    return {
        "version": str(payload.get("tag_name", "")).strip(),
        "published": str(payload.get("published_at", "")),
        "name": asset["name"],
        "url": asset["browser_download_url"],
        "sha256": digest.split(":", 1)[1].casefold(),
        "source": REPOSITORY,
    }


def upstream_release(fetch_json: JsonFetcher = _fetch_json) -> dict:
    """Report the newest published release without installing it."""
    try:
        payload = fetch_json(LATEST_RELEASE_API)
    except Exception as error:
        return {"runtime": "Memoria", "pinned": PINNED_RELEASE, "error": str(error)}
    latest = str(payload.get("tag_name", "")).strip()
    return {
        "runtime": "Memoria",
        "pinned": PINNED_RELEASE,
        "latest": latest,
        "published": str(payload.get("published_at", "")),
        "behind": bool(latest) and latest != PINNED_RELEASE,
        "source": REPOSITORY,
    }


def _game_running(game_root: Path) -> bool:
    """The patcher rewrites managed assemblies, so the game has to be closed."""
    if os.name != "nt":
        return False
    try:
        listing = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq FF9.exe", "/NH"],
            capture_output=True, text=True, timeout=10, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "FF9.exe" in listing


def installed_version(game_root: Path) -> str:
    """Read the version Memoria recorded in its own configuration."""
    config = Path(game_root) / CONFIG_NAME
    try:
        text = config.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    match = re.search(r"(?im)^\s*Version\s*=\s*\"?([\w.\-]+)", text)
    return match.group(1) if match else ""


def status(game_root: Path, state_path: Path = STATE_PATH) -> dict:
    """Report what is installed without contacting the network."""
    root = Path(game_root)
    config = root / CONFIG_NAME
    managed = root / MANAGED_RELATIVE
    assemblies = sorted(path.name for path in managed.glob("Memoria*.dll")) if managed.is_dir() else []
    state = _read_state(state_path)
    installed = config.is_file() and bool(assemblies)
    return {
        "runtime": "Memoria",
        "installed": installed,
        "configured": config.is_file(),
        "assemblies": assemblies,
        "version": installed_version(root) or str(state.get("version", "")),
        "managedPath": str(managed),
        "configPath": str(config),
        "source": REPOSITORY,
        "lastInstalled": str(state.get("installed", "")),
        "message": (
            "Memoria is installed and its configuration is present."
            if installed else
            "Memoria is not installed. Lexeditor can edit this project's CSV data, "
            "but Final Fantasy 9 cannot load it until Memoria patches the game."
        ),
    }


def available(fetch_json: JsonFetcher = _fetch_json) -> dict:
    """Describe the newest published release for the editor to offer."""
    try:
        return {"available": True, **release(fetch_json)}
    except Exception as error:  # network and payload problems are reportable
        return {"available": False, "error": str(error)}


def stage(*, fetch_json: JsonFetcher = _fetch_json,
          fetch_file: FileFetcher = _fetch_file,
          cache_root: Path = CACHE_ROOT,
          progress: Progress | None = None) -> tuple[Path, dict]:
    """Download the patcher and prove it matches the published digest."""
    published = release(fetch_json)
    cache = Path(cache_root)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"Memoria-{published['version']}.exe"
    if not target.is_file() or _sha256(target) != published["sha256"]:
        temporary = target.with_suffix(".part")
        fetch_file(published["url"], temporary, progress)
        digest = _sha256(temporary)
        if digest != published["sha256"]:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(
                "The downloaded Memoria patcher does not match its published SHA-256 digest")
        temporary.replace(target)
    return target, published


def install(game_root: Path, *,
            fetch_json: JsonFetcher = _fetch_json,
            fetch_file: FileFetcher = _fetch_file,
            cache_root: Path = CACHE_ROOT,
            state_path: Path = STATE_PATH,
            progress: Progress | None = None,
            runner: Callable[[list[str], Path], int] | None = None) -> dict:
    """Verify and run the publisher's patcher against a closed game folder.

    Only ever called from an explicit editor request. The digest check runs
    before anything is executed, and a running game is refused outright because
    the patcher rewrites assemblies the process holds open.
    """
    root = Path(game_root).resolve()
    executable = root / "x64" / "FF9.exe"
    if not executable.is_file():
        raise RuntimeError(f"Final Fantasy 9 was not found at {executable}")
    if _game_running(root):
        raise RuntimeError("Close Final Fantasy 9 before installing Memoria")
    patcher, published = stage(
        fetch_json=fetch_json, fetch_file=fetch_file,
        cache_root=cache_root, progress=progress)
    if progress:
        progress(1, 1, "Running the Memoria patcher…")
    command = [str(patcher), str(root)]
    run = runner or (lambda argv, cwd: subprocess.run(
        argv, cwd=str(cwd), timeout=900, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode)
    code = run(command, root)
    if code != 0:
        raise RuntimeError(f"The Memoria patcher exited with code {code}")
    result = status(root, state_path)
    if not result["installed"]:
        raise RuntimeError(
            "The Memoria patcher finished but the game folder does not show an install")
    _save_state({
        "version": published["version"],
        "sha256": published["sha256"],
        "source": published["source"],
        "installed": _now(),
        "gameRoot": str(root),
    }, state_path)
    return status(root, state_path)
