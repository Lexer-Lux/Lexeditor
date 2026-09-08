"""Reversible, fail-closed Better Lock-on prompt suppression (#429).

The small ``LOCK ON`` prompt and the target reticle are deliberately separate.
Installed vanilla Resident_TxtRes resources must prove one exact US prompt text
ID and the same ID must exist exactly once in every installed localization before
this tweak can be enabled.  When enabled, only that localized text entry is
blanked, and only in the temporary PAK build staging tree.

The active-reticle red tint remains unresolved/read-only. Enabling this resource
never claims or attempts the tint half of #429.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from .archive import extract_pair
from .dataobject import Entry
from .lockon_text_probe import discover_lockon_prompt_texts
from .runtime_dataobject import VirtualPackage, VirtualProperty
from .textresource import TextResourcePackage


BETTER_LOCKON_SCHEMA_VERSION = 1
BETTER_LOCKON_CONFIG_NAME = "LexeditorFF7RBetterLockon.json"
BETTER_LOCKON_ASSET = "Lexeditor/BetterLockon"
DEFAULT_BETTER_LOCKON_CONFIG = {
    "schemaVersion": BETTER_LOCKON_SCHEMA_VERSION,
    "removePrompt": False,
}


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / BETTER_LOCKON_CONFIG_NAME


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Better Lock-on config must be an object")
    if set(value) - {"schemaVersion", "removePrompt"}:
        raise ValueError("Better Lock-on config contains unsupported fields")
    if value.get("schemaVersion", BETTER_LOCKON_SCHEMA_VERSION) != BETTER_LOCKON_SCHEMA_VERSION:
        raise ValueError(f"unsupported Better Lock-on schema: {value.get('schemaVersion')}")
    enabled = value.get("removePrompt", False)
    if not isinstance(enabled, bool):
        raise ValueError("Better Lock-on removePrompt must be boolean")
    return {
        "schemaVersion": BETTER_LOCKON_SCHEMA_VERSION,
        "removePrompt": enabled,
    }


def load_config(project_root: Path) -> dict[str, Any]:
    target = config_path(project_root)
    if not target.is_file():
        return dict(DEFAULT_BETTER_LOCKON_CONFIG)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R Better Lock-on config: {error}") from error
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
        raise RuntimeError("FF7R Better Lock-on config failed atomic readback")
    return reread


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def resource_spec(game_root: Path, data_root: Path, project_root: Path, index: dict,
                  *, vanilla: bool = False) -> dict[str, Any]:
    evidence = discover_lockon_prompt_texts(
        game_root, data_root, project_root, index)
    config = dict(DEFAULT_BETTER_LOCKON_CONFIG) if vanilla else load_config(project_root)
    source_sha = _canonical_hash(evidence)
    active_sha = _canonical_hash({"source": source_sha, "config": config})
    notes = list(evidence.get("notes", ()))
    if evidence.get("labelTextIdResolved"):
        notes.append(
            "Prompt ownership is proven for this installed text set; enabling removes only this text ID in temporary build staging."
        )
    else:
        notes.append(
            "Prompt removal remains blocked until one exact US LOCK ON ID is unique and maps exactly once across every installed Resident_TxtRes language."
        )
    notes.append(
        "Active-reticle red tint is a separate unresolved requirement; this toggle never modifies or claims the reticle asset."
    )
    return {
        "sourceSha256": source_sha,
        "activeSha256": active_sha,
        "usingProject": (not vanilla and config_path(project_root).is_file()),
        "evidence": evidence,
        "properties": [
            VirtualProperty("RemovePrompt", "Remove LOCK ON Prompt", "BOOL", True, 0, 1),
            VirtualProperty("PromptTextIdResolved", "Localized Prompt Text ID Proven", "BOOL"),
            VirtualProperty("PromptTextId", "Prompt Text ID", "STRING"),
            VirtualProperty("LocalizedResources", "Localized Resident Text Resources", "INT32"),
            VirtualProperty("ScanErrors", "Text Scan Errors", "INT32"),
            VirtualProperty("RedReticleReady", "Red Active Reticle Ready", "BOOL"),
            VirtualProperty("ResearchNotes", "Safety / Validation Notes", "STRING"),
        ],
        "values": {
            "RemovePrompt": config["removePrompt"],
            "PromptTextIdResolved": bool(evidence.get("labelTextIdResolved", False)),
            "PromptTextId": str(evidence.get("anchorTextId", "")),
            "LocalizedResources": len(evidence.get("localizedPromptEntries", ())),
            "ScanErrors": len(evidence.get("scanErrors", ())),
            "RedReticleReady": False,
            "ResearchNotes": " ".join(str(note) for note in notes),
        },
    }


def load_virtual_package(game_root: Path, data_root: Path, project_root: Path, index: dict,
                         *, vanilla: bool = False):
    spec = resource_spec(
        game_root, data_root, project_root, index, vanilla=vanilla)
    package = VirtualPackage(
        asset=BETTER_LOCKON_ASSET,
        export_name="LexeditorBetterLockon",
        properties=spec["properties"],
        entries=[Entry(0, "Better Lock-on", spec["values"], {})],
        source_sha=spec["sourceSha256"],
        active_sha=spec["activeSha256"],
    )
    return package, spec["sourceSha256"], spec["usingProject"]


def save_virtual_edits(game_root: Path, data_root: Path, project_root: Path, index: dict,
                       *, source_sha256: str, active_sha256: str,
                       edits: list[dict[str, Any]]) -> dict[str, Any]:
    spec = resource_spec(game_root, data_root, project_root, index)
    if spec["sourceSha256"] != source_sha256:
        raise RuntimeError("Installed FF7R lock-on prompt evidence changed; reload Better Lock-on before saving")
    if spec["activeSha256"] != active_sha256:
        raise RuntimeError("FF7R Better Lock-on config changed on disk; reload before saving")
    if not isinstance(edits, list):
        raise TypeError("Better Lock-on edits must be a list")

    config = load_config(project_root)
    seen = False
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("each Better Lock-on edit must be an object")
        if int(edit.get("entry", -1)) != 0 or "index" in edit:
            raise ValueError("Better Lock-on accepts scalar edits on its single record only")
        if str(edit.get("property", "")) != "RemovePrompt":
            raise ValueError("Better Lock-on property is read-only or unknown")
        if seen:
            raise ValueError("duplicate Better Lock-on prompt edit")
        seen = True
        enabled = edit.get("value")
        if not isinstance(enabled, bool):
            raise ValueError("Remove LOCK ON Prompt must be boolean")
        if enabled and not spec["evidence"].get("labelTextIdResolved", False):
            blockers = ", ".join(str(value) for value in spec["evidence"].get("blockers", ())) or "unresolved"
            raise RuntimeError("Better Lock-on prompt ownership is not fully validated: " + blockers)
        config["removePrompt"] = enabled

    saved = save_config(project_root, config)
    refreshed = resource_spec(game_root, data_root, project_root, index)
    return {
        "asset": BETTER_LOCKON_ASSET,
        "path": str(config_path(project_root)),
        "saved": len(edits),
        "removePrompt": saved["removePrompt"],
        "activeSha256": refreshed["activeSha256"],
        "usingProject": True,
    }


def has_enabled_better_lockon(project_root: Path) -> bool:
    return bool(load_config(project_root)["removePrompt"])


def _staging_pair(staging_root: Path, source_uasset: Path, source_uexp: Path,
                  asset: str) -> tuple[Path, Path]:
    root = Path(staging_root).resolve()
    uasset = (root / f"{asset}.uasset").resolve()
    uexp = (root / f"{asset}.uexp").resolve()
    if root not in uasset.parents or root not in uexp.parents:
        raise ValueError(f"Unsafe FF7R Better Lock-on staging path: {asset}")
    if uasset.is_file() != uexp.is_file():
        raise RuntimeError(f"Better Lock-on staging has an incomplete package pair for {asset}")
    if not uasset.is_file():
        uasset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_uasset, uasset)
        shutil.copy2(source_uexp, uexp)
    return uasset, uexp


def _semantic_rows(package: TextResourcePackage) -> list[tuple[str, str, tuple[tuple[str, str], ...]]]:
    return [
        (
            str(entry.id),
            str(entry.text),
            tuple((str(sub.id), str(sub.text)) for sub in entry.subentries),
        )
        for entry in package.entries
    ]


def materialize_better_lockon(game_root: Path, data_root: Path, project_root: Path,
                              index: dict, staging_root: Path) -> list[dict[str, Any]]:
    """Blank only the proven prompt ID in temporary localized text packages."""
    if not has_enabled_better_lockon(project_root):
        return []

    evidence = discover_lockon_prompt_texts(
        game_root, data_root, project_root, index)
    if not evidence.get("labelTextIdResolved", False):
        blockers = ", ".join(str(value) for value in evidence.get("blockers", ())) or "unresolved"
        raise RuntimeError("Better Lock-on prompt ownership is not fully validated: " + blockers)
    text_id = str(evidence.get("anchorTextId", ""))
    localized = list(evidence.get("localizedPromptEntries", ()))
    if not text_id or not localized:
        raise RuntimeError("Better Lock-on prompt evidence resolved without a usable localized text ID")
    if any(row.get("subentryIndex") is not None for row in localized):
        raise RuntimeError("Better Lock-on prompt resolved to a text sub-entry; automatic staging edit is not supported")

    assets = [str(row.get("asset", "")) for row in localized]
    if any(not asset for asset in assets) or len(set(assets)) != len(assets):
        raise RuntimeError("Better Lock-on localized prompt evidence contains missing or duplicate assets")

    results: list[dict[str, Any]] = []
    for evidence_row in localized:
        asset = str(evidence_row["asset"])
        expected_language = str(evidence_row.get("language", "")).upper()
        source_uasset, source_uexp = extract_pair(
            game_root, data_root, index, asset, collection="textAssets")
        target_uasset, target_uexp = _staging_pair(
            staging_root, source_uasset, source_uexp, asset)
        package = TextResourcePackage(target_uasset, target_uexp, asset=asset)
        if expected_language and str(package.language).upper() != expected_language:
            raise RuntimeError(
                f"Better Lock-on staging language changed for {asset}: "
                f"expected {expected_language}, found {package.language}"
            )
        matches = [entry.index if hasattr(entry, "index") else index_value
                   for index_value, entry in enumerate(package.entries)
                   if str(entry.id) == text_id]
        if len(matches) != 1:
            raise RuntimeError(
                f"Better Lock-on staging text ID {text_id!r} resolved {len(matches)} times in {asset}"
            )
        entry_index = int(matches[0])
        before = _semantic_rows(package)
        package.apply_edits([{"entry": entry_index, "text": ""}])
        expected = list(before)
        old_id, _old_text, old_subs = expected[entry_index]
        expected[entry_index] = (old_id, "", old_subs)
        package.write_pair(target_uasset, target_uexp)

        verified = TextResourcePackage(target_uasset, target_uexp, asset=asset)
        after = _semantic_rows(verified)
        if after != expected:
            raise RuntimeError(
                f"Better Lock-on staging readback changed text other than {text_id!r} in {asset}"
            )
        results.append({
            "asset": asset,
            "language": expected_language or str(verified.language),
            "textId": text_id,
            "entry": entry_index,
            "oldText": before[entry_index][1],
            "newText": "",
        })

    return results
