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
CUTSCENE_LIFECYCLE_NEEDLES = (
    "RequestPlayCutScene",
    "PlayCutScene",
    "EventScene",
    "CutScene",
)
FAST_FORWARD_NEEDLES = (
    "SkipCinema",
    "IsSkipCinema",
    "IsSkipCinemaAtThisFrame",
    "FastForward",
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


def assess_cutscene_runtime_evidence(native: dict[str, Any]) -> dict[str, Any]:
    """Classify cutscene-speed evidence without authorizing a runtime hook."""
    speed_counts = _hit_counts(native, CUT_SPEED_NEEDLES)
    lifecycle_counts = _hit_counts(native, CUTSCENE_LIFECYCLE_NEEDLES)
    fast_counts = _hit_counts(native, FAST_FORWARD_NEEDLES)
    isolation_counts = _hit_counts(native, ISOLATION_NEEDLES)

    set_speed = _function_evidence(native, ("SetGameSpeed",))
    get_speed = _function_evidence(native, ("GetGameSpeed",))
    cut_channel = _function_evidence(native, ("EGameSpeed_CUT",))
    lifecycle = _function_evidence(native, CUTSCENE_LIFECYCLE_NEEDLES)
    fast_forward = _function_evidence(native, FAST_FORWARD_NEEDLES)
    non_cut = _function_evidence(native, ISOLATION_NEEDLES)

    speed_direct = set_speed["direct"] | get_speed["direct"]
    speed_all = _all_functions(set_speed) | _all_functions(get_speed)
    cut_direct = cut_channel["direct"]
    cut_all = _all_functions(cut_channel)
    lifecycle_direct = lifecycle["direct"]
    lifecycle_all = _all_functions(lifecycle)
    fast_direct = fast_forward["direct"]
    fast_all = _all_functions(fast_forward)

    direct_cut_speed_overlap = sorted(speed_direct & cut_direct)
    reachable_cut_speed_overlap = sorted(speed_all & cut_all)
    direct_lifecycle_speed_overlap = sorted(lifecycle_direct & (speed_direct | cut_direct))
    reachable_lifecycle_speed_overlap = sorted(lifecycle_all & (speed_all | cut_all))
    direct_fast_forward_speed_overlap = sorted(fast_direct & (speed_direct | cut_direct))
    reachable_fast_forward_speed_overlap = sorted(fast_all & (speed_all | cut_all))

    cut_contract_present = bool(
        speed_counts.get("SetGameSpeed")
        and speed_counts.get("GetGameSpeed")
        and speed_counts.get("EGameSpeed_CUT")
    )
    lifecycle_present = any(lifecycle_counts.values())
    fast_forward_state_present = bool(
        fast_counts.get("SkipCinema")
        or fast_counts.get("IsSkipCinema")
        or fast_counts.get("IsSkipCinemaAtThisFrame")
        or fast_counts.get("FastForward")
    )

    blockers: list[str] = []
    if not cut_contract_present:
        blockers.append("cut-game-speed-contract-unresolved")
    if not direct_cut_speed_overlap:
        if reachable_cut_speed_overlap:
            blockers.append("cut-game-speed-channel-next-hop-unvalidated")
        else:
            blockers.append("cut-game-speed-channel-function-unvalidated")
    if not lifecycle_present:
        blockers.append("cutscene-lifecycle-anchors-unresolved")
    if not direct_lifecycle_speed_overlap:
        if reachable_lifecycle_speed_overlap:
            blockers.append("cutscene-lifecycle-next-hop-to-speed-unvalidated")
        else:
            blockers.append("cutscene-lifecycle-to-speed-link-unvalidated")
    if not fast_forward_state_present:
        blockers.append("native-fast-forward-state-unresolved")
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
        "fastForwardNeedleHits": fast_counts,
        "isolationNeedleHits": isolation_counts,
        "cutGameSpeedContractPresent": cut_contract_present,
        "cutsceneLifecycleCandidatePresent": lifecycle_present,
        "nativeFastForwardStateCandidatePresent": fast_forward_state_present,
        "candidateFunctions": {
            "setGameSpeed": serialize(set_speed),
            "getGameSpeed": serialize(get_speed),
            "cutChannel": serialize(cut_channel),
            "cutSpeedDirectOverlap": direct_cut_speed_overlap,
            "cutSpeedReachableOverlap": reachable_cut_speed_overlap,
            "cutsceneLifecycle": serialize(lifecycle),
            "lifecycleSpeedDirectOverlap": direct_lifecycle_speed_overlap,
            "lifecycleSpeedReachableOverlap": reachable_lifecycle_speed_overlap,
            "nativeFastForward": serialize(fast_forward),
            "fastForwardSpeedDirectOverlap": direct_fast_forward_speed_overlap,
            "fastForwardSpeedReachableOverlap": reachable_fast_forward_speed_overlap,
            "nonCutSpeedCategories": serialize(non_cut),
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
            "SkipCinema/IsSkipCinema are reflected native skip-state contracts. They are useful R2/fast-forward research anchors, but their names do not prove the existing held-R2 multiplier or its numeric value.",
            "When exact PE .pdata bounds are available, bounded CALL/JMP/code-LEA next hops are shown separately from direct reflected-string owner functions. A next hop is stronger navigation evidence, not semantic validation.",
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
