"""Fail-closed installed-build research for FF7R minimap tap/hold (#414).

The authored EnemyTerritory.HideNavimap editor addresses one source of forced
visibility changes. This probe targets the remaining native problem: identify
an authoritative minimap visibility/state path and the map-button/full-map path
without mistaking generic NaviMap UI strings for callable hooks.
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
# Generated Remake EOptionCategory exposes KeyboardToggleMap separately from
# KeyboardMapMenu. That is valuable evidence that minimap toggling is a native
# input concept rather than something Lexeditor should synthesize purely from
# show/hide presentation calls. It is still only an enum/option anchor until an
# installed callsite is proven.
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


def _function_rvas(native: dict[str, Any], needles: Iterable[str]) -> set[int]:
    result: set[int] = set()
    for needle in needles:
        row = _needle_row(native, needle)
        for hit in row.get("hits", ()):
            for xref in hit.get("leaRipXrefs", ()):
                value = xref.get("candidateFunctionRva")
                if value is not None:
                    result.add(int(value))
    return result


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

    hide_gate_functions = _function_rvas(
        native,
        ("EndFieldOnOffTable_HideNaviMap", "HideNaviMap", "HideNavimap"),
    )
    show_hide_functions = _function_rvas(native, ("BPShowNavimap", "BPHideNavimap"))
    trigger_functions = _function_rvas(native, MINIMAP_TRIGGER_NEEDLES)
    map_menu_functions = _function_rvas(native, MAP_MENU_INPUT_NEEDLES)
    toggle_input_functions = _function_rvas(native, MINIMAP_TOGGLE_INPUT_NEEDLES)
    input_functions = map_menu_functions | toggle_input_functions

    state_functions = hide_gate_functions | show_hide_functions | trigger_functions
    state_overlap = sorted(hide_gate_functions & (show_hide_functions | trigger_functions))
    input_state_overlap = sorted(input_functions & state_functions)
    toggle_state_overlap = sorted(toggle_input_functions & state_functions)

    blockers: list[str] = []
    if not any(state_counts.values()):
        blockers.append("minimap-state-anchors-not-found")
    if not hide_gate_functions:
        blockers.append("hide-state-writer-function-unresolved")
    if not show_hide_functions and not trigger_functions:
        blockers.append("show-hide-state-function-unresolved")
    if not map_menu_functions:
        blockers.append("map-button-full-map-function-unresolved")
    if not any(toggle_input_counts.values()):
        blockers.append("native-minimap-toggle-input-anchor-unresolved")
    elif not toggle_input_functions:
        blockers.append("native-minimap-toggle-input-function-unresolved")
    if not state_overlap:
        blockers.append("central-minimap-state-controller-unvalidated")
    if not input_state_overlap:
        blockers.append("tap-hold-input-to-minimap-link-unvalidated")
    if toggle_input_functions and not toggle_state_overlap:
        blockers.append("native-toggle-input-to-state-link-unvalidated")

    # Even a same-function string correlation is only a candidate. Installed
    # disassembly/behavior still has to prove argument semantics and that a hook
    # can suppress the tap on a hold without breaking normal full-map access.
    blockers.extend((
        "map-button-press-release-semantics-unvalidated",
        "player-choice-persistence-write-interception-unvalidated",
    ))

    return {
        "implementationReady": False,
        "blockers": blockers,
        "stateNeedleHits": state_counts,
        "triggerNeedleHits": trigger_counts,
        "inputNeedleHits": input_counts,
        "mapMenuNeedleHits": map_menu_counts,
        "toggleInputNeedleHits": toggle_input_counts,
        "candidateFunctions": {
            "hideGate": sorted(hide_gate_functions),
            "showHide": sorted(show_hide_functions),
            "stateTrigger": sorted(trigger_functions),
            "mapInput": sorted(input_functions),
            "mapMenuInput": sorted(map_menu_functions),
            "nativeToggleInput": sorted(toggle_input_functions),
            "stateOverlap": state_overlap,
            "inputStateOverlap": input_state_overlap,
            "toggleStateOverlap": toggle_state_overlap,
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
