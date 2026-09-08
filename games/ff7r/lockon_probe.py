"""Read-only installed-build research for the FF7R Better Lock-on tweak.

The tweak is presentation-only: remove the small ``LOCK ON`` label and tint the
active lock-on reticle red without touching target selection or camera behavior.
Remake exposes both a dedicated battle lock-on marker widget/API and an explicit
battle-target presentation state enum whose locked variants can provide a much
safer locked-vs-unlocked predicate once the installed call path is validated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .native_probe import probe_installed_exe
from .raw_asset_probe import probe_installed_assets


ASSET_TERMS = ("lockon", "lock_on", "battlelock", "battletarget")
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
    # Class/API names such as EndBattleLockonMarkerIcon must not count as label
    # evidence. Only a standalone printable label candidate qualifies here.
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
            "This is a strong locked-vs-unlocked presentation lead, but it must be validated against the exact on-screen reticle/crosshair requested by #429 before any hook uses it.",
        ],
    }


def rank_lockon_assets(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank cooked assets; resolved widget ownership dominates string-only noise."""
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        strings = _flatten_strings(asset)
        objects = _flatten_objects(asset)
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
        if not widget_hits and not api_hits and not label_hits and not resolved_owners and not state_hits:
            continue

        score = (
            len(resolved_owners) * 6000
            + len(resolved_label_children) * 2600
            + len(resolved_reticle_children) * 1800
            + len(widget_hits) * 1200
            + len(api_hits) * 500
            + len(state_hits) * 250
            + len(label_hits) * 1600
            + min(len(presentation_hits), 32) * 30
        )
        if widget_hits and presentation_hits:
            score += 1800
        if widget_hits and label_hits:
            score += 3500
        if resolved_owners and label_hits:
            score += 5000
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
            "objectTableErrors": object_table_errors,
            "containsDedicatedWidgetAnchor": bool(widget_hits or resolved_owners),
            "containsLiteralLockOnLabel": bool(label_hits),
            "resolvedDedicatedOwnerEvidence": bool(resolved_owners),
            "resolvedLabelChildEvidence": bool(resolved_label_children),
            "resolvedReticleChildEvidence": bool(resolved_reticle_children),
            "strongPresentationCandidate": bool(
                (widget_hits or resolved_owners)
                and (presentation_hits or resolved_label_children or resolved_reticle_children)
            ),
            "score": score,
        })

    return sorted(
        ranked,
        key=lambda row: (-int(row["score"]), str(row.get("asset", "")).casefold()),
    )


def probe_better_lockon_sources(game_root: Path) -> dict[str, Any]:
    """Inspect installed cooked UI assets and reflected native anchors read-only."""
    raw = probe_installed_assets(
        Path(game_root),
        terms=ASSET_TERMS,
        interesting_tokens=INTERESTING_TOKENS,
    )
    ranked = rank_lockon_assets(raw.get("assets", ()))
    native = probe_installed_exe(Path(game_root), needles=NATIVE_NEEDLES)
    lock_state = assess_lock_state_evidence(native)
    resolved_owner_count = sum(
        1 for row in ranked if row.get("resolvedDedicatedOwnerEvidence"))
    object_errors = [
        error
        for row in ranked
        for error in row.get("objectTableErrors", ())
    ]
    blockers = [
        "exact-lockon-text-child-unresolved",
        "exact-lockon-tint-property-unresolved",
        "single-cooked-presentation-owner-unvalidated",
    ]
    if lock_state["reflectedContractPresent"]:
        blockers.append("locked-state-predicate-unvalidated")
    else:
        blockers.append("locked-state-predicate-unresolved")
    if raw.get("scanErrors"):
        blockers.append("installed-cooked-asset-scan-errors")
    if object_errors and not resolved_owner_count:
        blockers.append("cooked-object-table-ownership-unresolved")
    return {
        "candidates": ranked,
        "native": native,
        "lockStateResearch": lock_state,
        "scanErrors": list(raw.get("scanErrors", ())),
        "objectTableErrors": object_errors,
        "resolvedOwnerCandidateCount": resolved_owner_count,
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
        },
        "notes": [
            "The dedicated battle lock-on marker widget is the preferred presentation owner; generic battle target widgets are not assumed equivalent.",
            "A standalone LOCK ON string is label evidence only when tied to the same cooked presentation asset; class names containing Lockon do not count as label evidence.",
            "Resolved import/export paths strengthen class/outer ownership beyond printable strings, but still do not prove the exact TextBlock or tint field serialized in the widget payload.",
            "ShowBattleTargetIcon's explicit locked target states provide a separate candidate predicate for active lock state; it is not assumed to drive the same reticle until installed-game behavior validates the relation.",
            "Color/tint/brush/visibility strings rank candidates but do not prove which widget child owns the reticle or label.",
            "No UI asset is rewritten by this probe; exact label-child, locked-state and tint-property ownership must be validated before implementing suppression/tinting.",
        ],
    }
