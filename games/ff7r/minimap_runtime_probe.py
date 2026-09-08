"""Fail-closed installed-build research for FF7R minimap tap/hold (#414).

The authored EnemyTerritory.HideNavimap editor addresses one source of forced
visibility changes. This probe targets the remaining native problem: identify
an authoritative minimap visibility/state path and the map-button/full-map path
without mistaking generic NaviMap UI strings for callable hooks.

Generated Remake data distinguishes the full-map menu action from a native map
toggle action. Reflected names commonly point at Unreal registration glue, so
exact PE ``.pdata`` function owners may also contribute conservative bounded
next hops. Direct owners and next hops remain separate, unvalidated evidence.
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
MAP_MENU_INPUT_NEEDLES = (
    "EndFieldOnOffTable_DisableTouchPad",
    "EndFieldOnOffTable_DisableOptionsButton",
    "EndFieldOnOffTable_ShowMapJournal",
    "MapJournal",
    "KeyboardMapMenu",
)
MINIMAP_TOGGLE_INPUT_NEEDLES = (
    "KeyboardToggleMap",
)
MAP_INPUT_NEEDLES = (
    *MAP_MENU_INPUT_NEEDLES,
    *MINIMAP_TOGGLE_INPUT_NEEDLES,
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
    map_menu_counts = _hit_counts(native, MAP_MENU_INPUT_NEEDLES)
    toggle_input_counts = _hit_counts(native, MINIMAP_TOGGLE_INPUT_NEEDLES)

    hide_gate = _function_evidence(
        native,
        ("EndFieldOnOffTable_HideNaviMap", "HideNaviMap", "HideNavimap"),
    )
    show_hide = _function_evidence(native, ("BPShowNavimap", "BPHideNavimap"))
    triggers = _function_evidence(native, MINIMAP_TRIGGER_NEEDLES)
    map_menu = _function_evidence(native, MAP_MENU_INPUT_NEEDLES)
    native_toggle = _function_evidence(native, MINIMAP_TOGGLE_INPUT_NEEDLES)

    state_direct_set = hide_gate["direct"] | show_hide["direct"] | triggers["direct"]
    state_all_set = _all_functions(hide_gate) | _all_functions(show_hide) | _all_functions(triggers)
    input_direct_set = map_menu["direct"] | native_toggle["direct"]
    input_all_set = _all_functions(map_menu) | _all_functions(native_toggle)

    state_direct = hide_gate["direct"] & (show_hide["direct"] | triggers["direct"])
    state_reachable = _all_functions(hide_gate) & (_all_functions(show_hide) | _all_functions(triggers))
    input_direct = input_direct_set & state_direct_set
    input_reachable = input_all_set & state_all_set
    toggle_direct = native_toggle["direct"] & state_direct_set
    toggle_reachable = _all_functions(native_toggle) & state_all_set

    blockers: list[str] = []
    if not any(state_counts.values()):
        blockers.append("minimap-state-anchors-not-found")
    if not _all_functions(hide_gate):
        blockers.append("hide-state-writer-function-unresolved")
    if not _all_functions(show_hide) and not _all_functions(triggers):
        blockers.append("show-hide-state-function-unresolved")
    if not _all_functions(map_menu):
        blockers.append("map-button-full-map-function-unresolved")
    if not any(toggle_input_counts.values()):
        blockers.append("native-minimap-toggle-input-anchor-unresolved")
    elif not _all_functions(native_toggle):
        blockers.append("native-minimap-toggle-input-function-unresolved")
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
    if _all_functions(native_toggle) and not toggle_direct:
        if toggle_reachable:
            blockers.append("native-toggle-input-next-hop-to-state-unvalidated")
        else:
            blockers.append("native-toggle-input-to-state-link-unvalidated")

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

    state_direct_rows = sorted(state_direct)
    input_direct_rows = sorted(input_direct)
    toggle_direct_rows = sorted(toggle_direct)
    return {
        "implementationReady": False,
        "blockers": blockers,
        "stateNeedleHits": state_counts,
        "triggerNeedleHits": trigger_counts,
        "inputNeedleHits": input_counts,
        "mapMenuNeedleHits": map_menu_counts,
        "toggleInputNeedleHits": toggle_input_counts,
        "candidateFunctions": {
            "hideGate": serialize(hide_gate),
            "showHide": serialize(show_hide),
            "stateTrigger": serialize(triggers),
            "mapInput": {
                "direct": sorted(input_direct_set),
                "nextHops": sorted((map_menu["nextHops"] | native_toggle["nextHops"])),
                "all": sorted(input_all_set),
            },
            "mapMenuInput": serialize(map_menu),
            "nativeToggleInput": serialize(native_toggle),
            "stateDirectOverlap": state_direct_rows,
            "stateReachableOverlap": sorted(state_reachable),
            "inputStateDirectOverlap": input_direct_rows,
            "inputStateReachableOverlap": sorted(input_reachable),
            "toggleStateDirectOverlap": toggle_direct_rows,
            "toggleStateReachableOverlap": sorted(toggle_reachable),
            # Backward-compatible aliases for the direct-only classifier shape.
            "stateOverlap": state_direct_rows,
            "inputStateOverlap": input_direct_rows,
            "toggleStateOverlap": toggle_direct_rows,
        },
        "knownContracts": {
            "hideGate": "EndFieldOnOffTable_HideNaviMap",
            "show": "UEndMenuAPI::BPShowNavimap(UObject*)",
            "hide": "UEndMenuAPI::BPHideNavimap()",
            "stateTrigger": "UEndFieldAPI::SendStateTrigger/SendStateTriggerDirect",
            "fullMapGate": "EndFieldOnOffTable_ShowMapJournal",
            "touchInputGate": "EndFieldOnOffTable_DisableTouchPad",
            "keyboardMapMenuOption": "EOptionCategory::KeyboardMapMenu",
            "keyboardToggleMapOption": "EOptionCategory::KeyboardToggleMap",
        },
        "notes": [
            "EndFieldOnOffTable_HideNaviMap is a Remake-native central state anchor and is distinct from authored EnemyTerritory.HideNavimap rows.",
            "BPShowNavimap/BPHideNavimap are presentation APIs; their presence alone does not prove the automatic visibility writer.",
            "Generated EOptionCategory distinguishes KeyboardMapMenu from KeyboardToggleMap. Prefer routing a hold into the game's native toggle action if installed callsite evidence proves it, rather than inventing toggle semantics from presentation calls.",
            "MapJournal/TouchPad/OptionsButton anchors are input/full-map research leads only; no controller binding is assumed from their names.",
            "Bounded .pdata next hops are navigation evidence only; heuristic function bounds cannot strengthen the result.",
            "The runtime tap/hold state machine is independently tested, but the installed input hook must still delay the vanilla tap action until release, consume it on a hold, toggle exactly once, and reassert the chosen state after automatic transitions.",
        ],
    }


def probe_minimap_runtime(game_root: Path) -> dict[str, Any]:
    native = probe_installed_exe(Path(game_root), needles=MINIMAP_NATIVE_NEEDLES)
    return {
        "path": native.get("path"),
        "native": native,
        **assess_minimap_runtime_evidence(native),
    }
