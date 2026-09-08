"""Read-only installed-build research for the FF7R Better Lock-on reticle.

The localized ``LOCK ON`` prompt is handled separately by ``lockon_tweaks`` once
its Resident_TxtRes ID is proven across languages. This probe now concentrates
on the remaining #429 requirement: tint the active lock-on reticle red without
touching target selection, camera behavior, or unrelated target UI.

Remake exposes both a dedicated battle lock-on marker widget/API and an explicit
battle-target presentation state enum. Cooked object-table ownership is further
correlated with read-only serialized FName/property-tag candidates when the
split-package export mapping can be proven from the installed package header.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .cooked_serial_probe import probe_installed_serialized_exports
from .native_probe import probe_installed_exe
from .raw_asset_probe import probe_installed_assets


# Resident_TxtRes remains in the broad raw scan as historical/diagnostic label
# evidence only. Serialized reticle probing deliberately excludes text resources.
ASSET_TERMS = ("lockon", "lock_on", "battlelock", "battletarget", "resident_txtres")
SERIALIZED_ASSET_TERMS = ("lockon", "lock_on", "battlelock", "battletarget")
WIDGET_ANCHORS = (
    "EndBattleLockonMarkerIcon",
    "BattleLockonMarker",
)
API_ANCHORS = (
    "BPShowBattleLockonMarkerIcon",
    "EEndMenuLockonMarkerType",
)
LOCK_STATE_ANCHORS = (
    "ShowBattleTargetIcon",
    "EEndMenuBattleTargetState",
    "LockedEnabled",
    "LockedDisabled",
    "OutLockedEnabled",
    "OutLockedDisabled",
)
PRESENTATION_TERMS = (
    "ColorAndOpacity",
    "SlateColor",
    "Color",
    "Tint",
    "Brush",
    "Image",
    "Opacity",
    "Visibility",
    "Visible",
    "Hidden",
    "Text",
)
TINT_SERIAL_TERMS = (
    "ColorAndOpacity", "SlateColor", "Color", "Tint", "Brush", "Image",
)
LABEL_CHILD_TERMS = ("text", "label", "caption", "title")
RETICLE_CHILD_TERMS = ("reticle", "marker", "image", "icon", "brush", "crosshair")
INTERESTING_TOKENS = WIDGET_ANCHORS + API_ANCHORS + LOCK_STATE_ANCHORS + PRESENTATION_TERMS + (
    "LOCK ON",
    "LockOn",
    "Marker",
    "Reticle",
    "Crosshair",
)
NATIVE_NEEDLES = (
    "BPShowBattleLockonMarkerIcon",
    "BattleLockonMarker",
    "EndBattleLockonMarkerIcon",
    "EEndMenuLockonMarkerType",
    *LOCK_STATE_ANCHORS,
)
LOCKED_STATES = (
    "LockedEnabled",
    "LockedDisabled",
    "OutLockedEnabled",
    "OutLockedDisabled",
)


def _flatten_strings(asset: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file_row in asset.get("files", ()):
        suffix = str(file_row.get("suffix", ""))
        path = str(file_row.get("path", ""))
        for string_row in file_row.get("interestingStrings", ()):
            rows.append({"suffix": suffix, "path": path, **string_row})
    return rows


def _flatten_objects(asset: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file_row in asset.get("files", ()):
        suffix = str(file_row.get("suffix", ""))
        path = str(file_row.get("path", ""))
        for kind in ("resolvedImports", "resolvedExports"):
            for object_row in file_row.get(kind, ()):
                rows.append({
                    "suffix": suffix,
                    "path": path,
                    "objectKind": "import" if kind == "resolvedImports" else "export",
                    **object_row,
                })
    return rows


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    folded = value.casefold()
    return any(str(term).casefold() in folded for term in terms)


def _literal_lock_on_label(value: str) -> bool:
    normalized = " ".join(value.strip().casefold().replace("-", " ").split())
    return normalized in {"lock on", "lockon"}


def _object_searchable(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("objectName", "objectPath", "outerPath", "className", "classPath", "classPackage")
    )


def _is_child_of_dedicated_owner(row: dict[str, Any]) -> bool:
    ownership = " ".join((
        str(row.get("outerPath") or ""),
        str(row.get("objectPath") or ""),
    ))
    return _contains_any(ownership, WIDGET_ANCHORS)


def _serialized_ref_is_dedicated(row: dict[str, Any]) -> bool:
    return _contains_any(_object_searchable(row), WIDGET_ANCHORS)


def _needle_counts(native: dict[str, Any]) -> dict[str, int]:
    return {
        str(row.get("needle", "")): len(row.get("hits", ()))
        for row in native.get("needles", ())
        if row.get("needle")
    }


def assess_lock_state_evidence(native: dict[str, Any]) -> dict[str, Any]:
    """Classify the explicit target-state surface without promoting it to a hook."""
    counts = _needle_counts(native)
    show_hits = counts.get("ShowBattleTargetIcon", 0)
    enum_hits = counts.get("EEndMenuBattleTargetState", 0)
    locked_hits = {state: counts.get(state, 0) for state in LOCKED_STATES}
    reflected_contract_present = bool(show_hits and enum_hits)
    locked_enumerator_evidence = any(locked_hits.values())
    return {
        "showBattleTargetIconHits": show_hits,
        "battleTargetStateEnumHits": enum_hits,
        "lockedStateNeedleHits": locked_hits,
        "reflectedContractPresent": reflected_contract_present,
        "lockedEnumeratorEvidence": locked_enumerator_evidence,
        "validatedAsIssuePredicate": False,
        "notes": [
            "UEndMenuAPI::ShowBattleTargetIcon receives EEndMenuBattleTargetState, whose reflected locked states are LockedEnabled, LockedDisabled, OutLockedEnabled and OutLockedDisabled.",
            "The dedicated UEndBattleLockonMarkerIcon may itself be lock-state-scoped; the target-state enum is retained as a separate fallback/validation lead until installed behavior proves which surface draws the requested reticle.",
        ],
    }


def rank_lockon_assets(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank cooked reticle candidates; serialized dedicated tags outrank strings."""
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        strings = _flatten_strings(asset)
        objects = _flatten_objects(asset)
        serial = dict(asset.get("serializedExportEvidence") or {})
        serialized_refs = list(serial.get("refs", ()))
        serialized_dedicated_refs = [
            row for row in serialized_refs
            if row.get("propertyTagLike") and _serialized_ref_is_dedicated(row)
        ]
        serialized_tint_refs = [
            row for row in serialized_dedicated_refs
            if _contains_any(str(row.get("name", "")), TINT_SERIAL_TERMS)
        ]

        widget_hits = [row for row in strings if _contains_any(str(row.get("text", "")), WIDGET_ANCHORS)]
        api_hits = [row for row in strings if _contains_any(str(row.get("text", "")), API_ANCHORS)]
        state_hits = [row for row in strings if _contains_any(str(row.get("text", "")), LOCK_STATE_ANCHORS)]
        presentation_hits = [
            row for row in strings
            if _contains_any(str(row.get("text", "")), PRESENTATION_TERMS)
        ]
        label_hits = [
            row for row in strings
            if _literal_lock_on_label(str(row.get("text", "")))
        ]
        resolved_owners = [
            row for row in objects
            if _contains_any(_object_searchable(row), WIDGET_ANCHORS)
        ]
        resolved_label_children = [
            row for row in objects
            if _is_child_of_dedicated_owner(row)
            and _contains_any(
                " ".join((str(row.get("objectName") or ""), str(row.get("className") or ""))),
                LABEL_CHILD_TERMS,
            )
        ]
        resolved_reticle_children = [
            row for row in objects
            if _is_child_of_dedicated_owner(row)
            and _contains_any(
                " ".join((str(row.get("objectName") or ""), str(row.get("className") or ""))),
                RETICLE_CHILD_TERMS,
            )
        ]
        object_table_errors = [
            str(file_row.get("objectTableError"))
            for file_row in asset.get("files", ())
            if file_row.get("objectTableError")
        ]
        if not (
            widget_hits or api_hits or label_hits or resolved_owners or state_hits
            or serialized_dedicated_refs
        ):
            continue

        score = (
            len(serialized_tint_refs) * 9000
            + len(serialized_dedicated_refs) * 3500
            + len(resolved_owners) * 6000
            + len(resolved_label_children) * 800
            + len(resolved_reticle_children) * 1800
            + len(widget_hits) * 1200
            + len(api_hits) * 500
            + len(state_hits) * 250
            + len(label_hits) * 250
            + min(len(presentation_hits), 32) * 30
        )
        if widget_hits and presentation_hits:
            score += 1800
        if resolved_owners and presentation_hits:
            score += 2400

        ranked.append({
            **asset,
            "widgetAnchorHits": widget_hits,
            "apiAnchorHits": api_hits,
            "lockStateAnchorHits": state_hits,
            "literalLockOnLabelHits": label_hits,
            "presentationPropertyHits": presentation_hits,
            "resolvedDedicatedOwners": resolved_owners,
            "resolvedLabelChildren": resolved_label_children,
            "resolvedReticleChildren": resolved_reticle_children,
            "serializedExportMappingTrusted": bool(serial.get("mappingTrusted", False)),
            "serializedExportMappingReason": str(serial.get("mappingReason", "")),
            "serializedDedicatedPropertyRefs": serialized_dedicated_refs,
            "serializedTintPropertyRefs": serialized_tint_refs,
            "objectTableErrors": object_table_errors,
            "containsDedicatedWidgetAnchor": bool(widget_hits or resolved_owners or serialized_dedicated_refs),
            "containsLiteralLockOnLabel": bool(label_hits),
            "resolvedDedicatedOwnerEvidence": bool(resolved_owners),
            "resolvedLabelChildEvidence": bool(resolved_label_children),
            "resolvedReticleChildEvidence": bool(resolved_reticle_children),
            "serializedTintPropertyEvidence": bool(serialized_tint_refs),
            "strongPresentationCandidate": bool(
                serialized_tint_refs
                or ((widget_hits or resolved_owners) and (
                    presentation_hits or resolved_reticle_children
                ))
            ),
            "score": score,
        })

    return sorted(
        ranked,
        key=lambda row: (-int(row["score"]), str(row.get("asset", "")).casefold()),
    )


def probe_better_lockon_sources(game_root: Path) -> dict[str, Any]:
    """Inspect installed cooked reticle assets and reflected native anchors read-only."""
    root = Path(game_root)
    raw = probe_installed_assets(
        root,
        terms=ASSET_TERMS,
        interesting_tokens=INTERESTING_TOKENS,
    )
    serialized = probe_installed_serialized_exports(
        root,
        terms=SERIALIZED_ASSET_TERMS,
        tokens=INTERESTING_TOKENS,
    )
    serialized_by_asset = {
        str(row.get("asset", "")).casefold(): row
        for row in serialized.get("assets", ())
    }
    enriched = []
    for asset in raw.get("assets", ()):
        serial = serialized_by_asset.get(str(asset.get("asset", "")).casefold())
        enriched.append({
            **asset,
            "serializedExportEvidence": serial or {},
        })
    # A serialized candidate may be absent from the broad raw result only after
    # a partial scan error. Never synthesize it into ranking without the normal
    # raw/object evidence surface; report the error instead.
    ranked = rank_lockon_assets(enriched)
    native = probe_installed_exe(root, needles=NATIVE_NEEDLES)
    lock_state = assess_lock_state_evidence(native)
    resolved_owner_count = sum(
        1 for row in ranked if row.get("resolvedDedicatedOwnerEvidence"))
    serialized_tint_count = sum(
        1 for row in ranked if row.get("serializedTintPropertyEvidence"))
    object_errors = [
        error
        for row in ranked
        for error in row.get("objectTableErrors", ())
    ]
    scan_errors = [
        *list(raw.get("scanErrors", ())),
        *list(serialized.get("scanErrors", ())),
    ]

    blockers = ["single-cooked-reticle-owner-unvalidated"]
    if serialized_tint_count:
        blockers.append("serialized-lockon-tint-property-semantics-unvalidated")
    else:
        blockers.append("exact-lockon-tint-property-unresolved")
    if lock_state["reflectedContractPresent"]:
        blockers.append("locked-state-predicate-unvalidated")
    else:
        blockers.append("locked-state-predicate-unresolved")
    if scan_errors:
        blockers.append("installed-cooked-asset-scan-errors")
    if object_errors and not resolved_owner_count:
        blockers.append("cooked-object-table-ownership-unresolved")

    return {
        "candidates": ranked,
        "native": native,
        "lockStateResearch": lock_state,
        "serializedExportResearch": serialized,
        "scanErrors": scan_errors,
        "objectTableErrors": object_errors,
        "resolvedOwnerCandidateCount": resolved_owner_count,
        "serializedTintCandidateCount": serialized_tint_count,
        "implementationReady": False,
        "blockers": blockers,
        "knownContracts": {
            "widgetClass": "UEndBattleLockonMarkerIcon",
            "widgetSetting": "UEndMenuSettings::BattleLockonMarker",
            "showFunction": "UEndMenuAPI::BPShowBattleLockonMarkerIcon",
            "markerType": "EEndMenuLockonMarkerType",
            "targetIconFunction": "UEndMenuAPI::ShowBattleTargetIcon(UObject*, FVector, EEndMenuBattleTargetState)",
            "targetState": "EEndMenuBattleTargetState",
            "lockedTargetStates": list(LOCKED_STATES),
            "promptImplementation": "Lexeditor/BetterLockon removes the proven localized Resident_TxtRes prompt ID in temporary PAK staging",
        },
        "notes": [
            "The localized LOCK ON prompt is no longer a blocker in this probe; it is an independent staging-only text tweak once its cross-language text ID is proven.",
            "The dedicated battle lock-on marker widget is the preferred reticle owner; generic battle target widgets are not assumed equivalent.",
            "Serialized property-tag-like references are accepted only when split-package export mapping is proven and the immediately following FName is a known UE *Property serializer type. They still do not identify the encoded color value layout.",
            "ShowBattleTargetIcon's explicit locked target states remain a separate predicate lead. If installed behavior proves UEndBattleLockonMarkerIcon exists only while locked, the dedicated widget lifecycle may remove the need for a second state hook.",
            "No cooked UI export is rewritten by this probe. Exact serialized value semantics and installed visual ownership must be validated before reticle tinting is implemented.",
        ],
    }
