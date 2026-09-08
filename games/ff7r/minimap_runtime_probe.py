"""Fail-closed installed-build research for FF7R minimap tap/hold (#414).

The authored EnemyTerritory.HideNavimap editor addresses one source of forced
visibility changes. This probe targets the remaining native problem: identify
an authoritative minimap visibility/state path and the map-button/full-map path
without mistaking generic NaviMap UI strings for callable hooks.

Reflected names commonly point at Unreal registration glue. Exact PE ``.pdata``
function owners may expose conservative cross-function next hops; these are kept
separate from direct owners and remain unvalidated navigation evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .native_probe import probe_installed_exe


MINIMAP_STATE_NEEDLES = (
    "EndFieldOnOffTable_HideNaviMap",
    "HideNaviMap",
    "HideNavimap",
    "BPShowNavimap",
    "BPHideNavimap",
)
MINIMAP_TRIGGER_NEEDLES = (
    "SendStateTrigger",
    "SendStateTriggerDirect",
    "trgCmn_NaviMap_Update_On",
    "trgCmn_NaviMap_Update_Off",
)
MAP_INPUT_NEEDLES = (
    "EndFieldOnOffTable_DisableTouchPad",
    "EndFieldOnOffTable_DisableOptionsButton",
    "EndFieldOnOffTable_ShowMapJournal",
    "MapJournal",
)
MINIMAP_NATIVE_NEEDLES = (
    *MINIMAP_STATE_NEEDLES,
    *MINIMAP_TRIGGER_NEEDLES,
    *MAP_INPUT_NEEDLES,
)


def _needle_row(native: dict[str, Any], needle: str) -> dict[str, Any]:
    for row in native.get("needles", ()):
        if str(row.get("needle", "")) == needle:
            return dict(row)
    return {}


def _function_evidence(native: dict[str, Any], needles: Iterable[str]) -> dict[str, set[int]]:
    direct: set[int] = set()
    next_hops: set[int] = set()
    for needle in needles:
        row = _needle_row(native, needle)
        for hit in row.get("hits", ()):
            for xref in hit.get("leaRipXrefs", ()):
                source = xref.get("candidateFunctionSource")
                value = xref.get("candidateFunctionRva")
                if value is not None and source in (None, "pdata"):
                    direct.add(int(value))
                if source != "pdata":
                    continue
                code_refs = xref.get("candidateFunctionCodeRefs") or {}
                for ref in code_refs.get("refs", ()):
                    target = ref.get("targetFunctionRva")
                    if target is not None:
                        next_hops.add(int(target))
    return {"direct": direct, "nextHops": next_hops}


def _all_functions(evidence: dict[str, set[int]]) -> set[int]:
    return set(evidence["direct"]) | set(evidence["nextHops"])


def _hit_counts(native: dict[str, Any], needles: Iterable[str]) -> dict[str, int]:
    return {
        needle: len(_needle_row(native, needle).get("hits", ()))
        for needle in needles
    }


def assess_minimap_runtime_evidence(native: dict[str, Any]) -> dict[str, Any]:
    """Classify installed string/function evidence without promoting it to hooks."""
    state_counts = _hit_counts(native, MINIMAP_STATE_NEEDLES)
    trigger_counts = _hit_counts(native, MINIMAP_TRIGGER_NEEDLES)
    input_counts = _hit_counts(native, MAP_INPUT_NEEDLES)

    hide_gate = _function_evidence(
        native,
        ("EndFieldOnOffTable_HideNaviMap", "HideNaviMap", "HideNavimap"),
    )
    show_hide = _function_evidence(native, ("BPShowNavimap", "BPHideNavimap"))
    triggers = _function_evidence(native, MINIMAP_TRIGGER_NEEDLES)
    map_input = _function_evidence(native, MAP_INPUT_NEEDLES)

    state_direct = hide_gate["direct"] & (show_hide["direct"] | triggers["direct"])
    state_reachable = _all_functions(hide_gate) & (_all_functions(show_hide) | _all_functions(triggers))
    input_direct = map_input["direct"] & (
        hide_gate["direct"] | show_hide["direct"] | triggers["direct"]
    )
    input_reachable = _all_functions(map_input) & (
        _all_functions(hide_gate) | _all_functions(show_hide) | _all_functions(triggers)
    )

    blockers: list[str] = []
    if not any(state_counts.values()):
        blockers.append("minimap-state-anchors-not-found")
    if not _all_functions(hide_gate):
        blockers.append("hide-state-writer-function-unresolved")
    if not _all_functions(show_hide) and not _all_functions(triggers):
        blockers.append("show-hide-state-function-unresolved")
    if not _all_functions(map_input):
        blockers.append("map-button-full-map-function-unresolved")
    if not state_direct:
        if state_reachable:
            blockers.append("central-minimap-state-controller-next-hop-unvalidated")
        else:
            blockers.append("central-minimap-state-controller-unvalidated")
    if not input_direct:
        if input_reachable:
            blockers.append("tap-hold-input-next-hop-to-minimap-unvalidated")
        else:
            blockers.append("tap-hold-input-to-minimap-link-unvalidated")

    # Even a same-function or bounded-next-hop correlation is only a candidate.
    # Installed disassembly/behavior still has to prove argument semantics and
    # that a hold can suppress the tap without breaking normal full-map access.
    blockers.extend((
        "map-button-press-release-semantics-unvalidated",
        "player-choice-persistence-write-interception-unvalidated",
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
        "stateNeedleHits": state_counts,
        "triggerNeedleHits": trigger_counts,
        "inputNeedleHits": input_counts,
        "candidateFunctions": {
            "hideGate": serialize(hide_gate),
            "showHide": serialize(show_hide),
            "stateTrigger": serialize(triggers),
            "mapInput": serialize(map_input),
            "stateDirectOverlap": sorted(state_direct),
            "stateReachableOverlap": sorted(state_reachable),
            "inputStateDirectOverlap": sorted(input_direct),
            "inputStateReachableOverlap": sorted(input_reachable),
        },
        "knownContracts": {
            "hideGate": "EndFieldOnOffTable_HideNaviMap",
            "show": "UEndMenuAPI::BPShowNavimap(UObject*)",
            "hide": "UEndMenuAPI::BPHideNavimap()",
            "stateTrigger": "UEndFieldAPI::SendStateTrigger/SendStateTriggerDirect",
            "fullMapGate": "EndFieldOnOffTable_ShowMapJournal",
            "touchInputGate": "EndFieldOnOffTable_DisableTouchPad",
        },
        "notes": [
            "EndFieldOnOffTable_HideNaviMap is a Remake-native central state anchor and is distinct from authored EnemyTerritory.HideNavimap rows.",
            "BPShowNavimap/BPHideNavimap are presentation APIs; their presence alone does not prove the automatic visibility writer.",
            "EndFieldOnOffTable_ShowMapJournal and DisableTouchPad are stronger Remake input/full-map gates than a generic MapJournal string, but they still do not identify press/release timing or the controller binding by themselves.",
            "Bounded .pdata next hops are navigation evidence only; heuristic function bounds cannot strengthen the result.",
            "The final runtime must delay the vanilla tap action until release, consume it on a hold, toggle exactly once, and reassert the chosen minimap state after automatic transitions.",
        ],
    }


def probe_minimap_runtime(game_root: Path) -> dict[str, Any]:
    native = probe_installed_exe(Path(game_root), needles=MINIMAP_NATIVE_NEEDLES)
    return {
        "path": native.get("path"),
        "native": native,
        **assess_minimap_runtime_evidence(native),
    }
