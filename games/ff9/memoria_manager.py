"""Pinned Memoria installation, verified payloads and recoverable writes.

Only an explicit editor action downloads or runs the publisher's patcher.
The official patcher catches some extraction errors and still returns zero;
verify its declared output files before accepting an installation.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
from typing import Callable

from .memoria_patcher import inspect_payload, installation_files
from .memoria_recovery import Recovery, atomic_json, digest, install_lock, root_key, verify_install

LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path(__file__).resolve().parents[2] / "out")) / "Lexeditor"
STATE_PATH = LOCAL_DATA / "helpers" / "memoria.json"
CACHE_ROOT = LOCAL_DATA / "helpers" / "downloads"
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
_sha256 = digest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_state(path: Path = STATE_PATH) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_state(state: dict, path: Path = STATE_PATH) -> None:
    atomic_json(Path(path), state)


def _state_for_root(root: Path, state_path: Path) -> dict:
    state = _read_state(state_path)
    entries = state.get("installations", {})
    if isinstance(entries, dict) and isinstance(entries.get(root_key(root)), dict):
        return entries[root_key(root)]
    # Migrate the previous single-install record, but never use another root.
    recorded_root = state.get("gameRoot")
    if isinstance(recorded_root, str) and root_key(Path(recorded_root)) == root_key(root):
        return state
    return {}


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise RuntimeError("The Memoria release metadata is too large")
    return json.loads(data.decode("utf-8"))


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
    """Require the exact approved tag, asset, publisher URL and SHA-256."""
    payload = fetch_json(RELEASE_API)
    if (not isinstance(payload, dict) or payload.get("tag_name") != PINNED_RELEASE
            or payload.get("draft") or payload.get("prerelease")):
        raise RuntimeError("GitHub did not return the pinned stable Memoria release")
    candidates = [asset for asset in payload.get("assets", [])
                  if isinstance(asset, dict) and asset.get("name") == ASSET_NAME]
    if len(candidates) != 1:
        raise RuntimeError(f"The pinned Memoria release has no unique {ASSET_NAME}")
    asset = candidates[0]
    expected_url = f"{REPOSITORY}/releases/download/{PINNED_RELEASE}/{ASSET_NAME}"
    value = str(asset.get("digest", ""))
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", value):
        raise RuntimeError("The Memoria release does not publish a valid SHA-256 digest")
    if asset.get("browser_download_url") != expected_url:
        raise RuntimeError("The Memoria patcher URL does not belong to the pinned release")
    size = asset.get("size")
    if size is not None and (type(size) is not int or not 0 < size <= MAX_ASSET_BYTES):
        raise RuntimeError("The Memoria patcher asset size is invalid")
    return {"version": PINNED_RELEASE, "published": str(payload.get("published_at", "")),
            "name": ASSET_NAME, "url": expected_url, "sha256": value[7:].casefold(),
            "source": REPOSITORY}


def upstream_release(fetch_json: JsonFetcher = _fetch_json) -> dict:
    try:
        payload = fetch_json(LATEST_RELEASE_API)
        latest = str(payload.get("tag_name", "")).strip()
        return {"runtime": "Memoria", "pinned": PINNED_RELEASE, "latest": latest,
                "published": str(payload.get("published_at", "")),
                "behind": bool(latest) and latest != PINNED_RELEASE, "source": REPOSITORY}
    except Exception as error:
        return {"runtime": "Memoria", "pinned": PINNED_RELEASE, "error": str(error)}


def _game_running(game_root: Path) -> bool:
    """Fail closed when the process list is unavailable, including the launcher."""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                                text=True, timeout=10, check=False,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError("Windows could not check whether Final Fantasy 9 is running")
        rows = list(csv.reader(io.StringIO(result.stdout)))
        if not rows or any(len(row) < 2 or not row[1].isdigit() for row in rows):
            raise RuntimeError("Windows returned an unreadable process list; Memoria will not modify the game")
        names = {row[0].casefold() for row in rows}
        return bool(names & {"ff9.exe", "ff9_launcher.exe", "ff9_launcher.fix", "memoria.patcher.exe"}) or any(
            name.startswith("memoria-") and name.endswith(".exe") for name in names)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("Cannot check running processes. Memoria will not modify the game.") from error


def _binary_version(path: Path) -> str:
    """Read the assembly's Windows version resource, not an arbitrary INI key."""
    if os.name != "nt" or not path.is_file():
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        library = ctypes.WinDLL("version", use_last_error=True)
        library.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        library.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        library.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        library.GetFileVersionInfoW.restype = wintypes.BOOL
        library.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
        library.VerQueryValueW.restype = wintypes.BOOL
        handle = wintypes.DWORD()
        size = library.GetFileVersionInfoSizeW(str(path), ctypes.byref(handle))
        if not size or size > 1024 * 1024:
            return ""
        buffer = ctypes.create_string_buffer(size)
        if not library.GetFileVersionInfoW(str(path), 0, size, buffer):
            return ""
        pointer, length = ctypes.c_void_p(), wintypes.UINT()
        if not library.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
            return ""
        fixed = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
        if fixed[0] != 0xFEEF04BD:
            return ""
        numbers = (fixed[2] >> 16, fixed[2] & 0xffff, fixed[3] >> 16, fixed[3] & 0xffff)
        return ".".join(map(str, numbers)) if any(numbers) else ""
    except (OSError, ValueError, AttributeError):
        return ""


def installed_version(game_root: Path) -> str:
    managed = Path(game_root) / MANAGED_RELATIVE
    return _binary_version(managed / "Memoria.Prime.dll") or _binary_version(managed / "Assembly-CSharp.dll")


def _control_root(state_path: Path) -> Path:
    return Path(state_path).parent / "memoria-transactions"


def _pending(root: Path, state_path: Path) -> Path:
    return _control_root(state_path) / (root_key(root) + ".json")


def status(game_root: Path, state_path: Path = STATE_PATH) -> dict:
    root = Path(game_root).resolve()
    config, managed = root / CONFIG_NAME, root / MANAGED_RELATIVE
    assemblies = sorted(path.name for path in managed.glob("Memoria*.dll") if path.is_file()) if managed.is_dir() else []
    installed = config.is_file() and bool(assemblies) and (managed / "Assembly-CSharp.dll").is_file()
    record = _state_for_root(root, state_path)
    version = installed_version(root) if installed else ""
    hashes = record.get("runtimeHashes", {})
    recorded = installed and isinstance(hashes, dict) and bool(hashes) and all(
        (managed / name).is_file() and digest(managed / name) == sha for name, sha in hashes.items()
        if Path(name).name == name)
    if recorded and any(Path(name).name != name for name in hashes):
        recorded = False
    if not version and recorded:
        version = str(record.get("version", ""))
    pending = _read_state(_pending(root, state_path))
    return {"runtime": "Memoria", "installed": installed, "configured": config.is_file(),
            "assemblies": assemblies, "version": version, "pinned": PINNED_RELEASE,
            "managedPath": str(managed), "configPath": str(config), "source": REPOSITORY,
            "lastInstalled": str(record.get("installed", "")) if recorded else "",
            "recoveryRequired": bool(pending), "recoveryBackup": str(pending.get("journal", "")),
            "message": ("An interrupted Memoria installation needs recovery before further changes." if pending else
                        "Memoria is installed and its configuration is present." if installed else
                        "Memoria is not installed. Lexeditor can edit this project's CSV data, but Final Fantasy 9 cannot load it until Memoria patches the game.")}


def available(fetch_json: JsonFetcher = _fetch_json) -> dict:
    try:
        return {"available": True, **release(fetch_json)}
    except Exception as error:
        return {"available": False, "error": str(error)}


def stage(*, fetch_json: JsonFetcher = _fetch_json, fetch_file: FileFetcher = _fetch_file,
          cache_root: Path = CACHE_ROOT, progress: Progress | None = None) -> tuple[Path, dict]:
    published = release(fetch_json)
    cache = Path(cache_root)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"Memoria-{PINNED_RELEASE}.exe"
    if target.is_file() and target.stat().st_size <= MAX_ASSET_BYTES and digest(target) == published["sha256"]:
        return target, published
    fd, name = tempfile.mkstemp(prefix=target.stem + "-", suffix=".part", dir=cache)
    os.close(fd)
    temporary = Path(name)
    try:
        fetch_file(published["url"], temporary, progress)
        if temporary.stat().st_size > MAX_ASSET_BYTES or digest(temporary) != published["sha256"]:
            raise RuntimeError("The downloaded Memoria patcher does not match its published SHA-256 digest")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target, published


def _require_closed(root: Path) -> None:
    if _game_running(root):
        raise RuntimeError("Close Final Fantasy 9, its launcher and any patcher before modifying Memoria")


def install(game_root: Path, *, fetch_json: JsonFetcher = _fetch_json,
            fetch_file: FileFetcher = _fetch_file, cache_root: Path = CACHE_ROOT,
            state_path: Path = STATE_PATH, progress: Progress | None = None,
            runner: Callable[[list[str], Path], int] | None = None) -> dict:
    root = Path(game_root).resolve()
    if not (root / "x64" / "FF9.exe").is_file():
        raise RuntimeError(f"Final Fantasy 9 was not found at {root / 'x64' / 'FF9.exe'}")
    if os.name != "nt" and runner is None:
        raise RuntimeError("The official Memoria patcher must run on Windows")
    with install_lock(root, _control_root(state_path)):
        _require_closed(root)
        pointer = _pending(root, state_path)
        if pointer.exists():
            raise RuntimeError("Recover the interrupted Memoria installation before installing again")
        patcher, published = stage(fetch_json=fetch_json, fetch_file=fetch_file, cache_root=cache_root, progress=progress)
        files = installation_files(inspect_payload(patcher), root)
        _require_closed(root)  # The player may have started FF9 during download.
        recovery = Recovery.prepare(root, files, _control_root(state_path) / "backups")
        atomic_json(pointer, {"journal": str(recovery.journal), "root": str(root)})
        try:
            _require_closed(root)  # Also recheck after the recovery copy.
            if digest(patcher) != published["sha256"]:
                raise RuntimeError("The staged Memoria patcher changed before execution")
            if progress:
                progress(1, 1, "Running the verified Memoria patcher…")
            recovery.phase("patching")
            run = runner or (lambda argv, cwd: subprocess.run(
                argv, cwd=str(cwd), stdin=subprocess.DEVNULL, timeout=900, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode)
            code = run([str(patcher), str(root)], root)
            if code != 0:
                raise RuntimeError(f"The Memoria patcher exited with code {code}")
            _require_closed(root)
            verify_install(root, files)
            recovery.preserve_config()
            if not status(root, state_path)["installed"]:
                raise RuntimeError("The Memoria patcher did not produce a usable x64 runtime")
            managed = root / MANAGED_RELATIVE
            runtime_hashes = {name: digest(managed / name) for name in
                              ["Assembly-CSharp.dll", *status(root, state_path)["assemblies"]]}
            with install_lock(Path(state_path), _control_root(state_path) / "state-locks"):
                state = _read_state(state_path)
                entries = state.get("installations", {})
                if not isinstance(entries, dict):
                    entries = {}
                entries[root_key(root)] = {"version": published["version"], "sha256": published["sha256"],
                    "source": REPOSITORY, "installed": _now(), "gameRoot": str(root),
                    "runtimeHashes": runtime_hashes, "backup": str(recovery.journal)}
                _save_state({"installations": entries}, state_path)
            recovery.phase("committed")
            pointer.unlink()
        except Exception as error:
            # Never restore assemblies while the player or a timed-out child
            # still has them open. Keep the journal for an explicit recovery.
            try:
                _require_closed(root)
                recovery.rollback()
                pointer.unlink(missing_ok=True)
            except Exception as recovery_error:
                raise RuntimeError(f"Memoria installation failed: {error}. Recovery is required: {recovery_error}. Backup: {recovery.journal}") from error
            raise RuntimeError(f"Memoria installation failed; the previous game files were restored. {error}") from error
        return status(root, state_path)


def recover(game_root: Path, state_path: Path = STATE_PATH) -> dict:
    root = Path(game_root).resolve()
    _require_closed(root)
    with install_lock(root, _control_root(state_path), recover_stale=True):
        pointer = _pending(root, state_path)
        pending = _read_state(pointer)
        if not pending or pending.get("root") != str(root):
            raise RuntimeError("There is no interrupted Memoria operation for this game folder")
        journal = Path(pending["journal"]).resolve()
        expected = (_control_root(state_path) / "backups").resolve()
        if expected not in journal.parents:
            raise RuntimeError("The Memoria recovery journal is outside its backup folder")
        _require_closed(root)
        Recovery(root, journal).rollback()
        pointer.unlink()
    return status(root, state_path)


@contextmanager
def configuration_write(game_root: Path, state_path: Path | None = None):
    """Serialize configuration and launcher actions against installation."""
    root = Path(game_root).resolve()
    state_path = Path(state_path or STATE_PATH)
    with install_lock(root, _control_root(state_path)):
        _require_closed(root)
        if _pending(root, state_path).exists():
            raise RuntimeError("Recover Memoria before changing its settings")
        yield


def open_settings(game_root: Path, *, runner=None) -> dict:
    """Settings-only action. Never used by the normal Play control."""
    root = Path(game_root).resolve()
    with configuration_write(root):
        if not status(root)["installed"]:
            raise RuntimeError("Install Memoria before opening its settings launcher")
        target = root / "FF9_Launcher.exe"
        if not target.is_file():
            raise FileNotFoundError("The Memoria settings launcher is missing")
        if os.name != "nt" and runner is None:
            raise RuntimeError("The Memoria settings launcher requires Windows")
        (runner or (lambda argv, cwd: subprocess.Popen(argv, cwd=str(cwd))))([str(target)], root)
    return {"opened": True, "path": str(target)}
