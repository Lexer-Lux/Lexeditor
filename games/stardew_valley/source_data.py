"""Read-only access to StardewXnbHack output for supported vanilla data assets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .datasets import dataset_spec, validate_field_value

MAX_SOURCE_BYTES = 64 * 1024 * 1024
OBJECT_DEFAULTS = {"Price": 0, "Edibility": -300, "IsDrink": False}


def objects_source_path(game_root: Path) -> Path:
    """Return the canonical StardewXnbHack output path for Data/Objects."""
    return Path(game_root).expanduser().resolve() / "Content (unpacked)" / "Data" / "Objects.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_status(game_root: Path) -> dict:
    root = Path(game_root).expanduser().resolve()
    path = objects_source_path(root)
    helpers = [root / "StardewXnbHack.exe", root / "StardewXnbHack"]
    helper = next((candidate for candidate in helpers if candidate.is_file()), None)
    return {
        "kind": "stardew-xnb-hack-json",
        "path": str(path),
        "available": path.is_file(),
        "helperInstalled": helper is not None,
        "helperPath": str(helper) if helper else None,
        "xnbPath": str(root / "Content" / "Data" / "Objects.xnb"),
        "xnbAvailable": (root / "Content" / "Data" / "Objects.xnb").is_file(),
    }


def load_base_objects(game_root: Path) -> tuple[dict[str, dict], dict]:
    """Load Data/Objects JSON produced by StardewXnbHack without modifying it."""
    status = source_status(game_root)
    path = Path(status["path"])
    if not path.is_file():
        return {}, status
    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        status.update({"available": False, "error": f"Unpacked Data/Objects JSON is too large ({size} bytes)"})
        return {}, status
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        status.update({"available": False, "error": f"Could not read unpacked Data/Objects JSON: {error}"})
        return {}, status
    # xnbcli wraps ordinary data files in {content: ...}. It doesn't reliably
    # support Stardew's typed 1.6 models, but accepting the wrapper is harmless
    # for compatible user-provided exports while StardewXnbHack stays canonical.
    if isinstance(payload, dict) and isinstance(payload.get("content"), dict):
        payload = payload["content"]
    if not isinstance(payload, dict) or not payload:
        status.update({"available": False, "error": "Unpacked Data/Objects JSON is not a non-empty object lookup"})
        return {}, status

    rows: dict[str, dict] = {}
    invalid = 0
    for object_id, raw in payload.items():
        if not isinstance(raw, dict):
            invalid += 1
            continue
        base_fields = {
            key: raw.get(key, default)
            for key, default in OBJECT_DEFAULTS.items()
        }
        if isinstance(base_fields["Price"], bool) or not isinstance(base_fields["Price"], int):
            invalid += 1
            continue
        if isinstance(base_fields["Edibility"], bool) or not isinstance(base_fields["Edibility"], int):
            invalid += 1
            continue
        if not isinstance(base_fields["IsDrink"], bool):
            invalid += 1
            continue
        rows[str(object_id)] = {
            "id": str(object_id),
            "name": str(raw.get("DisplayName") or raw.get("Name") or object_id),
            "internalName": str(raw.get("Name") or object_id),
            "description": str(raw.get("Description") or ""),
            "baseFields": base_fields,
        }
    if not rows:
        status.update({"available": False, "error": "Unpacked Data/Objects JSON contained no compatible object records"})
        return {}, status
    status.update({
        "available": True,
        "recordCount": len(rows),
        "ignoredRecordCount": invalid,
        "sha256": _sha256(path),
    })
    return rows, status

def dataset_source_path(game_root: Path, key: str) -> Path:
    spec = dataset_spec(key)
    return Path(game_root).expanduser().resolve() / "Content (unpacked)" / "Data" / f"{spec['source']}.json"


def dataset_source_status(game_root: Path, key: str) -> dict:
    root = Path(game_root).expanduser().resolve()
    spec = dataset_spec(key)
    path = dataset_source_path(root, key)
    helpers = [root / "StardewXnbHack.exe", root / "StardewXnbHack"]
    helper = next((candidate for candidate in helpers if candidate.is_file()), None)
    xnb = root / "Content" / "Data" / f"{spec['source']}.xnb"
    return {
        "kind": "stardew-xnb-hack-json", "datasetKey": key, "asset": spec["target"],
        "path": str(path), "available": path.is_file(), "helperInstalled": helper is not None,
        "helperPath": str(helper) if helper else None, "xnbPath": str(xnb), "xnbAvailable": xnb.is_file(),
    }


def load_base_dataset(game_root: Path, key: str) -> tuple[dict[str, dict], dict]:
    """Load one supported 1.6 string-to-model lookup without writing installed data."""
    if key == "objects":
        return load_base_objects(game_root)
    spec = dataset_spec(key)
    status = dataset_source_status(game_root, key)
    path = Path(status["path"])
    if not path.is_file():
        return {}, status
    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        status.update({"available": False, "error": f"Unpacked {spec['target']} JSON is too large ({size} bytes)"})
        return {}, status
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        status.update({"available": False, "error": f"Could not read unpacked {spec['target']} JSON: {error}"})
        return {}, status
    if isinstance(payload, dict) and isinstance(payload.get("content"), dict):
        payload = payload["content"]
    if not isinstance(payload, dict) or not payload:
        status.update({"available": False, "error": f"Unpacked {spec['target']} JSON is not a non-empty object lookup"})
        return {}, status

    rows: dict[str, dict] = {}
    invalid_records = 0
    for record_id, raw in payload.items():
        if not isinstance(raw, dict):
            invalid_records += 1
            continue
        base_fields = {}
        invalid_fields = 0
        for field_key, field in spec["fields"].items():
            if field_key in raw:
                try:
                    base_fields[field_key] = validate_field_value(field, raw[field_key])
                except ValueError:
                    invalid_fields += 1
            elif "default" in field:
                base_fields[field_key] = field["default"]
        name = raw.get("DisplayName") or raw.get("Name") or raw.get("ID") or record_id
        rows[str(record_id)] = {
            "id": str(record_id), "name": str(name), "internalName": str(raw.get("Name") or record_id),
            "description": str(raw.get("Description") or ""), "baseFields": base_fields,
            "invalidFieldCount": invalid_fields,
        }
    if not rows:
        status.update({"available": False, "error": f"Unpacked {spec['target']} JSON contained no model records"})
        return {}, status
    status.update({
        "available": True, "recordCount": len(rows), "ignoredRecordCount": invalid_records,
        "sha256": _sha256(path),
    })
    return rows, status

