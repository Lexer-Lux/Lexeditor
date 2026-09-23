"""Schema-validated FF7R navimap visibility semantics.

Rebirth's generated DataObject schema is useful only as a name oracle here: it
contains EnemyTerritory.HideNavimap.  Remake gets a semantic surface only when
the user's installed EnemyTerritory DataObject independently proves the same
scalar boolean field exists and is safely editable.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from .storage import load_package, save_edits


ENEMY_TERRITORY_TABLE_NAME = "enemyterritory"
HIDE_NAVIMAP_FIELD = "HideNavimap"


def _basename(asset: str) -> str:
    return PurePosixPath(asset).name.casefold()


def _asset_row(index: dict) -> dict | None:
    for row in index.get("assets", []):
        if _basename(str(row.get("asset", ""))) == ENEMY_TERRITORY_TABLE_NAME:
            return row
    return None


def _property(package, name: str):
    return next((prop for prop in package.properties if prop.name == name), None)


def minimap_visibility_payload(game_root, data_root, project_root, index: dict,
                               *, vanilla: bool = False) -> dict[str, Any]:
    row = _asset_row(index)
    if row is None:
        return {
            "available": False,
            "reason": "EnemyTerritory DataObject was not found in the installed FF7R archives.",
            "rows": [],
        }

    asset = row["asset"]
    package, source_sha, using_project = load_package(
        game_root, data_root, project_root, index, asset, vanilla=vanilla)
    prop = _property(package, HIDE_NAVIMAP_FIELD)
    if prop is None:
        return {
            "available": False,
            "asset": asset,
            "reason": "EnemyTerritory exists, but HideNavimap is absent in this installed FF7R schema.",
            "rows": [],
        }

    api = prop.api()
    if api["type"] != "BOOL" or api["array"] or not api["editable"]:
        return {
            "available": False,
            "asset": asset,
            "reason": (
                "EnemyTerritory.HideNavimap exists, but is not an editable scalar boolean "
                "in this installed FF7R schema."
            ),
            "rows": [],
            "property": api,
        }

    rows = [
        {
            "entry": entry.index,
            "id": entry.tag,
            "hideNavimap": bool(entry.values[HIDE_NAVIMAP_FIELD]),
        }
        for entry in package.entries
    ]
    forced = [entry for entry in rows if entry["hideNavimap"]]
    return {
        "available": True,
        "asset": asset,
        "sourceSha256": source_sha,
        "activeSha256": package.api_payload()["activeSha256"],
        "usingProject": using_project,
        "property": api,
        "forcedHideCount": len(forced),
        "rows": rows,
        "notes": [
            "These are authored EnemyTerritory forced-hide flags, not the player's current minimap preference.",
            "Clearing them prevents this specific territory rule from overriding a player-controlled minimap.",
            "Other hide mechanisms are not modified unless independently identified and schema-validated.",
        ],
    }


def save_minimap_visibility_edits(game_root, data_root, project_root, index: dict, asset: str,
                                  *, source_sha256: str, active_sha256: str,
                                  edits: list[dict[str, Any]]) -> dict:
    """Write only validated EnemyTerritory.HideNavimap scalar boolean values."""
    if _basename(asset) != ENEMY_TERRITORY_TABLE_NAME:
        raise ValueError("Minimap visibility saves are limited to EnemyTerritory")
    if not isinstance(edits, list):
        raise TypeError("Minimap visibility edits must be a list")

    package, _source_sha, _using_project = load_package(
        game_root, data_root, project_root, index, asset, vanilla=False)
    prop = _property(package, HIDE_NAVIMAP_FIELD)
    if prop is None:
        raise ValueError("HideNavimap is not present in this installed FF7R EnemyTerritory DataObject")
    api = prop.api()
    if api["type"] != "BOOL" or api["array"] or not api["editable"]:
        raise ValueError("HideNavimap is not an editable scalar boolean in this installed FF7R DataObject")

    generic_edits = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("Each minimap visibility edit must be an object")
        value = edit.get("hideNavimap")
        if not isinstance(value, bool):
            raise ValueError("hideNavimap must be boolean")
        generic_edits.append({
            "entry": int(edit.get("entry", -1)),
            "property": HIDE_NAVIMAP_FIELD,
            "value": value,
        })

    result = save_edits(
        game_root, data_root, project_root, index, asset,
        source_sha256=source_sha256,
        active_sha256=active_sha256,
        edits=generic_edits,
    )
    return {**result, "surface": "minimap-visibility"}
