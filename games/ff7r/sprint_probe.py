"""Fail-closed installed-build research for FF7R Better Sprint (#430).

The issue requires actual player sprint velocity, not merely faster animation.  This
probe therefore keeps several superficially relevant root-motion/animation fields
separate and never promotes them into an implementation until their runtime scope
is demonstrated on the installed Remake build.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .dataobject import DataObjectPackage
from .native_probe import probe_installed_exe


SPRINT_NATIVE_NEEDLES = (
    "DashRootMotionTranslationScale",
    "RunToDashBlendInputThreshold",
    "RootMotionTranslationScale",
    "RootMotionScale",
    "AnimNotify_EndModifyRootMotionScale",
    "IdleSwitchBehaviorDashInputBlockTime",
    "RunSwitchBehaviorDashInputBlockTime",
)
SPRINT_DATA_FIELDS = frozenset({
    "DashRootMotionTranslationScale",
    "RootMotionTranslationScale",
    "AnimationPlayRate",
})
SPRINT_DATA_ASSET_TOKENS = ("indoorvolume", "charaspec")
MAX_DATA_CANDIDATES = 128

# Generated Remake SDK evidence used only to classify candidate semantics.  These
# declarations do not prove which installed native callsite controls movement.
KNOWN_CONTRACTS = (
    {
        "symbol": "FEndDataTableInDoorVolume.DashRootMotionTranslationScale",
        "meaning": "authored dash root-motion scale associated with indoor-volume data",
        "sprintAuthority": "unproven",
        "risk": "volume-scoped; not evidence for a global player-only sprint coefficient",
    },
    {
        "symbol": "UEndAnimationSettings.RunToDashBlendInputThreshold",
        "meaning": "run-to-dash blend/input threshold",
        "sprintAuthority": "rejected-as-speed-coefficient",
        "risk": "changes transition threshold, not demonstrated movement velocity",
    },
    {
        "symbol": "FEndDataTableCharaSpec.RootMotionTranslationScale",
        "meaning": "general character root-motion translation scale",
        "sprintAuthority": "unproven",
        "risk": "too broad until walking/jogging/scripted motion isolation is demonstrated",
    },
    {
        "symbol": "UAnimNotify_EndModifyRootMotionScale.RootMotionScale",
        "meaning": "per-animation root-motion modifier",
        "sprintAuthority": "unproven",
        "risk": "candidate animation-local mechanism; authoritative sprint animation/callsite is unknown",
    },
)


def _needle_rows(native: dict[str, Any]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for row in native.get("needles", ()):
        needle = str(row.get("needle", ""))
        if not needle:
            continue
        hits = list(row.get("hits", ()))
        xrefs = [xref for hit in hits for xref in hit.get("leaRipXrefs", ())]
        functions = {
            int(xref["candidateFunctionRva"])
            for xref in xrefs
            if xref.get("candidateFunctionRva") is not None
        }
        result[needle] = {
            "stringHits": len(hits),
            "leaXrefs": len(xrefs),
            "candidateFunctions": len(functions),
        }
    return result


def assess_sprint_evidence(native: dict[str, Any], data_candidates: list[dict[str, Any]],
                           *, scan_errors: list[str] | tuple[str, ...] = (),
                           data_scan_truncated: bool = False) -> dict[str, Any]:
    """Classify evidence without confusing animation/root motion with sprint velocity."""
    native_rows = _needle_rows(native)
    field_counts = Counter(str(row.get("field", "")) for row in data_candidates)
    blockers = [
        "authoritative-player-sprint-speed-path-unvalidated",
        "walk-jog-scripted-movement-isolation-unvalidated",
        "playable-character-relative-speed-preservation-unvalidated",
    ]
    if scan_errors:
        blockers.append("installed-data-scan-errors")
    if data_scan_truncated:
        blockers.append("installed-data-candidate-scan-truncated")

    return {
        "implementationReady": False,
        "blockers": blockers,
        "nativeNeedleStats": native_rows,
        "fieldCandidateCounts": dict(sorted(field_counts.items())),
        "dataCandidates": data_candidates,
        "knownContracts": [dict(row) for row in KNOWN_CONTRACTS],
        "scanErrors": list(scan_errors),
        "dataScanTruncated": bool(data_scan_truncated),
        "notes": [
            "RunToDashBlendInputThreshold is a transition/input threshold and is not treated as movement speed.",
            "DashRootMotionTranslationScale is kept as an indoor-volume authored candidate, not promoted to a global sprint multiplier.",
            "CharaSpec RootMotionTranslationScale is intentionally rejected as a safe tweak until sprint-only scope is proved.",
            "AnimNotify_EndModifyRootMotionScale is a per-animation lead; the installed sprint animation/callsite still needs validation.",
            "A valid implementation must multiply actual player sprint displacement/velocity while leaving walking, jogging, scripted movement, cutscenes and non-player actors unchanged.",
        ],
    }


def probe_better_sprint_sources(game_root: Path, data_root: Path, index: dict) -> dict[str, Any]:
    """Collect bounded native plus likely authored-data evidence from an installed build."""
    from .archive import extract_pair

    native = probe_installed_exe(game_root, needles=SPRINT_NATIVE_NEEDLES)
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    truncated = False

    for row in index.get("assets", ()):
        if row.get("synthetic"):
            continue
        asset = str(row.get("asset", ""))
        folded = asset.casefold()
        if not any(token in folded for token in SPRINT_DATA_ASSET_TOKENS):
            continue
        try:
            uasset, uexp = extract_pair(game_root, data_root, index, asset)
            package = DataObjectPackage(uasset, uexp, asset=asset)
        except Exception as error:
            errors.append(f"{asset}: {error}")
            continue
        matched_fields = [prop.name for prop in package.properties if prop.name in SPRINT_DATA_FIELDS]
        if not matched_fields:
            continue
        for entry in package.entries:
            for field in matched_fields:
                if field not in entry.values:
                    continue
                candidates.append({
                    "asset": asset,
                    "entryIndex": entry.index,
                    "record": entry.tag,
                    "field": field,
                    "value": entry.values[field],
                })
                if len(candidates) >= MAX_DATA_CANDIDATES:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break

    assessed = assess_sprint_evidence(
        native,
        candidates,
        scan_errors=errors,
        data_scan_truncated=truncated,
    )
    return {
        "path": native.get("path"),
        "native": native,
        **assessed,
    }
