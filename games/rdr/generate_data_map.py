"""Generate the structured RDR Data Map from installed archive indexes.

The generator reads RPF6 archives. It does not write to them. It also reads the
prepared Lexeditor cache to report which indexed files have a supported editor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from . import mission_rewards, paths
from .server import _shop_records


SCHEMA_VERSION = 1
CONTRACT = "Lexeditor.data-map"

ARCHIVES = (
    {
        "id": "tuning",
        "label": "Tuning",
        "archive": "game/tune_d11generic.rpf",
        "manifest": "tuning",
        "cache": "tuning",
        "cachePrefix": "",
    },
    {
        "id": "content",
        "label": "Content",
        "archive": "game/content.rpf",
        "manifest": "content",
        "cache": "content",
        "cachePrefix": "",
    },
    {
        "id": "gringores",
        "label": "Gringo resources",
        "archive": "game/gringores.rpf",
        "manifest": "gringores",
        "cache": "gringoresUnpacked",
        "cachePrefix": "",
    },
)

INVENTORY_PATHS = {
    "content/init/inventory/inventory.xml": "Base-game inventory items",
    "content/init/inventory/dlc_inventory.xml": "Undead Nightmare inventory items",
}

EXTENSION_ROLES = {
    ".arm": "Arm and ragdoll tuning",
    ".bk2": "Bink video",
    ".cfg": "Game configuration",
    ".charclothmanager": "Character cloth tuning",
    ".clm": "Cloth simulation tuning",
    ".colors": "Color configuration",
    ".csv": "Tabular game data",
    ".dat": "Game data",
    ".dds": "Texture image",
    ".env": "Environment tuning",
    ".envclothmanager": "Environment cloth tuning",
    ".expl": "Explosion tuning",
    ".film": "Post-process film tuning",
    ".flare": "Lens-flare tuning",
    ".fx": "Visual-effect tuning",
    ".fxm": "Visual-effect material tuning",
    ".hud": "HUD tuning",
    ".list": "Game-data list",
    ".map": "Map configuration",
    ".mtl": "Material definition",
    ".pop": "Population tuning",
    ".ppp": "Post-process profile",
    ".refgroup": "Resource-reference group",
    ".rmptx": "Texture resource metadata",
    ".sco": "Compiled game script",
    ".spm": "Streaming or population map",
    ".streaming": "Streaming configuration",
    ".strtbl": "String table",
    ".textune": "Texture tuning",
    ".tod": "Time-of-day tuning",
    ".todlight": "Time-of-day light tuning",
    ".tr": "AI rule or transition data",
    ".traffic": "Traffic tuning",
    ".trainmanager": "Train tuning",
    ".tune": "Game tuning",
    ".tuning": "Game tuning",
    ".vehboat": "Boat tuning",
    ".vehdraft": "Draft-vehicle tuning",
    ".vehgyro": "Vehicle gyroscope tuning",
    ".vehinput": "Vehicle input tuning",
    ".vehmodel": "Vehicle model tuning",
    ".vehpushcart": "Push-cart tuning",
    ".vehsim": "Vehicle simulation tuning",
    ".vehstuck": "Vehicle recovery tuning",
    ".weap": "Weapon tuning",
    ".wgd": "Gringo resource dictionary",
    ".wsc": "Game script resource",
    ".xml": "Structured game configuration",
    ".txt": "Text game data",
}


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _normalize_archive_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if normalized.casefold().startswith("root/"):
        normalized = normalized[5:]
    return normalized


def _list_archive(tool: Path, archive: Path) -> list[dict]:
    result = subprocess.run(
        [str(tool), "list", str(archive)],
        cwd=str(tool.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Could not index {archive.name}: {detail}")
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("path\t") or line.startswith("LISTED\t"):
            continue
        cells = line.split("\t")
        if len(cells) != 5:
            raise ValueError(f"Unexpected RPF6 index row for {archive.name}: {line}")
        source_path = _normalize_archive_path(cells[0])
        rows.append({
            "sourcePath": source_path,
            "storedBytes": int(cells[1]),
            "unpackedBytes": int(cells[2]),
            "compressed": cells[3] == "1",
            "resource": cells[4] == "1",
        })
    if not rows:
        raise RuntimeError(f"RPF6 index is empty: {archive}")
    return rows


def _cache_files(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _inventory_records(content_cache: Path) -> tuple[dict[str, int], Counter]:
    records: dict[str, int] = {}
    types: Counter = Counter()
    for source_path in INVENTORY_PATHS:
        target = content_cache / Path(source_path)
        if not target.is_file():
            records[source_path] = 0
            continue
        items = ET.parse(target).findall("./Types/Item")
        records[source_path] = len(items)
        types.update(item.get("type", "[unnamed]") for item in items)
    return records, types


def _shop_records_by_file(gringo_cache: Path) -> tuple[dict[str, dict], int]:
    result: dict[str, dict] = {}
    shop_ids = set()
    if not gringo_cache.is_dir():
        return result, 0
    for target in sorted(gringo_cache.rglob("*.wgd")):
        source_path = target.relative_to(gringo_cache).as_posix()
        relative = PurePosixPath(source_path)
        rows = _shop_records(target.read_bytes(), relative, False)
        roots = {row["rootHash"] for row in rows}
        shop_ids.update((source_path, root_hash) for root_hash in roots)
        result[source_path] = {
            "items": len(rows),
            "shops": len(roots),
            "categories": dict(sorted(Counter(row["category"] for row in rows).items())),
        }
    return result, len(shop_ids)


def _setting_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(
        1 for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith((";", "#", "["))
        and "=" in line
    )


def _loot_counts(path: Path) -> dict:
    if not path.is_file():
        return {"bonusItems": 0, "itemPaths": 0, "moneyPaths": 0}
    document = _load_json(path)
    return {
        "bonusItems": len(document.get("corpseBonusItem", {}).get("entries", [])),
        "itemPaths": len(document.get("itemPaths", [])),
        "moneyPaths": len(document.get("money", {}).get("decoratorPaths", [])),
    }


def _controls(archive_id: str, source_path: str) -> str:
    lowered = source_path.casefold()
    if source_path in INVENTORY_PATHS:
        return INVENTORY_PATHS[source_path]
    if archive_id == "gringores":
        return "Location and activity definitions, including supported shop inventories"
    if "achievement" in lowered:
        return "Achievement definitions"
    if "challenge" in lowered:
        return "Challenge definitions"
    if "/mission" in lowered or "/missions" in lowered:
        return "Mission data or mission script behavior"
    if lowered.startswith("content/release64/"):
        return "Story, system, activity, or mission script behavior"
    if "/ai/" in f"/{lowered}":
        return "AI behavior, motives, or decision rules"
    if "/asd/" in f"/{lowered}":
        return "Actor species or character tuning"
    if "/physics/" in f"/{lowered}":
        return "Physics behavior"
    if "/vehicle" in lowered or Path(source_path).suffix.casefold().startswith(".veh"):
        return "Vehicle behavior"
    return EXTENSION_ROLES.get(
        Path(source_path).suffix.casefold(),
        f"Game data in {PurePosixPath(source_path).parent.as_posix()}",
    )


def _archive_row(
    definition: dict,
    indexed: dict,
    prepared: bool,
    inventory_records: dict[str, int],
    shops_by_file: dict[str, dict],
) -> dict:
    archive = definition["archive"]
    archive_id = definition["id"]
    source_path = indexed["sourcePath"]
    filename = f"{archive}:/{source_path}"
    record_count = None
    record_unit = ""
    status = "not-integrated"
    target = None
    openable = False
    editable_fields: list[str] = []
    write_target = ""

    if source_path in INVENTORY_PATHS:
        status = "partial"
        target = "items"
        openable = prepared
        record_count = inventory_records.get(source_path, 0)
        record_unit = "items"
        editable_fields = ["direct scalar child fields"]
        write_target = f"mod/content/{source_path}"
        caveat = (
            "Items edits direct scalar fields. Nested structures, record creation, and "
            "record deletion are not supported."
        )
    elif archive_id == "gringores":
        shop = shops_by_file.get(source_path, {"items": 0, "shops": 0, "categories": {}})
        record_count = shop["items"]
        record_unit = "shop inventory items"
        if record_count:
            status = "partial"
            target = "shops"
            openable = prepared
            editable_fields = [
                "PriceModifier", "QuantityPerPurchase", "TotalAvailableQuantity",
            ]
            write_target = f"mod/gringores/{source_path}"
            caveat = (
                "Shops edits only complete ShopInventory item records. Other Gringo "
                "components and attributes remain unchanged."
            )
        else:
            caveat = (
                "No complete ShopInventory item record was found. The dictionary is "
                "indexed, but it has no supported editor record."
            )
    elif prepared:
        caveat = "Prepared as read-only research data. No dedicated Lexeditor editor is connected."
    else:
        caveat = "Indexed in the installed archive, but not prepared in the Lexeditor cache."

    return {
        "filename": filename,
        "controls": _controls(archive_id, source_path),
        "notes": caveat,
        "status": status,
        "target": target,
        "openable": openable,
        "sourceArchive": archive,
        "sourcePath": source_path,
        "prepared": prepared,
        "storedBytes": indexed["storedBytes"],
        "unpackedBytes": indexed["unpackedBytes"],
        "compressed": indexed["compressed"],
        "resource": indexed["resource"],
        "recordCount": record_count,
        "recordUnit": record_unit,
        "editability": {
            "mode": status,
            "fields": editable_fields,
            "writeTarget": write_target,
        },
        "caveats": [caveat],
    }


def _project_rows(project_root: Path, setting_count: int, loot_counts: dict,
                  mission_count: int) -> list[dict]:
    loot_record_count = sum(loot_counts.values())
    return [
        {
            "filename": "LexerRDR.ini",
            "controls": "LexerRDR runtime feature settings",
            "notes": "Settings preserves comments and section order while it edits supported values.",
            "status": "integrated",
            "target": "settings",
            "openable": True,
            "sourceArchive": "project",
            "sourcePath": "LexerRDR.ini",
            "prepared": True,
            "recordCount": setting_count,
            "recordUnit": "settings",
            "editability": {
                "mode": "integrated",
                "fields": ["INI values"],
                "writeTarget": "LexerRDR.ini",
            },
            "caveats": ["The ASI must implement a setting before it can affect the game."],
        },
        {
            "filename": "LexerRDR.loot.json",
            "controls": "LexerRDR corpse bonus-item and money overrides",
            "notes": "Loot Tables edits the validated LexerRDR runtime override contract.",
            "status": "integrated",
            "target": "loot",
            "openable": True,
            "sourceArchive": "project",
            "sourcePath": "LexerRDR.loot.json",
            "prepared": True,
            "recordCount": loot_record_count,
            "recordUnit": "override records",
            "editability": {
                "mode": "integrated",
                "fields": ["corpse bonus items", "item paths", "money paths"],
                "writeTarget": "LexerRDR.loot.json",
            },
            "caveats": [
                "This project file is an ASI override. It does not rewrite the source game script."
            ],
        },
        {
            "filename": "LexerRDR.missions.json",
            "controls": "Story mission cash, fame, and honor reward overrides",
            "notes": "Missions writes only reward fields that differ from the read-only extracted base table.",
            "status": "integrated",
            "target": "missions",
            "openable": True,
            "sourceArchive": "project",
            "sourcePath": "LexerRDR.missions.json",
            "prepared": True,
            "recordCount": mission_count,
            "recordUnit": "Story missions",
            "editability": {
                "mode": "integrated",
                "fields": ["cash", "fame", "honor"],
                "writeTarget": "LexerRDR.missions.json",
            },
            "caveats": [
                "Mission identity and base reward evidence remain read-only."
            ],
        },
    ]


def build_data_map(data_root: Path, game_root: Path, project_root: Path) -> dict:
    manifest_path = data_root / "manifest.json"
    manifest = _load_json(manifest_path)
    if manifest.get("version") != 3:
        raise ValueError("RDR data-map generation requires cache manifest version 3")
    tool = paths.RPF6_TOOL
    if not tool.is_file():
        raise FileNotFoundError(f"Missing RPF6 index tool: {tool}")

    caches = {
        name: Path(value)
        for name, value in manifest.get("caches", {}).items()
    }
    required_caches = {"tuning", "content", "gringores", "gringoresUnpacked"}
    if not required_caches.issubset(caches):
        raise ValueError("RDR cache manifest does not name every required cache")

    inventory_records, inventory_types = _inventory_records(caches["content"])
    shops_by_file, shop_count = _shop_records_by_file(caches["gringoresUnpacked"])
    setting_count = _setting_count(project_root / "LexerRDR.ini")
    loot_counts = _loot_counts(project_root / "LexerRDR.loot.json")
    mission_document = mission_rewards.load_generated()
    mission_count = len(mission_document["missions"])

    rows = []
    source_rows = []
    archive_indexes: dict[str, list[dict]] = {}
    for definition in ARCHIVES:
        archive_path = game_root / Path(definition["archive"])
        if not archive_path.is_file():
            raise FileNotFoundError(f"Missing installed RDR archive: {archive_path}")
        indexed = _list_archive(tool, archive_path)
        archive_indexes[definition["id"]] = indexed
        prepared_files = _cache_files(caches[definition["cache"]])
        prepared_count = sum(row["sourcePath"] in prepared_files for row in indexed)
        source = manifest["sources"][definition["manifest"]]
        source_rows.append({
            "id": definition["id"],
            "label": definition["label"],
            "archive": definition["archive"],
            "sha256": source["sha256"],
            "archiveBytes": source["size"],
            "archiveFileCount": len(indexed),
            "preparedFileCount": prepared_count,
            "coveragePercent": round(prepared_count * 100 / len(indexed), 2),
            "readOnlySource": True,
        })
        rows.extend(
            _archive_row(
                definition, indexed_row,
                indexed_row["sourcePath"] in prepared_files,
                inventory_records, shops_by_file,
            )
            for indexed_row in indexed
        )

    rows.extend(_project_rows(project_root, setting_count, loot_counts, mission_count))
    rows.sort(key=lambda row: row["filename"].casefold())
    status_counts = Counter(row["status"] for row in rows)
    prepared_source_files = sum(source["preparedFileCount"] for source in source_rows)
    shop_file_count = sum(value["items"] > 0 for value in shops_by_file.values())
    item_count = sum(inventory_records.values())
    shop_item_count = sum(value["items"] for value in shops_by_file.values())

    datasets = [
        {
            "id": "items",
            "label": "Items",
            "sourceArchive": "game/content.rpf",
            "sourcePaths": list(INVENTORY_PATHS),
            "fileCount": len(INVENTORY_PATHS),
            "recordCount": item_count,
            "recordUnit": "items",
            "status": "partial",
            "target": "items",
            "editability": "Direct scalar child fields on existing Item records.",
            "caveats": ["Nested structures and record creation or deletion are not supported."],
            "details": {
                "recordsByFile": inventory_records,
                "recordsByType": dict(sorted(inventory_types.items())),
            },
        },
        {
            "id": "shops",
            "label": "Shops",
            "sourceArchive": "game/gringores.rpf",
            "sourcePaths": ["gringores/*.wgd"],
            "fileCount": len(shops_by_file),
            "supportedFileCount": shop_file_count,
            "recordCount": shop_item_count,
            "recordUnit": "shop inventory items",
            "shopCount": shop_count,
            "status": "partial",
            "target": "shops",
            "editability": "Price modifier, purchase quantity, and available stock.",
            "caveats": ["Other Gringo components and attributes are preserved but not editable."],
            "details": {"recordsByFile": shops_by_file},
        },
        {
            "id": "tuning-index",
            "label": "Tuning archive index",
            "sourceArchive": "game/tune_d11generic.rpf",
            "sourcePaths": ["tune/**"],
            "fileCount": len(archive_indexes["tuning"]),
            "recordCount": None,
            "recordUnit": "",
            "status": "not-integrated",
            "target": None,
            "editability": "Read-only Data Map coverage.",
            "caveats": ["No dedicated editor is connected to these prepared files."],
        },
        {
            "id": "content-index",
            "label": "Content archive index",
            "sourceArchive": "game/content.rpf",
            "sourcePaths": ["content/**"],
            "fileCount": len(archive_indexes["content"]),
            "recordCount": None,
            "recordUnit": "",
            "status": "partial",
            "target": None,
            "editability": "Only the two inventory XML files have a dedicated editor.",
            "caveats": ["Game scripts are research evidence and are not rewritten."],
        },
        {
            "id": "settings",
            "label": "Settings",
            "sourceArchive": "project",
            "sourcePaths": ["LexerRDR.ini"],
            "fileCount": 1,
            "recordCount": setting_count,
            "recordUnit": "settings",
            "status": "integrated",
            "target": "settings",
            "editability": "Supported project INI values.",
            "caveats": ["A setting needs matching ASI support to affect the game."],
        },
        {
            "id": "loot",
            "label": "Loot Tables",
            "sourceArchive": "project",
            "sourcePaths": ["LexerRDR.loot.json"],
            "fileCount": 1,
            "recordCount": sum(loot_counts.values()),
            "recordUnit": "override records",
            "status": "integrated",
            "target": "loot",
            "editability": "Validated LexerRDR ASI override fields.",
            "caveats": ["The source game script remains read-only."],
            "details": loot_counts,
        },
        {
            "id": "missions",
            "label": "Missions",
            "sourceArchive": "game/content.rpf",
            "sourcePaths": [source["file"] for source in mission_document["sources"]],
            "fileCount": len(mission_document["sources"]),
            "recordCount": mission_count,
            "recordUnit": "Story missions",
            "status": "integrated",
            "target": "missions",
            "editability": "Cash, fame, and honor reward overrides.",
            "caveats": ["The extracted mission registry and reward table remain read-only."],
            "details": mission_document["summary"],
        },
    ]

    return {
        "schemaVersion": SCHEMA_VERSION,
        "contract": CONTRACT,
        "game": "rdr",
        "sourceManifestVersion": manifest["version"],
        "sourcePreparedAt": manifest.get("preparedAt", ""),
        "generator": "games/rdr/generate_data_map.py",
        "summary": {
            "archiveFiles": sum(source["archiveFileCount"] for source in source_rows),
            "preparedSourceFiles": prepared_source_files,
            "rows": len(rows),
            "status": {
                name: status_counts.get(name, 0)
                for name in ("integrated", "partial", "not-integrated")
            },
            "editorRecords": {
                "items": item_count,
                "shopItems": shop_item_count,
                "shops": shop_count,
                "settings": setting_count,
                "lootOverrides": sum(loot_counts.values()),
                "missions": mission_count,
            },
        },
        "sources": source_rows,
        "datasets": datasets,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=paths.EXTRACT_ROOT)
    parser.add_argument("--game-root", type=Path, default=paths.GAME_ROOT)
    parser.add_argument("--project-root", type=Path, default=paths.PROJECT_ROOT)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parent / "data_map.generated.json",
    )
    arguments = parser.parse_args()
    payload = build_data_map(
        arguments.data_root.resolve(),
        arguments.game_root.resolve(),
        arguments.project_root.resolve(),
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Generated {payload['summary']['rows']} Data Map rows from "
        f"{payload['summary']['archiveFiles']} archive files: {arguments.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
