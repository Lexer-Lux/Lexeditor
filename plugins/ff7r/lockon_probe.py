"""Read-only installed-build research for the FF7R Better Lock-on reticle.

The localized ``LOCK ON`` prompt is handled separately by ``lockon_tweaks``. This
probe concentrates on the remaining #429 requirement: tint the active lock-on
reticle red without touching target selection, camera behavior, or unrelated UI.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

from .cooked_serial_probe import probe_installed_serialized_exports
from .native_probe import probe_installed_exe
from .raw_asset_probe import probe_installed_assets


ASSET_TERMS = (
    "lockon", "lock_on", "battlelock", "battletarget", "resident_txtres",
    "menusettings",
)
SERIALIZED_ASSET_TERMS = (
    "lockon", "lock_on", "battlelock", "battletarget", "menusettings",
)
WIDGET_ANCHORS = (
    "EndBattleLockonMarkerIcon",
    "BattleLockonMarker",
)
MARKER_SLOT_ANCHORS = (
    "BattleLockonMarker00Widget",
    "BattleLockonMarker01Widget",
    "BattleLockonMarker02Widget",
)
MARKER_TYPE_ORDER = ("Default", "Wimp", "Libra")
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
INTERESTING_TOKENS = (
    WIDGET_ANCHORS
    + MARKER_SLOT_ANCHORS
    + API_ANCHORS
    + LOCK_STATE_ANCHORS
    + PRESENTATION_TERMS
    + (
        "LOCK ON",
        "LockOn",
        "Marker",
        "Reticle",
        "Crosshair",
    )
)
NATIVE_NEEDLES = (
    "BPShowBattleLockonMarkerIcon",
    "BattleLockonMarker",
    *MARKER_SLOT_ANCHORS,
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


def _contains_dedicated_widget_anchor(value: str) -> bool:
    folded = value.casefold()
    if "endbattlelockonmarkericon" in folded:
        return True
    return re.search(
        r"(?<![a-z0-9_])battlelockonmarker(?![a-z0-9_])",
        folded,
    ) is not None


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
    return _contains_dedicated_widget_anchor(ownership)


def _serialized_ref_is_dedicated(row: dict[str, Any]) -> bool:
    return _contains_dedicated_widget_anchor(_object_searchable(row))


def _serialized_marker_slot_ref(row: dict[str, Any]) -> bool:
    return bool(
        str(row.get("name", "")) in MARKER_SLOT_ANCHORS
        and row.get("propertyTagLayoutPlausible")
        and row.get("softObjectPathValuePlausible")
    )


def _needle_counts(native: dict[str, Any]) -> dict[str, int]:
    return {
        str(row.get("needle", "")): len(row.get("hits", ()))
        for row in native.get("needles", ())
        if row.get("needle")
    }


def assess_lock_state_evidence(native: dict[str, Any]) -> dict[str, Any]:
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
            "The dedicated UEndBattleLockonMarkerIcon may itself be lock-state-scoped; the target-state enum remains a separate fallback/validation lead.",
        ],
    }


def assess_marker_slot_evidence(native: dict[str, Any]) -> dict[str, Any]:
    counts = _needle_counts(native)
    slot_hits = {slot: counts.get(slot, 0) for slot in MARKER_SLOT_ANCHORS}
    return {
        "slotNeedleHits": slot_hits,
        "allSlotAnchorsPresent": all(slot_hits.values()),
        "markerTypeOrder": list(MARKER_TYPE_ORDER),
        "slotOrder": list(MARKER_SLOT_ANCHORS),
        "slotToMarkerTypeMappingValidated": False,
        "notes": [
            "UEndMenuSettings declares BattleLockonMarker00Widget, BattleLockonMarker01Widget and BattleLockonMarker02Widget as separate FSoftClassPath settings.",
            "EEndMenuLockonMarkerType declares Default, Wimp and Libra in that order; ordered-trio correspondence remains a hypothesis until installed behavior validates it.",
        ],
    }


def assess_serialized_marker_slots(candidates: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Collect exact decoded SoftClass/SoftObject values for the three numbered slots."""
    values: dict[str, list[dict[str, Any]]] = {slot: [] for slot in MARKER_SLOT_ANCHORS}
    for candidate in candidates:
        asset_name = str(candidate.get("asset", ""))
        for ref in candidate.get("serializedMarkerSlotRefs", ()):
            slot = str(ref.get("name", ""))
            if slot not in values:
                continue
            path = dict(ref.get("softObjectPathValue") or {})
            if not path.get("assetPath"):
                continue
            row = {
                "asset": asset_name,
                "ownerObjectName": ref.get("objectName"),
                "ownerClassName": ref.get("className"),
                "assetPath": path.get("assetPath"),
                "subPath": path.get("subPath", ""),
            }
            if row not in values[slot]:
                values[slot].append(row)

    unique_values = {
        slot: rows[0] if len(rows) == 1 else None
        for slot, rows in values.items()
    }
    all_resolved = all(unique_values[slot] is not None for slot in MARKER_SLOT_ANCHORS)
    resolved_paths = [
        str(unique_values[slot]["assetPath"])
        for slot in MARKER_SLOT_ANCHORS
        if unique_values[slot] is not None
    ]
    return {
        "slotValues": values,
        "uniqueSlotValues": unique_values,
        "allSlotValuesResolved": all_resolved,
        "allResolvedPathsDistinct": all_resolved and len(set(resolved_paths)) == len(resolved_paths),
        "slotToMarkerTypeMappingValidated": False,
        "markerTypeOrder": list(MARKER_TYPE_ORDER),
        "slotOrder": list(MARKER_SLOT_ANCHORS),
        "notes": [
            "Decoded SoftClass/SoftObject values establish the installed class path configured for a numbered marker slot when exactly one value is found.",
            "Even three unique decoded paths do not prove 00/01/02 correspond to Default/Wimp/Libra or identify which one is the requested active blue target square without installed behavior validation.",
        ],
    }


def rank_lockon_assets(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        strings = _flatten_strings(asset)
        objects = _flatten_objects(asset)
        serial = dict(asset.get("serializedExportEvidence") or {})
        mapping_trusted = bool(serial.get("mappingTrusted", False))
        serialized_refs = list(serial.get("refs", ())) if mapping_trusted else []
        serialized_dedicated_refs = [
            row for row in serialized_refs
            if row.get("propertyTagLike") and _serialized_ref_is_dedicated(row)
        ]
        serialized_tint_refs = [
            row for row in serialized_dedicated_refs
            if _contains_any(str(row.get("name", "")), TINT_SERIAL_TERMS)
        ]
        serialized_plausible_tint_refs = [
            row for row in serialized_tint_refs
            if row.get("propertyTagHeaderPlausible")
        ]
        serialized_layout_tint_refs = [
            row for row in serialized_tint_refs
            if row.get("propertyTagLayoutPlausible")
        ]
        serialized_linear_color_tint_refs = [
            row for row in serialized_layout_tint_refs
            if row.get("linearColorValuePlausible")
        ]
        serialized_marker_slot_refs = [
            row for row in serialized_refs
            if _serialized_marker_slot_ref(row)
        ]

        widget_hits = [
            row for row in strings
            if _contains_dedicated_widget_anchor(str(row.get("text", "")))
        ]
        marker_slot_hits = [
            row for row in strings
            if _contains_any(str(row.get("text", "")), MARKER_SLOT_ANCHORS)
        ]
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
            if _contains_dedicated_widget_anchor(_object_searchable(row))
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
            widget_hits or marker_slot_hits or api_hits or label_hits or resolved_owners
            or state_hits or serialized_dedicated_refs or serialized_marker_slot_refs
        ):
            continue

        score = (
            len(serialized_linear_color_tint_refs) * 20000
            + len(serialized_layout_tint_refs) * 12000
            + len(serialized_plausible_tint_refs) * 9000
            + len(serialized_marker_slot_refs) * 7000
            + len(serialized_tint_refs) * 3000
            + len(serialized_dedicated_refs) * 1500
            + len(resolved_owners) * 6000
            + len(resolved_label_children) * 800
            + len(resolved_reticle_children) * 1800
            + len(marker_slot_hits) * 1500
            + len(widget_hits) * 1200
            + len(api_hits) * 500
            + len(state_hits) * 250
            + len(label_hits) * 250
            + min(len(presentation_hits), 32) * 30
        )
        if widget_hits and presentation_hits:
            score += 1800
        if marker_slot_hits and resolved_owners:
            score += 3000
        if resolved_owners and presentation_hits:
            score += 2400

        ranked.append({
            **asset,
            "widgetAnchorHits": widget_hits,
            "markerSlotAnchorHits": marker_slot_hits,
            "apiAnchorHits": api_hits,
            "lockStateAnchorHits": state_hits,
            "literalLockOnLabelHits": label_hits,
            "presentationPropertyHits": presentation_hits,
            "resolvedDedicatedOwners": resolved_owners,
            "resolvedLabelChildren": resolved_label_children,
            "resolvedReticleChildren": resolved_reticle_children,
            "serializedExportMappingTrusted": mapping_trusted,
            "serializedExportMappingReason": str(serial.get("mappingReason", "")),
            "serializedDedicatedPropertyRefs": serialized_dedicated_refs,
            "serializedTintPropertyRefs": serialized_tint_refs,
            "serializedPlausibleTintTagRefs": serialized_plausible_tint_refs,
            "serializedLayoutTintTagRefs": serialized_layout_tint_refs,
            "serializedLinearColorTintRefs": serialized_linear_color_tint_refs,
            "serializedMarkerSlotRefs": serialized_marker_slot_refs,
            "objectTableErrors": object_table_errors,
            "containsDedicatedWidgetAnchor": bool(widget_hits or resolved_owners or serialized_dedicated_refs),
            "containsMarkerSlotAnchor": bool(marker_slot_hits or serialized_marker_slot_refs),
            "containsLiteralLockOnLabel": bool(label_hits),
            "resolvedDedicatedOwnerEvidence": bool(resolved_owners),
            "resolvedLabelChildEvidence": bool(resolved_label_children),
            "resolvedReticleChildEvidence": bool(resolved_reticle_children),
            "serializedTintPropertyEvidence": bool(serialized_tint_refs),
            "serializedPlausibleTintTagEvidence": bool(serialized_plausible_tint_refs),
            "serializedTintValueLayoutEvidence": bool(serialized_layout_tint_refs),
            "serializedLinearColorTintValueEvidence": bool(serialized_linear_color_tint_refs),
            "serializedMarkerSlotValueEvidence": bool(serialized_marker_slot_refs),
            "strongPresentationCandidate": bool(
                serialized_plausible_tint_refs
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
    ranked = rank_lockon_assets(enriched)
    native = probe_installed_exe(root, needles=NATIVE_NEEDLES)
    lock_state = assess_lock_state_evidence(native)
    marker_slots = assess_marker_slot_evidence(native)
    serialized_marker_slots = assess_serialized_marker_slots(ranked)
    resolved_owner_count = sum(
        1 for row in ranked if row.get("resolvedDedicatedOwnerEvidence"))
    serialized_tint_count = sum(
        1 for row in ranked if row.get("serializedTintPropertyEvidence"))
    plausible_tint_count = sum(
        1 for row in ranked if row.get("serializedPlausibleTintTagEvidence"))
    layout_tint_count = sum(
        1 for row in ranked if row.get("serializedTintValueLayoutEvidence"))
    linear_color_tint_count = sum(
        1 for row in ranked if row.get("serializedLinearColorTintValueEvidence"))
    marker_slot_value_candidate_count = sum(
        len(row.get("serializedMarkerSlotRefs", ())) for row in ranked
    )
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
    if linear_color_tint_count:
        blockers.append("serialized-lockon-linearcolor-ownership-and-rewrite-unvalidated")
    elif layout_tint_count:
        blockers.append("serialized-lockon-tint-value-semantics-unvalidated")
    elif plausible_tint_count:
        blockers.append("serialized-lockon-tint-value-layout-unvalidated")
    elif serialized_tint_count:
        blockers.append("serialized-lockon-tint-property-header-unvalidated")
    else:
        blockers.append("exact-lockon-tint-property-unresolved")
    if lock_state["reflectedContractPresent"]:
        blockers.append("locked-state-predicate-unvalidated")
    else:
        blockers.append("locked-state-predicate-unresolved")
    if serialized_marker_slots["allSlotValuesResolved"]:
        blockers.append("marker-slot-enum-pairing-unvalidated")
    elif marker_slots["allSlotAnchorsPresent"]:
        blockers.append("marker-slot-class-path-values-unresolved")
    else:
        blockers.append("marker-slot-class-path-mapping-unresolved")
    if scan_errors:
        blockers.append("installed-cooked-asset-scan-errors")
    if object_errors and not resolved_owner_count:
        blockers.append("cooked-object-table-ownership-unresolved")

    return {
        "candidates": ranked,
        "native": native,
        "lockStateResearch": lock_state,
        "markerSlotResearch": marker_slots,
        "serializedMarkerSlotResearch": serialized_marker_slots,
        "serializedExportResearch": serialized,
        "scanErrors": scan_errors,
        "objectTableErrors": object_errors,
        "resolvedOwnerCandidateCount": resolved_owner_count,
        "serializedTintCandidateCount": serialized_tint_count,
        "serializedPlausibleTintTagCandidateCount": plausible_tint_count,
        "serializedTintValueLayoutCandidateCount": layout_tint_count,
        "serializedLinearColorTintValueCandidateCount": linear_color_tint_count,
        "serializedMarkerSlotValueCandidateCount": marker_slot_value_candidate_count,
        "implementationReady": False,
        "blockers": blockers,
        "knownContracts": {
            "widgetClass": "UEndBattleLockonMarkerIcon",
            "widgetSetting": "UEndMenuSettings::BattleLockonMarker",
            "markerWidgetSlots": [
                "UEndMenuSettings::BattleLockonMarker00Widget",
                "UEndMenuSettings::BattleLockonMarker01Widget",
                "UEndMenuSettings::BattleLockonMarker02Widget",
            ],
            "markerTypeOrder": list(MARKER_TYPE_ORDER),
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
            "The serialized probe can now decode exact SoftClass/SoftObject path values for numbered marker settings. This can establish configured class paths, but not the enum pairing or which configured class owns the requested active blue reticle.",
            "Serialized tint evidence is accepted only when split-package mapping, property type/header, versioned metadata and bounded value range are independently plausible.",
            "An exact LinearColor identifies a value encoding candidate, not reticle ownership, lock-state scope, or permission to invoke the generic cooked-value writer.",
            "ShowBattleTargetIcon's explicit locked target states remain a separate predicate lead.",
            "No cooked UI export is rewritten by this probe. Exact visual ownership, marker-slot semantics and installed behavior must be validated before reticle tinting is wired to the writer.",
        ],
    }
