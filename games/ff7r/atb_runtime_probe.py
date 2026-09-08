"""Read-only native research for the remaining FF7R ATB Tweaks mechanics.

The data-backed part of issue #425 is intentionally separate: installed
BattlePlayerParameter guard arrays and BattleAbility.ATB costs can already be
edited reversibly.  This probe concentrates on the unresolved accumulator
semantics needed for passive/Speed/hit generation and the new movement/dodge
modifiers.  Reflected names are evidence only, never validated hooks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .native_probe import probe_installed_exe


ATB_NATIVE_NEEDLES = (
    "ATBValue",
    "ATBUsedValue",
    "EndAnimNotifyBattleEnableForceUpdateATB",
    "EnableForceUpdateATB",
    "BPGetPlayerDexterity",
    "HitBonusATBRecoverAdd",
    "StartATBAdd",
    "IsDodge",
    "GuardReactionNoneAddATB_Array",
    "GuardReactionMediumAddATB_Array",
    "GuardReactionLargeAddATB_Array",
)


def _hit_count(native: dict[str, Any], needle: str) -> int:
    for row in native.get("needles", ()):
        if str(row.get("needle", "")) == needle:
            return len(row.get("hits", ()))
    return 0


def assess_atb_runtime_evidence(
    native: dict[str, Any],
    *,
    resident_rows: int = 0,
    guard_rows: int = 0,
    ability_rows: int = 0,
    discovery_errors: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Report known data contracts and unresolved runtime-hook requirements."""
    hits = {needle: _hit_count(native, needle) for needle in ATB_NATIVE_NEEDLES}

    accumulator_candidates = bool(
        hits["ATBValue"]
        or hits["ATBUsedValue"]
        or hits["EndAnimNotifyBattleEnableForceUpdateATB"]
        or hits["EnableForceUpdateATB"]
    )
    speed_candidate = bool(hits["BPGetPlayerDexterity"])
    hit_gain_candidate = bool(hits["HitBonusATBRecoverAdd"])
    dodge_state_candidate = bool(hits["IsDodge"])

    blockers: list[str] = []
    if discovery_errors:
        blockers.append("data-discovery-errors")
    if not accumulator_candidates:
        blockers.append("atb-accumulator-path-unresolved")
    else:
        # A reflected string/xref is not enough to establish accumulator units or
        # whether a function is the central update path rather than debug/UI glue.
        blockers.append("atb-accumulator-semantics-unvalidated")
    if not speed_candidate:
        blockers.append("speed-input-path-unresolved")
    else:
        blockers.append("speed-atb-formula-unvalidated")
    if not hit_gain_candidate:
        blockers.append("hit-atb-source-unresolved")
    else:
        blockers.append("hit-atb-formula-unvalidated")
    if not dodge_state_candidate:
        blockers.append("dodge-state-path-unresolved")
    if guard_rows <= 0:
        blockers.append("guard-atb-data-unresolved")
    if ability_rows <= 0:
        blockers.append("ability-cost-data-unresolved")

    return {
        "implementationReady": False,
        "blockers": blockers,
        "nativeNeedleHits": hits,
        "dataBacked": {
            "residentCandidateRows": int(resident_rows),
            "guardSlots": int(guard_rows),
            "abilityCostRows": int(ability_rows),
            "guardContract": "BattlePlayerParameter.GuardReaction*AddATB_Array",
            "abilityCostContract": "BattleAbility.ATB",
            "guardEditableNow": guard_rows > 0 and not discovery_errors,
            "abilityCostsEditableNow": ability_rows > 0 and not discovery_errors,
            "residentSemanticsValidated": False,
        },
        "runtimeResearch": {
            "accumulatorCandidatePresent": accumulator_candidates,
            "accumulatorSemanticsValidated": False,
            "speedCandidatePresent": speed_candidate,
            "speedFormulaValidated": False,
            "hitGainCandidatePresent": hit_gain_candidate,
            "hitFormulaValidated": False,
            "dodgeStateCandidatePresent": dodge_state_candidate,
            "movementStateStrategy": "derive from authoritative character movement/velocity only after the ATB accumulator hook is validated",
        },
        "notes": [
            "BattleAbility.ATB is an authored action-cost field; it is not evidence about ATB generation.",
            "GuardReaction*AddATB_Array explicitly identifies guard-generated ATB and can be edited as data.",
            "ResidentParameter rows containing ATB remain candidates until each requested baseline/Speed/hit term is semantically identified on the installed build.",
            "BPGetPlayerDexterity identifies the runtime stat source corresponding to the player's Speed stat, but not the coefficient used by ATB generation.",
            "HitBonusATBRecoverAdd proves a hit-recovery modifier exists, but not whether vanilla base gain is per hit, per move, damage-scaled, or another formula.",
            "IsDodge is a narrow reflected dodge-state query candidate for applying the new roll reduction; it does not itself mutate ATB.",
        ],
    }


def probe_atb_runtime_sources(game_root: Path, discovery: dict[str, Any] | None = None) -> dict[str, Any]:
    """Probe the installed executable and correlate it with installed ATB data discovery."""
    native = probe_installed_exe(Path(game_root), needles=ATB_NATIVE_NEEDLES)
    discovery = discovery or {}
    assessment = assess_atb_runtime_evidence(
        native,
        resident_rows=len(discovery.get("resident", ())),
        guard_rows=len(discovery.get("guard", ())),
        ability_rows=len(discovery.get("abilities", ())),
        discovery_errors=list(discovery.get("errors", ())),
    )
    return {"native": native, **assessment}
