"""Fail-closed installed-build research for FF7R cutscene speed (#413).

Remake exposes a dedicated ``EGameSpeed_CUT`` channel through
``AEndGameState::SetGameSpeed``. The requested tweak also has to compose with
the game's existing R2/skip/fast-forward behavior, so finding the CUT channel is
not enough: this probe keeps base cutscene speed, cutscene lifecycle, and native
skip/fast-forward evidence separate until an installed build proves the exact
call/argument semantics.

Reflected Unreal names often land in registration glue. When the generic native
probe has exact PE ``.pdata`` function bounds, it also reports conservative
cross-function next hops. This classifier records those separately from direct
string-owner functions rather than pretending a next hop is already a hook.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .native_probe import probe_installed_exe


CUT_SPEED_NEEDLES = (
    "SetGameSpeed",
    "GetGameSpeed",
    "EGameSpeed_CUT",
)
CUTSCENE_ACTION_NEEDLES = (
    "RequestPlayCutScene",
    "PlayCutScene",
)
CUTSCENE_SUPPORT_NEEDLES = (
    "EventScene",
    "CutScene",
)
CUTSCENE_LIFECYCLE_NEEDLES = (
    *CUTSCENE_ACTION_NEEDLES,
    *CUTSCENE_SUPPORT_NEEDLES,
)
FAST_FORWARD_STATE_NEEDLES = (
    "SkipCinema",
    "IsSkipCinema",
    "IsSkipCinemaAtThisFrame",
)
FAST_FORWARD_SUPPORT_NEEDLES = (
    "FastForward",
)
FAST_FORWARD_NEEDLES = (
    *FAST_FORWARD_STATE_NEEDLES,
    *FAST_FORWARD_SUPPORT_NEEDLES,
)
ISOLATION_NEEDLES = (
    "EGameSpeed_SYSTEM",
    "EGameSpeed_BATTLE",
    "EGameSpeed_BATTLE_COMMAND",
)
CUTSCENE_NATIVE_NEEDLES = (
    *CUT_SPEED_NEEDLES,
    *CUTSCENE_LIFECYCLE_NEEDLES,
    *FAST_FORWARD_NEEDLES,
    *ISOLATION_NEEDLES,
)


def _needle_row(native: dict[str, Any], needle: str) -> dict[str, Any]:
    for row in native.get("needles", ()):
        if str(row.get("needle", "")) == needle:
            return dict(row)
    return {}


def _hit_counts(native: dict[str, Any], needles: Iterable[str]) -> dict[str, int]:
    return {
        needle: len(_needle_row(native, needle).get("hits", ()))
        for needle in needles
    }


def _function_evidence(native: dict[str, Any], needles: Iterable[str]) -> dict[str, set[int]]:
    """Collect direct bounded string owners and their trusted cross-function hops."""
    direct: set[int] = set()
    next_hops: set[int] = set()
    for needle in needles:
        row = _needle_row(native, needle)
        for hit in row.get("hits", ()):
            for xref in hit.get("leaRipXrefs", ()):
                source = xref.get("candidateFunctionSource")
                rva = xref.get("candidateFunctionRva")
                # Older/synthetic evidence without a source can still be shown as
                # a direct candidate; stronger cross-function navigation requires
                # the explicit exact-bounds marker.
                if rva is not None and source in (None, "pdata"):
                    direct.add(int(rva))
                if source != "pdata":
                    continue
                # The generic probe emits code refs only for exact .pdata-bounded
                # functions. Recheck that provenance here so malformed inputs
                # cannot smuggle heuristic next hops into the stronger evidence.
                code_refs = xref.get("candidateFunctionCodeRefs") or {}
                for ref in code_refs.get("refs", ()):
                    target = ref.get("targetFunctionRva")
                    if target is not None:
                        next_hops.add(int(target))
    return {"direct": direct, "nextHops": next_hops}


def _all_functions(evidence: dict[str, set[int]]) -> set[int]:
    return set(evidence["direct"]) | set(evidence["nextHops"])


def _function_clusters(native: dict[str, Any]) -> list[dict[str, Any]]:
    """Cluster exact semantic families while preserving direct/next-hop provenance."""
    families = {
        "cut-speed": CUT_SPEED_NEEDLES,
        "cutscene-action": CUTSCENE_ACTION_NEEDLES,
        "cutscene-support": CUTSCENE_SUPPORT_NEEDLES,
        "fast-forward-state": FAST_FORWARD_STATE_NEEDLES,
        "fast-forward-support": FAST_FORWARD_SUPPORT_NEEDLES,
        "non-cut-speed": ISOLATION_NEEDLES,
    }
    needle_family = {
        needle: family
        for family, needles in families.items()
        for needle in needles
    }
    rows: dict[int, dict[str, Any]] = {}
    for needle, family in needle_family.items():
        evidence = _function_evidence(native, (needle,))
        for key, destination in (
            ("direct", "directNeedles"),
            ("nextHops", "nextHopNeedles"),
        ):
            for raw_rva in evidence[key]:
                rva = int(raw_rva)
                row = rows.setdefault(rva, {
                    "functionRva": rva,
                    "families": set(),
                    "directNeedles": set(),
                    "nextHopNeedles": set(),
                })
                row["families"].add(family)
                row[destination].add(needle)

    result = []
    for rva in sorted(rows):
        row = rows[rva]
        families_for_row = sorted(row["families"])
        direct = sorted(row["directNeedles"])
        next_hops = sorted(row["nextHopNeedles"])
        result.append({
            "functionRva": rva,
            "families": families_for_row,
            "familyCount": len(families_for_row),
            "directNeedles": direct,
            "nextHopNeedles": next_hops,
            "crossFamily": len(families_for_row) >= 2,
            "registrationCollisionRisk": len(direct) >= 2,
        })
    return result


def assess_cutscene_runtime_evidence(native: dict[str, Any]) -> dict[str, Any]:
    """Classify cutscene-speed evidence without authorizing a runtime hook."""
    speed_counts = _hit_counts(native, CUT_SPEED_NEEDLES)
    lifecycle_counts = _hit_counts(native, CUTSCENE_LIFECYCLE_NEEDLES)
    lifecycle_action_counts = _hit_counts(native, CUTSCENE_ACTION_NEEDLES)
    lifecycle_support_counts = _hit_counts(native, CUTSCENE_SUPPORT_NEEDLES)
    fast_counts = _hit_counts(native, FAST_FORWARD_NEEDLES)
    fast_state_counts = _hit_counts(native, FAST_FORWARD_STATE_NEEDLES)
    fast_support_counts = _hit_counts(native, FAST_FORWARD_SUPPORT_NEEDLES)
    isolation_counts = _hit_counts(native, ISOLATION_NEEDLES)

    set_speed = _function_evidence(native, ("SetGameSpeed",))
    get_speed = _function_evidence(native, ("GetGameSpeed",))
    cut_channel = _function_evidence(native, ("EGameSpeed_CUT",))
    lifecycle_action = _function_evidence(native, CUTSCENE_ACTION_NEEDLES)
    lifecycle_support = _function_evidence(native, CUTSCENE_SUPPORT_NEEDLES)
    lifecycle = _function_evidence(native, CUTSCENE_LIFECYCLE_NEEDLES)
    fast_forward_state = _function_evidence(native, FAST_FORWARD_STATE_NEEDLES)
    fast_forward_support = _function_evidence(native, FAST_FORWARD_SUPPORT_NEEDLES)
    fast_forward = _function_evidence(native, FAST_FORWARD_NEEDLES)
    non_cut = _function_evidence(native, ISOLATION_NEEDLES)
    clusters = _function_clusters(native)

    speed_direct = set_speed["direct"] | get_speed["direct"]
    speed_all = _all_functions(set_speed) | _all_functions(get_speed)
    cut_direct = cut_channel["direct"]
    cut_all = _all_functions(cut_channel)
    lifecycle_action_direct = lifecycle_action["direct"]
    lifecycle_action_all = _all_functions(lifecycle_action)
    fast_state_direct = fast_forward_state["direct"]
    fast_state_all = _all_functions(fast_forward_state)

    direct_cut_speed_overlap = sorted(speed_direct & cut_direct)
    reachable_cut_speed_overlap = sorted(speed_all & cut_all)
    direct_lifecycle_speed_overlap = sorted(lifecycle_action_direct & (speed_direct | cut_direct))
    reachable_lifecycle_speed_overlap = sorted(lifecycle_action_all & (speed_all | cut_all))
    direct_fast_forward_speed_overlap = sorted(fast_state_direct & (speed_direct | cut_direct))
    reachable_fast_forward_speed_overlap = sorted(fast_state_all & (speed_all | cut_all))

    cut_contract_present = bool(
        speed_counts.get("SetGameSpeed")
        and speed_counts.get("GetGameSpeed")
        and speed_counts.get("EGameSpeed_CUT")
    )
    # Generic EventScene/CutScene labels are useful search anchors but cannot
    # establish the lifecycle call path. Require a generated callable action.
    lifecycle_present = any(lifecycle_action_counts.values())
    lifecycle_support_present = any(lifecycle_support_counts.values())
    # Likewise, generic FastForward text cannot stand in for the generated
    # SkipCinema/IsSkipCinema state contracts used to investigate held-R2.
    fast_forward_state_present = any(fast_state_counts.values())
    fast_forward_support_present = any(fast_support_counts.values())

    blockers: list[str] = []
    if not cut_contract_present:
        blockers.append("cut-game-speed-contract-unresolved")
    if not direct_cut_speed_overlap:
        if reachable_cut_speed_overlap:
            blockers.append("cut-game-speed-channel-next-hop-unvalidated")
        else:
            blockers.append("cut-game-speed-channel-function-unvalidated")
    if not lifecycle_present:
        blockers.append("cutscene-lifecycle-action-unresolved")
        if lifecycle_support_present:
            blockers.append("cutscene-generic-lifecycle-support-only")
    if lifecycle_present and not direct_lifecycle_speed_overlap:
        if reachable_lifecycle_speed_overlap:
            blockers.append("cutscene-lifecycle-next-hop-to-speed-unvalidated")
        else:
            blockers.append("cutscene-lifecycle-to-speed-link-unvalidated")
    if not fast_forward_state_present:
        blockers.append("native-fast-forward-state-unresolved")
        if fast_forward_support_present:
            blockers.append("generic-fast-forward-support-only")
    elif direct_fast_forward_speed_overlap:
        blockers.append("native-fast-forward-multiplier-semantics-unvalidated")
    elif reachable_fast_forward_speed_overlap:
        blockers.append("native-fast-forward-next-hop-semantics-unvalidated")
    else:
        blockers.append("native-fast-forward-to-speed-link-unvalidated")

    # Even perfect co-location or a bounded code edge cannot prove whether the
    # native R2 path replaces, multiplies, or independently layers time scale.
    blockers.extend((
        "base-times-native-fast-forward-formula-unvalidated",
        "cut-only-gameplay-speed-isolation-unvalidated",
        "cutscene-audio-animation-synchronization-unvalidated",
    ))

    def serialize(evidence: dict[str, set[int]]) -> dict[str, list[int]]:
        return {
            "direct": sorted(evidence["direct"]),
            "nextHops": sorted(evidence["nextHops"]),
            "all": sorted(_all_functions(evidence)),
        }

    return {
        "implementationReady": False,
        "blockers": blockers,
        "speedNeedleHits": speed_counts,
        "lifecycleNeedleHits": lifecycle_counts,
        "lifecycleActionNeedleHits": lifecycle_action_counts,
        "lifecycleSupportNeedleHits": lifecycle_support_counts,
        "fastForwardNeedleHits": fast_counts,
        "fastForwardStateNeedleHits": fast_state_counts,
        "fastForwardSupportNeedleHits": fast_support_counts,
        "isolationNeedleHits": isolation_counts,
        "cutGameSpeedContractPresent": cut_contract_present,
        "cutsceneLifecycleCandidatePresent": lifecycle_present,
        "cutsceneLifecycleSupportPresent": lifecycle_support_present,
        "nativeFastForwardStateCandidatePresent": fast_forward_state_present,
        "nativeFastForwardSupportPresent": fast_forward_support_present,
        "candidateFunctions": {
            "setGameSpeed": serialize(set_speed),
            "getGameSpeed": serialize(get_speed),
            "cutChannel": serialize(cut_channel),
            "cutSpeedDirectOverlap": direct_cut_speed_overlap,
            "cutSpeedReachableOverlap": reachable_cut_speed_overlap,
            "cutsceneLifecycle": serialize(lifecycle),
            "cutsceneAction": serialize(lifecycle_action),
            "cutsceneSupport": serialize(lifecycle_support),
            "lifecycleSpeedDirectOverlap": direct_lifecycle_speed_overlap,
            "lifecycleSpeedReachableOverlap": reachable_lifecycle_speed_overlap,
            "nativeFastForward": serialize(fast_forward),
            "nativeFastForwardState": serialize(fast_forward_state),
            "nativeFastForwardSupport": serialize(fast_forward_support),
            "fastForwardSpeedDirectOverlap": direct_fast_forward_speed_overlap,
            "fastForwardSpeedReachableOverlap": reachable_fast_forward_speed_overlap,
            "nonCutSpeedCategories": serialize(non_cut),
            "functionClusters": clusters,
        },
        "knownContracts": {
            "setGameSpeed": "AEndGameState::SetGameSpeed(EGameSpeed, float)",
            "getGameSpeed": "AEndGameState::GetGameSpeed() -> float",
            "cutChannel": "EGameSpeed::EGameSpeed_CUT (separate from SYSTEM/BATTLE categories)",
            "cutSpeedStorage": "AEndGameState::GameSpeed[11], initialized to 1.0; CUT is the generated enum's tenth entry",
            "skipSetter": "UEndCutAPI::SkipCinema(bool)",
            "skipState": "UEndCutAPI::IsSkipCinema() / IsSkipCinemaAtThisFrame()",
            "cutsceneStart": "UEndCutAPI::PlayCutScene(..., bool bStopSkip) / RequestPlayCutScene(FName)",
        },
        "notes": [
            "Remake's generated EGameSpeed surface gives CUT its own speed category, so the intended base multiplier has a plausible cutscene-only channel without modifying SYSTEM or BATTLE categories.",
            "PlayCutScene/RequestPlayCutScene are treated as lifecycle action contracts. Generic EventScene/CutScene labels remain supporting navigation evidence and cannot satisfy the lifecycle-action blocker by themselves.",
            "SkipCinema/IsSkipCinema/IsSkipCinemaAtThisFrame are the specific native skip-state contracts used for held-R2 research. Generic FastForward evidence remains support-only and cannot satisfy the native fast-forward-state blocker.",
            "When exact PE .pdata bounds are available, bounded CALL/JMP/code-LEA next hops are shown separately from direct reflected-string owner functions. A next hop is stronger navigation evidence, not semantic validation.",
            "Multi-name direct owners can be Unreal reflection/registration glue; functionClusters keeps that provenance visible through registrationCollisionRisk.",
            "The requested behavior must preserve the game's native fast-forward factor and multiply it by the configured base rather than replacing it; that composition must be measured/validated on the installed build.",
            "No fixed executable offsets or enum-memory offsets are emitted by this probe.",
        ],
    }


def probe_cutscene_runtime(game_root: Path) -> dict[str, Any]:
    native = probe_installed_exe(Path(game_root), needles=CUTSCENE_NATIVE_NEEDLES)
    return {
        "path": native.get("path"),
        "native": native,
        **assess_cutscene_runtime_evidence(native),
    }
