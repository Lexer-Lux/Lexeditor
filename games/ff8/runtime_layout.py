"""Compose editable FF8 mod source into the isolated FFNx runtime tree."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 in Lexeditor's bundled environment.
    import tomli as tomllib

from . import (field_background, field_encounters, field_walkmesh, fixed_data_merge,
               iroj_archive, kernel_merge, mngrp_merge, mod_folders, world_data_merge)


COMPOSITION_FILE = "composition.json"
# These are normalized source roots. Direct and Hext are already wired to
# FFNx. The media roots are composed now so their later FFNx path binding uses
# the same order and conflict manifest rather than a second mod system.
# Roots Lexeditor can compose and bind to a proved FFNx path without executing
# package code. Hext remains an ordered patch stream; the others are file
# overlays whose higher-priority path claimant wins unless a semantic merger
# understands the file.
SOURCE_FOLDERS = (
    "direct", "hext", "textures", "sfx", "voice", "ambient",
    "override", "save",
)
MOD_FILE = "mod.json"
IROJ_STATE_SUFFIX = ".lexeditor.json"
IROJ_CACHE_FOLDER = ".iroj-cache"
LIVE_CONDITIONAL_ROOT = "direct/lexeditor/conditional-variants"
LIVE_CONDITIONAL_MANIFEST = "direct/lexeditor/live-conditions.json"
MAX_LIVE_CONDITIONAL_OUTPUTS = 4096
MAX_LIVE_CONDITIONAL_BYTES = 256 * 1024 * 1024
MAX_LIVE_CONDITIONAL_INPUTS = 4096
MAX_LIVE_CONDITIONS_PER_PATH = 12
MAX_LIVE_VARIANTS_PER_PATH = 4096
MAX_LIVE_VARIANTS_TOTAL = 65536
LIVE_CONDITIONAL_ROOTS = {"direct", "sfx", "voice", "ambient"}
WORLD_MERGE_SPECS = {
    "direct/world/dat/wmx.obj": ("world/wmx.obj", "geometry"),
    "direct/world/dat/wmsetus.obj": ("world/wmsetus.obj", "wmset"),
    "direct/world/dat/rail.obj": ("world/rail.obj", "rail"),
    "direct/world/dat/texl.obj": ("world/texl.obj", "textures"),
}
FIELD_WALKMESH_PATH = re.compile(
    r"^direct/field/mapdata/[^/]+/([^/]+)/\1\.id$", re.IGNORECASE)
FIELD_BACKGROUND_PATH = re.compile(
    r"^direct/field/mapdata/[^/]+/([^/]+)/\1\.map$", re.IGNORECASE)
FIELD_ENCOUNTER_PATH = re.compile(
    r"^direct/field/mapdata/[^/]+/([^/]+)/\1\.(mrt|rat)$", re.IGNORECASE)


def _field_walkmesh_baseline(logical_path: str,
                             baseline_root: Path | None) -> Path | None:
    if baseline_root is None or FIELD_WALKMESH_PATH.fullmatch(logical_path) is None:
        return None
    candidate = Path(baseline_root) / Path(*_path_parts(logical_path)[1:])
    return candidate if candidate.is_file() else None


def _field_background_baseline(logical_path: str,
                               baseline_root: Path | None) -> tuple[Path, Path] | None:
    if baseline_root is None or FIELD_BACKGROUND_PATH.fullmatch(logical_path) is None:
        return None
    map_path = Path(baseline_root) / Path(*_path_parts(logical_path)[1:])
    mim_path = map_path.with_suffix(".mim")
    return (map_path, mim_path) if map_path.is_file() and mim_path.is_file() else None


def _field_encounter_baseline(logical_path: str,
                              baseline_root: Path | None) -> tuple[Path, str] | None:
    match = FIELD_ENCOUNTER_PATH.fullmatch(logical_path)
    if baseline_root is None or match is None:
        return None
    candidate = Path(baseline_root) / Path(*_path_parts(logical_path)[1:])
    return (candidate, match.group(2).casefold()) if candidate.is_file() else None


def prelaunch_condition_state(config: Path | None = None,
                              now: datetime | None = None) -> dict:
    """Freeze safe process-independent values for one atomic composition."""
    ffnx: dict[str, int] = {}
    if config is not None:
        try:
            values = tomllib.loads(Path(config).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            values = {}
        for key, value in values.items():
            if isinstance(value, bool):
                ffnx[str(key)] = int(value)
            elif isinstance(value, int):
                ffnx[str(key)] = value
            elif isinstance(value, str):
                try:
                    ffnx[str(key)] = int(value, 0)
                except ValueError:
                    pass
    return {"system": mod_folders.system_state(now), "ffnx": ffnx}


def _metadata_path(root: Path) -> Path:
    return (root.with_name(root.name + IROJ_STATE_SUFFIX)
            if root.is_file() else root / MOD_FILE)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(root: Path) -> list[dict]:
    rows = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()),
                       key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(root).as_posix()
        if (path.name == COMPOSITION_FILE
                or relative.casefold() == LIVE_CONDITIONAL_MANIFEST
                or relative.casefold().startswith(LIVE_CONDITIONAL_ROOT + "/")):
            continue
        rows.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return rows


def _hext_runtime_path(relative: Path, order: int, mod_id: str) -> Path:
    """Give every Hext source a stable name in Lexeditor load order.

    FFNx reads only regular files in the final language directory. Keeping each
    source file separate preserves checkpoints and per-file global offsets.
    The derivative sorts these names before applying them, so later mods patch
    memory after earlier mods.
    """
    parts = relative.parts
    if not parts or parts[0].casefold() != "hext":
        return relative
    safe_mod = re.sub(r"[^A-Za-z0-9._-]+", "-", mod_id).strip(".-") or "mod"
    filename = relative.name
    return relative.parent / f"{order:06d}__{safe_mod}__{filename}"


def _remove_private_tree(path: Path, parent: Path, prefix: str) -> None:
    """Remove only a staging tree created beside the configured active tree."""
    resolved_parent = parent.resolve()
    if path.parent.resolve() != resolved_parent or not path.name.startswith(prefix):
        raise RuntimeError(f"Refusing to remove an unexpected runtime path: {path}")
    if path.exists():
        shutil.rmtree(path)


def _metadata(root: Path, *, selected: bool = False) -> dict:
    data = {}
    archive_error = ""
    try:
        data = json.loads(_metadata_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    rules = mod_folders.PackageRules()
    folder_error = ""
    mod_xml = None
    if root.is_file() and root.suffix.casefold() == ".iroj":
        try:
            import xml.etree.ElementTree as ET
            archive = iroj_archive.Archive(root)
            mod_xml = archive.read("mod.xml") if archive.has("mod.xml") else None
            document = ET.fromstring(mod_xml) if mod_xml else None
        except iroj_archive.IrojError as error:
            archive_error = str(error)
            document = None
        except (ValueError, KeyError, ET.ParseError):
            document = None
        if document is not None:
            data.setdefault("id", (document.findtext("ID") or "").strip())
            data.setdefault("name", (document.findtext("Name") or "").strip())
    elif root.is_dir():
        try:
            mod_xml = (root / "mod.xml").read_bytes()
        except OSError:
            mod_xml = None
    try:
        rules = mod_folders.parse(mod_xml)
    except mod_folders.FolderMetadataError as error:
        folder_error = str(error)
    mod_id = str(data.get("id") or root.stem).strip()
    if not mod_id or any(char in mod_id for char in "/\\"):
        raise ValueError(f"Invalid FF8 mod id in {root / MOD_FILE}")
    source = data.get("source", "")
    if not isinstance(source, (str, dict)):
        source = ""
    try:
        folder_options = rules.resolved_options(data.get("folderOptions"))
    except mod_folders.FolderMetadataError as error:
        folder_error = str(error)
        folder_options = {option.id: option.default for option in rules.options}
    return {
        "id": mod_id,
        "name": str(data.get("name") or mod_id),
        "path": str(root.resolve()),
        "enabled": data.get("enabled", True if selected else False) is True,
        "order": int(data.get("order", 0 if selected else 1000)),
        "featured": data.get("featured") is True,
        "source": source,
        "version": str(data.get("version") or ""),
        "releaseUrl": str(data.get("releaseUrl") or ""),
        "selected": selected,
        "deletable": not selected,
        "readOnly": data.get("readOnly") is True,
        "container": "iroj" if root.is_file() else "folder",
        "error": archive_error,
        "folderError": folder_error,
        "folderConfig": [option.json() for option in rules.options],
        "folderOptions": folder_options,
    }


def catalog(project_root: Path, mods_root: Path) -> list[dict]:
    """List the selected project and installed managed mods without mutation."""
    project = Path(project_root).resolve()
    rows = [_metadata(project, selected=True)]
    root = Path(mods_root)
    if root.is_dir():
        for child in sorted((item for item in root.iterdir()
                             if item.is_dir() or (item.is_file() and item.suffix.casefold() == ".iroj")),
                            key=lambda item: item.name.casefold()):
            if child.resolve() == project or (child.is_dir() and not (child / MOD_FILE).is_file()):
                continue
            rows.append(_metadata(child))
    seen: set[str] = set()
    for row in rows:
        key = row["id"].casefold()
        if key in seen:
            raise ValueError(f"Duplicate FF8 mod id: {row['id']}")
        seen.add(key)
    return sorted(rows, key=lambda row: (row["order"], row["name"].casefold()))


def configure(project_root: Path, mods_root: Path, order: list[str],
              enabled: dict[str, bool], folder_options: dict[str, dict] | None = None) -> list[dict]:
    """Persist the complete managed-mod order and enabled state.

    Enabled state controls runtime composition only. The editable project stays
    available as the edit target even when it is disabled in the runtime stack.
    """
    rows = catalog(project_root, mods_root)
    by_id = {row["id"]: row for row in rows}
    if len(order) != len(rows) or set(order) != set(by_id):
        raise ValueError("The FF8 mod order must contain every managed mod exactly once")
    for position, mod_id in enumerate(order):
        row = by_id[mod_id]
        root = Path(row["path"])
        path = _metadata_path(root)
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        metadata.setdefault("id", row["id"])
        metadata.setdefault("name", row["name"])
        metadata["order"] = position
        metadata["enabled"] = enabled.get(mod_id) is True
        requested_options = ((folder_options or {}).get(mod_id)
                             if folder_options is not None else row["folderOptions"])
        definitions = {item["id"]: item for item in row["folderConfig"]}
        if requested_options is None:
            requested_options = row["folderOptions"]
        if not isinstance(requested_options, dict):
            raise ValueError(f"Folder options for {mod_id} must be an object")
        normalized_options = {}
        for option_id, definition in definitions.items():
            value = requested_options.get(option_id, definition["default"])
            if isinstance(value, bool):
                value = int(value)
            allowed = {choice["value"] for choice in definition["values"]}
            if not isinstance(value, int) or value not in allowed:
                raise ValueError(f"Option {option_id} for {mod_id} has an invalid value")
            normalized_options[option_id] = value
        unknown = set(requested_options) - set(definitions)
        if unknown:
            raise ValueError(f"Unknown folder option for {mod_id}: {sorted(unknown)[0]}")
        if normalized_options:
            metadata["folderOptions"] = normalized_options
        else:
            metadata.pop("folderOptions", None)
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=".mod.", suffix=".json.tmp", dir=parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(metadata, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    return catalog(project_root, mods_root)


def install_iroj(source: Path, project_root: Path, mods_root: Path,
                 name_hint: str = "", *, replace_existing: bool = False,
                 metadata: dict | None = None) -> dict:
    """Validate and install one archive without importing a Junction profile."""
    source = Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.casefold() != ".iroj":
        raise ValueError("Select one .iroj mod archive")
    archive = iroj_archive.Archive(source)
    # Validate every member Lexeditor can deploy before changing the library.
    for member in archive.names():
        archive.read(member)
    incoming = _metadata(source)
    # The HTTP upload is stored under a private temporary name. If mod.xml has
    # no ID, use the browser-supplied original filename instead of exposing
    # that temporary name as the permanent mod identity.
    archive_id = ""
    archive_name = ""
    if archive.has("mod.xml"):
        try:
            import xml.etree.ElementTree as ET
            document = ET.fromstring(archive.read("mod.xml"))
            archive_id = (document.findtext("ID") or "").strip()
            archive_name = (document.findtext("Name") or "").strip()
        except ET.ParseError:
            pass
    if not archive_id and name_hint:
        hinted_stem = Path(Path(name_hint).name).stem.strip()
        if hinted_stem:
            incoming["id"] = hinted_stem
            if not archive_name:
                incoming["name"] = hinted_stem
    current = catalog(project_root, mods_root)
    existing = next((row for row in current
                     if row["id"].casefold() == incoming["id"].casefold()), None)
    if existing and (not replace_existing or existing["selected"]):
        raise ValueError(f"An FF8 mod already uses id {incoming['id']}")
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", incoming["id"]).strip(".-")
    if not safe_id:
        safe_id = _sha256(source)[:16]
    library = Path(mods_root).resolve()
    library.mkdir(parents=True, exist_ok=True)
    destination = library / f"{safe_id}.iroj"
    if ((destination.exists() or _metadata_path(destination).exists())
            and (existing is None or Path(existing["path"]).resolve() != destination.resolve())):
        raise ValueError(f"The managed-mod archive already exists: {destination.name}")
    handle, temporary_name = tempfile.mkstemp(prefix=f".{safe_id}.", suffix=".iroj.tmp", dir=library)
    os.close(handle)
    temporary = Path(temporary_name)
    state = {
        "id": incoming["id"], "name": incoming["name"],
        "enabled": existing["enabled"] if existing else False,
        "order": (existing["order"] if existing else
                  max((int(row["order"]) for row in current), default=-1) + 1),
        "readOnly": True, "source": str(source),
    }
    allowed_metadata = {
        "featured", "source", "version", "releaseUrl", "releaseId", "assetSha256",
    }
    for key, value in (metadata or {}).items():
        if key in allowed_metadata:
            state[key] = value
    state_handle, state_temp_name = tempfile.mkstemp(
        prefix=f".{safe_id}.", suffix=".json.tmp", dir=library)
    state_temporary = Path(state_temp_name)
    with os.fdopen(state_handle, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())

    old_root = Path(existing["path"]).resolve() if existing else None
    old_metadata = _metadata_path(old_root) if old_root else None
    old_was_file = old_root.is_file() if old_root else False
    backup_root = library / f".{safe_id}.replaced-{os.getpid()}"
    backup_metadata = library / f".{safe_id}.replaced-{os.getpid()}.json"
    moved_root = False
    moved_metadata = False
    try:
        shutil.copy2(source, temporary)
        if _sha256(temporary) != _sha256(source):
            raise RuntimeError("The copied IROJ archive did not verify")
        if old_root is not None:
            if old_root.parent != library:
                raise RuntimeError("Refusing to replace a mod outside the managed FF8 library")
            old_root.replace(backup_root)
            moved_root = True
            if old_was_file and old_metadata and old_metadata.exists():
                old_metadata.replace(backup_metadata)
                moved_metadata = True
        temporary.replace(destination)
        path = _metadata_path(destination)
        state_temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        if state_temporary.exists():
            state_temporary.unlink()
        if destination.exists() and (old_root is None or moved_root):
            destination.unlink()
        if moved_root and old_root is not None and backup_root.exists():
            backup_root.replace(old_root)
        if moved_metadata and old_metadata is not None and backup_metadata.exists():
            backup_metadata.replace(old_metadata)
        raise
    if backup_root.exists():
        if backup_root.is_dir():
            _remove_private_tree(backup_root, library, f".{safe_id}.replaced-")
        else:
            backup_root.unlink()
    backup_metadata.unlink(missing_ok=True)
    return next(row for row in catalog(project_root, mods_root)
                if row["id"] == incoming["id"])


def delete_mod(project_root: Path, mods_root: Path, mod_id: str) -> dict:
    """Delete exactly one managed mod. The selected editable project is protected."""
    rows = catalog(project_root, mods_root)
    row = next((candidate for candidate in rows if candidate["id"] == mod_id), None)
    if row is None:
        raise ValueError(f"Unknown FF8 managed mod: {mod_id}")
    if row["selected"]:
        raise ValueError("The selected editable mod cannot be deleted from the load order")
    library = Path(mods_root).resolve()
    target = Path(row["path"]).resolve()
    if target.parent != library:
        raise RuntimeError("Refusing to delete a mod outside the managed FF8 library")
    metadata = _metadata_path(target)
    target_was_file = target.is_file()
    token = hashlib.sha256(f"{target}:{os.getpid()}".encode()).hexdigest()[:12]
    staged_target = library / f".{target.name}.deleting-{token}"
    staged_metadata = library / f".{target.name}.deleting-{token}.json"
    target.replace(staged_target)
    metadata_moved = False
    try:
        if target_was_file and metadata.exists():
            metadata.replace(staged_metadata)
            metadata_moved = True
    except Exception:
        staged_target.replace(target)
        raise
    try:
        if staged_target.is_dir():
            _remove_private_tree(staged_target, library, f".{target.name}.deleting-")
        else:
            staged_target.unlink()
        if metadata_moved:
            staged_metadata.unlink()
    except Exception:
        if staged_target.exists() and not target.exists():
            staged_target.replace(target)
        if metadata_moved and staged_metadata.exists() and not metadata.exists():
            staged_metadata.replace(metadata)
        raise
    return row


def root_for_mod(project_root: Path, mods_root: Path, mod_id: str) -> Path:
    """Resolve one catalog id without accepting an arbitrary filesystem path."""
    match = next((row for row in catalog(project_root, mods_root)
                  if row["id"] == mod_id), None)
    if match is None:
        raise ValueError(f"Unknown FF8 managed mod: {mod_id}")
    root = Path(match["path"])
    return _materialize_iroj(root, Path(mods_root), mod_id) if root.is_file() else root


def _materialize_iroj(source: Path, mods_root: Path, mod_id: str) -> Path:
    """Expose an archive as a read-only dataset for the existing FF8 readers."""
    archive_hash = _sha256(source)
    cache_parent = Path(mods_root).resolve() / IROJ_CACHE_FOLDER
    target = cache_parent / archive_hash
    marker = target / ".complete"
    if marker.is_file() and marker.read_text(encoding="ascii", errors="ignore") == archive_hash:
        return target
    cache_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{archive_hash}.staging-", dir=cache_parent))
    try:
        archive = iroj_archive.Archive(source)
        for member in archive.names():
            parts = member.split("/")
            if len(parts) < 2 or parts[0].casefold() not in SOURCE_FOLDERS:
                continue
            destination = staging / parts[0].casefold() / Path(*parts[1:])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))
        (staging / MOD_FILE).write_text(json.dumps({
            "id": mod_id, "name": mod_id, "readOnly": True,
            "sourceArchive": str(source.resolve()), "sha256": archive_hash,
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
        (staging / ".complete").write_text(archive_hash, encoding="ascii")
        if target.exists():
            _remove_private_tree(target, cache_parent, archive_hash)
        staging.replace(target)
    except Exception:
        if staging.exists():
            _remove_private_tree(staging, cache_parent, f".{archive_hash}.staging-")
        raise
    return target


def _package_entries(root: Path, archive: iroj_archive.Archive | None) -> tuple[list[str], object]:
    """Return safe package-relative names and a byte reader."""
    if archive is not None:
        names = list(archive.names())
        return names, archive.read
    names = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*") if path.is_file()
    ]
    by_name = {name.casefold(): root / Path(*_path_parts(name)) for name in names}

    def read(name: str) -> bytes:
        return by_name[name.casefold()].read_bytes()

    return names, read


def _path_parts(value: str) -> tuple[str, ...]:
    """Convert a validated package name without accepting a host separator."""
    parts = tuple(part for part in value.replace("\\", "/").split("/") if part)
    if not parts or any(part in (".", "..") or ":" in part for part in parts):
        raise ValueError(f"Unsafe FF8 mod package path: {value}")
    return parts


def _resolved_mod_sources(mod: dict, archive: iroj_archive.Archive | None,
                          condition_state: dict | None) -> tuple[
                              dict[str, tuple[object, str]], dict,
                              dict[str, list[tuple[object, str, list[dict]]]],
                              dict[str, tuple[object, str]],
                          ]:
    """Resolve root, option, and safe pre-launch conditional layers in one mod."""
    root = Path(mod["path"]).resolve()
    names, read = _package_entries(root, archive)
    mod_xml = read("mod.xml") if any(name.casefold() == "mod.xml" for name in names) else None
    try:
        rules = mod_folders.parse(mod_xml)
        layers, report, options = mod_folders.select_layers(
            rules, mod.get("folderOptions"), condition_state,
        )
    except mod_folders.FolderMetadataError as error:
        rules, layers, options = mod_folders.PackageRules(), [], {}
        report = [{
            "folder": "", "kind": "metadata", "active": False,
            "reason": str(error), "filesActive": 0, "filesInactive": 0,
        }]

    # The ordinary package roots are always the base layer.  This differs from
    # Junction's profile wrapper on purpose: Lexeditor resolves special layers
    # inside one mod, then merges that result into its own global priority list.
    candidates: list[tuple[str, mod_folders.FolderLayer | None]] = [("", None)]
    candidates.extend((layer.folder, layer) for layer in layers)
    resolved: dict[str, tuple[object, str]] = {}
    static_resolved: dict[str, tuple[object, str]] = {}
    live_sources: dict[str, list[tuple[object, str, list[dict]]]] = {}
    report_by_key = {(row["kind"], row["folder"]): row for row in report}
    for prefix, layer in candidates:
        marker = (prefix.rstrip("/") + "/").casefold() if prefix else ""
        active_count = 0
        inactive_count = 0
        reasons: set[str] = set()
        for name in sorted(names, key=str.casefold):
            normalized = name.replace("\\", "/").strip("/")
            if prefix:
                if not normalized.casefold().startswith(marker):
                    continue
                target = normalized[len(marker):]
            else:
                # A root layer includes only direct recognized roots.  Files
                # below a named variant folder cannot leak into this layer.
                target = normalized
            parts = _path_parts(target)
            if len(parts) < 2 or parts[0].casefold() not in SOURCE_FOLDERS:
                continue
            # FF8 and FFNx run on the Windows case-insensitive filesystem.
            # One mod's Foo.bin and another's foo.bin are the same conflict.
            key = "/".join((parts[0], *parts[1:])).casefold()
            if layer is not None:
                active, reason = mod_folders.condition_for_file(
                    layer, key, rules, condition_state,
                )
                if not active:
                    inactive_count += 1
                    if reason:
                        reasons.add(reason)
                    continue
            active_count += 1
            resolved[key] = (lambda item=name, source=read: source(item), prefix or "base")
            if layer is None or layer.kind != "runtime":
                static_resolved[key] = resolved[key]
        if layer is not None:
            row = report_by_key[(layer.kind, layer.folder)]
            row["filesActive"] = active_count
            row["filesInactive"] = inactive_count
            if reasons:
                row["active"] = active_count > 0
                row["reason"] = "; ".join(sorted(reasons))

    # Preserve every active runtime folder candidate and its parsed condition.
    # The current materialized output still fails closed for process-memory,
    # counter and random values.  These copies are inert evidence/input for a
    # future FFNx lookup hook; they never bypass Lexeditor's composer.
    active_layers = {id(layer) for layer in layers if layer.kind == "runtime"}
    for layer in rules.conditionals:
        if id(layer) not in active_layers:
            continue
        marker = (layer.folder.rstrip("/") + "/").casefold()
        for name in sorted(names, key=str.casefold):
            normalized = name.replace("\\", "/").strip("/")
            if not normalized.casefold().startswith(marker):
                continue
            target = normalized[len(marker):]
            parts = _path_parts(target)
            if len(parts) < 2 or parts[0].casefold() not in SOURCE_FOLDERS:
                continue
            key = "/".join((parts[0], *parts[1:])).casefold()
            program = mod_folders.runtime_program(layer, key, rules)
            if program is None:
                continue
            live_sources.setdefault(key, []).append(
                (lambda item=name, source=read: source(item), layer.folder, program)
            )
    return resolved, {
        "mod": mod["id"], "options": options, "layers": report,
        "liveMemoryConditions": "preserved for managed FFNx final-variant evaluation",
    }, live_sources, static_resolved


def _runtime_program_error(program: object) -> str:
    """Validate the inert postfix format before it enters a route manifest."""
    if not isinstance(program, list) or not program:
        return "Runtime condition program is empty or is not a list"
    if len(program) > mod_folders.MAX_RUNTIME_PROGRAM_TOKENS:
        return f"Runtime condition exceeds {mod_folders.MAX_RUNTIME_PROGRAM_TOKENS} tokens"
    depth = 0
    for token in program:
        if not isinstance(token, dict):
            return "Runtime condition token is not an object"
        operation = token.get("op")
        if operation == "unsupported":
            return str(token.get("reason") or "Unsupported runtime condition")
        if operation == "var":
            if set(token) != {"op", "spec", "values"}:
                return "Runtime variable token has unexpected fields"
            if not isinstance(token.get("spec"), str) or not token["spec"].strip():
                return "Runtime variable has no specification"
            if not isinstance(token.get("values"), str) or not token["values"].strip():
                return "Runtime variable has no comparison values"
            spec_error = _runtime_spec_error(token["spec"], token["values"])
            if spec_error:
                return spec_error
            depth += 1
            continue
        if operation not in {"not", "and", "or"}:
            return f"Unsupported runtime operation: {operation}"
        arity = token.get("arity")
        expected = 1 if operation == "not" else arity
        if (not isinstance(arity, int) or isinstance(arity, bool)
                or arity < 1 or (operation == "not" and arity != 1)):
            return f"Runtime {operation} token has invalid arity"
        if depth < expected:
            return f"Runtime {operation} token underflows the postfix stack"
        depth = depth - expected + 1
    return "" if depth == 1 else "Runtime condition does not leave one postfix result"


def _runtime_spec_error(spec: str, values: str) -> str:
    """Validate the Junction-compatible variable shape without reading it."""
    parts = spec.split(":")
    kind = parts[0].casefold()
    numeric_memory = {"byte", "short", "int"}
    stateful = {
        "counter", "counteradv", "counterrnd", "random", "randomvaronce",
    }
    if kind == "sys":
        if len(parts) != 2 or parts[1].casefold() not in {
                name.casefold() for name in mod_folders.SYSTEM_FIELDS}:
            return f"Invalid Sys runtime variable: {spec}"
    elif kind in numeric_memory:
        if len(parts) not in {2, 3}:
            return f"Invalid {parts[0]} runtime variable: {spec}"
        try:
            address = int(parts[1], 0)
            if address < 0:
                raise ValueError
            if len(parts) == 3:
                int(parts[2], 0)
        except ValueError:
            return f"Invalid {parts[0]} address or mask: {spec}"
    elif kind == "ffstring":
        try:
            valid = len(parts) == 3 and int(parts[1], 0) >= 0 and int(parts[2], 0) > 0
        except ValueError:
            valid = False
        if not valid:
            return f"Invalid FFString runtime variable: {spec}"
        return "" if any(value.strip() for value in values.split("|")) else (
            "FFString runtime variable has no comparison value"
        )
    elif kind in stateful or kind == "randomvar":
        expected_lengths = {3, 4} if kind == "randomvar" else {3}
        try:
            valid = (len(parts) in expected_lengths and bool(parts[1])
                     and int(parts[2], 0) > 0
                     and (len(parts) < 4 or int(parts[3], 0) >= 0))
        except ValueError:
            valid = False
        if not valid:
            return f"Invalid {parts[0]} runtime variable: {spec}"
    else:
        return f"Unsupported runtime variable type: {parts[0]}"
    try:
        mod_folders._compare(0, values)
    except (ValueError, mod_folders.FolderMetadataError):
        return f"Runtime variable has invalid comparison values: {values}"
    return ""


def _compose_logical_payload(logical_path: str,
                             inputs: list[tuple[str, bytes]],
                             baseline_root: Path | None,
                             kernel_definitions: dict[int, dict] | None,
                             fallback: bytes | None) -> tuple[bytes | None, str, list[dict]]:
    """Compose one complete path for one live-condition outcome."""
    if not inputs:
        return fallback, "pass-through" if fallback is None else "unconditional", []
    if logical_path == "direct/kernel.bin" and baseline_root is not None:
        baseline = Path(baseline_root) / "main" / "kernel.bin"
        if baseline.is_file() and kernel_definitions is not None:
            merged, conflicts = kernel_merge.merge(
                baseline.read_bytes(), inputs, kernel_definitions)
            return merged, "semantic merge", conflicts
    spec = fixed_data_merge.SPECS.get(logical_path)
    if spec is not None and baseline_root is not None:
        baseline = Path(baseline_root) / spec["baseline"]
        if baseline.is_file():
            merged, conflicts = fixed_data_merge.merge(
                baseline.read_bytes(), inputs, spec, logical_path)
            return merged, "semantic merge", conflicts
    if logical_path == "direct/menu/mngrp.bin" and baseline_root is not None:
        baseline = Path(baseline_root) / "menu" / "mngrp.bin"
        if baseline.is_file():
            merged, conflicts, reason = mngrp_merge.merge(
                baseline.read_bytes(), inputs, logical_path)
            if merged is not None:
                return merged, "semantic merge", conflicts
            return inputs[-1][1], f"opaque winner: {reason}", []
    world_spec = WORLD_MERGE_SPECS.get(logical_path)
    if world_spec is not None and baseline_root is not None:
        baseline = Path(baseline_root) / world_spec[0]
        if baseline.is_file():
            merged, conflicts, reason = world_data_merge.merge(
                baseline.read_bytes(), inputs, world_spec[1], logical_path)
            if merged is not None:
                return merged, "semantic merge", conflicts
            return inputs[-1][1], f"opaque winner: {reason}", []
    encounter_baseline = _field_encounter_baseline(logical_path, baseline_root)
    if encounter_baseline is not None:
        baseline, kind = encounter_baseline
        merge = (field_encounters.merge_mrt if kind == "mrt"
                 else field_encounters.merge_rat)
        merged, conflicts, reason = merge(
            baseline.read_bytes(), inputs, logical_path)
        if merged is not None:
            return merged, "semantic merge", conflicts
        return inputs[-1][1], f"opaque winner: {reason}", []
    background_baseline = _field_background_baseline(logical_path, baseline_root)
    if background_baseline is not None:
        baseline_map, baseline_mim = background_baseline
        merged, conflicts, reason = field_background.merge(
            baseline_map.read_bytes(), baseline_mim.read_bytes(), inputs, logical_path)
        if merged is not None:
            return merged, "semantic merge", conflicts
        return inputs[-1][1], f"opaque winner: {reason}", []
    walkmesh_baseline = _field_walkmesh_baseline(logical_path, baseline_root)
    if walkmesh_baseline is not None:
        merged, conflicts, reason = field_walkmesh.merge(
            walkmesh_baseline.read_bytes(), inputs, logical_path)
        if merged is not None:
            return merged, "semantic merge", conflicts
        return inputs[-1][1], f"opaque winner: {reason}", []
    return inputs[-1][1], "opaque winner", []


def _precompose_live_routes(staging: Path, enabled: list[dict],
                            static_by_mod: dict[str, dict[str, tuple[object, str]]],
                            resolved_by_mod: dict[str, dict[str, tuple[object, str]]],
                            live_by_mod: dict[str, dict[str, list[tuple[object, str, list[dict]]]]],
                            baseline_root: Path | None,
                            kernel_definitions: dict[int, dict] | None) -> list[dict]:
    """Enumerate bounded outcomes and emit only complete final files.

    The route data remains inert until the FFNx derivative has a guarded live
    evaluator.  No route points at a package candidate.
    """
    affected = sorted({path for paths in live_by_mod.values() for path in paths})
    routes: list[dict] = []
    input_count = 0
    input_bytes = 0
    output_count = 0
    output_bytes = 0
    total_variants = 0
    live_root = staging / Path(*_path_parts(LIVE_CONDITIONAL_ROOT))
    for logical_path in affected:
        route: dict = {
            "routeVersion": 1,
            "logicalPath": logical_path,
            "status": "ready: final variants precomposed",
            "outcomeEncoding": "condition-id bitmask, least-significant bit first",
            "conditions": [],
            "variants": [],
        }
        root_name = _path_parts(logical_path)[0].casefold()
        if root_name not in LIVE_CONDITIONAL_ROOTS:
            route["status"] = f"inactive: no proved live lookup seam for {root_name}"
            routes.append(route)
            continue

        # Equal postfix programs represent one boolean result.  This prevents
        # impossible variants in which the same condition is both true and
        # false, and keeps the outcome space bounded by distinct conditions.
        program_ids: dict[str, int] = {}
        candidate_rows: list[dict] = []
        rejected: list[dict] = []
        for mod_order, mod in enumerate(enabled):
            for candidate_order, (read_source, folder, program) in enumerate(
                    live_by_mod[mod["id"]].get(logical_path, [])):
                input_count += 1
                if input_count > MAX_LIVE_CONDITIONAL_INPUTS:
                    raise ValueError(
                        "FF8 live conditional folders exceed the 4096-input safety limit"
                    )
                error = _runtime_program_error(program)
                if error:
                    rejected.append({"mod": mod["id"], "folder": folder, "reason": error})
                    continue
                canonical = json.dumps(program, sort_keys=True, separators=(",", ":"))
                condition_id = program_ids.setdefault(canonical, len(program_ids))
                candidate_rows.append({
                    "mod": mod["id"], "modOrder": mod_order,
                    "candidateOrder": candidate_order, "folder": folder,
                    "condition": condition_id, "read": read_source,
                })
        route["conditions"] = [
            {"id": condition_id, "program": json.loads(canonical)}
            for canonical, condition_id in sorted(program_ids.items(), key=lambda row: row[1])
        ]
        if rejected:
            route["rejected"] = rejected
        condition_count = len(program_ids)
        if condition_count > MAX_LIVE_CONDITIONS_PER_PATH:
            raise ValueError(
                f"FF8 live conditional path {logical_path} exceeds the "
                f"{MAX_LIVE_CONDITIONS_PER_PATH}-condition safety limit"
            )
        variant_count = 1 << condition_count
        if variant_count > MAX_LIVE_VARIANTS_PER_PATH:
            raise ValueError(
                f"FF8 live conditional path {logical_path} exceeds the "
                f"{MAX_LIVE_VARIANTS_PER_PATH}-variant safety limit"
            )
        total_variants += variant_count
        if total_variants > MAX_LIVE_VARIANTS_TOTAL:
            raise ValueError(
                f"FF8 live conditional folders exceed the "
                f"{MAX_LIVE_VARIANTS_TOTAL}-variant total safety limit"
            )

        payload_cache: dict[int, bytes] = {}
        ordinary_by_mod = {
            mod["id"]: static_by_mod[mod["id"]].get(logical_path)
            for mod in enabled
        }
        fallback_path = staging / Path(*_path_parts(logical_path))
        fallback = fallback_path.read_bytes() if fallback_path.is_file() else None
        emitted_assets: dict[str, str] = {}
        suffix = Path(logical_path).suffix or ".bin"
        for outcome in range(variant_count):
            inputs: list[tuple[str, bytes]] = []
            selected: list[dict] = []
            for mod in enabled:
                source = ordinary_by_mod[mod["id"]]
                selected_source = source[0]() if source is not None else None
                selected_folder = source[1] if source is not None else ""
                for index, candidate in enumerate(candidate_rows):
                    if candidate["mod"] != mod["id"]:
                        continue
                    if outcome & (1 << candidate["condition"]):
                        if index not in payload_cache:
                            payload = candidate["read"]()
                            input_bytes += len(payload)
                            if input_bytes > MAX_LIVE_CONDITIONAL_BYTES:
                                raise ValueError(
                                    "FF8 live conditional folders exceed the 256 MiB input safety limit"
                                )
                            payload_cache[index] = payload
                        selected_source = payload_cache[index]
                        selected_folder = candidate["folder"]
                if selected_source is not None:
                    inputs.append((mod["id"], selected_source))
                    selected.append({"mod": mod["id"], "folder": selected_folder})
            payload, mode, conflicts = _compose_logical_payload(
                logical_path, inputs, baseline_root, kernel_definitions, fallback)
            variant = {"outcome": outcome, "mode": mode, "sources": selected}
            if conflicts:
                variant["conflicts"] = conflicts
            if payload is None:
                variant["passThrough"] = True
            else:
                digest = hashlib.sha256(payload).hexdigest()
                asset = emitted_assets.get(digest)
                if asset is None:
                    output_count += 1
                    output_bytes += len(payload)
                    if output_count > MAX_LIVE_CONDITIONAL_OUTPUTS:
                        raise ValueError(
                            "FF8 live conditional folders exceed the 4096-output safety limit"
                        )
                    if output_bytes > MAX_LIVE_CONDITIONAL_BYTES:
                        raise ValueError(
                            "FF8 live conditional folders exceed the 256 MiB output safety limit"
                        )
                    destination = live_root / f"{digest[:24]}{suffix}"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(payload)
                    asset = destination.relative_to(staging / "direct").as_posix()
                    emitted_assets[digest] = asset
                variant["asset"] = asset
                variant["sha256"] = digest
            route["variants"].append(variant)
        fallback_inputs = []
        for mod in enabled:
            source = resolved_by_mod[mod["id"]].get(logical_path)
            if source is not None:
                fallback_inputs.append((mod["id"], source[0]()))
        fallback_payload, fallback_mode, fallback_conflicts = _compose_logical_payload(
            logical_path, fallback_inputs, baseline_root, kernel_definitions, fallback)
        route_fallback: dict = {"mode": fallback_mode}
        if fallback_conflicts:
            route_fallback["conflicts"] = fallback_conflicts
        if fallback_payload is None:
            route_fallback["passThrough"] = True
        else:
            fallback_digest = hashlib.sha256(fallback_payload).hexdigest()
            fallback_asset = emitted_assets.get(fallback_digest)
            if fallback_asset is None:
                output_count += 1
                output_bytes += len(fallback_payload)
                if output_count > MAX_LIVE_CONDITIONAL_OUTPUTS:
                    raise ValueError(
                        "FF8 live conditional folders exceed the 4096-output safety limit"
                    )
                if output_bytes > MAX_LIVE_CONDITIONAL_BYTES:
                    raise ValueError(
                        "FF8 live conditional folders exceed the 256 MiB output safety limit"
                    )
                destination = live_root / f"{fallback_digest[:24]}{suffix}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(fallback_payload)
                fallback_asset = destination.relative_to(staging / "direct").as_posix()
                emitted_assets[fallback_digest] = fallback_asset
            route_fallback["asset"] = fallback_asset
            route_fallback["sha256"] = fallback_digest
        route["fallback"] = route_fallback
        if not candidate_rows:
            route["status"] = "inactive: every live condition was rejected"
        routes.append(route)
    return routes


def compose(project_root: Path, runtime_root: Path,
            mod_rows: list[dict] | None = None,
            baseline_root: Path | None = None,
            kernel_definitions: dict[int, dict] | None = None,
            condition_state: dict | None = None) -> dict:
    """Atomically compose enabled mods from low to high priority."""
    project = Path(project_root).resolve()
    active = Path(runtime_root).resolve()
    supplied_state = condition_state if isinstance(condition_state, dict) else {}
    frozen_condition_state = {
        "system": (dict(supplied_state["system"])
                   if isinstance(supplied_state.get("system"), dict)
                   else mod_folders.system_state()),
        "ffnx": (dict(supplied_state["ffnx"])
                 if isinstance(supplied_state.get("ffnx"), dict) else {}),
    }
    if active == project or active in project.parents:
        raise ValueError("The FF8 runtime and editable mod must be separate folders")
    parent = active.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{active.name}.staging-", dir=parent))
    previous = parent / f".{active.name}.previous-{os.getpid()}"
    mods = mod_rows if mod_rows is not None else [_metadata(project, selected=True)]
    enabled = [row for row in mods if row.get("enabled") is True]
    claims: dict[str, list[str]] = {}
    try:
        for folder_name in SOURCE_FOLDERS:
            (staging / folder_name).mkdir(parents=True, exist_ok=True)
        archive_cache: dict[Path, iroj_archive.Archive] = {}
        materialized_sources: dict[str, tuple[str, str]] = {}
        resolved_by_mod: dict[str, dict[str, tuple[object, str]]] = {}
        static_by_mod: dict[str, dict[str, tuple[object, str]]] = {}
        live_by_mod: dict[str, dict[str, list[tuple[object, str, list[dict]]]]] = {}
        folder_reports: list[dict] = []
        for mod_order, mod in enumerate(enabled):
            mod_root = Path(mod["path"]).resolve()
            archive = (archive_cache.setdefault(mod_root, iroj_archive.Archive(mod_root))
                       if mod_root.is_file() else None)
            sources, folder_report, live_sources, static_sources = _resolved_mod_sources(
                mod, archive, frozen_condition_state)
            resolved_by_mod[mod["id"]] = sources
            static_by_mod[mod["id"]] = static_sources
            live_by_mod[mod["id"]] = live_sources
            folder_reports.append(folder_report)
            for key, (read_source, layer_name) in sorted(
                    sources.items(), key=lambda row: row[0].casefold()):
                claims.setdefault(key, []).append(mod["id"])
                relative = Path(*_path_parts(key))
                output_relative = _hext_runtime_path(relative, mod_order, mod["id"])
                output_key = output_relative.as_posix()
                materialized_sources[output_key] = (key, mod["id"])
                destination = staging / output_relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(read_source())

        # Every live outcome is composed through the same low-to-high merger
        # as the unconditional output.  The inert manifest never redirects to
        # a raw package candidate.
        live_routes = _precompose_live_routes(
            staging, enabled, static_by_mod, resolved_by_mod, live_by_mod,
            baseline_root, kernel_definitions,
        )
        live_manifest = staging / Path(*_path_parts(LIVE_CONDITIONAL_MANIFEST))
        live_manifest.parent.mkdir(parents=True, exist_ok=True)
        live_manifest.write_text(json.dumps({
            "schemaVersion": 1,
            "liveConditionalRoutes": live_routes,
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
        semantic_conflicts_by_path: dict[str, list[dict]] = {}
        semantic_fallback_by_path: dict[str, str] = {}
        semantic_merged: set[str] = set()
        kernel_key = "direct/kernel.bin"
        kernel_claimants = claims.get(kernel_key, [])
        if (len(kernel_claimants) > 1 and baseline_root is not None
                and kernel_definitions is not None):
            baseline = Path(baseline_root) / "main" / "kernel.bin"
            if baseline.is_file():
                inputs = []
                for mod in enabled:
                    source = resolved_by_mod[mod["id"]].get(kernel_key)
                    if source is not None:
                        inputs.append((mod["id"], source[0]()))
                merged, semantic_conflicts = kernel_merge.merge(
                    baseline.read_bytes(), inputs, kernel_definitions)
                (staging / kernel_key).write_bytes(merged)
                semantic_merged.add(kernel_key)
                semantic_conflicts_by_path[kernel_key] = semantic_conflicts
        if baseline_root is not None:
            for direct_key, spec in fixed_data_merge.SPECS.items():
                claimants = claims.get(direct_key, [])
                baseline = Path(baseline_root) / spec["baseline"]
                if len(claimants) < 2 or not baseline.is_file():
                    continue
                inputs = []
                for mod in enabled:
                    source = resolved_by_mod[mod["id"]].get(direct_key)
                    if source is not None:
                        inputs.append((mod["id"], source[0]()))
                merged, unit_conflicts = fixed_data_merge.merge(
                    baseline.read_bytes(), inputs, spec, direct_key)
                (staging / direct_key).write_bytes(merged)
                semantic_merged.add(direct_key)
                semantic_conflicts_by_path[direct_key] = unit_conflicts
            mngrp_key = "direct/menu/mngrp.bin"
            mngrp_claimants = claims.get(mngrp_key, [])
            mngrp_baseline = Path(baseline_root) / "menu" / "mngrp.bin"
            if len(mngrp_claimants) > 1 and mngrp_baseline.is_file():
                inputs = []
                for mod in enabled:
                    source = resolved_by_mod[mod["id"]].get(mngrp_key)
                    if source is not None:
                        inputs.append((mod["id"], source[0]()))
                merged, unit_conflicts, fallback = mngrp_merge.merge(
                    mngrp_baseline.read_bytes(), inputs, mngrp_key)
                if merged is not None:
                    (staging / mngrp_key).write_bytes(merged)
                    semantic_merged.add(mngrp_key)
                    semantic_conflicts_by_path[mngrp_key] = unit_conflicts
                else:
                    semantic_fallback_by_path[mngrp_key] = fallback
            for world_key, (baseline_name, kind) in WORLD_MERGE_SPECS.items():
                world_claimants = claims.get(world_key, [])
                world_baseline = Path(baseline_root) / baseline_name
                if len(world_claimants) < 2 or not world_baseline.is_file():
                    continue
                inputs = []
                for mod in enabled:
                    source = resolved_by_mod[mod["id"]].get(world_key)
                    if source is not None:
                        inputs.append((mod["id"], source[0]()))
                merged, unit_conflicts, fallback = world_data_merge.merge(
                    world_baseline.read_bytes(), inputs, kind, world_key)
                if merged is not None:
                    (staging / world_key).write_bytes(merged)
                    semantic_merged.add(world_key)
                    semantic_conflicts_by_path[world_key] = unit_conflicts
                else:
                    semantic_fallback_by_path[world_key] = fallback
            for encounter_key, encounter_claimants in claims.items():
                encounter_baseline = _field_encounter_baseline(
                    encounter_key, baseline_root)
                if len(encounter_claimants) < 2 or encounter_baseline is None:
                    continue
                inputs = []
                for mod in enabled:
                    source = resolved_by_mod[mod["id"]].get(encounter_key)
                    if source is not None:
                        inputs.append((mod["id"], source[0]()))
                baseline, kind = encounter_baseline
                merge = (field_encounters.merge_mrt if kind == "mrt"
                         else field_encounters.merge_rat)
                merged, unit_conflicts, fallback = merge(
                    baseline.read_bytes(), inputs, encounter_key)
                if merged is not None:
                    (staging / encounter_key).write_bytes(merged)
                    semantic_merged.add(encounter_key)
                    semantic_conflicts_by_path[encounter_key] = unit_conflicts
                else:
                    semantic_fallback_by_path[encounter_key] = fallback
            for background_key, background_claimants in claims.items():
                background_baseline = _field_background_baseline(
                    background_key, baseline_root)
                if len(background_claimants) < 2 or background_baseline is None:
                    continue
                mim_key = background_key[:-4] + ".mim"
                if claims.get(mim_key):
                    semantic_fallback_by_path[background_key] = (
                        "a field MIM override makes baseline MAP semantics unsafe")
                    continue
                inputs = []
                for mod in enabled:
                    source = resolved_by_mod[mod["id"]].get(background_key)
                    if source is not None:
                        inputs.append((mod["id"], source[0]()))
                baseline_map, baseline_mim = background_baseline
                merged, unit_conflicts, fallback = field_background.merge(
                    baseline_map.read_bytes(), baseline_mim.read_bytes(),
                    inputs, background_key)
                if merged is not None:
                    (staging / background_key).write_bytes(merged)
                    semantic_merged.add(background_key)
                    semantic_conflicts_by_path[background_key] = unit_conflicts
                else:
                    semantic_fallback_by_path[background_key] = fallback
            for walkmesh_key, walkmesh_claimants in claims.items():
                walkmesh_baseline = _field_walkmesh_baseline(
                    walkmesh_key, baseline_root)
                if len(walkmesh_claimants) < 2 or walkmesh_baseline is None:
                    continue
                inputs = []
                for mod in enabled:
                    source = resolved_by_mod[mod["id"]].get(walkmesh_key)
                    if source is not None:
                        inputs.append((mod["id"], source[0]()))
                merged, unit_conflicts, fallback = field_walkmesh.merge(
                    walkmesh_baseline.read_bytes(), inputs, walkmesh_key)
                if merged is not None:
                    (staging / walkmesh_key).write_bytes(merged)
                    semantic_merged.add(walkmesh_key)
                    semantic_conflicts_by_path[walkmesh_key] = unit_conflicts
                else:
                    semantic_fallback_by_path[walkmesh_key] = fallback
        files = _files(staging)
        conflicts = [
            {"path": path, "winner": ("ordered runtime patches"
                                        if path.casefold().startswith("hext/")
                                        else "semantic merge" if path in semantic_merged
                                        else claimants[-1]),
             "claimants": claimants,
             **({"mode": "low-to-high patch stream"}
                if path.casefold().startswith("hext/") else {}),
             **({"units": semantic_conflicts_by_path[path]}
                if semantic_conflicts_by_path.get(path) else {}),
             **({"semanticFallback": semantic_fallback_by_path[path]}
                if path in semantic_fallback_by_path else {})}
            for path, claimants in sorted(claims.items()) if len(claimants) > 1
        ]
        manifest = {
            "version": 1,
            "composedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mods": enabled,
            "folderSelection": folder_reports,
            "conditionState": frozen_condition_state,
            "liveConditionalRoutes": live_routes,
            "files": [],
            "conflicts": conflicts,
        }
        for row in files:
            source_path, materialized_owner = materialized_sources.get(
                row["path"], (row["path"], ""))
            is_hext = source_path.casefold().startswith("hext/")
            entry = {
                **row,
                "winner": (materialized_owner if is_hext else
                           "semantic merge" if source_path in semantic_merged else
                           claims[source_path][-1]),
                "claimants": ([materialized_owner] if is_hext else claims[source_path]),
            }
            if source_path != row["path"]:
                entry["sourcePath"] = source_path
                entry["loadOrder"] = int(Path(row["path"]).name.split("__", 1)[0])
            manifest["files"].append(entry)
        (staging / COMPOSITION_FILE).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n",
        )
        if previous.exists():
            _remove_private_tree(previous, parent, f".{active.name}.previous-")
        if active.exists():
            active.replace(previous)
        try:
            staging.replace(active)
        except Exception:
            if previous.exists() and not active.exists():
                previous.replace(active)
            raise
        if previous.exists():
            _remove_private_tree(previous, parent, f".{active.name}.previous-")
        return {
            "runtimeRoot": str(active),
            "directRoot": str(active / "direct"),
            "hextRoot": str(active / "hext"),
            "projectRoot": str(project),
            "fileCount": len(files),
            "conflicts": conflicts,
            "manifest": str(active / COMPOSITION_FILE),
            "folderSelection": folder_reports,
        }
    except Exception:
        if staging.exists():
            _remove_private_tree(staging, parent, f".{active.name}.staging-")
        raise


def read(runtime_root: Path) -> dict:
    path = Path(runtime_root) / COMPOSITION_FILE
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}
