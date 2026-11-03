"""Prepare an isolated Mod Engine 2 profile; never replace installed files.

This is a backend/export entry point, not a bundled runtime or a UI integration.
Runtime launch must validate the snapshot and use the pinned DSR-capable build.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

from .composition import compose, CompositionError, ConflictError, MAX_MODS

SOURCE_REPOSITORY = "AltimorTASDK/ModEngine2"
SOURCE_REVISION = "76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d"
RELATIVE = Path("param/GameParam/GameParam.parambnd.dcx")
MAX_FILES = 4096
MAX_INPUT_BYTES = 512 * 1024 * 1024
MAX_PARAM_BYTES = 64 * 1024 * 1024


class ProfileConflictError(CompositionError):
    def __init__(self, report: dict):
        self.report = report
        super().__init__(f"{len(report['fileConflicts'])} conflicting files and "
                         f"{len(report['conflicts'])} conflicting fields; choose a load order explicitly")


@dataclass(frozen=True)
class Mod:
    id: str
    root: Path
    enabled: bool = True
    requires: tuple[str, ...] = ()
    base_sha256: str | None = None


def safe_path(path: Path) -> Path:
    """Check lexical ancestors before resolve can hide a symlink or junction."""
    text = os.fspath(path)
    if not isinstance(text, str) or any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise CompositionError("Invalid filesystem path")
    result = Path(os.path.abspath(text))
    for part in (result, *result.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise CompositionError(f"Symlinks and junctions are not supported: {part}")
    return result.resolve()


def disjoint(a: Path, b: Path):
    if a == b or a in b.parents or b in a.parents:
        raise CompositionError(f"Output, game and mod roots must be separate: {a} / {b}")


def _digest(path: Path) -> str:
    digest = sha256()
    with safe_path(path).open("rb") as stream:
        remaining = MAX_INPUT_BYTES
        while block := stream.read(min(1024 * 1024, remaining + 1)):
            remaining -= len(block)
            if remaining < 0:
                raise CompositionError("An input file exceeds the size limit")
            digest.update(block)
    return digest.hexdigest()


def _walk_error(error):
    raise CompositionError(f"Could not inventory a mod: {error}")


def _inventory(root: Path):
    result, total, visited = {}, 0, 0
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=_walk_error):
        visited += 1
        if visited > MAX_FILES:
            raise CompositionError("Too many mod directories")
        # A project's Git history is not game data.
        dirs[:] = sorted(name for name in dirs if name != ".git")
        for name in dirs + files:
            safe_path(Path(directory) / name)
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if any(":" in part or part.endswith((" ", ".")) for part in Path(relative).parts):
                raise CompositionError(f"Unsupported Windows filename: {relative}")
            key = relative.casefold()
            if key in result:
                raise CompositionError(f"Case-insensitive path collision: {relative}")
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise CompositionError(f"Not a regular mod file: {path}")
            total += info.st_size
            if total > MAX_INPUT_BYTES or len(result) >= MAX_FILES:
                raise CompositionError("Mod exceeds the file-count or byte limit")
            result[key] = {"relative": relative, "sha256": _digest(path), "size": info.st_size}
    return result


def _read_param(path: Path):
    with safe_path(path).open("rb") as stream:
        data = stream.read(MAX_PARAM_BYTES + 1)
    if len(data) > MAX_PARAM_BYTES:
        raise CompositionError("Parameter archive exceeds the size limit")
    return data


def prepare_profile(game_root: Path, base_path: Path, destination: Path, mods: list[Mod],
                    *, expected_base_sha256: str, policy: str = "error") -> dict:
    """Export once to a NEW folder, with low-to-high mod priority.

    The caller explicitly supplies a known common baseline and its hash. A hash
    proves byte identity, not that an arbitrary installed file is vanilla.
    No files are written until composition and conflict checks have succeeded.
    Existing destinations are refused instead of overwritten or accumulated.
    """
    if policy not in ("error", "last-wins") or len(mods) > MAX_MODS:
        raise CompositionError("Invalid policy or too many mods")
    ids = [mod.id for mod in mods]
    if any(not isinstance(name, str) or not name.strip() or len(name) > 128 for name in ids):
        raise CompositionError("Invalid mod ID")
    if len(set(ids)) != len(ids):
        raise CompositionError("Duplicate mod IDs")
    if "lexeditor-composed" in ids:
        raise CompositionError("The generated overlay uses the reserved mod ID lexeditor-composed")
    if any(type(mod.enabled) is not bool for mod in mods):
        raise CompositionError("Enabled must be a boolean")
    active = [mod for mod in mods if mod.enabled]
    positions = {mod.id: index for index, mod in enumerate(active)}
    for index, mod in enumerate(active):
        if any(not isinstance(dep, str) or dep not in positions or positions[dep] >= index for dep in mod.requires):
            raise CompositionError(f"{mod.id}: dependencies must be enabled and earlier in the load order")
        if mod.base_sha256 is not None and mod.base_sha256 != expected_base_sha256:
            raise CompositionError(f"{mod.id}: baseline version mismatch")

    game_root, base_path, destination = map(safe_path, (game_root, base_path, destination))
    if not game_root.is_dir():
        raise CompositionError("Game root directory does not exist")
    disjoint(destination, game_root)
    if destination == base_path or destination in base_path.parents:
        raise CompositionError("Output would contain the baseline")
    if destination.exists():
        raise CompositionError("Choose a new, empty profile destination")
    if not destination.parent.is_dir():
        raise CompositionError("Profile parent directory does not exist")
    base = _read_param(base_path)
    if sha256(base).hexdigest() != expected_base_sha256:
        raise CompositionError("Baseline hash mismatch")

    archives, roots, snapshots, winners, file_conflicts = [], [], [], {}, []
    total = total_files = 0
    for mod in active:
        mod_root = safe_path(mod.root)
        if not mod_root.is_dir():
            raise CompositionError(f"Missing mod folder: {mod.id}")
        disjoint(destination, mod_root)
        disjoint(game_root, mod_root)
        for previous in roots:
            disjoint(mod_root, previous)
        roots.append(mod_root)
        inventory = _inventory(mod_root)
        total += sum(item["size"] for item in inventory.values())
        total_files += len(inventory)
        if total > MAX_INPUT_BYTES or total_files > MAX_FILES:
            raise CompositionError("Enabled mods exceed the combined file-count or byte limit")
        snapshots.append({"id": mod.id, "root": str(mod_root), "files": inventory,
                          "requires": list(mod.requires), "baseSha256": mod.base_sha256})
        parameter = inventory.get(RELATIVE.as_posix().casefold())
        if parameter:
            data = _read_param(mod_root / parameter["relative"])
            if sha256(data).hexdigest() != parameter["sha256"]:
                raise CompositionError("Mod changed while preparing its profile")
            archives.append((mod.id, data))
        for key, item in inventory.items():
            if key == RELATIVE.as_posix().casefold() or ("/" not in key and key.startswith(".lexeditor")):
                continue
            previous = winners.get(key)
            if previous and previous[1] != item["sha256"]:
                file_conflicts.append({"path": item["relative"], "loser": previous[0], "winner": mod.id,
                                       "granularity": "file"})
            winners[key] = (mod.id, item["sha256"])

    # Use last-wins only to obtain the full report, then enforce the selected
    # policy before writing any output.
    archive, report = compose(base, archives, policy="last-wins")
    report.update(policy=policy, fileConflicts=file_conflicts,
                  unverifiedBaselines=[mod.id for mod in active if mod.base_sha256 is None])
    if policy == "error" and (report["conflicts"] or file_conflicts):
        if file_conflicts:
            raise ProfileConflictError(report)
        raise ConflictError(report)

    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    entries = [("lexeditor-composed", destination / "merged")]
    # Mod Engine's find_override_file returns the FIRST existing path.
    entries += [(mod.id, path) for mod, path in reversed(list(zip(active, roots)))]
    rows = [f"  {{ enabled = true, name = {quote(name)}, path = {quote(path)} }}" for name, path in entries]
    config = ("[modengine]\ndebug = false\nexternal_dlls = []\n\n"
              "[extension.mod_loader]\nenabled = true\nloose_params = false\nmods = [\n"
              + ",\n".join(rows) + "\n]\n\n[extension.scylla_hide]\nenabled = false\n")
    manifest = {"schema": 1, "sourceRepository": SOURCE_REPOSITORY, "sourceRevision": SOURCE_REVISION,
                "runtimeBundled": False, "gameRoot": str(game_root), "basePath": str(base_path), "baseSha256": expected_base_sha256,
                "mods": snapshots, "configSha256": sha256(config.encode()).hexdigest(), "composition": report}
    # Check source snapshots again immediately before publishing.
    if _digest(base_path) != expected_base_sha256:
        raise CompositionError("Baseline changed while preparing its profile")
    for snapshot in snapshots:
        if _inventory(Path(snapshot["root"])) != snapshot["files"]:
            raise CompositionError("Mod changed while preparing its profile")

    from core.plugin_files import atomic_write

    destination.mkdir()  # Exclusive claim; no existing folder is modified.
    output = destination / "merged" / RELATIVE
    output.parent.mkdir(parents=True)
    atomic_write(output, archive)
    atomic_write(destination / "profile.json", (json.dumps(manifest, indent=2) + "\n").encode())
    # Publish the runnable configuration last. Failed exports are never launched.
    atomic_write(destination / "config_darksoulsremastered.toml", config.encode())
    return manifest


def verify_profile(directory: Path) -> dict:
    """Reject edited, removed or newly added inputs before a future launch."""
    directory = safe_path(directory)
    marker = safe_path(directory / "profile.json")
    with marker.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise CompositionError("Profile manifest is too large")
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise CompositionError("Unsupported profile manifest")
    if manifest.get("sourceRevision") != SOURCE_REVISION:
        raise CompositionError("Profile targets a different loader revision")
    snapshots = manifest.get("mods")
    if not isinstance(snapshots, list) or len(snapshots) > MAX_MODS:
        raise CompositionError("Invalid profile mod list")
    if _digest(Path(manifest["basePath"])) != manifest["baseSha256"]:
        raise CompositionError("Baseline changed; rebuild the profile")
    if _digest(directory / "config_darksoulsremastered.toml") != manifest["configSha256"]:
        raise CompositionError("Loader configuration changed; rebuild the profile")
    if _digest(directory / "merged" / RELATIVE) != manifest["composition"]["outputSha256"]:
        raise CompositionError("Composed archive changed; rebuild the profile")
    for snapshot in snapshots:
        path = safe_path(Path(snapshot["root"]))
        if not path.is_dir() or _inventory(path) != snapshot["files"]:
            raise CompositionError(f"Mod {snapshot['id']} changed; rebuild the profile")
    return manifest
