"""Content Patcher project editing and reversible deployment for Stardew Valley."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

OBJECT_TARGET = "Data/Objects"
OBJECT_FIELDS = {"Price", "Edibility", "IsDrink"}
DEPLOY_MARKER = ".lexeditor-deployment.json"
ACCEPTANCE_MARKER = ".lexeditor-stardew-acceptance.json"
MIN_CONTENT_PATCHER_VERSION = "2.9.0"
MAX_JSON_BYTES = 8 * 1024 * 1024


def _json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f"Content pack JSON is too large to edit safely: {path}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                     dir=path.parent, prefix=path.name + ".",
                                     suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _version_tuple(value: str | None) -> tuple[int, ...] | None:
    if not value:
        return None
    match = re.match(r"^(\d+(?:\.\d+){1,3})", str(value).strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _version_at_least(actual: str | None, minimum: str) -> bool:
    actual_parts = _version_tuple(actual)
    minimum_parts = _version_tuple(minimum)
    if actual_parts is None or minimum_parts is None:
        return False
    width = max(len(actual_parts), len(minimum_parts))
    return actual_parts + (0,) * (width - len(actual_parts)) >= minimum_parts + (0,) * (width - len(minimum_parts))


def _object_change(payload: dict, *, create: bool) -> dict | None:
    changes = payload.get("Changes")
    if changes is None and create:
        changes = []
        payload["Changes"] = changes
    if not isinstance(changes, list):
        raise ValueError("content.json Changes must be an array")
    for change in changes:
        if not isinstance(change, dict):
            continue
        action = str(change.get("Action", "")).casefold()
        target = change.get("Target")
        if action == "editdata" and target == OBJECT_TARGET and isinstance(change.get("Fields", {}), dict):
            change.setdefault("Fields", {})
            return change
    if not create:
        return None
    change = {"Action": "EditData", "Target": OBJECT_TARGET, "Fields": {}}
    changes.append(change)
    return change


class ContentPackStore:
    """Edit only Lexeditor-supported fields while preserving the rest of content.json."""

    def __init__(self, project_root: Path):
        self.root = Path(project_root).expanduser().resolve()
        self.content_path = self.root / "content.json"
        self.manifest_path = self.root / "manifest.json"

    def validate(self) -> None:
        manifest = _json(self.manifest_path)
        content_pack_for = manifest.get("ContentPackFor")
        if not isinstance(content_pack_for, dict) or content_pack_for.get("UniqueID") != "Pathoschild.ContentPatcher":
            raise ValueError("manifest.json is not a Content Patcher content pack")
        content = _json(self.content_path)
        if not isinstance(content.get("Changes", []), list):
            raise ValueError("content.json Changes must be an array")

    def objects(self) -> dict:
        self.validate()
        payload = _json(self.content_path)
        change = _object_change(payload, create=False)
        fields = change.get("Fields", {}) if change else {}
        rows = []
        for object_id, values in fields.items():
            if not isinstance(values, dict):
                continue
            supported = {key: values[key] for key in OBJECT_FIELDS if key in values}
            rows.append({
                "id": str(object_id),
                "fields": supported,
                "present": sorted(supported),
                "unsupportedFieldCount": len(values) - len(supported),
            })
        rows.sort(key=lambda row: row["id"].casefold())
        return {
            "asset": OBJECT_TARGET,
            "sha256": _sha256(self.content_path),
            "rows": rows,
            "editableFields": ["Price", "Edibility", "IsDrink"],
            "source": "project-patches",
        }

    def save_objects(self, expected_sha256: str, edits: list[dict]) -> dict:
        self.validate()
        if not isinstance(expected_sha256, str) or not expected_sha256:
            raise ValueError("A source SHA-256 is required")
        current = _sha256(self.content_path)
        if current != expected_sha256:
            raise RuntimeError("content.json changed since it was opened; reload before saving")
        if not isinstance(edits, list) or len(edits) > 10000:
            raise ValueError("edits must be a bounded array")
        payload = _json(self.content_path)
        change = _object_change(payload, create=True)
        assert change is not None
        records = change["Fields"]
        for edit in edits:
            if not isinstance(edit, dict):
                raise ValueError("Each object edit must be an object")
            object_id = str(edit.get("id", "")).strip()
            if not object_id or len(object_id) > 160 or any(ch in object_id for ch in "\r\n"):
                raise ValueError("Each object edit needs a valid Stardew object ID")
            incoming = edit.get("fields")
            if not isinstance(incoming, dict) or set(incoming) - OBJECT_FIELDS:
                raise ValueError("Unsupported Data/Objects field edit")
            existing = records.get(object_id)
            if existing is None:
                existing = {}
                records[object_id] = existing
            if not isinstance(existing, dict):
                raise ValueError(f"Data/Objects patch {object_id} is not a field object")
            for key, value in incoming.items():
                if value is None:
                    existing.pop(key, None)
                    continue
                if key in {"Price", "Edibility"}:
                    if isinstance(value, bool) or not isinstance(value, int):
                        raise ValueError(f"{key} must be an integer")
                    if key == "Price" and value < 0:
                        raise ValueError("Price cannot be negative")
                    if key == "Edibility" and value < -300:
                        raise ValueError("Edibility cannot be below Stardew's -300 inedible sentinel")
                elif key == "IsDrink" and not isinstance(value, bool):
                    raise ValueError("IsDrink must be true or false")
                existing[key] = value
            if not existing:
                records.pop(object_id, None)
        _atomic_json(self.content_path, payload)
        return self.objects()


def initialize_project(root: Path) -> None:
    """Give a cloned template a stable, project-specific SMAPI identity."""
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    manifest = _json(manifest_path)
    name = root.name.strip() or "Stardew Project"
    slug = re.sub(r"[^A-Za-z0-9]+", "", name) or "Project"
    identity_seed = os.path.normcase(str(root))
    suffix = hashlib.sha256(identity_seed.encode("utf-8")).hexdigest()[:8]
    manifest["Name"] = name
    manifest["UniqueID"] = f"Lexer.Lexeditor.{slug}.{suffix}"
    _atomic_json(manifest_path, manifest)


def _find_mod_manifest(game_root: Path, unique_id: str) -> tuple[Path, dict] | None:
    mods = Path(game_root) / "Mods"
    if not mods.is_dir():
        return None
    for manifest_path in sorted(mods.glob("*/manifest.json")):
        try:
            manifest = _json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if manifest.get("UniqueID") == unique_id:
            return manifest_path.parent, manifest
    return None


def loader_status(game_root: Path) -> dict:
    root = Path(game_root).resolve()
    smapi = root / "StardewModdingAPI.exe"
    found = _find_mod_manifest(root, "Pathoschild.ContentPatcher")
    content_patcher = found[0] if found else None
    manifest = found[1] if found else {}
    version = str(manifest.get("Version")) if manifest.get("Version") is not None else None
    compatible = content_patcher is not None and _version_at_least(version, MIN_CONTENT_PATCHER_VERSION)
    return {
        "smapi": smapi.is_file(),
        "smapiExecutable": str(smapi),
        "contentPatcher": content_patcher is not None,
        "contentPatcherRoot": str(content_patcher) if content_patcher else None,
        "contentPatcherManifest": str(content_patcher / "manifest.json") if content_patcher else None,
        "contentPatcherVersion": version,
        "contentPatcherMinimumApiVersion": str(manifest.get("MinimumApiVersion")) if manifest.get("MinimumApiVersion") is not None else None,
        "contentPatcherCompatible": compatible,
        "requiredContentPatcherVersion": MIN_CONTENT_PATCHER_VERSION,
        "ready": smapi.is_file() and compatible,
    }


def _tree_hash(root: Path, *, ignore_marker: bool = True) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return ""
    for path in sorted((value for value in root.rglob("*") if value.is_file()),
                       key=lambda value: value.relative_to(root).as_posix().casefold()):
        relative = path.relative_to(root).as_posix()
        if ignore_marker and relative == DEPLOY_MARKER:
            continue
        digest.update(relative.encode("utf-8")); digest.update(b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def deployment_target(game_root: Path, project_root: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9 _.-]+", "_", Path(project_root).name).strip(" .") or "Project"
    return Path(game_root).resolve() / "Mods" / f"[CP] Lexeditor {safe}"


def deployment_status(game_root: Path, project_root: Path) -> dict:
    game = Path(game_root).resolve(); project = Path(project_root).resolve()
    target = deployment_target(game, project)
    loader = loader_status(game)
    managed = False; changed = False
    if (target / DEPLOY_MARKER).is_file():
        try:
            marker = _json(target / DEPLOY_MARKER)
            managed = Path(marker.get("sourceProject", "")).resolve() == project
            if managed:
                changed = marker.get("contentHash") != _tree_hash(target)
        except (OSError, ValueError):
            changed = True
    return {
        "target": str(target), "deployed": target.is_dir(), "managed": managed,
        "externallyChanged": changed, "loader": loader,
    }


def deploy(game_root: Path, project_root: Path) -> dict:
    game = Path(game_root).resolve(); project = Path(project_root).resolve()
    ContentPackStore(project).validate()
    loader = loader_status(game)
    if not loader["smapi"]:
        raise RuntimeError("Install SMAPI before deploying this project")
    if not loader["contentPatcher"]:
        raise RuntimeError("Install Content Patcher before deploying this project")
    if not loader["contentPatcherCompatible"]:
        raise RuntimeError(
            f"Content Patcher {loader['contentPatcherVersion'] or 'unknown'} is installed; "
            f"Lexeditor requires {MIN_CONTENT_PATCHER_VERSION} or newer"
        )
    target = deployment_target(game, project)
    target.parent.mkdir(parents=True, exist_ok=True)
    status = deployment_status(game, project)
    if target.exists() and not status["managed"]:
        raise RuntimeError(f"Refusing to replace an unmanaged mod folder: {target}")
    if status["externallyChanged"]:
        raise RuntimeError("The deployed content pack changed outside Lexeditor; reconcile it before redeploying")
    temporary = target.parent / (target.name + ".lexeditor-new")
    backup = target.parent / (target.name + ".lexeditor-old")
    for stale in (temporary, backup):
        if stale.exists():
            shutil.rmtree(stale)
    shutil.copytree(
        project,
        temporary,
        ignore=shutil.ignore_patterns(".git", "__pycache__", DEPLOY_MARKER, ACCEPTANCE_MARKER),
    )
    content_hash = _tree_hash(temporary)
    _atomic_json(temporary / DEPLOY_MARKER, {
        "schema": 1, "sourceProject": str(project), "contentHash": content_hash,
    })
    try:
        if target.exists():
            target.rename(backup)
        temporary.rename(target)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if target.exists() and backup.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup.exists() and not target.exists():
            backup.rename(target)
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    return deployment_status(game, project)


def revert(game_root: Path, project_root: Path) -> dict:
    game = Path(game_root).resolve(); project = Path(project_root).resolve()
    target = deployment_target(game, project)
    status = deployment_status(game, project)
    if not target.exists():
        return status
    if not status["managed"]:
        raise RuntimeError(f"Refusing to remove an unmanaged mod folder: {target}")
    if status["externallyChanged"]:
        raise RuntimeError("The deployed content pack changed outside Lexeditor; remove or reconcile it manually")
    shutil.rmtree(target)
    return deployment_status(game, project)
