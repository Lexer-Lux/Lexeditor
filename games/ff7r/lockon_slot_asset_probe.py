"""Correlate FF7R lock-on marker SoftClass paths with cooked widget candidates.

This is a read-only follow-up to :mod:`games.ff7r.lockon_probe` for issue #429.
The main probe can decode UEndMenuSettings' three BattleLockonMarkerXXWidget
SoftClass paths and can separately rank cooked assets with exact serialized tint
properties. This module joins those two evidence sets by *full package path*.

The red-reticle planner at the end of this module is still fail-closed: it only
produces a write plan when all three numbered lock-on marker widgets resolve
uniquely, each is a dedicated lock-on owner, and each has exactly one blue-
dominant serialized LinearColor candidate. The planner patches all three marker
slots, so it does not need to guess the Default/Wimp/Libra slot mapping.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


MARKER_SLOTS = (
    "BattleLockonMarker00Widget",
    "BattleLockonMarker01Widget",
    "BattleLockonMarker02Widget",
)
BLUE_MIN_COMPONENT = 0.20
BLUE_MIN_DOMINANCE = 0.08


def canonical_cooked_package_path(value: object) -> str:
    """Return a root-neutral Unreal package path suitable for exact joins.

    Examples::

        /Game/UI/WBP_Marker0.WBP_Marker0_C -> ui/wbp_marker0
        End/Content/UI/WBP_Marker0         -> ui/wbp_marker0
        UI/WBP_Marker0.uasset              -> ui/wbp_marker0

    Object/class suffixes are discarded because the cooked asset catalog names
    packages, not generated Blueprint classes. Directory/package identity is
    otherwise preserved exactly so equally named assets in different folders do
    not collide merely because their leaf names match.
    """
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""

    if "'" in text:
        first = text.find("'")
        last = text.rfind("'")
        if 0 <= first < last:
            text = text[first + 1:last]

    text = text.split(":", 1)[0]
    package = text.split(".", 1)[0]
    folded = package.strip().replace("\\", "/").casefold()
    while folded.startswith("//"):
        folded = folded[1:]

    for prefix in (
        "/game/",
        "game/",
        "/end/content/",
        "end/content/",
    ):
        if folded.startswith(prefix):
            folded = folded[len(prefix):]
            break
    folded = folded.lstrip("/")

    for suffix in (".uasset", ".uexp", ".ubulk"):
        if folded.endswith(suffix):
            folded = folded[:-len(suffix)]
            break
    return folded.rstrip("/")


def _candidate_summary(candidate: Mapping[str, Any]) -> dict[str, Any]:
    linear_refs = []
    for ref in candidate.get("serializedLinearColorTintRefs", ()):
        linear_refs.append({
            "property": ref.get("name"),
            "ownerObjectName": ref.get("objectName"),
            "ownerClassName": ref.get("className"),
            "valueOffset": ref.get("valueOffset"),
            "valueEndOffset": ref.get("valueEndOffset"),
            "linearColorValue": ref.get("linearColorValue"),
        })
    return {
        "asset": str(candidate.get("asset", "")),
        "canonicalPackagePath": canonical_cooked_package_path(candidate.get("asset", "")),
        "score": int(candidate.get("score", 0) or 0),
        "containsDedicatedWidgetAnchor": bool(candidate.get("containsDedicatedWidgetAnchor")),
        "resolvedDedicatedOwnerEvidence": bool(candidate.get("resolvedDedicatedOwnerEvidence")),
        "serializedTintPropertyEvidence": bool(candidate.get("serializedTintPropertyEvidence")),
        "serializedTintValueLayoutEvidence": bool(candidate.get("serializedTintValueLayoutEvidence")),
        "serializedLinearColorTintValueEvidence": bool(
            candidate.get("serializedLinearColorTintValueEvidence")
        ),
        "serializedLinearColorTintRefs": linear_refs,
    }


def correlate_marker_slots_to_assets(
    slot_research: Mapping[str, Any],
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Join uniquely decoded marker slots to ranked cooked assets by exact path."""
    if not isinstance(slot_research, Mapping):
        raise TypeError("slot research must be a mapping")

    unique_values = slot_research.get("uniqueSlotValues", {})
    if not isinstance(unique_values, Mapping):
        raise ValueError("slot research uniqueSlotValues must be a mapping")

    by_package: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise TypeError("lock-on candidates must be mappings")
        summary = _candidate_summary(candidate)
        package = summary["canonicalPackagePath"]
        if package:
            by_package.setdefault(package, []).append(summary)

    slot_rows: dict[str, dict[str, Any]] = {}
    correlated = 0
    correlated_with_linear_color = 0
    ambiguous = 0
    unresolved = 0

    for slot in MARKER_SLOTS:
        raw_value = unique_values.get(slot)
        configured_path = ""
        if isinstance(raw_value, Mapping):
            configured_path = str(raw_value.get("assetPath") or "")
        canonical = canonical_cooked_package_path(configured_path)
        matches = list(by_package.get(canonical, ())) if canonical else []
        unique_match = matches[0] if len(matches) == 1 else None

        if not canonical:
            status = "slot-value-unresolved"
            unresolved += 1
        elif not matches:
            status = "cooked-asset-not-found"
            unresolved += 1
        elif len(matches) > 1:
            status = "ambiguous-cooked-asset-match"
            ambiguous += 1
        else:
            status = "unique-exact-package-match"
            correlated += 1
            if unique_match["serializedLinearColorTintValueEvidence"]:
                correlated_with_linear_color += 1

        slot_rows[slot] = {
            "status": status,
            "configuredAssetPath": configured_path or None,
            "canonicalPackagePath": canonical or None,
            "matchCount": len(matches),
            "matches": matches,
            "uniqueCookedAsset": unique_match,
            "uniqueCookedAssetWithLinearColor": bool(
                unique_match and unique_match["serializedLinearColorTintValueEvidence"]
            ),
        }

    all_unique = correlated == len(MARKER_SLOTS)
    blockers: list[str] = []
    if unresolved:
        blockers.append("marker-slot-cooked-assets-unresolved")
    if ambiguous:
        blockers.append("marker-slot-cooked-assets-ambiguous")
    if all_unique:
        blockers.append("marker-slot-to-marker-type-semantics-unvalidated")
        blockers.append("active-blue-reticle-slot-unvalidated")
    if correlated_with_linear_color == 0:
        blockers.append("correlated-marker-linearcolor-unresolved")
    elif correlated_with_linear_color < correlated:
        blockers.append("correlated-marker-linearcolor-incomplete")
    else:
        blockers.append("correlated-marker-linearcolor-rewrite-unvalidated")

    return {
        "implementationReady": False,
        "slotOrder": list(MARKER_SLOTS),
        "slotCorrelations": slot_rows,
        "correlatedSlotCount": correlated,
        "ambiguousSlotCount": ambiguous,
        "unresolvedSlotCount": unresolved,
        "correlatedLinearColorSlotCount": correlated_with_linear_color,
        "allSlotsUniquelyCorrelated": all_unique,
        "slotToMarkerTypeMappingValidated": False,
        "activeBlueReticleSlotValidated": False,
        "redReticleOwnerValidated": False,
        "blockers": blockers,
        "notes": [
            "SoftClass paths and cooked candidates are joined only by normalized full Unreal package path; leaf-name and fuzzy matches are intentionally rejected.",
            "A unique exact package match proves which cooked candidate a numbered UEndMenuSettings marker slot names, provided the upstream decoded SoftClass value is itself unique.",
            "Exact serialized LinearColor evidence on that cooked candidate narrows the presentation owner but does not by itself identify a blue marker value.",
            "00/01/02 -> Default/Wimp/Libra remains unvalidated even when all three slots resolve to distinct cooked assets.",
            "This correlation stage is read-only and never rewrites a cooked asset.",
        ],
    }


def _decoded_rgba(ref: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    value = ref.get("linearColorValue")
    if not isinstance(value, Mapping):
        return None
    try:
        rgba = tuple(float(value[key]) for key in ("r", "g", "b", "a"))
    except (KeyError, TypeError, ValueError):
        return None
    if any(not math.isfinite(component) for component in rgba):
        return None
    return rgba


def _blue_dominant(rgba: tuple[float, float, float, float]) -> bool:
    red, green, blue, alpha = rgba
    return (
        alpha > 0.0
        and blue >= BLUE_MIN_COMPONENT
        and blue - red >= BLUE_MIN_DOMINANCE
        and blue - green >= BLUE_MIN_DOMINANCE
    )


def plan_red_reticle_rewrites(correlation: Mapping[str, Any]) -> dict[str, Any]:
    """Produce exact cooked LinearColor rewrites for all numbered lock-on markers.

    Patching all three UEndMenuSettings BattleLockonMarkerXXWidget slots avoids
    guessing their Default/Wimp/Libra mapping. Ordinary unlocked targeting UI is
    outside these dedicated lock-on marker widget slots, so the planner never
    targets generic BattleTarget assets. A plan is emitted only when every slot
    uniquely resolves to a distinct dedicated lock-on asset and exactly one
    serialized LinearColor in that asset is visibly blue-dominant.
    """
    if not isinstance(correlation, Mapping):
        raise TypeError("lock-on slot correlation must be a mapping")
    rows = correlation.get("slotCorrelations")
    if not isinstance(rows, Mapping):
        raise ValueError("lock-on slot correlation is missing slotCorrelations")

    blockers: list[str] = []
    plan: list[dict[str, Any]] = []
    seen_assets: set[str] = set()

    if not correlation.get("allSlotsUniquelyCorrelated"):
        blockers.append("all-numbered-lockon-marker-assets-not-unique")

    for slot in MARKER_SLOTS:
        row = rows.get(slot)
        if not isinstance(row, Mapping):
            blockers.append(f"{slot}:correlation-missing")
            continue
        candidate = row.get("uniqueCookedAsset")
        if not isinstance(candidate, Mapping):
            blockers.append(f"{slot}:cooked-asset-unresolved")
            continue
        asset = str(candidate.get("asset") or "")
        if not asset:
            blockers.append(f"{slot}:asset-path-missing")
            continue
        canonical = canonical_cooked_package_path(asset)
        if canonical in seen_assets:
            blockers.append(f"{slot}:duplicate-marker-asset")
            continue
        seen_assets.add(canonical)

        if not candidate.get("containsDedicatedWidgetAnchor"):
            blockers.append(f"{slot}:dedicated-lockon-anchor-unproven")
            continue
        if not candidate.get("resolvedDedicatedOwnerEvidence"):
            blockers.append(f"{slot}:dedicated-lockon-owner-unproven")
            continue
        if not candidate.get("serializedLinearColorTintValueEvidence"):
            blockers.append(f"{slot}:linearcolor-unproven")
            continue

        refs = candidate.get("serializedLinearColorTintRefs", ())
        blue_refs: list[tuple[Mapping[str, Any], tuple[float, float, float, float]]] = []
        for ref in refs if isinstance(refs, Iterable) else ():
            if not isinstance(ref, Mapping):
                continue
            rgba = _decoded_rgba(ref)
            if rgba is not None and _blue_dominant(rgba):
                blue_refs.append((ref, rgba))
        if len(blue_refs) != 1:
            blockers.append(f"{slot}:expected-one-blue-linearcolor-found-{len(blue_refs)}")
            continue

        ref, rgba = blue_refs[0]
        property_name = str(ref.get("property") or "")
        object_name = str(ref.get("ownerObjectName") or "")
        class_name = str(ref.get("ownerClassName") or "")
        if not property_name or not object_name or not class_name:
            blockers.append(f"{slot}:linearcolor-owner-identity-incomplete")
            continue

        intensity = max(rgba[0], rgba[1], rgba[2])
        replacement = (intensity, 0.0, 0.0, rgba[3])
        plan.append({
            "slot": slot,
            "asset": asset,
            "canonicalPackagePath": canonical,
            "property": property_name,
            "objectName": object_name,
            "className": class_name,
            "expectedRgba": list(rgba),
            "replacementRgba": list(replacement),
        })

    ready = not blockers and len(plan) == len(MARKER_SLOTS)
    return {
        "implementationReady": ready,
        "redReticleOwnerValidated": ready,
        "rewriteAllNumberedMarkerSlots": ready,
        "slotToMarkerTypeMappingRequired": False,
        "rewritePlan": plan if ready else [],
        "blockers": blockers,
        "notes": [
            "All three numbered BattleLockonMarker widget slots are rewritten together, so their Default/Wimp/Libra ordering is irrelevant to the color change.",
            "The write gate rejects generic target UI, duplicate package matches, shared marker assets, missing dedicated lock-on ownership, and ambiguous/non-blue LinearColor candidates.",
            "Replacement preserves the installed marker's strongest RGB intensity and alpha while rotating the color to red.",
            "The actual writer must still re-probe class/object/property identity and exact expected float32 bytes immediately before mutation.",
        ],
    }
