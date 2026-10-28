"""Reversible native replacement of the installed DS1 files a mod changes.

Loose files: the item parameter archive, the English item text archive
(msg/ENGLISH/item.msgbnd.dcx) that holds every item's in-game name, and
any map file (map/MapStudio/*.msb) a mod carries. Each is guarded the
same way and on its own, with its own backup and marker next to it;
what follows is written about the parameter archive, and holds for all.

Dark Souls Remastered ships param/GameParam/GameParam.parambnd.dcx as a plain
loose file next to the executable, not packed inside a BHD5/dvdbnd archive
(confirmed by inspecting a real installation: param/, map/, chr/, sound/ etc.
are ordinary folders, and this is why UXM-style unpacking is documented as
unnecessary for this title). The game therefore reads this exact file from
disk with no mod loader involved, which is also how real DS1R param mods are
distributed: back up GameParam.parambnd.dcx, then overwrite it. This module
automates that pattern with an ownership marker, a single durable backup of
the pristine original, and hash checks before every write.

Every mutation records its own destination hash in the marker as a durable
"pending" intent before touching the live file, and only clears it once the
live file is confirmed to hold that exact hash. A later call recognizes
exactly three states for the live file: it matches the preserved original,
it matches the marker's last confirmed install, or it matches the marker's
own recorded pending hash (meaning a prior call was interrupted after the
write but before it recorded success, so this call finishes recording it).
Anything else -- including the live file going missing -- is refused rather
than guessed at, whether or not the marker says "enabled".
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from core.plugin_files import atomic_write
from . import assets
from .assets import MAX_ASSET_BYTES as MAX_ASSET
from .formats import FormatError, ItemDocument, MAX_ARCHIVE, inflate, members
from .msb import MAP_DIR, MsbDocument
from .store import MARKER, RELATIVE
from .tae import CHR_DIR, TaeDocument
from . import texts

# Each managed file, and the reader that proves a copy of it is sound.
FILES = ((RELATIVE, ItemDocument), (texts.RELATIVE, texts.TextDocument), (texts.MENU_RELATIVE, texts.MenuDocument))

MOD_ID = "lexeditor-ds1"
NOTE = (
    "Dark Souls Remastered reads param/GameParam/GameParam.parambnd.dcx, its map "
    "files, its character files and any other asset as loose files from disk; no "
    "mod loader is installed or required. Apply preserves one original copy "
    "before replacing installed files, and Disable restores those exact bytes."
)


def _disk_maps(*roots: Path | None) -> list[Path]:
    """Every map/MapStudio/*.msb under the given roots, canonically named."""
    found: dict[Path, None] = {}
    for root in roots:
        if root is None:
            continue
        maps = Path(root) / MAP_DIR
        if not maps.is_dir():
            continue
        for path in sorted(maps.glob("*.msb")):
            found.setdefault(MAP_DIR / path.name.casefold())
    return sorted(found)


def _disk_chars(*roots: Path | None) -> list[Path]:
    """Every supported character archive/script, canonically named."""
    found: dict[Path, None] = {}
    for root in roots:
        if root is None:
            continue
        chars = Path(root) / CHR_DIR
        if not chars.is_dir():
            continue
        for path in sorted(chars.glob("*.dcx")):
            relative = CHR_DIR / path.name.casefold()
            if assets.is_character_file(relative):
                found.setdefault(relative)
    return sorted(found)


def _check_anibnd(payload: bytes) -> None:
    """Prove a character binder is sound: openable with readable animations."""
    plain = inflate(payload)
    owned = members(plain)
    for name, entry in owned.items():
        if name.endswith(".tae"):
            TaeDocument(bytes(plain[entry.offset:entry.offset + entry.size]), name)


def _check_esd(payload: bytes) -> None:
    """A loose state machine must parse before any installed file changes."""
    from . import esd
    esd.parse(inflate(payload))


def _disk_assets(game_root: Path | None = None, project_root: Path | None = None) -> list[Path]:
    """Asset overrides the project carries, plus installed files Lexeditor marked.

    The game side contributes only marked files, so status checks never hash
    the whole installed game.
    """
    found: dict[Path, None] = {}
    if project_root is not None and Path(project_root).is_dir():
        for row in assets.scan_project(Path(project_root), strict=False):
            found.setdefault(Path(row["relative"]))
    if game_root is not None:
        root = Path(game_root)
        for top in assets.ASSET_ROOTS:
            folder = root / top
            if not folder.is_dir():
                continue
            for path in sorted(folder.rglob("*")):
                if path.is_dir() or path.name.startswith(".lexeditor-") or path.name.endswith(".lexeditor-original"):
                    continue
                relative = path.relative_to(root)
                if assets.is_owned(relative):
                    continue
                if _marker_path(root, relative).is_file():
                    found.setdefault(relative)
    return sorted(found)


def _check_asset_like(game_root: Path, relative: Path, payload: bytes) -> None:
    """An override of a binder must itself open as a binder."""
    live = Path(game_root) / relative
    if not live.is_file():
        raise FileNotFoundError(f"The installed game has no {relative.as_posix()}; cannot safely preserve its original data.")
    try:
        members(inflate(live.read_bytes()))
    except FormatError:
        return
    try:
        members(inflate(bytes(payload)))
    except FormatError as error:
        raise ValueError(f"{relative.name} does not open as the binder it replaces") from error


def _backup_path(game_root: Path, relative: Path = RELATIVE) -> Path:
    return game_root / relative.parent / (relative.name + ".lexeditor-original")


def _marker_path(game_root: Path, relative: Path = RELATIVE) -> Path:
    # The two archives keep their original shared marker names; map files
    # share one folder, so each gets its own marker next to its backup.
    if relative in (RELATIVE, texts.RELATIVE):
        return game_root / relative.parent / ".lexeditor-ds1-deployment.json"
    return game_root / relative.parent / (".lexeditor-ds1-deployment." + relative.name + ".json")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_marker(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read the Lexeditor deployment marker: {error}") from error
    if not isinstance(value, dict) or value.get("modId") != MOD_ID or not isinstance(value.get("originalHash"), str):
        raise RuntimeError("The Lexeditor deployment marker is invalid")
    value.setdefault("pendingHash", None)
    value.setdefault("pendingKind", None)
    return value


def _write_marker(path: Path, marker: dict) -> None:
    atomic_write(path, (json.dumps(marker, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _atomic_copy(source: Path, target: Path) -> None:
    atomic_write(target, source.read_bytes())


def _is_reparse_point(path: Path) -> bool:
    # Path.is_symlink() only recognizes true symlinks; an NTFS directory
    # junction (mklink /J, no admin rights needed) sets the same
    # FILE_ATTRIBUTE_REPARSE_POINT bit but is NOT reported by is_symlink(),
    # confirmed against a real junction in this environment. Checking the raw
    # attribute catches symlinks, junctions and mount points alike.
    try:
        metadata = os.lstat(path)
        attributes = getattr(metadata, "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise RuntimeError(f"Could not check {path} for a symlink or junction: {error}") from error
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_no_reparse_points(path: Path, boundary: Path) -> None:
    """Refuse a symlink, junction or mount point anywhere between `path` and `boundary`.

    Walking via `.parent` never follows a link, so this cannot itself be
    fooled by the thing it is checking for. A relative path string like
    param/GameParam/... only names where a write is meant to land; without
    this, a reparse point on any ancestor could make the real, physical
    destination somewhere else entirely.
    """
    current, boundary = Path(path), Path(boundary)
    while True:
        if _is_reparse_point(current):
            raise RuntimeError(f"Refusing to use a symlink or junction in a protected path: {current}")
        if current == boundary or current.parent == current:
            return
        current = current.parent


def _lexical_root(path: Path) -> Path:
    """An absolute, lexically normalized path (`..`/`.`/`//` collapsed) that never
    touches the filesystem, so it cannot itself follow a symlink or junction.

    `Path.resolve()` follows every link on the way to its answer, so calling it
    on a root the caller does not control first would silently accept a root
    that is itself a reparse point, or sits beneath one -- erasing the one
    piece of evidence (the raw path) needed to catch that. `os.path.abspath`
    only joins with the cwd and normalizes the string; ordinary absolute
    Windows paths (`C:\\...`) pass through unchanged.
    """
    return Path(os.path.normpath(os.path.abspath(str(path))))


def _assert_no_reparse_ancestry(path: Path) -> Path:
    """Lexically normalize `path`, then refuse a symlink/junction/mount point at
    it or at any ancestor up to its drive root. Must run before any `.resolve()`
    on a caller-supplied root: only the raw, unresolved path can still show
    that the root itself (or something above it) was a reparse point."""
    normalized = _lexical_root(path)
    current = normalized
    while True:
        if _is_reparse_point(current):
            raise RuntimeError(f"Refusing to use a symlink or junction in a protected path: {current}")
        if current.parent == current:
            return normalized
        current = current.parent


def _assert_disjoint(game_root: Path, project_root: Path) -> None:
    if game_root == project_root or game_root in project_root.parents or project_root in game_root.parents:
        raise ValueError("The mod project must be outside the installed game.")


def vanilla_source(game_root: Path, relative: Path = RELATIVE) -> Path:
    """The true pristine original: the preserved backup once Apply owns the installed
    file, otherwise the installed file itself (still pristine, since nothing has
    taken control of it yet). Once a marker exists, the live file may hold a
    deployed mod's bytes, so an unverifiable backup must refuse rather than fall
    back to live and silently label modded data as Vanilla."""
    game_root = Path(game_root).resolve()
    backup = _backup_path(game_root, relative)
    marker = _read_marker(_marker_path(game_root, relative))
    if marker is None:
        return game_root / relative
    if backup.is_file() and _hash_file(backup) == marker["originalHash"]:
        return backup
    raise RuntimeError(
        f"The preserved original copy of {relative.as_posix()} is missing or has changed at {backup}. "
        "Vanilla cannot be shown safely because the installed file may hold a deployed mod instead. "
        "Restore the preserved copy manually, or use Apply/Restore original to re-establish a verified state."
    )


def _reconcile(marker: dict, marker_path: Path, live: Path) -> dict:
    """Validate the live file against the marker's known-good hashes, self-healing
    only an exact match on the marker's own recorded pending hash. Everything else
    that is not an exact match to a known hash is refused, including a missing file:
    recreating it silently could mask a real external deletion, so that case gets
    its own explicit error rather than a silent rewrite."""
    if not live.is_file():
        raise RuntimeError(
            f"The installed {live.name} is missing at {live}. Verify or restore the game's "
            "files before continuing; Lexeditor will not recreate a missing file automatically."
        )
    live_hash = _hash_file(live)
    pending = marker.get("pendingHash")
    if pending and live_hash == pending:
        if marker.get("pendingKind") == "apply":
            marker.update(activeHash=pending, enabled=True, pendingHash=None, pendingKind=None)
        else:
            marker.update(activeHash=None, enabled=False, pendingHash=None, pendingKind=None)
        _write_marker(marker_path, marker)
        return marker
    if live_hash in (marker["originalHash"], marker.get("activeHash")):
        if pending:
            # The interrupted write never reached the live file, so the stale
            # intent is safe to drop: live is unchanged from before it was recorded.
            marker.update(pendingHash=None, pendingKind=None)
            _write_marker(marker_path, marker)
        return marker
    raise RuntimeError(
        f"The installed {live.name} changed outside Lexeditor; restore or verify game files before continuing."
    )


def _text_status(game_root: Path, project_root: Path | None) -> dict:
    """Whether the installed item text matches what this project would apply."""
    live = game_root / texts.RELATIVE
    marker = _read_marker(_marker_path(game_root, texts.RELATIVE))
    live_hash = _hash_file(live) if live.is_file() else None
    source = (project_root / texts.RELATIVE) if project_root else None
    wanted = _hash_file(source) if source and source.is_file() else None
    applied = bool(marker and marker.get("enabled") and live_hash == marker.get("activeHash"))
    pending = (marker or {}).get("pendingHash")
    backup = _backup_path(game_root, texts.RELATIVE)
    backup_ok = True if marker is None else (backup.is_file() and _hash_file(backup) == marker["originalHash"])
    return {
        "sourceReady": wanted is not None,
        "enabled": applied,
        # In step with the project: its names are installed, or it has none
        # and the original text is.
        "current": (applied and live_hash == wanted) if wanted else not applied,
        "changedExternally": bool(marker and live_hash and live_hash != pending
                                  and live_hash not in (marker["originalHash"], marker.get("activeHash"))),
        "pendingRecovery": bool(marker and pending and live_hash == pending),
        "marked": marker is not None,
        "backupOk": backup_ok,
    }


def _maps_status(game_root: Path, project_root: Path | None) -> dict:
    """Which map files a project carries, and which are applied to the game."""
    present, applied = [], []
    stale = changed = recovery = foreign = False
    backup_ok, ever = True, False
    project_id = str(project_root.resolve()) if project_root else ""
    for relative in _disk_maps(game_root, project_root):
        live = game_root / relative
        marker = _read_marker(_marker_path(game_root, relative))
        live_hash = _hash_file(live) if live.is_file() else None
        source = (project_root / relative) if project_root else None
        if source is not None and source.is_file():
            present.append(relative.name)
        if marker is None:
            continue
        ever = True
        backup = _backup_path(game_root, relative)
        ok = backup.is_file() and _hash_file(backup) == marker["originalHash"]
        backup_ok = backup_ok and ok
        pending = marker.get("pendingHash")
        if pending and live_hash == pending:
            recovery = True
        if live_hash and live_hash != pending and live_hash not in (marker["originalHash"], marker.get("activeHash")):
            changed = True
        if marker.get("enabled") and ok and live_hash == marker.get("activeHash"):
            applied.append(relative.name)
            if marker.get("activeProjectRoot") != project_id:
                foreign = True
            elif source is not None and source.is_file() and _hash_file(source) != marker.get("sourceHash", marker.get("activeHash")):
                stale = True
    return {"present": present, "applied": applied, "stale": stale, "changedExternally": changed,
            "pendingRecovery": recovery, "backupOk": backup_ok, "everApplied": ever, "foreignApplied": foreign}


def _chars_status(game_root: Path, project_root: Path | None) -> dict:
    """Which character files a project carries, and which are applied to the game."""
    present, applied = [], []
    stale = changed = recovery = foreign = False
    backup_ok, ever = True, False
    project_id = str(project_root.resolve()) if project_root else ""
    for relative in _disk_chars(game_root, project_root):
        live = game_root / relative
        marker = _read_marker(_marker_path(game_root, relative))
        live_hash = _hash_file(live) if live.is_file() else None
        source = (project_root / relative) if project_root else None
        if source is not None and source.is_file():
            present.append(relative.name)
        if marker is None:
            continue
        ever = True
        backup = _backup_path(game_root, relative)
        ok = backup.is_file() and _hash_file(backup) == marker["originalHash"]
        backup_ok = backup_ok and ok
        pending = marker.get("pendingHash")
        if pending and live_hash == pending:
            recovery = True
        if live_hash and live_hash != pending and live_hash not in (marker["originalHash"], marker.get("activeHash")):
            changed = True
        if marker.get("enabled") and ok and live_hash == marker.get("activeHash"):
            applied.append(relative.name)
            if marker.get("activeProjectRoot") != project_id:
                foreign = True
            elif source is not None and source.is_file() and _hash_file(source) != marker.get("sourceHash", marker.get("activeHash")):
                stale = True
    return {"present": present, "applied": applied, "stale": stale, "changedExternally": changed,
            "pendingRecovery": recovery, "backupOk": backup_ok, "everApplied": ever, "foreignApplied": foreign}


def _assets_status(game_root: Path, project_root: Path | None) -> dict:
    """Which asset overrides a project carries, and which are applied."""
    present, applied = [], []
    stale = changed = recovery = foreign = False
    backup_ok, ever = True, False
    project_id = str(project_root.resolve()) if project_root else ""
    for relative in _disk_assets(game_root, project_root):
        live = game_root / relative
        marker = _read_marker(_marker_path(game_root, relative))
        live_hash = _hash_file(live) if live.is_file() else None
        source = (project_root / relative) if project_root else None
        if source is not None and source.is_file():
            present.append(relative.as_posix())
        if marker is None:
            continue
        ever = True
        backup = _backup_path(game_root, relative)
        ok = backup.is_file() and _hash_file(backup) == marker["originalHash"]
        backup_ok = backup_ok and ok
        pending = marker.get("pendingHash")
        if pending and live_hash == pending:
            recovery = True
        if live_hash and live_hash != pending and live_hash not in (marker["originalHash"], marker.get("activeHash")):
            changed = True
        if marker.get("enabled") and ok and live_hash == marker.get("activeHash"):
            applied.append(relative.as_posix())
            if marker.get("activeProjectRoot") != project_id:
                foreign = True
            elif source is not None and source.is_file() and _hash_file(source) != marker.get("sourceHash", marker.get("activeHash")):
                stale = True
    return {"present": present, "applied": applied, "stale": stale, "changedExternally": changed,
            "pendingRecovery": recovery, "backupOk": backup_ok, "everApplied": ever, "foreignApplied": foreign}


def _empty_group_status() -> dict:
    return {"present": [], "applied": [], "stale": False, "changedExternally": False,
            "pendingRecovery": False, "backupOk": True, "everApplied": False, "foreignApplied": False}


def status(game_root: Path | None, project_root: Path | None) -> dict:
    if game_root is None:
        return {"isProject": False, "sourceReady": False, "sourcePath": "",
                "liveReady": False, "livePath": "", "everApplied": False, "backupOk": False, "enabled": False,
                "matchesOriginal": False, "changedExternally": False, "stale": False, "pendingRecovery": False,
                "activeProjectRoot": "", "thisProjectActive": False, "appliedAt": "", "note": NOTE,
                "maps": _empty_group_status(), "chars": _empty_group_status(), "assets": _empty_group_status()}
    game_root = Path(game_root).resolve()
    live = game_root / RELATIVE
    live_exists = live.is_file()
    live_hash = _hash_file(live) if live_exists else None
    marker = _read_marker(_marker_path(game_root))
    backup = _backup_path(game_root)
    backup_ok = bool(marker) and backup.is_file() and _hash_file(backup) == marker["originalHash"]
    matches_original = bool(marker) and live_hash == marker["originalHash"]
    pending = (marker or {}).get("pendingHash")
    pending_recovery = bool(marker and pending and live_exists and live_hash == pending)
    enabled = bool(marker and marker.get("enabled") and backup_ok and live_hash == marker.get("activeHash"))
    changed_externally = bool(
        marker and live_exists and not pending_recovery
        and live_hash not in (marker["originalHash"], marker.get("activeHash"))
    )
    project_root = Path(project_root).resolve() if project_root else None
    is_project = bool(project_root) and (project_root / MARKER).is_file()
    source = (project_root / RELATIVE) if project_root else None
    source_ready = bool(source and source.is_file())
    active_project_root = (marker or {}).get("activeProjectRoot") or ""
    this_project_active = bool(enabled and project_root is not None and active_project_root == str(project_root))
    # A native rule rewrites the parameter archive as it is applied, so the
    # live file differs from the project's; staleness compares the project's
    # own bytes, recorded as sourceHash.
    stale = bool(this_project_active and source_ready and _hash_file(source) != marker.get("sourceHash", marker.get("activeHash")))
    text = _text_status(game_root, project_root)
    maps = _maps_status(game_root, project_root)
    chars = _chars_status(game_root, project_root)
    asset_group = _assets_status(game_root, project_root)
    combined_enabled = bool(enabled or text["enabled"] or maps["applied"] or chars["applied"] or asset_group["applied"])
    combined_active = bool(combined_enabled and (not enabled or this_project_active)
                           and (not maps["applied"] or not maps["foreignApplied"])
                           and (not chars["applied"] or not chars["foreignApplied"])
                           and (not asset_group["applied"] or not asset_group["foreignApplied"]))
    ever = bool(marker is not None or maps["everApplied"] or chars["everApplied"] or asset_group["everApplied"] or text["marked"])
    backup_all = bool(ever and (marker is None or backup_ok) and maps["backupOk"] and chars["backupOk"] and asset_group["backupOk"] and text["backupOk"])
    return {
        "texts": text,
        "maps": maps,
        "chars": chars,
        "assets": asset_group,
        "isProject": is_project,
        "sourceReady": bool(source_ready or text["sourceReady"] or maps["present"] or chars["present"] or asset_group["present"]),
        "sourcePath": str(source) if source else "",
        "liveReady": live_exists,
        "livePath": str(live),
        "everApplied": ever,
        "backupOk": backup_all,
        "enabled": combined_enabled,
        "matchesOriginal": bool(matches_original and not maps["applied"] and not chars["applied"] and not asset_group["applied"] and not text["enabled"]),
        "changedExternally": changed_externally or text["changedExternally"] or maps["changedExternally"] or chars["changedExternally"] or asset_group["changedExternally"],
        # Out of date when any file differs from what Apply would install.
        "stale": stale or maps["stale"] or chars["stale"] or asset_group["stale"] or bool(combined_active and not text["current"]),
        "pendingRecovery": pending_recovery or text["pendingRecovery"] or maps["pendingRecovery"] or chars["pendingRecovery"] or asset_group["pendingRecovery"],
        "activeProjectRoot": active_project_root,
        "thisProjectActive": combined_active,
        "appliedAt": (marker or {}).get("appliedAt") or "",
        "note": NOTE,
    }


def apply(game_root: Path, project_root: Path | None, *, transform=None, composed=None) -> dict:
    """Preserve installed originals once, then replace them with the saved project files.

    `composed` maps each file to the bytes the mod loader built from every
    enabled mod (mod_loader.py); a file it leaves out goes back to the
    original. The project still owns the deployment, and its own saved bytes
    are what a later Apply compares to see whether it is out of date.
    """
    if project_root is None:
        raise ValueError("Select or create a mod project before applying it to the installed game.")
    # Check the raw roots themselves, and everything above them, before any
    # .resolve() call: resolving first would silently follow a reparse point
    # at the root or on a parent and erase the evidence we need to reject it.
    game_root = _assert_no_reparse_ancestry(game_root).resolve()
    project_root = _assert_no_reparse_ancestry(project_root).resolve()
    project_marker = project_root / MARKER
    _assert_no_reparse_points(project_marker, project_root)
    if not project_marker.is_file():
        raise ValueError("Select a valid Dark Souls mod project before applying it.")
    source = project_root / RELATIVE
    map_targets = _disk_maps(game_root, project_root)
    char_targets = _disk_chars(game_root, project_root)
    asset_targets = _disk_assets(game_root, project_root)
    if composed is not None:
        map_targets += [relative for relative in composed
                        if relative.suffix == ".msb" and relative.parent == MAP_DIR and relative not in map_targets]
        char_targets += [relative for relative in composed
                         if assets.is_character_file(relative) and relative not in char_targets]
        asset_targets += [relative for relative in composed
                          if relative not in dict(FILES) and relative not in map_targets and relative not in char_targets
                          and relative not in asset_targets]
    targets = (list(FILES) + [(relative, MsbDocument) for relative in map_targets]
               + [(relative, _check_esd if relative.name.endswith('.esd.dcx') else _check_anibnd)
                  for relative in char_targets]
               + [(relative, None) for relative in asset_targets])
    if composed is None and not source.is_file() and not (project_root / texts.RELATIVE).is_file() \
            and not (project_root / texts.MENU_RELATIVE).is_file() \
            and not any((project_root / relative).is_file() for relative in map_targets + char_targets + asset_targets):
        raise FileNotFoundError("Save the project before applying it; it holds no game files to install.")
    _assert_disjoint(game_root, project_root)
    # Every file the project holds is checked before any of them is written.
    sources = {}
    for relative, reader in targets:
        candidate = project_root / relative
        _assert_no_reparse_points(candidate, project_root)
        own = candidate.is_file()
        cap = MAX_ASSET if reader is None else MAX_ARCHIVE
        if own and candidate.stat().st_size > cap:
            raise ValueError(f"{candidate.name} is too large to apply.")
        if composed is not None:
            if relative not in composed:
                continue
            payload = composed[relative]
            if not isinstance(payload, bytes) or len(payload) > cap:
                raise ValueError(f"The combined {relative.name} is invalid")
        elif not own:
            continue
        else:
            payload = candidate.read_bytes()
        source_hash = hashlib.sha256(candidate.read_bytes() if own else payload).hexdigest()
        if transform is not None and relative == RELATIVE:
            payload = transform(payload)
            if not isinstance(payload, bytes) or len(payload) > MAX_ARCHIVE:
                raise ValueError("The parameter transformation returned invalid output")
        # Reject corrupt/unsupported project output before any backup or live write.
        _check_asset_like(game_root, relative, payload) if reader is None else reader(payload)
        sources[relative] = (candidate, payload, source_hash)
    for relative, _reader in targets:
        if relative in sources:
            _apply_file(game_root, project_root, relative, *sources[relative])
        elif _read_marker(_marker_path(game_root, relative)):
            # The project no longer changes this file: put the original back.
            _restore_file(game_root, relative)
    return status(game_root, project_root)


def _apply_file(game_root: Path, project_root: Path, relative: Path, source: Path, new_bytes: bytes,
                source_hash: str) -> None:
    live = game_root / relative
    backup = _backup_path(game_root, relative)
    marker_path = _marker_path(game_root, relative)
    for path in (live, backup, marker_path):
        _assert_no_reparse_points(path, game_root)
    if source.resolve() == live.resolve():
        raise RuntimeError("The mod project's saved archive and the installed file must not be the same path.")
    new_hash = hashlib.sha256(new_bytes).hexdigest()
    marker = _read_marker(marker_path)

    if marker is None:
        if not live.is_file():
            raise FileNotFoundError(f"The installed game has no {relative.as_posix()}; cannot safely preserve its original data.")
        if backup.exists():
            raise RuntimeError(
                f"An unmanaged backup already exists at {backup}; remove or restore it manually before continuing."
            )
        original_hash = _hash_file(live)
        _atomic_copy(live, backup)
        if _hash_file(backup) != original_hash:
            backup.unlink(missing_ok=True)
            raise RuntimeError("Could not verify the preserved original copy; nothing installed was changed.")
        marker = {"schema": 1, "modId": MOD_ID, "originalHash": original_hash,
                  "activeHash": None, "activeProjectRoot": None, "enabled": False, "appliedAt": None,
                  "pendingHash": None, "pendingKind": None}
        _write_marker(marker_path, marker)
    else:
        if not backup.is_file() or _hash_file(backup) != marker["originalHash"]:
            raise RuntimeError(
                "The preserved original copy is missing or changed; refusing to continue until it is restored."
            )
        marker = _reconcile(marker, marker_path, live)

    # Record the intent durably before the live file is ever touched, so an
    # interruption after the write below is recognized next time, not guessed at.
    marker.update({"pendingHash": new_hash, "pendingKind": "apply"})
    _write_marker(marker_path, marker)
    atomic_write(live, new_bytes)
    if _hash_file(live) != new_hash:
        raise RuntimeError("Applying the mod failed verification; the original backup and pending intent were kept.")
    marker.update({"activeHash": new_hash, "sourceHash": source_hash, "activeProjectRoot": str(project_root),
                   "enabled": True, "appliedAt": datetime.now(timezone.utc).isoformat(),
                   "pendingHash": None, "pendingKind": None})
    _write_marker(marker_path, marker)


def disable(game_root: Path) -> dict:
    """Restore the exact preserved original bytes, leaving the backup in place for later reapply."""
    game_root = _assert_no_reparse_ancestry(game_root).resolve()
    targets = (list(FILES) + [(relative, MsbDocument) for relative in _disk_maps(game_root)]
               + [(relative, _check_anibnd) for relative in _disk_chars(game_root)]
               + [(relative, None) for relative in _disk_assets(game_root)])
    for relative, _reader in targets:
        if _read_marker(_marker_path(game_root, relative)) is not None:
            _restore_file(game_root, relative)
    return status(game_root, None)


def _restore_file(game_root: Path, relative: Path) -> None:
    marker_path = _marker_path(game_root, relative)
    marker = _read_marker(marker_path)
    if marker is None:
        return
    live = game_root / relative
    backup = _backup_path(game_root, relative)
    for path in (live, backup, marker_path):
        _assert_no_reparse_points(path, game_root)
    if not backup.is_file() or _hash_file(backup) != marker["originalHash"]:
        raise RuntimeError("The preserved original copy is missing or changed; cannot safely restore automatically.")
    # Always validate the live file against known-good state, even when the
    # marker already says "disabled": a second Disable after something else
    # wrote to the live file must refuse, not blindly restore over it.
    marker = _reconcile(marker, marker_path, live)

    marker.update({"pendingHash": marker["originalHash"], "pendingKind": "disable"})
    _write_marker(marker_path, marker)
    _atomic_copy(backup, live)
    if _hash_file(live) != marker["originalHash"]:
        raise RuntimeError("Restoring the original copy failed verification; the installed file may be inconsistent.")
    marker.update({"activeHash": None, "activeProjectRoot": None, "enabled": False, "pendingHash": None, "pendingKind": None})
    _write_marker(marker_path, marker)
