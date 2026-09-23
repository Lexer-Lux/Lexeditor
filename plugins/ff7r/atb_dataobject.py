"""DataObject-shaped views over the reversible FF7R ATB tweak config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atb_tweaks import (
    ATB_VIRTUAL_ASSETS,
    config_path,
    resource_spec,
    save_virtual_edits,
)
from .dataobject import Entry


@dataclass(frozen=True)
class ATBVirtualProperty:
    name: str
    label: str
    type: str
    editable: bool = False
    minimum: int | float | None = None
    maximum: int | float | None = None

    def api(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "typeCode": 0,
            "array": False,
            "editable": self.editable,
            "min": self.minimum,
            "max": self.maximum,
        }


class ATBVirtualPackage:
    def __init__(self, *, asset: str, properties: list[ATBVirtualProperty],
                 entries: list[Entry], source_sha: str, active_sha: str):
        self.asset = asset
        self.export_name = "LexeditorATBTweaks"
        self.properties = properties
        self.entries = entries
        self.names: list[str] = []
        self.source_sha = source_sha
        self.active_sha = active_sha

    def api_payload(self, *, source_sha256: str | None = None, using_project: bool = False) -> dict:
        return {
            "asset": self.asset,
            "sourceSha256": source_sha256 or self.source_sha,
            "activeSha256": self.active_sha,
            "usingProject": using_project,
            "exportName": self.export_name,
            "names": [],
            "properties": [prop.api() for prop in self.properties],
            "records": [
                {"id": entry.index, "tag": entry.tag, "values": entry.values}
                for entry in self.entries
            ],
        }


def is_atb_virtual_asset(asset: str) -> bool:
    return asset in ATB_VIRTUAL_ASSETS


def load_atb_virtual_package(game_root: Path, data_root: Path, project_root: Path,
                             index: dict, asset: str):
    spec = resource_spec(asset, game_root, data_root, project_root, index)
    properties = [
        ATBVirtualProperty(
            row["name"], row["label"], row["type"], bool(row["editable"]),
            row.get("min"), row.get("max"),
        )
        for row in spec["properties"]
    ]
    entries = [
        Entry(i, row["tag"], dict(row["values"]), {})
        for i, row in enumerate(spec["entries"])
    ]
    package = ATBVirtualPackage(
        asset=asset,
        properties=properties,
        entries=entries,
        source_sha=spec["sourceSha256"],
        active_sha=spec["activeSha256"],
    )
    return package, spec["sourceSha256"], config_path(project_root).is_file()


def save_atb_virtual_package(game_root: Path, data_root: Path, project_root: Path,
                             index: dict, asset: str, *, source_sha256: str,
                             active_sha256: str, edits: list[dict[str, Any]]) -> dict:
    return save_virtual_edits(
        game_root, data_root, project_root, index, asset,
        source_sha256=source_sha256,
        active_sha256=active_sha256,
        edits=edits,
    )
