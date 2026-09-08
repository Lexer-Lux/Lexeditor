"""Synthetic DataObject-style surfaces for FF7R runtime settings/research.

These resources intentionally reuse the normal Game Data editor instead of adding
an FF7R-only UI fork. Runtime settings write only the project JSON artifact;
research probes are read-only and inspect the installed game on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .dataobject import Entry
from .native_probe import probe_installed_exe
from .runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    config_path,
    load_runtime_config,
    runtime_status,
    save_runtime_config,
)


RUNTIME_TWEAKS_ASSET = "Lexeditor/RuntimeTweaks"
RUNTIME_PROBE_ASSET = "Lexeditor/RuntimeProbe"
NO_MORE_CHEATS_PROBE_ASSET = "Lexeditor/NoMoreCheatsProbe"
VIRTUAL_ASSET_ROWS = (
    {
        "asset": RUNTIME_TWEAKS_ASSET,
        "name": "Runtime Tweaks",
        "group": "Lexeditor Runtime",
        "synthetic": "runtime-settings",
    },
    {
        "asset": RUNTIME_PROBE_ASSET,
        "name": "Native Hook Probe",
        "group": "Lexeditor Runtime",
        "synthetic": "runtime-probe",
    },
    {
        "asset": NO_MORE_CHEATS_PROBE_ASSET,
        "name": "No More Cheats Probe",
        "group": "Lexeditor Research",
        "synthetic": "no-more-cheats-probe",
    },
)

_RUNTIME_SOURCE_SHA = hashlib.sha256(b"lexeditor-ff7r-runtime-config-schema-v3").hexdigest()


@dataclass(frozen=True)
class VirtualProperty:
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


class VirtualPackage:
    def __init__(self, *, asset: str, export_name: str, properties: list[VirtualProperty],
                 entries: list[Entry], source_sha: str, active_sha: str):
        self.asset = asset
        self.export_name = export_name
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


def is_virtual_asset(asset: str) -> bool:
    return asset in {RUNTIME_TWEAKS_ASSET, RUNTIME_PROBE_ASSET, NO_MORE_CHEATS_PROBE_ASSET}


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _runtime_properties() -> list[VirtualProperty]:
    return [
        VirtualProperty("CutsceneEnabled", "Cutscene Speed Enabled", "BOOL", True, 0, 1),
        VirtualProperty("CutsceneBaseMultiplier", "Cutscene Base Multiplier", "FLOAT", True, 1.000001, None),
        VirtualProperty("CutsceneR2Behavior", "R2 Fast-Forward Behavior", "STRING"),
        VirtualProperty("MinimapEnabled", "Minimap Tap/Hold Enabled", "BOOL", True, 0, 1),
        VirtualProperty("MinimapHoldMilliseconds", "Minimap Hold Threshold (ms)", "INT32", True, 150, 1500),
        VirtualProperty("MinimapPersistChosenState", "Persist Chosen Minimap State", "BOOL", True, 0, 1),
        VirtualProperty("MinimapTapBehavior", "Map Button Tap", "STRING"),
        VirtualProperty("MinimapHoldBehavior", "Map Button Hold", "STRING"),
        VirtualProperty("HPRebalanceEnabled", "HP Rebalance Enabled", "BOOL", True, 0, 1),
        VirtualProperty("HPMultiplier", "HP Multiplier", "FLOAT", True, 0.000001, None),
        VirtualProperty("HPRebalanceHookValidated", "HP Rebalance Hook Validated", "BOOL"),
        VirtualProperty("BetterSprintEnabled", "Better Sprint Enabled", "BOOL", True, 0, 1),
        VirtualProperty("SprintSpeedMultiplier", "Sprint Speed Multiplier", "FLOAT", True, 0.000001, None),
        VirtualProperty("BetterSprintHookValidated", "Better Sprint Hook Validated", "BOOL"),
        VirtualProperty("LoaderCandidatePresent", "Native Loader Detected", "BOOL"),
        VirtualProperty("ProjectDllPresent", "Runtime DLL Built", "BOOL"),
        VirtualProperty("ManifestPresent", "Validation Manifest Present", "BOOL"),
        VirtualProperty("HooksValidated", "Core Runtime Hooks Validated", "BOOL"),
        VirtualProperty("RequestedHooksValidated", "All Enabled Runtime Hooks Validated", "BOOL"),
        VirtualProperty("BuildSupported", "Installed EXE Build Supported", "BOOL"),
        VirtualProperty("RuntimeReady", "Runtime Ready To Deploy", "BOOL"),
        VirtualProperty("RuntimeActive", "Runtime Active", "BOOL"),
        VirtualProperty("InstalledExeTimestamp", "Installed EXE Timestamp", "STRING"),
        VirtualProperty("ProjectDllPath", "Project Runtime DLL", "STRING"),
        VirtualProperty("ManifestPath", "Validation Manifest", "STRING"),
        VirtualProperty("RuntimeNotes", "Runtime Validation Notes", "STRING"),
    ]


def runtime_settings_package(game_root: Path, project_root: Path, *, vanilla: bool = False) -> tuple[VirtualPackage, str, bool]:
    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG)) if vanilla else load_runtime_config(project_root)
    status = runtime_status(game_root, project_root)
    cutscene = config["cutsceneSpeed"]
    minimap = config["minimap"]
    hp_rebalance = config["hpRebalance"]
    better_sprint = config["betterSprint"]
    values = {
        "CutsceneEnabled": cutscene["enabled"],
        "CutsceneBaseMultiplier": cutscene["baseMultiplier"],
        "CutsceneR2Behavior": cutscene["r2Behavior"],
        "MinimapEnabled": minimap["enabled"],
        "MinimapHoldMilliseconds": minimap["holdMilliseconds"],
        "MinimapPersistChosenState": minimap["persistChosenState"],
        "MinimapTapBehavior": minimap["tapBehavior"],
        "MinimapHoldBehavior": minimap["holdBehavior"],
        "HPRebalanceEnabled": hp_rebalance["enabled"],
        "HPMultiplier": hp_rebalance["hpMultiplier"],
        "HPRebalanceHookValidated": status["hpRebalanceHookValidated"],
        "BetterSprintEnabled": better_sprint["enabled"],
        "SprintSpeedMultiplier": better_sprint["speedMultiplier"],
        "BetterSprintHookValidated": status["betterSprintHookValidated"],
        "LoaderCandidatePresent": status["loaderCandidatePresent"],
        "ProjectDllPresent": status["projectDllPresent"],
        "ManifestPresent": status["manifestPresent"],
        "HooksValidated": status["hooksValidated"],
        "RequestedHooksValidated": status["requestedHooksValidated"],
        "BuildSupported": status["buildSupported"],
        "RuntimeReady": status["runtimeReady"],
        "RuntimeActive": status["active"],
        "InstalledExeTimestamp": status["installedExeTimestampHex"] or "Unknown",
        "ProjectDllPath": status["projectDllPath"],
        "ManifestPath": status["manifestPath"],
        "RuntimeNotes": status["notes"],
    }
    package = VirtualPackage(
        asset=RUNTIME_TWEAKS_ASSET,
        export_name="LexeditorRuntimeTweaks",
        properties=_runtime_properties(),
        entries=[Entry(0, "Runtime Tweaks", values, {})],
        source_sha=_RUNTIME_SOURCE_SHA,
        active_sha=_canonical_hash(config),
    )
    using_project = not vanilla and config_path(project_root).is_file()
    return package, _RUNTIME_SOURCE_SHA, using_project


def _probe_properties() -> list[VirtualProperty]:
    return [
        VirtualProperty("ExecutableTimestamp", "Executable Timestamp", "STRING"),
        VirtualProperty("ExecutablePath", "Executable Path", "STRING"),
        VirtualProperty("HitCount", "String Hits", "INT32"),
        VirtualProperty("AsciiHits", "ASCII Hits", "INT32"),
        VirtualProperty("Utf16Hits", "UTF-16 Hits", "INT32"),
        VirtualProperty("LeaXrefCount", "RIP-relative LEA Xrefs", "INT32"),
        VirtualProperty("StringRvas", "String RVAs", "STRING"),
        VirtualProperty("CandidateFunctionRvas", "Candidate Function RVAs", "STRING"),
    ]


def _hex_list(values: set[int]) -> str:
    return ", ".join(f"0x{value:X}" for value in sorted(values)) or "—"


def runtime_probe_package(game_root: Path) -> tuple[VirtualPackage, str, bool]:
    result = probe_installed_exe(game_root)
    entries: list[Entry] = []
    for index, row in enumerate(result["needles"]):
        hits = row.get("hits", [])
        xrefs = [xref for hit in hits for xref in hit.get("leaRipXrefs", [])]
        string_rvas = {int(hit["rva"]) for hit in hits}
        candidate_rvas = {
            int(xref["candidateFunctionRva"])
            for xref in xrefs
            if xref.get("candidateFunctionRva") is not None
        }
        values = {
            "ExecutableTimestamp": result["timestampHex"],
            "ExecutablePath": result["path"],
            "HitCount": len(hits),
            "AsciiHits": sum(hit.get("encoding") == "ascii" for hit in hits),
            "Utf16Hits": sum(hit.get("encoding") == "utf16le" for hit in hits),
            "LeaXrefCount": len(xrefs),
            "StringRvas": _hex_list(string_rvas),
            "CandidateFunctionRvas": _hex_list(candidate_rvas),
        }
        entries.append(Entry(index, str(row["needle"]), values, {}))
    active_sha = _canonical_hash(result)
    package = VirtualPackage(
        asset=RUNTIME_PROBE_ASSET,
        export_name="LexeditorRuntimeProbe",
        properties=_probe_properties(),
        entries=entries,
        source_sha=active_sha,
        active_sha=active_sha,
    )
    return package, active_sha, False


def _cheat_probe_properties() -> list[VirtualProperty]:
    return [
        VirtualProperty("SearchTerms", "Search Terms", "STRING"),
        VirtualProperty("TextMatchCount", "Localized Text Matches", "INT32"),
        VirtualProperty("TextIds", "Matched Text IDs", "STRING"),
        VirtualProperty("TextMatches", "Localized Text Evidence", "STRING"),
        VirtualProperty("DataReferenceCount", "DataObject References", "INT32"),
        VirtualProperty("DataReferences", "DataObject Reference Evidence", "STRING"),
        VirtualProperty("SchemaMatches", "Schema / Property Candidates", "STRING"),
        VirtualProperty("TextResourcesScanned", "Text Resources Scanned", "INT32"),
        VirtualProperty("DataObjectsScanned", "DataObjects Scanned", "INT32"),
        VirtualProperty("ScanErrors", "Skipped / Unsupported Resources", "INT32"),
        VirtualProperty("ResearchNotes", "Research Notes", "STRING"),
    ]


def _lines(rows: list[dict], keys: tuple[str, ...]) -> str:
    if not rows:
        return "—"
    return "\n".join(" | ".join(str(row.get(key, "")) for key in keys) for row in rows)


def no_more_cheats_probe_package(game_root: Path, data_root: Path, project_root: Path,
                                 index: dict, *, language: str = "US") -> tuple[VirtualPackage, str, bool]:
    # Local imports avoid a module cycle: archive decorates its catalog with the
    # virtual rows defined in this module.
    from .archive import extract_pair
    from .cheat_probe import scan_installed_menu_candidates
    from .dataobject import DataObjectPackage
    from .text_storage import load_text_package

    text_sources = []
    data_sources = []
    errors: list[str] = []
    wanted_language = language.upper()

    for row in index.get("textAssets", []):
        if str(row.get("language", "")).upper() != wanted_language:
            continue
        asset = str(row.get("asset", ""))
        try:
            package, _source_uasset, _source_uexp, _using_project = load_text_package(
                game_root, data_root, project_root, index, asset, vanilla=True)
            text_sources.append((asset, package))
        except Exception as error:
            errors.append(f"{asset}: {error}")

    for row in index.get("assets", []):
        if row.get("synthetic"):
            continue
        asset = str(row.get("asset", ""))
        try:
            uasset, uexp = extract_pair(game_root, data_root, index, asset)
            data_sources.append((asset, DataObjectPackage(uasset, uexp, asset=asset)))
        except Exception as error:
            errors.append(f"{asset}: {error}")

    result = scan_installed_menu_candidates(
        text_sources, data_sources, language=wanted_language, scan_errors=errors)
    entries: list[Entry] = []
    notes = " ".join(result.get("notes", []))
    for entry_index, target in enumerate(result["targets"]):
        text_matches = target.get("textMatches", [])
        data_refs = target.get("dataReferences", [])
        values = {
            "SearchTerms": ", ".join(target.get("searchTerms", [])) or "—",
            "TextMatchCount": len(text_matches),
            "TextIds": ", ".join(target.get("textIds", [])) or "—",
            "TextMatches": _lines(text_matches, ("asset", "textId", "field", "text")),
            "DataReferenceCount": len(data_refs),
            "DataReferences": _lines(data_refs, ("asset", "record", "property", "value", "match")),
            "SchemaMatches": "\n".join(target.get("schemaMatches", [])) or "—",
            "TextResourcesScanned": result["textResourcesScanned"],
            "DataObjectsScanned": result["dataObjectsScanned"],
            "ScanErrors": len(result.get("scanErrors", [])),
            "ResearchNotes": notes,
        }
        entries.append(Entry(entry_index, target["label"], values, {}))

    active_sha = _canonical_hash(result)
    package = VirtualPackage(
        asset=NO_MORE_CHEATS_PROBE_ASSET,
        export_name="LexeditorNoMoreCheatsProbe",
        properties=_cheat_probe_properties(),
        entries=entries,
        source_sha=active_sha,
        active_sha=active_sha,
    )
    return package, active_sha, False


_EDIT_PATHS = {
    "CutsceneEnabled": ("cutsceneSpeed", "enabled"),
    "CutsceneBaseMultiplier": ("cutsceneSpeed", "baseMultiplier"),
    "MinimapEnabled": ("minimap", "enabled"),
    "MinimapHoldMilliseconds": ("minimap", "holdMilliseconds"),
    "MinimapPersistChosenState": ("minimap", "persistChosenState"),
    "HPRebalanceEnabled": ("hpRebalance", "enabled"),
    "HPMultiplier": ("hpRebalance", "hpMultiplier"),
    "BetterSprintEnabled": ("betterSprint", "enabled"),
    "SprintSpeedMultiplier": ("betterSprint", "speedMultiplier"),
}


def save_runtime_edits(project_root: Path, *, source_sha256: str, active_sha256: str,
                       edits: list[dict[str, Any]]) -> dict:
    if source_sha256 != _RUNTIME_SOURCE_SHA:
        raise RuntimeError("FF7R runtime settings schema changed; reload Runtime Tweaks before saving")
    current = load_runtime_config(project_root)
    if _canonical_hash(current) != active_sha256:
        raise RuntimeError("FF7R runtime settings changed on disk; reload before saving")
    if not isinstance(edits, list):
        raise TypeError("runtime edits must be a list")

    updated = json.loads(json.dumps(current))
    seen: set[str] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("each runtime edit must be an object")
        if int(edit.get("entry", -1)) != 0 or "index" in edit:
            raise ValueError("runtime settings support only scalar edits on the Runtime Tweaks record")
        prop = str(edit.get("property", ""))
        if prop not in _EDIT_PATHS:
            raise ValueError(f"runtime property is read-only or unknown: {prop}")
        if prop in seen:
            raise ValueError(f"duplicate runtime property edit: {prop}")
        seen.add(prop)
        group, field = _EDIT_PATHS[prop]
        updated[group][field] = edit.get("value")

    saved = save_runtime_config(project_root, updated)
    return {
        "asset": RUNTIME_TWEAKS_ASSET,
        "path": str(config_path(project_root)),
        "saved": len(edits),
        "activeSha256": _canonical_hash(saved),
        "usingProject": True,
    }
