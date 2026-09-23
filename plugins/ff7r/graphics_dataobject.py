"""DataObject-shaped Game Data surface for FF7R graphics tweaks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataobject import Entry
from .graphics_tweaks import (
    DEFAULT_GRAPHICS_CONFIG,
    GRAPHICS_TWEAKS_ASSET,
    canonical_hash,
    config_path,
    graphics_status,
    load_graphics_config,
    save_graphics_config,
)


_GRAPHICS_SOURCE_SHA = canonical_hash({
    "schema": "lexeditor-ff7r-graphics-v1",
    "fields": ["DisableEyeAdaptation"],
})


@dataclass(frozen=True)
class GraphicsVirtualProperty:
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


class GraphicsVirtualPackage:
    def __init__(self, *, properties: list[GraphicsVirtualProperty], entries: list[Entry],
                 active_sha: str):
        self.asset = GRAPHICS_TWEAKS_ASSET
        self.export_name = "LexeditorGraphicsTweaks"
        self.properties = properties
        self.entries = entries
        self.names: list[str] = []
        self.active_sha = active_sha

    def api_payload(self, *, source_sha256: str | None = None, using_project: bool = False) -> dict:
        return {
            "asset": self.asset,
            "sourceSha256": source_sha256 or _GRAPHICS_SOURCE_SHA,
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


def _properties() -> list[GraphicsVirtualProperty]:
    return [
        GraphicsVirtualProperty(
            "DisableEyeAdaptation", "Disable Eye Adaptation", "BOOL", True, 0, 1
        ),
        GraphicsVirtualProperty(
            "IniUnlockerCandidatePresent", "INI Unlocker Candidate Detected", "BOOL"
        ),
        GraphicsVirtualProperty(
            "IniUnlockerVerified", "Engine.ini Loading Verified", "BOOL"
        ),
        GraphicsVirtualProperty(
            "GraphicsDeployReady", "Graphics Tweak Ready To Deploy", "BOOL"
        ),
        GraphicsVirtualProperty(
            "ManagedOverridePresent", "Managed Engine.ini Override Present", "BOOL"
        ),
        GraphicsVirtualProperty(
            "ManagedOverrideEffectiveAtEnd", "Managed Override Has Final Precedence", "BOOL"
        ),
        GraphicsVirtualProperty("EngineIniPath", "Engine.ini Path", "STRING"),
        GraphicsVirtualProperty("GraphicsNotes", "Graphics Validation Notes", "STRING"),
    ]


def load_graphics_virtual_package(game_root: Path, project_root: Path, *, vanilla: bool = False):
    config = dict(DEFAULT_GRAPHICS_CONFIG) if vanilla else load_graphics_config(project_root)
    status = graphics_status(game_root, project_root)
    values = {
        "DisableEyeAdaptation": config["disableEyeAdaptation"],
        "IniUnlockerCandidatePresent": status["iniUnlockerCandidatePresent"],
        "IniUnlockerVerified": status["iniUnlockerVerified"],
        "GraphicsDeployReady": status["deployReady"],
        "ManagedOverridePresent": status["managedOverridePresent"],
        "ManagedOverrideEffectiveAtEnd": status["managedOverrideEffectiveAtEnd"],
        "EngineIniPath": status["engineIniPath"],
        "GraphicsNotes": status["notes"],
    }
    active_sha = canonical_hash(config)
    package = GraphicsVirtualPackage(
        properties=_properties(),
        entries=[Entry(0, "Graphics Tweaks", values, {})],
        active_sha=active_sha,
    )
    return package, _GRAPHICS_SOURCE_SHA, (not vanilla and config_path(project_root).is_file())


def save_graphics_virtual_package(project_root: Path, *, source_sha256: str,
                                  active_sha256: str, edits: list[dict[str, Any]]) -> dict:
    if source_sha256 != _GRAPHICS_SOURCE_SHA:
        raise RuntimeError("FF7R graphics settings schema changed; reload Graphics Tweaks before saving")
    current = load_graphics_config(project_root)
    if canonical_hash(current) != active_sha256:
        raise RuntimeError("FF7R graphics settings changed on disk; reload before saving")
    if not isinstance(edits, list):
        raise TypeError("graphics edits must be a list")

    updated = dict(current)
    seen = False
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("each graphics edit must be an object")
        if int(edit.get("entry", -1)) != 0 or "index" in edit:
            raise ValueError("Graphics Tweaks supports only scalar edits on its single record")
        prop = str(edit.get("property", ""))
        if prop != "DisableEyeAdaptation":
            raise ValueError(f"graphics property is read-only or unknown: {prop}")
        if seen:
            raise ValueError("duplicate DisableEyeAdaptation edit")
        seen = True
        value = edit.get("value")
        if not isinstance(value, bool):
            raise ValueError("Disable Eye Adaptation must be boolean")
        updated["disableEyeAdaptation"] = value

    saved = save_graphics_config(project_root, updated)
    return {
        "asset": GRAPHICS_TWEAKS_ASSET,
        "path": str(config_path(project_root)),
        "saved": len(edits),
        "activeSha256": canonical_hash(saved),
        "usingProject": True,
    }
