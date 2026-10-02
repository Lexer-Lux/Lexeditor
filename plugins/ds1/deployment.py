"""Reversible native replacement of the installed DS1 item parameter archive.

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
from .formats import ItemDocument, MAX_ARCHIVE
from .store import MARKER, RELATIVE

MOD_ID = "lexeditor-ds1"
NOTE = (
    "Dark Souls Remastered reads param/GameParam/GameParam.parambnd.dcx as a loose file "
    "from disk; no mod loader is installed or required. Apply preserves one original "
    "copy before replacing the installed file, and Disable restores those exact bytes."
)


def _backup_path(game_root: Path) -> Path:
    return game_root / RELATIVE.parent / (RELATIVE.name + ".lexeditor-original")


def _marker_path(game_root: Path) -> Path:
    return game_root / RELATIVE.parent / ".lexeditor-ds1-deployment.json"


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


def vanilla_source(game_root: Path) -> Path:
    """The true pristine original: the preserved backup once Apply owns the installed
    file, otherwise the installed file itself (still pristine, since nothing has
    taken control of it yet). Once a marker exists, the live file may hold a
    deployed mod's bytes, so an unverifiable backup must refuse rather than fall
    back to live and silently label modded data as Vanilla."""
    game_root = Path(game_root).resolve()
    backup = _backup_path(game_root)
    marker = _read_marker(_marker_path(game_root))
    if marker is None:
        return game_root / RELATIVE
    if backup.is_file() and _hash_file(backup) == marker["originalHash"]:
        return backup
    raise RuntimeError(
        f"The preserved original copy of {RELATIVE.as_posix()} is missing or has changed at {backup}. "
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
            f"The installed parameter archive is missing at {live}. Verify or restore the game's "
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
        "The installed parameter archive changed outside Lexeditor; restore or verify game files before continuing."
    )


def status(game_root: Path | None, project_root: Path | None) -> dict:
    if game_root is None:
        return {"isProject": False, "sourceReady": False, "sourcePath": "",
                "liveReady": False, "livePath": "", "everApplied": False, "backupOk": False, "enabled": False,
                "matchesOriginal": False, "changedExternally": False, "stale": False, "pendingRecovery": False,
                "activeProjectRoot": "", "thisProjectActive": False, "appliedAt": "", "note": NOTE}
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
    stale = bool(this_project_active and source_ready and _hash_file(source) != marker.get("sourceHash", marker.get("activeHash")))
    return {
        "isProject": is_project,
        "sourceReady": source_ready,
        "sourcePath": str(source) if source else "",
        "liveReady": live_exists,
        "livePath": str(live),
        "everApplied": marker is not None,
        "backupOk": backup_ok,
        "enabled": enabled,
        "matchesOriginal": matches_original,
        "changedExternally": changed_externally,
        "stale": stale,
        "pendingRecovery": pending_recovery,
        "activeProjectRoot": active_project_root,
        "thisProjectActive": this_project_active,
        "appliedAt": (marker or {}).get("appliedAt") or "",
        "note": NOTE,
    }


def apply(game_root: Path, project_root: Path | None, *, transform=None) -> dict:
    """Preserve the installed original once, then replace it with the saved project archive."""
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
    if not source.is_file():
        raise FileNotFoundError(f"Save the project before applying it; no {RELATIVE.as_posix()} was found in it.")
    if source.stat().st_size > MAX_ARCHIVE:
        raise ValueError("The parameter archive is too large to apply.")
    _assert_disjoint(game_root, project_root)

    live = game_root / RELATIVE
    backup = _backup_path(game_root)
    marker_path = _marker_path(game_root)
    for path in (live, backup, marker_path):
        _assert_no_reparse_points(path, game_root)
    _assert_no_reparse_points(source, project_root)
    if source.resolve() == live.resolve():
        raise RuntimeError("The mod project's saved archive and the installed file must not be the same path.")

    new_bytes = source.read_bytes()
    source_hash = hashlib.sha256(new_bytes).hexdigest()
    if transform is not None:
        new_bytes = transform(new_bytes)
        if not isinstance(new_bytes, bytes) or len(new_bytes) > MAX_ARCHIVE:
            raise ValueError("The parameter transformation returned invalid output")
    ItemDocument(new_bytes)  # Reject corrupt/unsupported project output before any backup or live write.
    new_hash = hashlib.sha256(new_bytes).hexdigest()
    marker = _read_marker(marker_path)

    if marker is None:
        if not live.is_file():
            raise FileNotFoundError(f"The installed game has no {RELATIVE.as_posix()}; cannot safely preserve its original data.")
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
    return status(game_root, project_root)


def disable(game_root: Path) -> dict:
    """Restore the exact preserved original bytes, leaving the backup in place for later reapply."""
    game_root = _assert_no_reparse_ancestry(game_root).resolve()
    marker_path = _marker_path(game_root)
    marker = _read_marker(marker_path)
    if marker is None:
        return status(game_root, None)
    live = game_root / RELATIVE
    backup = _backup_path(game_root)
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
    return status(game_root, None)
