"""Reversible, fail-closed Better Lock-on presentation tweak (#429).

The tweak has two independent presentation edits:
- remove the small localized ``LOCK ON`` prompt by blanking one proven text ID;
- recolor the three dedicated BattleLockonMarkerXXWidget assets from their
  uniquely proven blue LinearColor to red.

Both edits are materialized only in temporary PAK build staging. Installed game
files and permanent project/content overlays are never rewritten directly.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from .archive import extract_pair, installed_paks
from .cooked_serial_edit import rewrite_unique_linear_color
from .dataobject import Entry
from .lockon_probe import probe_better_lockon_sources
from .lockon_slot_asset_probe import (
    correlate_marker_slots_to_assets,
    plan_red_reticle_rewrites,
)
from .lockon_text_probe import discover_lockon_prompt_texts
from .runtime_dataobject import VirtualPackage, VirtualProperty
from .textresource import TextResourcePackage
from .tooling import get_file


BETTER_LOCKON_SCHEMA_VERSION = 1
BETTER_LOCKON_CONFIG_NAME = "LexeditorFF7RBetterLockon.json"
BETTER_LOCKON_ASSET = "Lexeditor/BetterLockon"
DEFAULT_BETTER_LOCKON_CONFIG = {
    "schemaVersion": BETTER_LOCKON_SCHEMA_VERSION,
    "removePrompt": False,
    "redReticle": False,
}


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / BETTER_LOCKON_CONFIG_NAME


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Better Lock-on config must be an object")
    if set(value) - {"schemaVersion", "removePrompt", "redReticle"}:
        raise ValueError("Better Lock-on config contains unsupported fields")
    if value.get("schemaVersion", BETTER_LOCKON_SCHEMA_VERSION) != BETTER_LOCKON_SCHEMA_VERSION:
        raise ValueError(f"unsupported Better Lock-on schema: {value.get('schemaVersion')}")
    remove_prompt = value.get("removePrompt", False)
    red_reticle = value.get("redReticle", False)
    if not isinstance(remove_prompt, bool):
        raise ValueError("Better Lock-on removePrompt must be boolean")
    if not isinstance(red_reticle, bool):
        raise ValueError("Better Lock-on redReticle must be boolean")
    return {
        "schemaVersion": BETTER_LOCKON_SCHEMA_VERSION,
        "removePrompt": remove_prompt,
        "redReticle": red_reticle,
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


def _red_reticle_plan(game_root: Path) -> dict[str, Any]:
    source = probe_better_lockon_sources(Path(game_root))
    correlation = correlate_marker_slots_to_assets(
        source.get("serializedMarkerSlotResearch", {}),
        source.get("candidates", ()),
    )
    planned = plan_red_reticle_rewrites(correlation)
    return {
        **planned,
        "sourceBlockers": list(source.get("blockers", ())),
        "scanErrors": list(source.get("scanErrors", ())),
        "correlation": correlation,
        "sourceCandidates": list(source.get("candidates", ())),
    }


def _safe_red_reticle_status(game_root: Path, *, requested: bool) -> dict[str, Any]:
    if not requested:
        return {
            "implementationReady": False,
            "rewritePlan": [],
            "blockers": ["enable-red-reticle-to-run-installed-write-gate"],
            "notes": [
                "Red-reticle ownership is validated lazily only when the option is enabled, avoiding a heavy cooked/native scan when merely browsing the resource."
            ],
        }
    try:
        return _red_reticle_plan(game_root)
    except Exception as error:
        return {
            "implementationReady": False,
            "rewritePlan": [],
            "blockers": [f"red-reticle-probe-error:{error}"],
            "notes": ["The installed lock-on marker probe failed closed; no cooked asset is writable."],
        }


def resource_spec(game_root: Path, data_root: Path, project_root: Path, index: dict,
                  *, vanilla: bool = False) -> dict[str, Any]:
    prompt_evidence = discover_lockon_prompt_texts(
        game_root, data_root, project_root, index)
    config = dict(DEFAULT_BETTER_LOCKON_CONFIG) if vanilla else load_config(project_root)
    reticle = _safe_red_reticle_status(game_root, requested=bool(config["redReticle"]))
    source_sha = _canonical_hash({
        "prompt": prompt_evidence,
        "reticleReady": bool(reticle.get("implementationReady")),
        "reticlePlan": reticle.get("rewritePlan", ()),
    })
    active_sha = _canonical_hash({"source": source_sha, "config": config})
    notes = list(prompt_evidence.get("notes", ()))
    if prompt_evidence.get("labelTextIdResolved"):
        notes.append(
            "Prompt ownership is proven for this installed text set; enabling removes only this text ID in temporary build staging."
        )
    else:
        notes.append(
            "Prompt removal remains blocked until one exact US LOCK ON ID is unique and maps exactly once across every installed Resident_TxtRes language."
        )
    if reticle.get("implementationReady"):
        notes.append(
            "Red-reticle gate resolved all three dedicated numbered lock-on marker widgets and one blue LinearColor in each; all three are rewritten to red together in temporary staging."
        )
    else:
        notes.append(
            "Red-reticle write remains fail-closed: "
            + ", ".join(str(value) for value in reticle.get("blockers", ()))
        )
    return {
        "sourceSha256": source_sha,
        "activeSha256": active_sha,
        "usingProject": (not vanilla and config_path(project_root).is_file()),
        "promptEvidence": prompt_evidence,
        "reticleEvidence": reticle,
        "properties": [
            VirtualProperty("RemovePrompt", "Remove LOCK ON Prompt", "BOOL", True, 0, 1),
            VirtualProperty("RedReticle", "Red Active Lock-on Reticle", "BOOL", True, 0, 1),
            VirtualProperty("PromptTextIdResolved", "Localized Prompt Text ID Proven", "BOOL"),
            VirtualProperty("PromptTextId", "Prompt Text ID", "STRING"),
            VirtualProperty("LocalizedResources", "Localized Resident Text Resources", "INT32"),
            VirtualProperty("ScanErrors", "Text Scan Errors", "INT32"),
            VirtualProperty("RedReticleReady", "Red Active Reticle Ready", "BOOL"),
            VirtualProperty("ReticleRewriteCount", "Validated Reticle Widgets", "INT32"),
            VirtualProperty("ResearchNotes", "Safety / Validation Notes", "STRING"),
        ],
        "values": {
            "RemovePrompt": config["removePrompt"],
            "RedReticle": config["redReticle"],
            "PromptTextIdResolved": bool(prompt_evidence.get("labelTextIdResolved", False)),
            "PromptTextId": str(prompt_evidence.get("anchorTextId", "")),
            "LocalizedResources": len(prompt_evidence.get("localizedPromptEntries", ())),
            "ScanErrors": len(prompt_evidence.get("scanErrors", ())),
            "RedReticleReady": bool(reticle.get("implementationReady", False)),
            "ReticleRewriteCount": len(reticle.get("rewritePlan", ())),
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
        raise RuntimeError("Installed FF7R Better Lock-on evidence changed; reload before saving")
    if spec["activeSha256"] != active_sha256:
        raise RuntimeError("FF7R Better Lock-on config changed on disk; reload before saving")
    if not isinstance(edits, list):
        raise TypeError("Better Lock-on edits must be a list")

    config = load_config(project_root)
    seen: set[str] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("each Better Lock-on edit must be an object")
        if int(edit.get("entry", -1)) != 0 or "index" in edit:
            raise ValueError("Better Lock-on accepts scalar edits on its single record only")
        prop = str(edit.get("property", ""))
        if prop not in {"RemovePrompt", "RedReticle"}:
            raise ValueError("Better Lock-on property is read-only or unknown")
        if prop in seen:
            raise ValueError(f"duplicate Better Lock-on edit: {prop}")
        seen.add(prop)
        enabled = edit.get("value")
        if not isinstance(enabled, bool):
            raise ValueError(f"{prop} must be boolean")
        if prop == "RemovePrompt":
            if enabled and not spec["promptEvidence"].get("labelTextIdResolved", False):
                blockers = ", ".join(
                    str(value) for value in spec["promptEvidence"].get("blockers", ())) or "unresolved"
                raise RuntimeError("Better Lock-on prompt ownership is not fully validated: " + blockers)
            config["removePrompt"] = enabled
        else:
            if enabled:
                reticle = _red_reticle_plan(game_root)
                if not reticle.get("implementationReady", False):
                    blockers = ", ".join(str(value) for value in reticle.get("blockers", ())) or "unresolved"
                    raise RuntimeError("Better Lock-on red reticle ownership is not fully validated: " + blockers)
            config["redReticle"] = enabled

    saved = save_config(project_root, config)
    refreshed = resource_spec(game_root, data_root, project_root, index)
    return {
        "asset": BETTER_LOCKON_ASSET,
        "path": str(config_path(project_root)),
        "saved": len(edits),
        "removePrompt": saved["removePrompt"],
        "redReticle": saved["redReticle"],
        "activeSha256": refreshed["activeSha256"],
        "usingProject": True,
    }


def has_enabled_better_lockon(project_root: Path) -> bool:
    config = load_config(project_root)
    return bool(config["removePrompt"] or config["redReticle"])


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


def _staging_bytes_pair(staging_root: Path, asset: str,
                        source_uasset: bytes, source_uexp: bytes) -> tuple[Path, Path]:
    root = Path(staging_root).resolve()
    uasset = (root / f"{asset}.uasset").resolve()
    uexp = (root / f"{asset}.uexp").resolve()
    if root not in uasset.parents or root not in uexp.parents:
        raise ValueError(f"Unsafe FF7R Better Lock-on staging path: {asset}")
    if uasset.is_file() != uexp.is_file():
        raise RuntimeError(f"Better Lock-on staging has an incomplete package pair for {asset}")
    if not uasset.is_file():
        uasset.parent.mkdir(parents=True, exist_ok=True)
        uasset.write_bytes(source_uasset)
        uexp.write_bytes(source_uexp)
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


def _materialize_prompt(game_root: Path, data_root: Path, project_root: Path,
                        index: dict, staging_root: Path) -> list[dict[str, Any]]:
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
            "kind": "prompt",
            "asset": asset,
            "language": expected_language or str(verified.language),
            "textId": text_id,
            "entry": entry_index,
            "oldText": before[entry_index][1],
            "newText": "",
        })
    return results


def _candidate_for_asset(source: dict[str, Any], asset: str) -> dict[str, Any]:
    matches = [
        row for row in source.get("candidates", ())
        if str(row.get("asset", "")).casefold() == str(asset).casefold()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Better Lock-on expected one cooked candidate for {asset}; found {len(matches)}")
    return dict(matches[0])


def _installed_raw_pair(game_root: Path, candidate: dict[str, Any]) -> tuple[bytes, bytes]:
    root = Path(game_root).resolve()
    pak_map = {
        pak.resolve().relative_to(root).as_posix(): pak
        for pak in installed_paks(root)
    }
    files: dict[str, dict[str, Any]] = {}
    for row in candidate.get("files", ()):
        suffix = str(row.get("suffix", ""))
        if suffix in {".uasset", ".uexp"}:
            if suffix in files:
                raise RuntimeError(f"Better Lock-on candidate contains duplicate {suffix} rows")
            files[suffix] = dict(row)
    if set(files) != {".uasset", ".uexp"}:
        raise RuntimeError("Better Lock-on cooked marker candidate does not contain a complete package pair")

    payload: dict[str, bytes] = {}
    for suffix, row in files.items():
        pak = pak_map.get(str(row.get("pak", "")))
        path = str(row.get("path", ""))
        if pak is None or not path:
            raise RuntimeError(f"Better Lock-on cooked marker source is missing for {suffix}")
        payload[suffix] = get_file(pak, path)
    return payload[".uasset"], payload[".uexp"]


def _materialize_red_reticle(game_root: Path, staging_root: Path) -> list[dict[str, Any]]:
    source = probe_better_lockon_sources(Path(game_root))
    correlation = correlate_marker_slots_to_assets(
        source.get("serializedMarkerSlotResearch", {}),
        source.get("candidates", ()),
    )
    plan = plan_red_reticle_rewrites(correlation)
    if not plan.get("implementationReady", False):
        blockers = ", ".join(str(value) for value in plan.get("blockers", ())) or "unresolved"
        raise RuntimeError("Better Lock-on red reticle ownership is not fully validated: " + blockers)

    results: list[dict[str, Any]] = []
    for rewrite in plan["rewritePlan"]:
        asset = str(rewrite["asset"])
        candidate = _candidate_for_asset(source, asset)
        source_uasset, source_uexp = _installed_raw_pair(game_root, candidate)
        target_uasset, target_uexp = _staging_bytes_pair(
            staging_root, asset, source_uasset, source_uexp)
        uasset_bytes = target_uasset.read_bytes()
        before_uexp = target_uexp.read_bytes()
        changed_uexp, report = rewrite_unique_linear_color(
            uasset_bytes,
            before_uexp,
            property_name=str(rewrite["property"]),
            class_name=str(rewrite["className"]),
            object_name=str(rewrite["objectName"]),
            expected_rgba=rewrite["expectedRgba"],
            replacement_rgba=rewrite["replacementRgba"],
            label=asset,
        )
        temporary = target_uexp.with_suffix(target_uexp.suffix + ".tmp")
        temporary.write_bytes(changed_uexp)
        os.replace(temporary, target_uexp)
        if target_uexp.read_bytes() != changed_uexp:
            raise RuntimeError(f"Better Lock-on red reticle write failed readback for {asset}")
        results.append({
            "kind": "reticle",
            "slot": rewrite["slot"],
            "asset": asset,
            "property": rewrite["property"],
            "className": rewrite["className"],
            "objectName": rewrite["objectName"],
            "oldColor": rewrite["expectedRgba"],
            "newColor": rewrite["replacementRgba"],
            "uexpValueOffset": report["uexpValueOffset"],
            "valueSize": report["valueSize"],
            "bytesOutsideValuePreserved": report["bytesOutsideValuePreserved"],
        })
    if len(results) != 3:
        raise RuntimeError(f"Better Lock-on expected three reticle rewrites; produced {len(results)}")
    return results


def materialize_better_lockon(game_root: Path, data_root: Path, project_root: Path,
                              index: dict, staging_root: Path) -> list[dict[str, Any]]:
    """Materialize enabled prompt removal and/or red lock-on markers."""
    config = load_config(project_root)
    if not config["removePrompt"] and not config["redReticle"]:
        return []

    results: list[dict[str, Any]] = []
    if config["removePrompt"]:
        results.extend(_materialize_prompt(
            game_root, data_root, project_root, index, staging_root))
    if config["redReticle"]:
        results.extend(_materialize_red_reticle(game_root, staging_root))
    return results
