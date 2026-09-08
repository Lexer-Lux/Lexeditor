"""Fail-closed installed-build research for FF7R cutscene speed (#413).

Remake exposes a dedicated ``EGameSpeed_CUT`` channel through
``AEndGameState::SetGameSpeed``.  The requested tweak also has to compose with
the game's existing R2/skip/fast-forward behavior, so finding the CUT channel is
not enough: this probe keeps base cutscene speed, cutscene lifecycle, and native
skip/fast-forward evidence separate until an installed build proves the exact
call/argument semantics.
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


def _function_rvas(native: dict[str, Any], needles: Iterable[str]) -> set[int]:
    """Collect only bounded functions reported by the generic native probe."""
    functions: set[int] = set()
    for needle in needles:
        row = _needle_row(native, needle)
        for hit in row.get("hits", ()):
            for xref in hit.get("leaRipXrefs", ()):
                rva = xref.get("candidateFunctionRva")
                if rva is not None:
                    functions.add(int(rva))
    return functions


def assess_cutscene_runtime_evidence(native: dict[str, Any]) -> dict[str, Any]:
    """Classify cutscene-speed evidence without authorizing a runtime hook."""
    speed_counts = _hit_counts(native, CUT_SPEED_NEEDLES)
    lifecycle_counts = _hit_counts(native, CUTSCENE_LIFECYCLE_NEEDLES)
    fast_counts = _hit_counts(native, FAST_FORWARD_NEEDLES)
    isolation_counts = _hit_counts(native, ISOLATION_NEEDLES)

    set_speed_functions = _function_rvas(native, ("SetGameSpeed",))
    get_speed_functions = _function_rvas(native, ("GetGameSpeed",))
    cut_channel_functions = _function_rvas(native, ("EGameSpeed_CUT",))
    lifecycle_functions = _function_rvas(native, CUTSCENE_LIFECYCLE_NEEDLES)
    fast_forward_functions = _function_rvas(native, FAST_FORWARD_NEEDLES)
    non_cut_speed_functions = _function_rvas(native, ISOLATION_NEEDLES)

    speed_channel_functions = set_speed_functions | get_speed_functions
    cut_speed_overlap = sorted(speed_channel_functions & cut_channel_functions)
    lifecycle_speed_overlap = sorted(lifecycle_functions & (speed_channel_functions | cut_channel_functions))
    fast_forward_speed_overlap = sorted(
        fast_forward_functions & (speed_channel_functions | cut_channel_functions)
    )

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
    if not cut_speed_overlap:
        blockers.append("cut-game-speed-channel-function-unvalidated")
    if not lifecycle_present:
        blockers.append("cutscene-lifecycle-anchors-unresolved")
    if not lifecycle_speed_overlap:
        blockers.append("cutscene-lifecycle-to-speed-link-unvalidated")
    if not fast_forward_state_present:
        blockers.append("native-fast-forward-state-unresolved")
    elif not fast_forward_speed_overlap:
        blockers.append("native-fast-forward-to-speed-link-unvalidated")
    else:
        blockers.append("native-fast-forward-multiplier-semantics-unvalidated")

    # Even perfect co-location of reflected strings cannot prove whether the
    # native R2 path replaces, multiplies, or independently layers time scale.
    blockers.extend((
        "base-times-native-fast-forward-formula-unvalidated",
        "cut-only-gameplay-speed-isolation-unvalidated",
        "cutscene-audio-animation-synchronization-unvalidated",
    ))

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
            "setGameSpeed": sorted(set_speed_functions),
            "getGameSpeed": sorted(get_speed_functions),
            "cutChannel": sorted(cut_channel_functions),
            "cutSpeedOverlap": cut_speed_overlap,
            "cutsceneLifecycle": sorted(lifecycle_functions),
            "lifecycleSpeedOverlap": lifecycle_speed_overlap,
            "nativeFastForward": sorted(fast_forward_functions),
            "fastForwardSpeedOverlap": fast_forward_speed_overlap,
            "nonCutSpeedCategories": sorted(non_cut_speed_functions),
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
            "The requested behavior must preserve the game's native fast-forward factor and multiply it by the configured base rather than replacing it; that composition must be measured/validated on the installed build.",
            "No fixed executable offsets or enum-memory offsets are emitted by this probe. Function/string co-location remains research evidence only.",
        ],
    }


def probe_cutscene_runtime(game_root: Path) -> dict[str, Any]:
    native = probe_installed_exe(Path(game_root), needles=CUTSCENE_NATIVE_NEEDLES)
    return {
        "path": native.get("path"),
        "native": native,
        **assess_cutscene_runtime_evidence(native),
    }
