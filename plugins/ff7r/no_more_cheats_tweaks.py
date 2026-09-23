"""Reversible, fail-closed removal of FF7R convenience/cheat menu entries.

The tweak never trusts string resemblance alone.  Installed source resources are
rescanned at load/build time and each requested option must resolve to exactly
one fixed-width DataObject array element with menu/control evidence before any
structural deletion is allowed.  Deletions are materialized only in the temporary
build tree, so disabling the tweak restores vanilla data without rewriting the
project overlay.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from .cheat_probe import TARGETS, scan_installed_menu_candidates
from .cheat_probe_safety import assess_menu_candidate_removals
from .dataobject import DataObjectPackage, Entry
from .runtime_dataobject import VirtualPackage, VirtualProperty


NO_MORE_CHEATS_SCHEMA_VERSION = 1
NO_MORE_CHEATS_CONFIG_NAME = "LexeditorFF7RNoMoreCheats.json"
NO_MORE_CHEATS_ASSET = "Lexeditor/NoMoreCheats"
DEFAULT_NO_MORE_CHEATS_CONFIG = {
    "schemaVersion": NO_MORE_CHEATS_SCHEMA_VERSION,
    "enabled": False,
}
EXPECTED_TARGET_KEYS = tuple(target.key for target in TARGETS)


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / NO_MORE_CHEATS_CONFIG_NAME


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("No More Cheats config must be an object")
    if set(value) - {"schemaVersion", "enabled"}:
        raise ValueError("No More Cheats config contains unsupported fields")
    if value.get("schemaVersion", NO_MORE_CHEATS_SCHEMA_VERSION) != NO_MORE_CHEATS_SCHEMA_VERSION:
        raise ValueError(f"unsupported No More Cheats schema: {value.get('schemaVersion')}")
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("No More Cheats enabled must be boolean")
    return {
        "schemaVersion": NO_MORE_CHEATS_SCHEMA_VERSION,
        "enabled": enabled,
    }


def load_config(project_root: Path) -> dict[str, Any]:
    target = config_path(project_root)
    if not target.is_file():
        return dict(DEFAULT_NO_MORE_CHEATS_CONFIG)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R No More Cheats config: {error}") from error
    return validate_config(value)


def save_config(project_root: Path, value: dict[str, Any]) -> dict[str, Any]:
    validated = validate_config(value)
    target = config_path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    reread = load_config(project_root)
    if reread != validated:
        raise RuntimeError("FF7R No More Cheats config failed atomic readback")
    return reread


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def collect_report(game_root: Path, data_root: Path, project_root: Path, index: dict,
                   *, language: str = "US") -> dict[str, Any]:
    """Scan installed vanilla resources only; project overlays never establish ownership."""
    from .archive import extract_pair
    from .text_storage import load_text_package

    text_sources = []
    data_sources = []
    errors: list[str] = []
    wanted_language = language.upper()

    for row in index.get("textAssets", ()):
        if str(row.get("language", "")).upper() != wanted_language:
            continue
        asset = str(row.get("asset", ""))
        try:
            package, _source_uasset, _source_uexp, _using_project = load_text_package(
                game_root, data_root, project_root, index, asset, vanilla=True)
            text_sources.append((asset, package))
        except Exception as error:
            errors.append(f"{asset}: {error}")

    for row in index.get("assets", ()):
        if row.get("synthetic"):
            continue
        asset = str(row.get("asset", ""))
        try:
            uasset, uexp = extract_pair(game_root, data_root, index, asset)
            data_sources.append((asset, DataObjectPackage(uasset, uexp, asset=asset)))
        except Exception as error:
            errors.append(f"{asset}: {error}")

    return scan_installed_menu_candidates(
        text_sources,
        data_sources,
        language=wanted_language,
        scan_errors=errors,
    )


def _status_text(target: dict[str, Any]) -> str:
    if target.get("actionable"):
        selector = target.get("selector") or {}
        return (
            "READY | "
            f"{selector.get('asset', '—')} :: {selector.get('record', '—')} :: "
            f"{selector.get('property', '—')}[{selector.get('index', -1)}]"
        )
    reasons = ", ".join(str(value) for value in target.get("reasonCodes", ())) or "unresolved"
    return f"BLOCKED | {reasons}"


def resource_spec(game_root: Path, data_root: Path, project_root: Path, index: dict,
                  *, vanilla: bool = False, language: str = "US") -> dict[str, Any]:
    report = collect_report(game_root, data_root, project_root, index, language=language)
    assessment = assess_menu_candidate_removals(report)
    config = dict(DEFAULT_NO_MORE_CHEATS_CONFIG) if vanilla else load_config(project_root)
    source_sha = _canonical_hash({"report": report, "assessment": assessment})
    active_sha = _canonical_hash({"source": source_sha, "config": config})
    by_key = {target["key"]: target for target in assessment.get("targets", ())}

    def target_ready(key: str) -> bool:
        return bool(by_key.get(key, {}).get("actionable", False))

    def target_status(key: str) -> str:
        target = by_key.get(key)
        return _status_text(target) if target else "BLOCKED | target-missing"

    notes = list(assessment.get("notes", ()))
    if report.get("scanErrors"):
        notes.append(
            f"{len(report['scanErrors'])} installed resource scan error(s) block structural ownership proof."
        )
    notes.append(
        "When enabled, deletion happens only in the temporary build staging tree; project/content is not structurally rewritten."
    )
    return {
        "sourceSha256": source_sha,
        "activeSha256": active_sha,
        "usingProject": (not vanilla and config_path(project_root).is_file()),
        "report": report,
        "assessment": assessment,
        "properties": [
            VirtualProperty("Enabled", "No More Cheats Enabled", "BOOL", True, 0, 1),
            VirtualProperty("AllTargetsActionable", "All Four Menu Entries Proven", "BOOL"),
            VirtualProperty("FastStartReady", "Fast / Head Start Ready", "BOOL"),
            VirtualProperty("FastStartStatus", "Fast / Head Start Ownership", "STRING"),
            VirtualProperty("EasyModeReady", "Easy Mode Ready", "BOOL"),
            VirtualProperty("EasyModeStatus", "Easy Mode Ownership", "STRING"),
            VirtualProperty("GiftBoxReady", "Gift Box Ready", "BOOL"),
            VirtualProperty("GiftBoxStatus", "Gift Box Ownership", "STRING"),
            VirtualProperty("StreamlinedProgressionReady", "Streamlined Progression Ready", "BOOL"),
            VirtualProperty("StreamlinedProgressionStatus", "Streamlined Progression Ownership", "STRING"),
            VirtualProperty("ScanErrors", "Installed Resource Scan Errors", "INT32"),
            VirtualProperty("ResearchNotes", "Safety / Validation Notes", "STRING"),
        ],
        "values": {
            "Enabled": config["enabled"],
            "AllTargetsActionable": bool(assessment.get("allTargetsActionable", False)),
            "FastStartReady": target_ready("fastStart"),
            "FastStartStatus": target_status("fastStart"),
            "EasyModeReady": target_ready("easyMode"),
            "EasyModeStatus": target_status("easyMode"),
            "GiftBoxReady": target_ready("giftBox"),
            "GiftBoxStatus": target_status("giftBox"),
            "StreamlinedProgressionReady": target_ready("streamlinedProgression"),
            "StreamlinedProgressionStatus": target_status("streamlinedProgression"),
            "ScanErrors": len(report.get("scanErrors", ())),
            "ResearchNotes": " ".join(str(value) for value in notes),
        },
    }


def load_virtual_package(game_root: Path, data_root: Path, project_root: Path, index: dict,
                         *, vanilla: bool = False):
    spec = resource_spec(
        game_root, data_root, project_root, index, vanilla=vanilla)
    package = VirtualPackage(
        asset=NO_MORE_CHEATS_ASSET,
        export_name="LexeditorNoMoreCheats",
        properties=spec["properties"],
        entries=[Entry(0, "No More Cheats", spec["values"], {})],
        source_sha=spec["sourceSha256"],
        active_sha=spec["activeSha256"],
    )
    return package, spec["sourceSha256"], spec["usingProject"]


def save_virtual_edits(game_root: Path, data_root: Path, project_root: Path, index: dict,
                       *, source_sha256: str, active_sha256: str,
                       edits: list[dict[str, Any]]) -> dict[str, Any]:
    spec = resource_spec(game_root, data_root, project_root, index)
    if spec["sourceSha256"] != source_sha256:
        raise RuntimeError("Installed FF7R menu ownership evidence changed; reload No More Cheats before saving")
    if spec["activeSha256"] != active_sha256:
        raise RuntimeError("FF7R No More Cheats config changed on disk; reload before saving")
    if not isinstance(edits, list):
        raise TypeError("No More Cheats edits must be a list")

    config = load_config(project_root)
    seen = False
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("each No More Cheats edit must be an object")
        if int(edit.get("entry", -1)) != 0 or "index" in edit:
            raise ValueError("No More Cheats accepts scalar edits on its single record only")
        if str(edit.get("property", "")) != "Enabled":
            raise ValueError("No More Cheats property is read-only or unknown")
        if seen:
            raise ValueError("duplicate No More Cheats enable edit")
        seen = True
        enabled = edit.get("value")
        if not isinstance(enabled, bool):
            raise ValueError("No More Cheats enabled must be boolean")
        config["enabled"] = enabled

    saved = save_config(project_root, config)
    refreshed = resource_spec(game_root, data_root, project_root, index)
    return {
        "asset": NO_MORE_CHEATS_ASSET,
        "path": str(config_path(project_root)),
        "saved": len(edits),
        "enabled": saved["enabled"],
        "activeSha256": refreshed["activeSha256"],
        "usingProject": True,
    }


def has_enabled_no_more_cheats(project_root: Path) -> bool:
    return bool(load_config(project_root)["enabled"])


def removal_plan(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a deterministic deletion plan only when all requested owners are proved."""
    targets = list(assessment.get("targets", ()))
    by_key = {str(target.get("key", "")): target for target in targets}
    if set(by_key) != set(EXPECTED_TARGET_KEYS) or len(targets) != len(EXPECTED_TARGET_KEYS):
        raise RuntimeError("No More Cheats ownership assessment does not contain exactly the four requested targets")
    if not assessment.get("allTargetsActionable"):
        blocked = [
            f"{key}: {','.join(str(value) for value in by_key[key].get('reasonCodes', ())) or 'blocked'}"
            for key in EXPECTED_TARGET_KEYS
            if not by_key[key].get("actionable")
        ]
        raise RuntimeError("No More Cheats menu ownership is not fully validated: " + "; ".join(blocked))

    plan = []
    identities: set[tuple[str, int, str, int]] = set()
    for key in EXPECTED_TARGET_KEYS:
        target = by_key[key]
        selector = target.get("selector")
        if not isinstance(selector, dict):
            raise RuntimeError(f"No More Cheats target {key} has no structural selector")
        identity = (
            str(selector.get("asset", "")),
            int(selector.get("entryIndex", -1)),
            str(selector.get("property", "")),
            int(selector.get("index", -1)),
        )
        if not identity[0] or identity[1] < 0 or not identity[2] or identity[3] < 0:
            raise RuntimeError(f"No More Cheats target {key} has an invalid structural selector")
        if identity in identities:
            raise RuntimeError("No More Cheats targets resolve to the same structural array element")
        identities.add(identity)
        plan.append({"key": key, "label": target.get("label", key), **selector})

    # Deleting higher indices first prevents one target from shifting another
    # target's selector when two options live in the same declared array.
    return sorted(
        plan,
        key=lambda row: (
            str(row["asset"]).casefold(),
            int(row["entryIndex"]),
            str(row["property"]).casefold(),
            -int(row["index"]),
            str(row["key"]),
        ),
    )


def _staging_pair(staging_root: Path, source_uasset: Path, source_uexp: Path,
                  asset: str) -> tuple[Path, Path]:
    root = Path(staging_root).resolve()
    uasset = (root / f"{asset}.uasset").resolve()
    uexp = (root / f"{asset}.uexp").resolve()
    if root not in uasset.parents or root not in uexp.parents:
        raise ValueError(f"Unsafe FF7R No More Cheats staging path: {asset}")
    if uasset.is_file() != uexp.is_file():
        raise RuntimeError(f"No More Cheats staging has an incomplete package pair for {asset}")
    if not uasset.is_file():
        uasset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_uasset, uasset)
        shutil.copy2(source_uexp, uexp)
    return uasset, uexp


def materialize_no_more_cheats(game_root: Path, data_root: Path, project_root: Path,
                               index: dict, staging_root: Path) -> list[dict[str, Any]]:
    """Apply proved menu-entry deletions to the temporary build tree only."""
    if not has_enabled_no_more_cheats(project_root):
        return []

    from .archive import extract_pair

    report = collect_report(game_root, data_root, project_root, index)
    assessment = assess_menu_candidate_removals(report)
    plan = removal_plan(assessment)
    by_asset: dict[str, list[dict[str, Any]]] = {}
    for row in plan:
        by_asset.setdefault(str(row["asset"]), []).append(row)

    materialized = []
    for asset, selectors in by_asset.items():
        source_uasset, source_uexp = extract_pair(game_root, data_root, index, asset)
        target_uasset, target_uexp = _staging_pair(
            staging_root, source_uasset, source_uexp, asset)
        package = DataObjectPackage(target_uasset, target_uexp, asset=asset)

        for selector in selectors:
            entry_index = int(selector["entryIndex"])
            property_name = str(selector["property"])
            array_index = int(selector["index"])
            matched_ids = {str(value) for value in selector.get("matchedTextIds", ()) if str(value)}
            if not matched_ids:
                raise RuntimeError(f"No More Cheats target {selector['key']} lost its installed text-ID proof")
            if entry_index < 0 or entry_index >= len(package.entries):
                raise RuntimeError(f"No More Cheats target {selector['key']} staged entry index is invalid")
            entry = package.entries[entry_index]
            expected_record = str(selector.get("record", ""))
            if expected_record and entry.tag != expected_record:
                raise RuntimeError(
                    f"No More Cheats target {selector['key']} staged record changed: "
                    f"expected {expected_record!r}, found {entry.tag!r}"
                )
            values = entry.values.get(property_name)
            if not isinstance(values, list) or array_index < 0 or array_index >= len(values):
                raise RuntimeError(
                    f"No More Cheats target {selector['key']} staged selector "
                    f"{property_name}[{array_index}] is no longer valid"
                )
            current = values[array_index]
            if str(current) not in matched_ids:
                raise RuntimeError(
                    f"No More Cheats target {selector['key']} staged value changed; "
                    "structural deletion refused"
                )
            before_length = len(values)
            package.delete_array_element(entry_index, property_name, array_index)
            after_values = package.entries[entry_index].values.get(property_name)
            if not isinstance(after_values, list) or len(after_values) != before_length - 1:
                raise RuntimeError(f"No More Cheats structural deletion failed readback for {selector['key']}")
            materialized.append({
                "key": selector["key"],
                "label": selector["label"],
                "asset": asset,
                "record": expected_record,
                "property": property_name,
                "removedIndex": array_index,
                "removedTextId": str(current),
            })

        package.write_pair(target_uasset, target_uexp)
        verified = DataObjectPackage(target_uasset, target_uexp, asset=asset)
        if bytes(verified.uasset_bytes) != bytes(package.uasset_bytes):
            raise RuntimeError(f"No More Cheats structural .uasset readback failed for {asset}")
        if bytes(verified.uexp_bytes) != bytes(package.uexp_bytes):
            raise RuntimeError(f"No More Cheats structural .uexp readback failed for {asset}")

    if {row["key"] for row in materialized} != set(EXPECTED_TARGET_KEYS):
        raise RuntimeError("No More Cheats build did not remove exactly the four requested menu entries")
    return materialized
