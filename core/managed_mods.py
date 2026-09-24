"""Trusted release policy and replacement for distributed Lexer mods.

Policy comes from a plugin descriptor, never from an imported mod.json.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request
import urllib.error

from core.mod_library import ModLibrary, digest, file_tree, relative_path


@dataclass(frozen=True)
class ManagedModSpec:
    repository: str
    asset_name: str
    folder_name: str = "Lexer's Mod"

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise ValueError("Invalid managed mod repository")
        if len(relative_path(self.folder_name).parts) != 1 or not self.asset_name.endswith(".zip"):
            raise ValueError("Managed mods require a folder name and a ZIP release asset")


def release_request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        "User-Agent": "Lexeditor", "Accept": "application/vnd.github+json"}), timeout=60)


def check_release(spec: ManagedModSpec) -> dict:
    try:
        with release_request(f"https://api.github.com/repos/{spec.repository}/releases/latest") as response:
            release = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ValueError("No stable managed mod release is available from the configured repository yet.") from error
        raise
    matches = [asset for asset in release.get("assets", []) if asset["name"] == spec.asset_name]
    if release.get("draft") or release.get("prerelease") or len(matches) != 1:
        raise ValueError("The latest stable release does not contain the configured mod ZIP")
    asset = matches[0]
    expected_prefix = f"https://github.com/{spec.repository}/releases/download/"
    if not asset["browser_download_url"].startswith(expected_prefix):
        raise ValueError("The release asset is outside the configured repository")
    return {"tag": str(release["tag_name"]), "asset": asset}


def refresh_active_mod(library: ModLibrary, plugin_id: str, adapter,
                       spec: ManagedModSpec, game_root: Path) -> bool:
    """Retry deployment on each open, including after a previous failed copy."""
    ids = adapter.active_mod_ids(game_root)
    if spec.folder_name not in ids:
        return False
    root = library.root / relative_path(plugin_id)
    paths = []
    for name in ids:
        relative = relative_path(name)
        if len(relative.parts) != 1:
            raise ValueError("An active mod has an invalid library folder name")
        path = root / relative
        if path.resolve().parent != root.resolve() or not path.is_dir():
            raise ValueError(f"The active mod is missing from the library: {name}")
        paths.append(path)
    adapter.activate(paths, game_root)
    return True


def recover_update(target: Path, state_path: Path) -> None:
    pending = state_path.with_suffix(".tmp")
    if not pending.exists():
        return
    next_state = json.loads(pending.read_text(encoding="utf-8"))
    previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    backup = target.parent / ("." + target.name + "-previous")
    def matches(folder, expected):
        return folder.is_dir() and {p.as_posix(): digest(folder / p) for p in file_tree(folder)} == expected
    if matches(target, next_state.get("files")):
        pending.replace(state_path)
    elif matches(target, previous.get("files")):
        pending.unlink()
    elif not target.exists() and matches(backup, previous.get("files")):
        backup.rename(target)
        pending.unlink()
    elif not target.exists() and not backup.exists() and not previous:
        pending.unlink()  # First installation did not replace any user files.
    else:
        raise ValueError("Managed update recovery found changed files. All copies were kept.")


def update_mod(library: ModLibrary, plugin_id: str, adapter, spec: ManagedModSpec,
               state_path: Path, *, author: bool) -> dict:
    """Authors never enter the updater. Failed copies preserve the installed mod."""
    if author:
        return {"updated": False, "message": "Author project: automatic mod replacement is disabled."}
    target = library.root / relative_path(plugin_id) / spec.folder_name
    recover_update(target, state_path)
    release = check_release(spec)
    previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if target.exists():
        actual = {path.as_posix(): digest(target / path) for path in file_tree(target)}
        if actual != previous.get("files"):
            raise ValueError("The managed mod has local changes. Make an editable copy before updating.")
        if previous.get("assetId") == release["asset"]["id"]:
            return {"updated": False, "version": previous.get("version", "")}
    size = int(release["asset"]["size"])
    if size <= 0 or size > 32 * 1024**3:
        raise ValueError("Release package size is outside the supported range")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".managed-update-", dir=target.parent) as temp:
        temporary = Path(temp)
        archive = temporary / "release.zip"
        if size * 2 > shutil.disk_usage(temporary).free:
            raise OSError("There is not enough space to update the mod")
        sha = hashlib.sha256()
        received = 0
        with release_request(release["asset"]["browser_download_url"]) as response, archive.open("xb") as out:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                received += len(block)
                if received > size:
                    raise ValueError("The release exceeds its declared size")
                sha.update(block)
                out.write(block)
        expected = release["asset"].get("digest")
        if received != size or (expected and expected != "sha256:" + sha.hexdigest()):
            raise ValueError("Release package verification failed")
        staged = ModLibrary(temporary / "stage").import_mod(plugin_id, archive, adapter, spec.folder_name)
        info_path = staged / "mod.json"
        info = json.loads(info_path.read_text(encoding="utf-8"))
        info["version"] = release["tag"]
        info_path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        state = {"repository": spec.repository, "assetId": release["asset"]["id"],
                 "recoveryFiles": previous.get("files", {}),
                 "version": release["tag"], "files": {p.as_posix(): digest(staged / p) for p in file_tree(staged)}}
        backup = target.parent / ("." + spec.folder_name + "-previous")
        if backup.exists():
            recovery = {p.as_posix(): digest(backup / p) for p in file_tree(backup)}
            if recovery != previous.get("recoveryFiles"):
                raise ValueError("The previous mod copy changed. Preserve it before updating again.")
            if backup.resolve().parent != target.parent.resolve() or not backup.name.endswith("-previous"):
                raise ValueError("Unexpected recovery path")
            shutil.rmtree(backup)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        pending = state_path.with_suffix(".tmp")
        pending.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        try:
            if target.exists():
                target.rename(backup)
            staged.rename(target)
            pending.replace(state_path)
        except Exception:
            if target.exists() and not staged.exists():
                target.rename(temporary / "failed")
            if backup.exists() and not target.exists():
                backup.rename(target)
            if pending.exists():
                pending.unlink()
            raise
        # The previous version stays available; it is never silently discarded.
        return {"updated": True, "version": release["tag"], "path": str(target),
                "recovery": str(backup) if backup.exists() else ""}
