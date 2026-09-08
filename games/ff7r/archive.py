"""Locate FF7R gameplay/text packages inside installed PAKs and extract on demand."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from .research_dataobject import RESEARCH_VIRTUAL_ASSET_ROWS
from .runtime_dataobject import VIRTUAL_ASSET_ROWS
from .tooling import REPAK_TAG, get_file, list_pak, pak_info


DATA_PREFIX = "End/Content/GameContents/DataObject/"
TEXT_PREFIX = "End/Content/GameContents/Text/"
INDEX_SCHEMA = 2
ATB_VIRTUAL_ASSET_ROWS = (
    {"asset": "Lexeditor/ATBTweaks", "name": "ATB Tweaks", "group": "Lexeditor ATB", "synthetic": "atb-settings"},
    {"asset": "Lexeditor/ATBResidentParameters", "name": "ATB Resident Parameters", "group": "Lexeditor ATB", "synthetic": "atb-resident"},
    {"asset": "Lexeditor/ATBGuardReactions", "name": "ATB Guard Reactions", "group": "Lexeditor ATB", "synthetic": "atb-guard"},
    {"asset": "Lexeditor/ATBAbilityCosts", "name": "ATB Ability Costs", "group": "Lexeditor ATB", "synthetic": "atb-abilities"},
)
ENCOUNTER_VIRTUAL_ASSET_ROWS = (
    {
        "asset": "Lexeditor/EncounterTweaks",
        "name": "Encounter Tweaks",
        "group": "Lexeditor Encounters",
        "synthetic": "encounter-tweaks",
    },
)
GRAPHICS_VIRTUAL_ASSET_ROWS = (
    {
        "asset": "Lexeditor/GraphicsTweaks",
        "name": "Graphics Tweaks",
        "group": "Lexeditor Graphics",
        "synthetic": "graphics-tweaks",
    },
)
TWEAK_VIRTUAL_ASSET_ROWS = (
    {
        "asset": "Lexeditor/NoMoreCheats",
        "name": "No More Cheats",
        "group": "Lexeditor Tweaks",
        "synthetic": "no-more-cheats",
    },
)


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


def _pair_rows(by_asset: dict[str, dict], prefix: str, *, text: bool = False) -> list[dict]:
    rows: list[dict] = []
    for asset, record in sorted(by_asset.items(), key=lambda pair: pair[0].casefold()):
        if "uasset" not in record or "uexp" not in record:
            continue
        display = asset[len(prefix):] if asset.casefold().startswith(prefix.casefold()) else asset
        folder, _, name = display.rpartition("/")
        row = {**record, "name": name, "group": folder or ("Text" if text else "DataObject")}
        if text:
            parts = display.split("/", 1)
            row["language"] = parts[0] if len(parts) > 1 else ""
            row["group"] = parts[1].rsplit("/", 1)[0] if len(parts) > 1 and "/" in parts[1] else "Text"
        rows.append(row)
    return rows


def _with_virtual_assets(payload: dict) -> dict:
    """Decorate an index in memory without persisting Lexeditor-only rows to cache."""
    rows = [dict(row) for row in payload.get("assets", [])]
    existing = {row.get("asset") for row in rows}
    # Semantic resources precede the long-standing runtime/research rows so
    # existing catalog-order assumptions about the Runtime Tweaks/Probe tail remain true.
    for row in (
        *ATB_VIRTUAL_ASSET_ROWS,
        *ENCOUNTER_VIRTUAL_ASSET_ROWS,
        *GRAPHICS_VIRTUAL_ASSET_ROWS,
        *TWEAK_VIRTUAL_ASSET_ROWS,
        *RESEARCH_VIRTUAL_ASSET_ROWS,
        *VIRTUAL_ASSET_ROWS,
    ):
        if row["asset"] not in existing:
            rows.append(dict(row))
            existing.add(row["asset"])
    return {**payload, "assets": rows}


def build_index(game_root: Path, data_root: Path) -> dict:
    game_root = Path(game_root).resolve()
    data_root = Path(data_root).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    fixture_root = os.environ.get("LEXEDITOR_FF7R_TEST_DATAOBJECTS")
    if fixture_root:
        # Smoke fixtures are deliberately archive-only so existing service tests
        # keep selecting their one generated gameplay resource deterministically.
        return _fixture_index(Path(fixture_root).resolve())

    paks = installed_paks(game_root)
    if not paks:
        raise RuntimeError("No FF7R .pak archives were found")
    signature = _signature(game_root, paks)
    signature_id = _signature_id(signature)
    cache_path = data_root / "ff7r-index.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        cached = {}
    if (cached.get("schema") == INDEX_SCHEMA and cached.get("signature") == signature
            and isinstance(cached.get("assets"), list)
            and isinstance(cached.get("textAssets"), list)):
        return _with_virtual_assets(cached)

    by_data: dict[str, dict] = {}
    by_text: dict[str, dict] = {}
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
            suffix = Path(internal).suffix.casefold()
            if suffix not in {".uasset", ".uexp"}:
                continue
            if internal.casefold().startswith(DATA_PREFIX.casefold()):
                target = by_data
            elif internal.casefold().startswith(TEXT_PREFIX.casefold()):
                target = by_text
            else:
                continue
            asset = internal[:-len(suffix)]
            record = target.setdefault(asset, {"asset": asset})
            # Later archives in the installed set replace earlier definitions.
            record[suffix[1:]] = {"pak": relative_pak, "path": internal}

    assets = _pair_rows(by_data, DATA_PREFIX)
    text_assets = _pair_rows(by_text, TEXT_PREFIX, text=True)
    if not assets:
        raise RuntimeError("FF7R archives contained no paired DataObject .uasset/.uexp files")

    payload = {
        "schema": INDEX_SCHEMA,
        "signature": signature,
        "signatureId": signature_id,
        "pakVersions": pak_versions,
        "assets": assets,
        "textAssets": text_assets,
    }
    temporary = cache_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(cache_path)
    return _with_virtual_assets(payload)


def _fixture_index(root: Path) -> dict:
    by_data: dict[str, dict] = {}
    by_text: dict[str, dict] = {}
    for path in root.rglob("*.uasset"):
        relative = path.relative_to(root).as_posix()
        uexp = path.with_suffix(".uexp")
        if not uexp.is_file():
            continue
        asset = relative[:-len(".uasset")]
        record = {
            "asset": asset,
            "uasset": {"fixture": path.as_posix()},
            "uexp": {"fixture": uexp.as_posix()},
        }
        if asset.casefold().startswith(TEXT_PREFIX.casefold()):
            by_text[asset] = record
        else:
            by_data[asset] = record
    return {
        "schema": INDEX_SCHEMA,
        "signature": {"fixture": str(root)},
        "signatureId": hashlib.sha256(str(root).encode()).hexdigest()[:20],
        "pakVersions": {},
        "assets": _pair_rows(by_data, DATA_PREFIX),
        "textAssets": _pair_rows(by_text, TEXT_PREFIX, text=True),
    }


def _find(index: dict, asset: str, collection: str = "assets") -> dict:
    normalized = _normalize(asset)
    rows = index.get(collection, [])
    if not isinstance(rows, list):
        raise KeyError(f"Unknown FF7R index collection: {collection}")
    for row in rows:
        if row.get("asset") == normalized:
            return row
    kind = "text resource" if collection == "textAssets" else "DataObject"
    raise KeyError(f"Unknown FF7R {kind}: {asset}")


def extract_pair(game_root: Path, data_root: Path, index: dict, asset: str,
                 *, collection: str = "assets") -> tuple[Path, Path]:
    row = _find(index, asset, collection)
    if row.get("synthetic"):
        raise ValueError(f"Synthetic FF7R resource has no archive pair: {asset}")
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
