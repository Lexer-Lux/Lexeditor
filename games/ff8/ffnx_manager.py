"""Verified installation and update management for the FFNx Steam helper."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from typing import Callable

import process_probe
from settings_manager import SettingsStore
from .ffnx_issue_51 import runtime_package


LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path(__file__).resolve().parents[2] / "out")) / "Lexeditor"
STATE_PATH = LOCAL_DATA / "helpers" / "ffnx.json"
CACHE_ROOT = LOCAL_DATA / "helpers" / "downloads"
BACKUP_ROOT = LOCAL_DATA / "helpers" / "backups" / "ffnx"
# Lexeditor installs the FFNx release it was built and tested against, not
# whatever is newest. An unattended jump to a new upstream release can change
# behaviour underneath every tweak in the plugin, so moving this pin is a
# deliberate edit, made after the new version has been tried.
PINNED_RELEASE = "1.24.3"
RELEASES_API = "https://api.github.com/repos/julianxhokaxhiu/FFNx/releases"
RELEASE_API = f"{RELEASES_API}/tags/{PINNED_RELEASE}"
LATEST_RELEASE_API = f"{RELEASES_API}/latest"
REPOSITORY = "https://github.com/julianxhokaxhiu/FFNx"
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
DIRECT_LINK_NAME = "lexeditor-direct"
RUNTIME_LINK_NAMES = {
    "direct": DIRECT_LINK_NAME,
    "textures": "lexeditor-textures",
    "sfx": "lexeditor-sfx",
    "voice": "lexeditor-voice",
    "ambient": "lexeditor-ambient",
    "override": "lexeditor-override",
    "save": "lexeditor-save",
}
Progress = Callable[[int, int, str], None]
JsonFetcher = Callable[[str], dict]
FileFetcher = Callable[[str, Path, Progress | None], None]
RunningCheck = Callable[[], bool]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def running_processes() -> list[dict]:
    """Game processes that are genuinely running.

    Windows keeps listing a terminated process while anything holds a handle to
    it. Those entries have no threads, cannot be killed, and are not the game
    running, so they must not block an install.
    """
    return process_probe.live_processes(("FF8_EN.exe", "FF8_Launcher.exe"))


def stale_processes() -> list[dict]:
    """Terminated entries Windows still lists, for explaining Task Manager."""
    return process_probe.zombie_processes(("FF8_EN.exe", "FF8_Launcher.exe"))


def _blocked_message() -> str:
    """Say exactly which processes are holding the install open."""
    processes = running_processes()
    if not processes:
        return "FFNx setup or update is waiting for Final Fantasy VIII to close."
    listed = ", ".join(f"{row['name']} (PID {row['pid']})" for row in processes)
    return f"FFNx setup is waiting for Final Fantasy VIII to close. Still running: {listed}."


def _game_running() -> bool:
    if os.name != "nt":
        return False
    if running_processes():
        return True
    return False


def _read_state(path: Path = STATE_PATH) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_file(url: str, target: Path, progress: Progress | None = None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as stream:
        total = int(response.headers.get("Content-Length") or 0)
        if total > MAX_ARCHIVE_BYTES:
            raise RuntimeError("The FFNx archive is larger than the allowed limit")
        current = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            current += len(block)
            if current > MAX_ARCHIVE_BYTES:
                raise RuntimeError("The FFNx archive is larger than the allowed limit")
            stream.write(block)
            if progress:
                progress(current, total, "Downloading FFNx…")


def _release(fetch_json: JsonFetcher) -> dict:
    payload = fetch_json(RELEASE_API)
    candidates = [
        asset for asset in payload.get("assets", [])
        if re.fullmatch(r"FFNx-Steam-v[0-9.]+\.zip", str(asset.get("name", "")))
    ]
    if len(candidates) != 1:
        raise RuntimeError("The latest FFNx release has no unique Steam archive")
    asset = candidates[0]
    digest = str(asset.get("digest", ""))
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise RuntimeError("The FFNx release does not publish a valid SHA-256 digest")
    return {
        "version": str(payload.get("tag_name", "")).strip(),
        "published": str(payload.get("published_at", "")),
        "name": asset["name"],
        "url": asset["browser_download_url"],
        "sha256": digest.split(":", 1)[1].casefold(),
        "source": REPOSITORY,
    }


def upstream_release(fetch_json: JsonFetcher = _fetch_json) -> dict:
    """Report the newest published release without installing it.

    Used by the helper-versions view so a new upstream release is something to
    look at and decide about, never something that lands on its own.
    """
    try:
        payload = fetch_json(LATEST_RELEASE_API)
    except Exception as error:
        return {"runtime": "FFNx", "pinned": PINNED_RELEASE, "error": str(error)}
    latest = str(payload.get("tag_name", "")).strip()
    return {
        "runtime": "FFNx",
        "pinned": PINNED_RELEASE,
        "latest": latest,
        "published": str(payload.get("published_at", "")),
        "behind": bool(latest) and latest.lstrip("vV") != PINNED_RELEASE.lstrip("vV"),
        "source": REPOSITORY,
    }


def _safe_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    result = []
    for info in archive.infolist():
        path = PurePosixPath(info.filename.replace("\\", "/"))
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise RuntimeError(f"The FFNx archive has an unsafe path: {info.filename}")
        if info.file_size > MAX_ARCHIVE_BYTES:
            raise RuntimeError(f"The FFNx archive entry is too large: {info.filename}")
        result.append(info)
    if not any(info.filename == "COPYING.TXT" for info in result):
        raise RuntimeError("The FFNx archive is missing its GPL license")
    if not any(info.filename == "FFNx.toml" for info in result):
        raise RuntimeError("The FFNx archive is missing FFNx.toml")
    if not any(info.filename == "AF3DN.P" for info in result):
        raise RuntimeError("The FFNx Steam driver is missing")
    return result


def _is_junction(path: Path) -> bool:
    """Recognise a directory junction on every supported Python.

    Path.is_junction only exists from 3.12. Without a fallback every managed
    link reads as a plain directory here, so an install refuses to reuse its
    own link and a rollback leaves it behind.
    """
    if hasattr(path, "is_junction"):
        return path.is_junction()
    try:
        entry = os.lstat(path)
    except (OSError, ValueError):
        return False
    return getattr(entry, "st_reparse_tag", 0) == getattr(
        stat, "IO_REPARSE_TAG_MOUNT_POINT", -1)

def _ensure_runtime_link(game_root: Path, target_root: Path, link_name: str) -> Path:
    """Give FFNx one game-relative path into the composed runtime."""
    game_root = game_root.resolve()
    target_root = target_root.resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    if link_name not in RUNTIME_LINK_NAMES.values():
        raise ValueError(f"Unknown FFNx managed link: {link_name}")
    link = game_root / link_name
    occupied = link.exists() or link.is_symlink() or (
        _is_junction(link)
    )
    if occupied:
        try:
            if link.resolve(strict=True) == target_root:
                return link
        except OSError:
            pass
        if (_is_junction(link)) or link.is_symlink():
            if link.parent.resolve() != game_root or link.name != link_name:
                raise RuntimeError("The FFNx Direct Mode link is outside the game directory")
            if link.is_dir():
                link.rmdir()
            else:
                link.unlink()
        else:
            raise RuntimeError(
                f"FFNx Direct Mode cannot use {link} because that path is not a Lexeditor link"
            )
    if os.name == "nt":
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"Could not create the FFNx Direct Mode link: {detail}")
    else:
        link.symlink_to(target_root, target_is_directory=True)
    if link.resolve(strict=True) != target_root:
        raise RuntimeError(f"The FFNx {link_name} link points to the wrong runtime folder")
    return link


def _ensure_direct_link(game_root: Path, direct_root: Path) -> Path:
    """Compatibility wrapper for the original Direct Mode link contract."""
    return _ensure_runtime_link(game_root, direct_root, DIRECT_LINK_NAME)


def _set_project_paths(config: Path, direct_root: Path) -> None:
    runtime_root = Path(direct_root).resolve().parent
    links = {
        key: _ensure_runtime_link(config.parent, runtime_root / key, name)
        for key, name in RUNTIME_LINK_NAMES.items()
    }
    text = config.read_text(encoding="utf-8", errors="strict")
    values = {
        # FFNx prefixes Direct Mode with its process directory. An absolute
        # value would become '<game>/C:/project/direct' and never resolve.
        "direct_mode_path": Path(links["direct"].name),
        "hext_patching_path": (runtime_root / "hext").resolve(),
        "mod_path": Path(links["textures"].name),
        "external_sfx_path": Path(links["sfx"].name),
        "external_voice_path": Path(links["voice"].name),
        "external_ambient_path": Path(links["ambient"].name),
        "override_path": Path(links["override"].name),
        "save_path": Path(links["save"].name),
    }
    for key, target in values.items():
        value = target.as_posix().replace('"', '\\"')
        pattern = re.compile(rf'(?m)^[ \t]*{re.escape(key)}[ \t]*=[ \t]*"[^"\r\n]*"[ \t]*$')
        replacement = f'{key} = "{value}"'
        if pattern.search(text):
            text = pattern.sub(replacement, text, count=1)
        else:
            text += f"\n{replacement}\n"
    has_sfx = any(path.is_file() for path in (runtime_root / "sfx").rglob("*"))
    sfx_pattern = re.compile(r'(?m)^[ \t]*use_external_sfx[ \t]*=[ \t]*(?:true|false)[ \t]*$')
    sfx_replacement = f"use_external_sfx = {'true' if has_sfx else 'false'}"
    if sfx_pattern.search(text):
        text = sfx_pattern.sub(sfx_replacement, text, count=1)
    else:
        text += f"\n{sfx_replacement}\n"
    temporary = config.with_suffix(config.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(config)


def _configured_direct_root(config: Path) -> Path:
    """Resolve the Direct Mode root exactly as FFNx resolves it."""
    try:
        text = config.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f"FFNx.toml could not be read: {error}") from error
    matches = re.findall(
        r'(?m)^\s*direct_mode_path\s*=\s*"([^"\r\n]+)"\s*$', text,
    )
    if len(matches) != 1:
        raise RuntimeError("FFNx.toml must contain one direct_mode_path value")
    configured = Path(matches[0])
    if configured.is_absolute():
        raise RuntimeError("FFNx direct_mode_path must be relative to the game directory")
    return (config.parent / configured).resolve(strict=True)


def _verify_project_path(config: Path, direct_root: Path) -> Path:
    """Prove that FFNx can reach this project's strict runtime file."""
    expected = Path(direct_root).resolve()
    actual = _configured_direct_root(config)
    if actual != expected:
        raise RuntimeError(f"FFNx Direct Mode uses {actual}, not {expected}")
    runtime_file = actual / "lexeditor" / "gameplay.toml"
    if runtime_file.parent.resolve() != (expected / "lexeditor").resolve():
        raise RuntimeError("The FFNx gameplay runtime path escapes the selected project")
    return runtime_file


def _restore_file(path: Path, existed: bool, content: bytes) -> None:
    """Restore an exact file snapshot without using the normal state writer."""
    if not existed:
        path.unlink(missing_ok=True)
        return
    if path.is_file():
        try:
            if path.read_bytes() == content:
                path.with_suffix(
                    path.suffix + ".lexeditor.rollback.tmp"
                ).unlink(missing_ok=True)
                return
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".lexeditor.rollback.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _is_managed_link(path: Path) -> bool:
    return path.is_symlink() or (
        _is_junction(path)
    )


RETIRED_SUFFIX = ".lexeditor-old"


def _sweep_retired(folder: Path) -> None:
    """Delete driver copies retired by an earlier install, once they unmap."""
    for stale in folder.glob("*" + RETIRED_SUFFIX + "*"):
        try:
            stale.unlink()
        except OSError:
            pass  # still mapped; the next install will get it


def record_runtime_failure(reason: str, state_path: Path = STATE_PATH) -> None:
    """Remember that a required runtime install did not complete.

    A required build that fails to install and says nothing leaves the editor
    reporting a healthy game while its features quietly do nothing. The
    failure is recorded so readiness can report the game as broken.
    """
    try:
        state = _read_state(state_path)
        state["runtimeBroken"] = True
        state["runtimeBrokenReason"] = str(reason)
        state["runtimeBrokenAt"] = _now()
        _save_state(state, state_path)
    except Exception:
        # Recording is best effort. It must never stop the caller from
        # putting the player's files back.
        pass


def clear_runtime_failure(state_path: Path = STATE_PATH) -> None:
    """Forget a recorded failure once an install completes and verifies."""
    state = _read_state(state_path)
    for key in ("runtimeBroken", "runtimeBrokenReason", "runtimeBrokenAt"):
        state.pop(key, None)
    _save_state(state, state_path)

def _replace_possibly_mapped(temporary: Path, destination: Path) -> None:
    """Put a new file where one that is still loaded as an image sits.

    Windows refuses to overwrite a file that any process still has mapped as
    a module, which is what AF3DN.P is. A terminated game whose process
    object has not been reaped keeps that mapping, so a plain replace fails
    with access denied and the game cannot be launched. Renaming a mapped
    file is allowed, so the old copy is moved aside and deleted whenever it
    finally unmaps.
    """
    try:
        temporary.replace(destination)
        return
    except OSError:
        if not destination.exists():
            raise
    _sweep_retired(destination.parent)
    retired = destination.with_name(
        destination.name + RETIRED_SUFFIX + str(os.getpid()))
    destination.rename(retired)
    try:
        temporary.replace(destination)
    except OSError:
        retired.rename(destination)
        raise
    try:
        retired.unlink()
    except OSError:
        pass  # cleared by the next install

def _remove_managed_link(path: Path) -> None:
    if not _is_managed_link(path):
        return
    if path.is_dir():
        path.rmdir()
    else:
        path.unlink()


def _snapshot_direct_link(path: Path) -> tuple[str, str]:
    """Record absence, collision, junction, or symbolic-link identity."""
    if _is_junction(path):
        return ("junction", str(path.resolve(strict=True)))
    if path.is_symlink():
        return ("symlink", os.readlink(path))
    if path.exists():
        return ("collision", "")
    return ("absent", "")


def _restore_runtime_link(game_root: Path, link_name: str,
                          snapshot: tuple[str, str]) -> None:
    """Restore the exact managed-link kind and target after a failed transaction."""
    link = Path(game_root).resolve() / link_name
    kind, target = snapshot
    if kind == "collision":
        return
    _remove_managed_link(link)
    if kind == "absent" and link.exists():
        # The snapshot proves nothing was here before this transaction, so
        # whatever the failed install left is ours to remove. Leaving a real
        # directory behind would read as a collision and block the next try.
        if link.is_dir():
            shutil.rmtree(link, ignore_errors=True)
        else:
            link.unlink(missing_ok=True)
    if kind == "junction":
        _ensure_runtime_link(Path(game_root).resolve(), Path(target), link_name)
    elif kind == "symlink":
        link.symlink_to(target, target_is_directory=True)


def _restore_direct_link(game_root: Path, snapshot: tuple[str, str]) -> None:
    _restore_runtime_link(game_root, DIRECT_LINK_NAME, snapshot)


def _snapshot_runtime_links(game_root: Path) -> dict[str, tuple[str, str]]:
    root = Path(game_root).resolve()
    return {name: _snapshot_direct_link(root / name)
            for name in RUNTIME_LINK_NAMES.values()}


def _restore_runtime_links(game_root: Path,
                           snapshots: dict[str, tuple[str, str]]) -> None:
    for name, snapshot in snapshots.items():
        _restore_runtime_link(game_root, name, snapshot)


def _install(archive_path: Path, release: dict, game_root: Path, direct_root: Path,
             state_path: Path, backup_root: Path, progress: Progress | None) -> dict:
    game_root = game_root.resolve()
    if not (game_root / "FF8_EN.exe").is_file():
        raise RuntimeError(f"FF8_EN.exe is missing from {game_root}")
    old_state = _read_state(state_path)
    managed_before = set(old_state.get("managedFiles", []))
    existing_config = (game_root / "FFNx.toml").is_file()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_root / stamp
    installed: list[str] = []
    skipped: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        entries = _safe_entries(archive)
        total = sum(not info.is_dir() for info in entries)
        current = 0
        for info in entries:
            if info.is_dir():
                continue
            relative = PurePosixPath(info.filename).as_posix()
            destination = game_root.joinpath(*PurePosixPath(relative).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if relative == "FFNx.toml" and existing_config:
                skipped.append(relative)
                current += 1
                continue
            if destination.exists() and relative not in managed_before:
                backup_file = backup.joinpath(*PurePosixPath(relative).parts)
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup_file)
            with archive.open(info) as source:
                temporary = destination.with_suffix(destination.suffix + ".lexeditor.tmp")
                with temporary.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                _replace_possibly_mapped(temporary, destination)
            installed.append(relative)
            current += 1
            if progress:
                progress(current, total, f"Installing FFNx: {relative}")
    config = game_root / "FFNx.toml"
    _set_project_paths(config, direct_root)
    state = {
        "distribution": "stock",
        "version": release["version"],
        "installedAt": _now(),
        "lastCheck": _now(),
        "lastResult": "FFNx is up to date.",
        "asset": release,
        "gameRoot": str(game_root),
        "managedFiles": sorted(set(installed) | managed_before),
        "skippedUserFiles": sorted(skipped),
        "backup": str(backup) if backup.is_dir() else "",
        "source": REPOSITORY,
        "license": str(game_root / "COPYING.TXT"),
        "directRoot": str(direct_root.resolve()),
        "hextRoot": str((direct_root.parent / "hext").resolve()),
    }
    _save_state(state, state_path)
    return state


def status(game_root: Path, state_path: Path = STATE_PATH,
           runtime_package_root: Path = runtime_package.PACKAGE_ROOT,
           *, direct_root: Path | None = None) -> dict:
    state = _read_state(state_path)
    root = game_root.resolve()
    driver = root / "AF3DN.P"
    derivative = runtime_package.status(root, runtime_package_root)
    selected_direct = direct_root
    if selected_direct is None and state.get("directRoot"):
        selected_direct = Path(state["directRoot"])
    path_ready = False
    path_message = derivative["message"]
    if derivative["available"] and selected_direct is None:
        path_message = "The selected Lexeditor project is not recorded in the FFNx helper state."
    if derivative["available"] and selected_direct is not None:
        try:
            _verify_project_path(root / "FFNx.toml", Path(selected_direct))
            path_ready = True
            path_message = derivative["message"]
        except (OSError, RuntimeError) as error:
            path_message = str(error)
    runtime_ready = bool(derivative["available"] and path_ready)
    installed = (root / "FFNx.toml").is_file() and driver.is_file() and (
        driver.stat().st_size > 1_000_000 or derivative["available"]
    )
    return {
        "id": "ffnx",
        "name": "FFNx",
        "installed": installed,
        "managed": bool(state.get("version") and Path(state.get("gameRoot", "")) == root),
        "version": state.get("version", ""),
        "lastCheck": state.get("lastCheck", ""),
        "lastResult": state.get("lastResult", "Not checked yet."),
        "source": REPOSITORY,
        "pinnedDerivative": bool(derivative["pinned"]),
        "sharedMagicInventoryRuntime": runtime_ready,
        "runtimeBroken": bool(state.get("runtimeBroken")),
        "runtimeBrokenReason": str(state.get("runtimeBrokenReason", "")),
        "sharedMagicInventoryPackageAvailable": derivative["packageAvailable"],
        "sharedMagicInventoryRuntimeMessage": path_message,
        "sharedMagicInventoryRuntimePath": (
            str(Path(selected_direct).resolve() / "lexeditor" / "gameplay.toml")
            if selected_direct is not None else ""
        ),
    }


def install_derivative(game_root: Path, *, state_path: Path = STATE_PATH,
                       backup_root: Path = BACKUP_ROOT,
                       runtime_package_root: Path = runtime_package.PACKAGE_ROOT,
                       direct_root: Path | None = None,
                       game_running: RunningCheck = _game_running) -> dict:
    """Install the derivative and its project path as one rollback unit."""
    root = Path(game_root).resolve()
    if game_running():
        raise RuntimeError("Final Fantasy VIII must be closed before installing its FFNx runtime")
    runtime_package.verify_game_installation(root)
    config = root / "FFNx.toml"
    if not config.is_file():
        raise RuntimeError("FFNx.toml is missing. Install FFNx before enabling shared Magic.")
    package = runtime_package.verify(runtime_package_root)
    source = Path(package["packagedDriver"])
    destination = root / runtime_package.DRIVER_NAME
    if direct_root is None:
        direct_root = _configured_direct_root(config)
    selected_direct = Path(direct_root).resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_root / stamp
    driver_existed = destination.is_file()
    driver_before = destination.read_bytes() if driver_existed else b""
    # FFNx loads Steamworks dynamically by this name and forces achievements
    # on for the Steam edition, so without this file the game shows a fatal
    # error dialog instead of starting. It installs and rolls back with the
    # driver as one unit.
    steam_api = root / package["steamApiName"]
    steam_api_existed = steam_api.is_file()
    steam_api_before = steam_api.read_bytes() if steam_api_existed else b""
    state_existed = state_path.is_file()
    state_before = state_path.read_bytes() if state_existed else b""
    config_before = config.read_bytes()
    runtime_link_snapshots = _snapshot_runtime_links(root)
    blocked = {str(value).lower()
               for value in _read_state(state_path).get("blockedDriverSha256", [])}
    if str(package["driverSha256"]).lower() in blocked:
        # A driver recorded here failed to load in the game. Reinstalling it
        # would overwrite whatever the player fell back to and break the game
        # again on the next launch, so the install stops instead.
        raise RuntimeError(
            "This Lexeditor FFNx build is recorded as failing to load and will "
            "not be reinstalled. The driver currently in the game folder was "
            "left untouched.")
    driver_changes = not driver_existed or _sha256(destination) != package["driverSha256"]
    if driver_changes and driver_existed:
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(destination, backup / destination.name)
    temporary = destination.with_suffix(destination.suffix + ".lexeditor.tmp")
    temporary.unlink(missing_ok=True)
    try:
        _set_project_paths(config, selected_direct)
        _verify_project_path(config, selected_direct)
        if driver_changes:
            shutil.copy2(source, temporary)
            if _sha256(temporary) != package["driverSha256"]:
                raise RuntimeError("The staged Lexeditor FFNx derivative failed hash verification")
            _replace_possibly_mapped(temporary, destination)
        # The shader set belongs to the driver version. Copying it in is
        # additive: files the build does not produce (the glut LUT images and
        # the hlsl sources) are left alone, and the originals are kept in the
        # same backup folder as the driver so a rollback restores both.
        shader_source = Path(package["packagedShaderRoot"])
        shader_target = root / package["shaderDirName"]
        if shader_source.is_dir():
            shader_target.mkdir(parents=True, exist_ok=True)
            for item in sorted(shader_source.glob("*")):
                if not item.is_file():
                    continue
                landing = shader_target / item.name
                if landing.is_file() and _sha256(landing) == _sha256(item):
                    continue
                if landing.is_file():
                    keep = backup / "shaders"
                    keep.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(landing, keep / landing.name)
                shutil.copy2(item, landing)
        if not steam_api_existed or _sha256(steam_api) != package["steamApiSha256"]:
            if steam_api_existed:
                backup.mkdir(parents=True, exist_ok=True)
                shutil.copy2(steam_api, backup / steam_api.name)
            staged = steam_api.with_suffix(steam_api.suffix + ".lexeditor.tmp")
            staged.unlink(missing_ok=True)
            shutil.copy2(package["packagedSteamApi"], staged)
            if _sha256(staged) != package["steamApiSha256"]:
                staged.unlink(missing_ok=True)
                raise RuntimeError("The staged Steamworks library failed hash verification")
            _replace_possibly_mapped(staged, steam_api)
        # FFNx forces Steam achievements on for the Steam edition and then
        # calls SteamAPI_RestartAppIfNecessary, exiting the game when it
        # returns true. It only auto-writes steam_appid.txt for NON-Steam
        # editions, so on a Steam copy that call can decide the game was not
        # launched properly and close it the instant it opens. The file makes
        # the check pass regardless of how the game was started.
        appid = root / "steam_appid.txt"
        if not appid.is_file():
            appid.write_text("39150", encoding="ascii")
        old_state = _read_state(state_path)
        state = {
            **old_state,
            "distribution": runtime_package.DISTRIBUTION,
            "version": f"lexeditor-{package['sourceCommit'][:12]}",
            "installedAt": _now(),
            "lastCheck": _now(),
            "lastResult": "The verified Lexeditor FFNx derivative is installed.",
            "gameRoot": str(root),
            "directRoot": str(selected_direct),
            "hextRoot": str((selected_direct.parent / "hext").resolve()),
            "sourceCommit": package["sourceCommit"],
            "driverSha256": package["driverSha256"],
            "runtimeManifest": package["manifest"],
            "runtimeManifestSha256": package["manifestSha256"],
            "runtimeIdentity": package["identity"],
            "runtimeHookCount": package["hookCount"],
            "runtimeLicenseSha256": package["licenseSha256"],
            "runtimeSourcePatchSha256": package["sourcePatchSha256"],
            "runtimeBuildReportSha256": package["buildReportSha256"],
            "steamApiSha256": package["steamApiSha256"],
            "backup": str(backup) if backup.is_dir() else "",
        }
        _save_state(state, state_path)
        verified = status(
            root, state_path, runtime_package_root, direct_root=selected_direct,
        )
        if not verified["sharedMagicInventoryRuntime"]:
            raise RuntimeError("The installed Lexeditor FFNx derivative did not verify")
        clear_runtime_failure(state_path)
        return verified
    except Exception as error:
        temporary.unlink(missing_ok=True)
        _restore_file(destination, driver_existed, driver_before)
        _restore_file(steam_api, steam_api_existed, steam_api_before)
        _restore_file(state_path, state_existed, state_before)
        _restore_file(config, True, config_before)
        _restore_runtime_links(root, runtime_link_snapshots)
        # Only once everything is back: a required runtime that fails to
        # install must not leave the editor reporting a healthy game.
        record_runtime_failure(str(error), state_path)
        raise


def ensure_ffnx(game_root: Path, direct_root: Path, progress: Progress | None = None,
                *, settings: SettingsStore | None = None, state_path: Path = STATE_PATH,
                cache_root: Path = CACHE_ROOT, backup_root: Path = BACKUP_ROOT,
                fetch_json: JsonFetcher = _fetch_json,
                fetch_file: FileFetcher = _fetch_file,
                game_running: RunningCheck = _game_running,
                runtime_package_root: Path = runtime_package.PACKAGE_ROOT) -> dict:
    current = status(game_root, state_path, runtime_package_root)
    old_state = _read_state(state_path)
    # Nothing to install means nothing to block. Asking the player to close a
    # game before doing no work at all is how a stale process turns into an
    # unexplained wall, so the running check only guards real file changes.
    installed_version = str(current.get("version") or old_state.get("version") or "")
    already_current = bool(
        current.get("installed")
        and installed_version.lstrip("vV") == PINNED_RELEASE.lstrip("vV")
    )
    if already_current:
        _save_state({**old_state, "lastCheck": _now(), "lastResult": ""}, state_path)
        return status(game_root, state_path, runtime_package_root)
    if game_running():
        state = {
            **old_state,
            "lastResult": _blocked_message(),
        }
        _save_state(state, state_path)
        return status(game_root, state_path, runtime_package_root)
    recorded_derivative = bool(
        old_state.get("distribution") == runtime_package.DISTRIBUTION
        and Path(old_state.get("gameRoot", "")) == Path(game_root).resolve()
    )
    if recorded_derivative and not current["pinnedDerivative"]:
        return {
            **current,
            "lastResult": (
                "The recorded Lexeditor FFNx derivative does not match the current "
                "reviewed package. Stock FFNx replacement is blocked; use the controlled "
                "derivative upgrade path."
            ),
        }
    if current["installed"] and current["pinnedDerivative"]:
        _set_project_paths(game_root / "FFNx.toml", direct_root)
        return {
            **status(
                game_root, state_path, runtime_package_root,
                direct_root=direct_root,
            ),
            "lastResult": "The pinned Lexeditor FFNx derivative was left unchanged.",
        }
    if current["installed"] and not current["managed"]:
        return {**current, "lastResult": "Existing user-managed FFNx installation was left unchanged."}
    if current["installed"]:
        _set_project_paths(game_root / "FFNx.toml", direct_root)
        old_state = {
            **old_state,
            "directRoot": str(direct_root.resolve()),
            "hextRoot": str((direct_root.parent / "hext").resolve()),
        }
        _save_state(old_state, state_path)
    store = settings or SettingsStore()
    if current["installed"] and not store.update_due(old_state.get("lastCheck", "")):
        return current
    checked = _now()
    try:
        release = _release(fetch_json)
        if current["installed"] and release["version"] == current["version"]:
            state = {**old_state, "lastCheck": checked, "lastResult": "FFNx is up to date."}
            _save_state(state, state_path)
            return status(game_root, state_path, runtime_package_root)
        cache_root.mkdir(parents=True, exist_ok=True)
        archive_path = cache_root / release["name"]
        if not archive_path.is_file() or _sha256(archive_path) != release["sha256"]:
            temporary = archive_path.with_suffix(archive_path.suffix + ".tmp")
            temporary.unlink(missing_ok=True)
            fetch_file(release["url"], temporary, progress)
            if _sha256(temporary) != release["sha256"]:
                temporary.unlink(missing_ok=True)
                raise RuntimeError("The FFNx download does not match GitHub's SHA-256 digest")
            temporary.replace(archive_path)
        _install(
            archive_path, release, game_root, direct_root, state_path, backup_root, progress,
        )
        return status(game_root, state_path, runtime_package_root)
    except Exception as error:
        prefix = "Update check failed" if current["installed"] else "Setup failed"
        state = {**old_state, "lastCheck": checked, "lastResult": f"{prefix}: {error}"}
        _save_state(state, state_path)
        return status(game_root, state_path, runtime_package_root)
