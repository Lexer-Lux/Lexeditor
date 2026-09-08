"""Locate FF7R DataObjects inside installed PAKs and extract them on demand."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from .tooling import REPAK_TAG, get_file, list_pak, pak_info


DATA_PREFIX = "End/Content/GameContents/DataObject/"
INDEX_SCHEMA = 1


def _normalize(path: str) -> str:
    path = path.replace("\\", "/").lstrip("/")
    parts = [part for part in path.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise ValueError(f"Unsafe PAK path: {path}")
    return "/".join(parts)


def installed_paks(game_root: Path) -> list[Path]:
    pak_root = Path(game_root) / "End" / "Content" / "Paks"
    if not pak_root.is_dir():
        raise FileNotFoundError(f"Missing FF7R PAK directory: {pak_root}")
    return sorted((path for path in pak_root.glob("*.pak") if path.is_file()),
                  key=lambda path: path.name.casefold())


def _signature(game_root: Path, paks: Iterable[Path]) -> dict:
    root = Path(game_root).resolve()
    return {
        "repak": REPAK_TAG,
        "paks": [
            {
                "path": path.resolve().relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "mtimeNs": path.stat().st_mtime_ns,
            }
            for path in paks
        ],
    }


def _signature_id(signature: dict) -> str:
    raw = json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def build_index(game_root: Path, data_root: Path) -> dict:
    game_root = Path(game_root).resolve()
    data_root = Path(data_root).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    fixture_root = os.environ.get("LEXEDITOR_FF7R_TEST_DATAOBJECTS")
    if fixture_root:
        return _fixture_index(Path(fixture_root).resolve())

    paks = installed_paks(game_root)
    if not paks:
        raise RuntimeError("No FF7R .pak archives were found")
    signature = _signature(game_root, paks)
    signature_id = _signature_id(signature)
    cache_path = data_root / "dataobject-index.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        cached = {}
    if (cached.get("schema") == INDEX_SCHEMA and cached.get("signature") == signature
            and isinstance(cached.get("assets"), list)):
        return cached

    by_asset: dict[str, dict] = {}
    pak_versions: dict[str, str] = {}
    for pak in paks:
        relative_pak = pak.relative_to(game_root).as_posix()
        try:
            info = pak_info(pak)
            pak_versions[relative_pak] = info.get("version", "")
            entries = list_pak(pak)
        except Exception as error:
            raise RuntimeError(f"Could not index FF7R archive {pak.name}: {error}") from error
        for internal in entries:
            internal = _normalize(internal)
            if not internal.casefold().startswith(DATA_PREFIX.casefold()):
                continue
            suffix = Path(internal).suffix.casefold()
            if suffix not in {".uasset", ".uexp"}:
                continue
            asset = internal[:-len(suffix)]
            record = by_asset.setdefault(asset, {"asset": asset})
            # Later archives in the installed set replace earlier definitions.
            record[suffix[1:]] = {"pak": relative_pak, "path": internal}

    assets = []
    for asset, record in sorted(by_asset.items(), key=lambda pair: pair[0].casefold()):
        if "uasset" not in record or "uexp" not in record:
            continue
        display = asset[len(DATA_PREFIX):] if asset.casefold().startswith(DATA_PREFIX.casefold()) else asset
        folder, _, name = display.rpartition("/")
        assets.append({**record, "name": name, "group": folder or "DataObject"})
    if not assets:
        raise RuntimeError("FF7R archives contained no paired DataObject .uasset/.uexp files")

    payload = {
        "schema": INDEX_SCHEMA,
        "signature": signature,
        "signatureId": signature_id,
        "pakVersions": pak_versions,
        "assets": assets,
    }
    temporary = cache_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(cache_path)
    return payload


def _fixture_index(root: Path) -> dict:
    by_asset = {}
    for path in root.rglob("*.uasset"):
        relative = path.relative_to(root).as_posix()
        uexp = path.with_suffix(".uexp")
        if not uexp.is_file():
            continue
        asset = relative[:-len(".uasset")]
        display = asset[len(DATA_PREFIX):] if asset.casefold().startswith(DATA_PREFIX.casefold()) else asset
        folder, _, name = display.rpartition("/")
        by_asset[asset] = {
            "asset": asset, "name": name, "group": folder or "DataObject",
            "uasset": {"fixture": path.as_posix()},
            "uexp": {"fixture": uexp.as_posix()},
        }
    return {
        "schema": INDEX_SCHEMA,
        "signature": {"fixture": str(root)},
        "signatureId": hashlib.sha256(str(root).encode()).hexdigest()[:20],
        "pakVersions": {},
        "assets": list(by_asset.values()),
    }


def _find(index: dict, asset: str) -> dict:
    normalized = _normalize(asset)
    for row in index.get("assets", []):
        if row.get("asset") == normalized:
            return row
    raise KeyError(f"Unknown FF7R DataObject: {asset}")


def extract_pair(game_root: Path, data_root: Path, index: dict, asset: str) -> tuple[Path, Path]:
    row = _find(index, asset)
    if "fixture" in row["uasset"]:
        return Path(row["uasset"]["fixture"]), Path(row["uexp"]["fixture"])
    source_root = Path(data_root).resolve() / "sources" / str(index["signatureId"])
    uasset_target = source_root / (row["asset"] + ".uasset")
    uexp_target = source_root / (row["asset"] + ".uexp")
    for key, target in (("uasset", uasset_target), ("uexp", uexp_target)):
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = row[key]
        pak = Path(game_root).resolve() / source["pak"]
        data = get_file(pak, source["path"])
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
    return uasset_target, uexp_target


def preferred_pak_version(index: dict) -> str:
    versions = [value for value in index.get("pakVersions", {}).values() if value]
    return versions[-1] if versions else ""
