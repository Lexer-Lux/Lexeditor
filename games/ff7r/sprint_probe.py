"""Fail-closed installed-build research for FF7R Better Sprint (#430).

The issue requires actual player sprint velocity, not merely faster animation. This
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

# Generated Remake SDK evidence used only to classify candidate semantics. These
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
        "meaning": "per-animation root-motion modifier whose generated default is 1.0",
        "sprintAuthority": "unproven",
        "risk": "candidate animation-local mechanism; authoritative sprint animation/callsite is unknown",
    },
)


def _native_function_evidence(native: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    """Collect exact .pdata-bounded direct and one-hop function candidates.

    Padding-heuristic function guesses are excluded from correlation. A direct
    candidate is a .pdata-described function containing the reflected-string LEA;
    a next-hop candidate is a .pdata-described function reached through one of the
    probe's conservative direct CALL/JMP/RIP-relative code references.
    """
    result: dict[str, dict[str, list[int]]] = {}
    for row in native.get("needles", ()):
        needle = str(row.get("needle", ""))
        if not needle:
            continue
        direct: set[int] = set()
        next_hops: set[int] = set()
        for hit in row.get("hits", ()):
            for xref in hit.get("leaRipXrefs", ()):
                if xref.get("candidateFunctionSource") != "pdata":
                    continue
                function_rva = xref.get("candidateFunctionRva")
                if function_rva is not None:
                    direct.add(int(function_rva))
                code_refs = xref.get("candidateFunctionCodeRefs") or {}
                for code_ref in code_refs.get("refs", ()):
                    target_rva = code_ref.get("targetFunctionRva")
                    if target_rva is not None:
                        next_hops.add(int(target_rva))
        result[needle] = {
            "directPdataFunctions": sorted(direct),
            "nextHopPdataFunctions": sorted(next_hops),
            "expandedPdataFunctions": sorted(direct | next_hops),
        }
    return result


def _needle_rows(native: dict[str, Any]) -> dict[str, dict[str, int]]:
    function_evidence = _native_function_evidence(native)
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
        exact = function_evidence.get(needle, {})
        result[needle] = {
            "stringHits": len(hits),
            "leaXrefs": len(xrefs),
            "candidateFunctions": len(functions),
            "pdataFunctions": len(exact.get("directPdataFunctions", ())),
            "nextHopPdataFunctions": len(exact.get("nextHopPdataFunctions", ())),
        }
    return result


def _expanded_functions(function_evidence: dict[str, dict[str, list[int]]], *needles: str) -> set[int]:
    functions: set[int] = set()
    for needle in needles:
        functions.update(function_evidence.get(needle, {}).get("expandedPdataFunctions", ()))
    return functions


def assess_sprint_evidence(native: dict[str, Any], data_candidates: list[dict[str, Any]],
                           *, scan_errors: list[str] | tuple[str, ...] = (),
                           data_scan_truncated: bool = False) -> dict[str, Any]:
    """Classify evidence without confusing animation/root motion with sprint velocity."""
    native_rows = _needle_rows(native)
    function_evidence = _native_function_evidence(native)
    field_counts = Counter(str(row.get("field", "")) for row in data_candidates)

    dash_functions = _expanded_functions(function_evidence, "DashRootMotionTranslationScale")
    transition_functions = _expanded_functions(function_evidence, "RunToDashBlendInputThreshold")
    animation_root_motion_functions = _expanded_functions(
        function_evidence,
        "AnimNotify_EndModifyRootMotionScale",
        "RootMotionScale",
    )
    general_root_motion_functions = _expanded_functions(function_evidence, "RootMotionTranslationScale")
    correlations = {
        "dashToAnimationRootMotion": sorted(dash_functions & animation_root_motion_functions),
        "runToDashToAnimationRootMotion": sorted(transition_functions & animation_root_motion_functions),
        "dashToGeneralRootMotion": sorted(dash_functions & general_root_motion_functions),
    }

    blockers = [
        "authoritative-player-sprint-speed-path-unvalidated",
        "walk-jog-scripted-movement-isolation-unvalidated",
        "playable-character-relative-speed-preservation-unvalidated",
    ]
    if scan_errors:
        blockers.append("installed-data-scan-errors")
    if data_scan_truncated:
        blockers.append("installed-data-candidate-scan-truncated")

    correlation_note = (
        "Exact .pdata candidate correlation: "
        f"dash↔animation-root-motion={len(correlations['dashToAnimationRootMotion'])}, "
        f"run-to-dash↔animation-root-motion={len(correlations['runToDashToAnimationRootMotion'])}, "
        f"dash↔general-root-motion={len(correlations['dashToGeneralRootMotion'])}. "
        "These overlaps are research leads only; reflected registration glue can share functions without proving runtime sprint authority."
    )

    return {
        "implementationReady": False,
        "blockers": blockers,
        "nativeNeedleStats": native_rows,
        "nativeFunctionEvidence": function_evidence,
        "nativeFunctionCorrelations": correlations,
        "fieldCandidateCounts": dict(sorted(field_counts.items())),
        "dataCandidates": data_candidates,
        "knownContracts": [dict(row) for row in KNOWN_CONTRACTS],
        "scanErrors": list(scan_errors),
        "dataScanTruncated": bool(data_scan_truncated),
        "notes": [
            "RunToDashBlendInputThreshold is a transition/input threshold and is not treated as movement speed.",
            "DashRootMotionTranslationScale is kept as an indoor-volume authored candidate, not promoted to a global sprint multiplier.",
            "CharaSpec RootMotionTranslationScale is intentionally rejected as a safe tweak until sprint-only scope is proved.",
            "AnimNotify_EndModifyRootMotionScale is a per-animation lead with a generated 1.0 RootMotionScale default; the installed sprint animation/callsite still needs validation.",
            correlation_note,
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
