"""Fail-closed installed-build research for FF7R minimap tap/hold (#414).

The authored EnemyTerritory.HideNavimap editor addresses one source of forced
visibility changes. This probe targets the remaining native problem: identify
an authoritative minimap visibility/state path and the map-button/full-map path
without mistaking generic NaviMap UI strings for callable hooks.

Generated Remake data distinguishes the full-map menu action from a native map
toggle action. Reflected names commonly point at Unreal registration glue, so
exact PE ``.pdata`` function owners may also contribute conservative bounded
next hops. Direct owners, next hops, and exact inbound callers remain separate,
unvalidated evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .map_input_signature_probe import probe_public_map_input_signatures
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
MAP_MENU_SUPPORT_NEEDLES = (
    "EndFieldOnOffTable_DisableTouchPad",
    "EndFieldOnOffTable_DisableOptionsButton",
    "EndFieldOnOffTable_ShowMapJournal",
    "MapJournal",
)
MAP_MENU_ACTION_NEEDLES = (
    "KeyboardMapMenu",
)
MAP_MENU_INPUT_NEEDLES = (
    *MAP_MENU_SUPPORT_NEEDLES,
    *MAP_MENU_ACTION_NEEDLES,
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


def _caller_rvas(inbound: dict[str, Any] | None) -> set[int]:
    callers: set[int] = set()
    for ref in (inbound or {}).get("refs", ()):
        value = ref.get("sourceFunctionRva")
        if value is not None:
            callers.add(int(value))
    return callers


def _function_evidence(native: dict[str, Any], needles: Iterable[str]) -> dict[str, set[int]]:
    direct: set[int] = set()
    next_hops: set[int] = set()
    direct_callers: set[int] = set()
    next_hop_callers: set[int] = set()
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
                direct_callers.update(
                    _caller_rvas(xref.get("candidateFunctionInboundCodeRefs"))
                )
                code_refs = xref.get("candidateFunctionCodeRefs") or {}
                for ref in code_refs.get("refs", ()):
                    target = ref.get("targetFunctionRva")
                    if target is not None:
                        next_hops.add(int(target))
                    next_hop_callers.update(
                        _caller_rvas(ref.get("targetFunctionInboundCodeRefs"))
                    )
    return {
        "direct": direct,
        "nextHops": next_hops,
        "directCallers": direct_callers,
        "nextHopCallers": next_hop_callers,
    }


def _all_functions(evidence: dict[str, set[int]]) -> set[int]:
    return set(evidence["direct"]) | set(evidence["nextHops"])


def _all_callers(evidence: dict[str, set[int]]) -> set[int]:
    return set(evidence["directCallers"]) | set(evidence["nextHopCallers"])


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
    map_menu_support_counts = _hit_counts(native, MAP_MENU_SUPPORT_NEEDLES)
    map_menu_action_counts = _hit_counts(native, MAP_MENU_ACTION_NEEDLES)
    toggle_input_counts = _hit_counts(native, MINIMAP_TOGGLE_INPUT_NEEDLES)

    hide_gate = _function_evidence(
        native,
        ("EndFieldOnOffTable_HideNaviMap", "HideNaviMap", "HideNavimap"),
    )
    show_hide = _function_evidence(native, ("BPShowNavimap", "BPHideNavimap"))
    triggers = _function_evidence(native, MINIMAP_TRIGGER_NEEDLES)
    map_menu_support = _function_evidence(native, MAP_MENU_SUPPORT_NEEDLES)
    map_menu_action = _function_evidence(native, MAP_MENU_ACTION_NEEDLES)
    map_menu = _function_evidence(native, MAP_MENU_INPUT_NEEDLES)
    native_toggle = _function_evidence(native, MINIMAP_TOGGLE_INPUT_NEEDLES)

    state_direct_set = hide_gate["direct"] | show_hide["direct"] | triggers["direct"]
    state_all_set = _all_functions(hide_gate) | _all_functions(show_hide) | _all_functions(triggers)
    state_caller_set = _all_callers(hide_gate) | _all_callers(show_hide) | _all_callers(triggers)

    # Only the two generated native action concepts may satisfy the input-path
    # classifier. MapJournal/TouchPad/OptionsButton rows remain useful navigation
    # evidence but cannot stand in for KeyboardMapMenu itself.
    action_direct_set = map_menu_action["direct"] | native_toggle["direct"]
    action_all_set = _all_functions(map_menu_action) | _all_functions(native_toggle)
    action_caller_set = _all_callers(map_menu_action) | _all_callers(native_toggle)

    state_direct = hide_gate["direct"] & (show_hide["direct"] | triggers["direct"])
    state_reachable = _all_functions(hide_gate) & (_all_functions(show_hide) | _all_functions(triggers))
    input_direct = action_direct_set & state_direct_set
    input_reachable = action_all_set & state_all_set
    map_menu_direct = map_menu_action["direct"] & state_direct_set
    map_menu_reachable = _all_functions(map_menu_action) & state_all_set
    toggle_direct = native_toggle["direct"] & state_direct_set
    toggle_reachable = _all_functions(native_toggle) & state_all_set

    # Common exact .pdata callers can expose a dispatcher/controller neighborhood
    # even when the reflected-string owners are distinct. This is directional
    # research evidence only and never substitutes for input-phase or state-write
    # semantics.
    input_state_caller_overlap = action_caller_set & state_caller_set
    map_menu_state_caller_overlap = _all_callers(map_menu_action) & state_caller_set
    toggle_state_caller_overlap = _all_callers(native_toggle) & state_caller_set
    map_menu_toggle_caller_overlap = _all_callers(map_menu_action) & _all_callers(native_toggle)

    blockers: list[str] = []
    if not any(state_counts.values()):
        blockers.append("minimap-state-anchors-not-found")
    if not _all_functions(hide_gate):
        blockers.append("hide-state-writer-function-unresolved")
    if not _all_functions(show_hide) and not _all_functions(triggers):
        blockers.append("show-hide-state-function-unresolved")

    if not any(map_menu_action_counts.values()):
        blockers.append("native-map-menu-input-anchor-unresolved")
        blockers.append("map-button-full-map-function-unresolved")
    elif not _all_functions(map_menu_action):
        blockers.append("native-map-menu-input-function-unresolved")
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
    if _all_functions(map_menu_action) and not map_menu_direct:
        if map_menu_reachable:
            blockers.append("native-map-menu-input-next-hop-to-state-unvalidated")
        else:
            blockers.append("native-map-menu-input-to-state-link-unvalidated")
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
            "directCallers": sorted(evidence["directCallers"]),
            "nextHopCallers": sorted(evidence["nextHopCallers"]),
            "allCallers": sorted(_all_callers(evidence)),
        }

    state_direct_rows = sorted(state_direct)
    input_direct_rows = sorted(input_direct)
    map_menu_direct_rows = sorted(map_menu_direct)
    toggle_direct_rows = sorted(toggle_direct)
    return {
        "implementationReady": False,
        "blockers": blockers,
        "stateNeedleHits": state_counts,
        "triggerNeedleHits": trigger_counts,
        "inputNeedleHits": input_counts,
        "mapMenuNeedleHits": map_menu_counts,
        "mapMenuSupportNeedleHits": map_menu_support_counts,
        "mapMenuActionNeedleHits": map_menu_action_counts,
        "toggleInputNeedleHits": toggle_input_counts,
        "candidateFunctions": {
            "hideGate": serialize(hide_gate),
            "showHide": serialize(show_hide),
            "stateTrigger": serialize(triggers),
            "mapInput": {
                "direct": sorted(action_direct_set),
                "nextHops": sorted((map_menu_action["nextHops"] | native_toggle["nextHops"])),
                "all": sorted(action_all_set),
                "allCallers": sorted(action_caller_set),
            },
            "mapMenuInput": serialize(map_menu),
            "mapMenuSupport": serialize(map_menu_support),
            "mapMenuAction": serialize(map_menu_action),
            "nativeToggleInput": serialize(native_toggle),
            "stateDirectOverlap": state_direct_rows,
            "stateReachableOverlap": sorted(state_reachable),
            "inputStateDirectOverlap": input_direct_rows,
            "inputStateReachableOverlap": sorted(input_reachable),
            "mapMenuStateDirectOverlap": map_menu_direct_rows,
            "mapMenuStateReachableOverlap": sorted(map_menu_reachable),
            "toggleStateDirectOverlap": toggle_direct_rows,
            "toggleStateReachableOverlap": sorted(toggle_reachable),
            "inputStateCallerOverlap": sorted(input_state_caller_overlap),
            "mapMenuStateCallerOverlap": sorted(map_menu_state_caller_overlap),
            "toggleStateCallerOverlap": sorted(toggle_state_caller_overlap),
            "mapMenuToggleCallerOverlap": sorted(map_menu_toggle_caller_overlap),
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
            "Generated EOptionCategory distinguishes KeyboardMapMenu from KeyboardToggleMap. The classifier requires KeyboardMapMenu itself for the native full-map action; MapJournal/TouchPad/OptionsButton gates cannot satisfy that requirement.",
            "MapJournal/TouchPad/OptionsButton anchors remain input/full-map navigation leads only; no controller binding or callable action is assumed from their names.",
            "Prefer routing a hold into the game's native KeyboardToggleMap action if installed callsite evidence proves it, rather than inventing toggle semantics from presentation calls.",
            "Bounded .pdata next hops are navigation evidence only; heuristic function bounds cannot strengthen the result.",
            "Exact .pdata inbound-caller overlaps are directional dispatcher/controller leads only; they do not validate press/release phase, ABI, state ownership, or a safe hook site.",
            "The runtime tap/hold state machine is independently tested, but the installed input hook must still delay the vanilla tap action until release, consume it on a hold, toggle exactly once, and reassert the chosen state after automatic transitions.",
        ],
    }


def probe_minimap_runtime(game_root: Path) -> dict[str, Any]:
    native = probe_installed_exe(Path(game_root), needles=MINIMAP_NATIVE_NEEDLES)
    public_signatures = (
        probe_public_map_input_signatures(Path(str(native["path"])))
        if native.get("path")
        else {
            "path": "",
            "scanError": "installed executable path was not resolved",
            "mapControl": {
                "matchCount": 0,
                "matches": [],
                "classification": "full-screen-map-controller",
                "mapButtonAuthority": False,
            },
            "rawInputRegistration": {
                "matchCount": 0,
                "matches": [],
                "classification": "raw-input-device-registration",
                "mapButtonAuthority": False,
            },
        }
    )
    return {
        "path": native.get("path"),
        "native": native,
        "publicSignatureResearch": public_signatures,
        **assess_minimap_runtime_evidence(native),
    }
