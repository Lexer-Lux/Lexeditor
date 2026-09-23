"""DataObject-shaped Game Data surface for reversible FF7R encounter tweaks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataobject import Entry
from .encounter_tweaks import (
    ENCOUNTER_TWEAKS_ASSET,
    config_path,
    resource_spec,
    save_virtual_edits,
)


@dataclass(frozen=True)
class EncounterVirtualProperty:
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


class EncounterVirtualPackage:
    def __init__(self, *, properties: list[EncounterVirtualProperty], entries: list[Entry],
                 source_sha: str, active_sha: str):
        self.asset = ENCOUNTER_TWEAKS_ASSET
        self.export_name = "LexeditorEncounterTweaks"
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


def load_encounter_virtual_package(game_root: Path, data_root: Path, project_root: Path,
                                   index: dict, *, vanilla: bool = False):
    spec = resource_spec(
        game_root, data_root, project_root, index, vanilla=vanilla)
    properties = [
        EncounterVirtualProperty(
            row["name"], row["label"], row["type"], bool(row["editable"]),
            row.get("min"), row.get("max"),
        )
        for row in spec["properties"]
    ]
    entries = [
        Entry(i, row["tag"], dict(row["values"]), {})
        for i, row in enumerate(spec["entries"])
    ]
    package = EncounterVirtualPackage(
        properties=properties,
        entries=entries,
        source_sha=spec["sourceSha256"],
        active_sha=spec["activeSha256"],
    )
    return package, spec["sourceSha256"], spec["usingProject"]


def save_encounter_virtual_package(game_root: Path, data_root: Path, project_root: Path,
                                   index: dict, *, source_sha256: str,
                                   active_sha256: str, edits: list[dict[str, Any]]) -> dict:
    return save_virtual_edits(
        game_root, data_root, project_root, index,
        source_sha256=source_sha256,
        active_sha256=active_sha256,
        edits=edits,
    )
