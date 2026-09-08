"""Correlate FF7R lock-on marker SoftClass paths with cooked widget candidates.

This is a read-only follow-up to :mod:`games.ff7r.lockon_probe` for issue #429.
The main probe can decode UEndMenuSettings' three BattleLockonMarkerXXWidget
SoftClass paths and can separately rank cooked assets with exact serialized tint
properties. This module joins those two evidence sets by *full package path*.

No filename-only, suffix-only or fuzzy matching is permitted. A successful join
still does not establish 00/01/02 -> Default/Wimp/Libra semantics, identify the
blue active-lock state, or authorize rewriting a cooked LinearColor.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


MARKER_SLOTS = (
    "BattleLockonMarker00Widget",
    "BattleLockonMarker01Widget",
    "BattleLockonMarker02Widget",
)


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

    # Accept the common textual wrappers without treating their type prefix as
    # part of the package identity (e.g. BlueprintGeneratedClass'/Game/...').
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
            "Exact serialized LinearColor evidence on that cooked candidate narrows the presentation owner but does not identify the requested blue active-lock state or prove that changing the value is state-scoped.",
            "00/01/02 -> Default/Wimp/Libra remains unvalidated even when all three slots resolve to distinct cooked assets.",
            "This stage is read-only and never rewrites a cooked asset.",
        ],
    }
