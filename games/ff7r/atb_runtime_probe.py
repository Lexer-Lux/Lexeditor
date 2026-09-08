"""Read-only native research for the remaining FF7R ATB Tweaks mechanics.

The data-backed part of issue #425 is intentionally separate: installed
BattlePlayerParameter guard arrays and BattleAbility.ATB costs can already be
edited reversibly. This probe concentrates on the unresolved accumulator
semantics needed for passive/Speed/hit generation and the new movement/dodge
modifiers. Reflected names are evidence only, never validated hooks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .native_probe import probe_installed_exe


ATB_ACCESSOR_NEEDLES = (
    "SetATB",
    "SetATBAll",
    "GetATB",
    "GetATBMax",
    "ResetATB",
)
HIT_EVENT_NEEDLES = (
    "NormalAttackHitSuccess",
    "NormalAttackPerHitSuccess",
    "WeaponAbilityHitSuccess",
    "WeaponAbilityPerHitSuccess",
    "MagicHitSuccess",
    "MagicPerHitSuccess",
    "LimitHitSuccess",
    "LimitPerHitSuccess",
)
ATTACK_LEVEL_HIT_EVENT_NEEDLES = tuple(
    needle for needle in HIT_EVENT_NEEDLES if "PerHitSuccess" not in needle
)
PER_HIT_EVENT_NEEDLES = tuple(
    needle for needle in HIT_EVENT_NEEDLES if "PerHitSuccess" in needle
)
ACCUMULATOR_NEEDLES = (
    "ATBValue",
    "ATBUsedValue",
    "EndAnimNotifyBattleEnableForceUpdateATB",
    "EnableForceUpdateATB",
)
ATB_NATIVE_NEEDLES = (
    *ACCUMULATOR_NEEDLES,
    "BPGetPlayerDexterity",
    "GetResidentParameterFloatBP",
    "HitBonusATBRecoverAdd",
    "StartATBAdd",
    "IsDodge",
    "IsDodgeInvincible",
    "GuardReactionNoneAddATB_Array",
    "GuardReactionMediumAddATB_Array",
    "GuardReactionLargeAddATB_Array",
    *ATB_ACCESSOR_NEEDLES,
    *HIT_EVENT_NEEDLES,
)

# Public Remake combat measurements plus independent ResidentParameter mods give
# useful vanilla fingerprints for the installed table. They are deliberately
# not mapped to a row solely by value: many unrelated ResidentParameter rows can
# share 0.0/1.0/0.1, so the installed tag and behavior still have to agree.
DOCUMENTED_VANILLA_ATB_REFERENCES = {
    "internalUnitsPerDisplayedBar": 1000.0,
    "normalGaugeInternalUnits": 2000.0,
    "playerPassiveMultiplier": 1.0,
    "aiPassiveMultiplier": 0.35,
    "cautionMultiplier": 0.0,
    "actionMultiplier": 0.0,
    "aiActionMultiplier": 0.25,
    "guardMultiplier": 0.1,
    "damageMultiplier": 0.0,
    "dodgeMultiplier": 0.0,
    "suspendActionMultiplier": 0.0,
    "hasteMultiplier": 1.4,
    "slowMultiplier": 0.6,
}


def _hit_count(native: dict[str, Any], needle: str) -> int:
    for row in native.get("needles", ()):
        if str(row.get("needle", "")) == needle:
            return len(row.get("hits", ()))
    return 0


def _counts(native: dict[str, Any], needles: tuple[str, ...]) -> dict[str, int]:
    return {needle: _hit_count(native, needle) for needle in needles}


def _native_function_evidence(native: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    """Collect only exact .pdata string owners and their bounded one-hop targets."""
    evidence: dict[str, dict[str, list[int]]] = {}
    for row in native.get("needles", ()):
        needle = str(row.get("needle", ""))
        if needle not in ATB_NATIVE_NEEDLES:
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
                for ref in (xref.get("candidateFunctionCodeRefs") or {}).get("refs", ()):
                    target = ref.get("targetFunctionRva")
                    if target is not None:
                        next_hops.add(int(target))
        evidence[needle] = {
            "directPdataFunctions": sorted(direct),
            "nextHopPdataFunctions": sorted(next_hops),
            "expandedPdataFunctions": sorted(direct | next_hops),
        }
    return evidence


def _functions(evidence: dict[str, dict[str, list[int]]], needles: Iterable[str]) -> set[int]:
    functions: set[int] = set()
    for needle in needles:
        functions.update(evidence.get(needle, {}).get("expandedPdataFunctions", ()))
    return functions


def _function_correlations(evidence: dict[str, dict[str, list[int]]]) -> dict[str, list[int]]:
    set_atb = _functions(evidence, ("SetATB",))
    get_atb = _functions(evidence, ("GetATB",))
    get_atb_max = _functions(evidence, ("GetATBMax",))
    reset_atb = _functions(evidence, ("ResetATB",))
    accumulators = _functions(evidence, ACCUMULATOR_NEEDLES)
    speed = _functions(evidence, ("BPGetPlayerDexterity",))
    resident = _functions(evidence, ("GetResidentParameterFloatBP",))
    hit_modifier = _functions(evidence, ("HitBonusATBRecoverAdd",))
    attack_events = _functions(evidence, ATTACK_LEVEL_HIT_EVENT_NEEDLES)
    per_hit_events = _functions(evidence, PER_HIT_EVENT_NEEDLES)
    dodge = _functions(evidence, ("IsDodge", "IsDodgeInvincible"))

    return {
        "setToGet": sorted(set_atb & get_atb),
        "setToMax": sorted(set_atb & get_atb_max),
        "setToReset": sorted(set_atb & reset_atb),
        "speedToAccumulator": sorted(speed & accumulators),
        "residentReaderToAccumulator": sorted(resident & accumulators),
        "hitModifierToAccumulator": sorted(hit_modifier & accumulators),
        "hitModifierToAttackLevelEvents": sorted(hit_modifier & attack_events),
        "hitModifierToPerHitEvents": sorted(hit_modifier & per_hit_events),
        "attackLevelEventsToAccumulator": sorted(attack_events & accumulators),
        "perHitEventsToAccumulator": sorted(per_hit_events & accumulators),
        "dodgeToAccumulator": sorted(dodge & accumulators),
        "dodgeToSetATB": sorted(dodge & set_atb),
    }


def _function_clusters(evidence: dict[str, dict[str, list[int]]]) -> list[dict[str, Any]]:
    families = {
        "accessor": ATB_ACCESSOR_NEEDLES,
        "accumulator": ACCUMULATOR_NEEDLES,
        "speed": ("BPGetPlayerDexterity",),
        "resident": ("GetResidentParameterFloatBP",),
        "hit-modifier": ("HitBonusATBRecoverAdd", "StartATBAdd"),
        "attack-event": ATTACK_LEVEL_HIT_EVENT_NEEDLES,
        "per-hit-event": PER_HIT_EVENT_NEEDLES,
        "dodge": ("IsDodge", "IsDodgeInvincible"),
    }
    family_by_needle = {
        needle: family
        for family, needles in families.items()
        for needle in needles
    }
    rows: dict[int, dict[str, Any]] = {}
    for needle, needle_evidence in evidence.items():
        family = family_by_needle.get(needle)
        if family is None:
            continue
        for key, destination in (
            ("directPdataFunctions", "directNeedles"),
            ("nextHopPdataFunctions", "nextHopNeedles"),
        ):
            for raw_rva in needle_evidence.get(key, ()):
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
        family_names = sorted(row["families"])
        direct = sorted(row["directNeedles"])
        next_hops = sorted(row["nextHopNeedles"])
        result.append({
            "functionRva": rva,
            "families": family_names,
            "familyCount": len(family_names),
            "directNeedles": direct,
            "nextHopNeedles": next_hops,
            "crossFamily": len(family_names) >= 2,
            "registrationCollisionRisk": len(direct) >= 2,
        })
    return result


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
    accessor_hits = _counts(native, ATB_ACCESSOR_NEEDLES)
    hit_event_hits = _counts(native, HIT_EVENT_NEEDLES)
    function_evidence = _native_function_evidence(native)
    correlations = _function_correlations(function_evidence)
    clusters = _function_clusters(function_evidence)

    accumulator_candidates = bool(
        hits["ATBValue"]
        or hits["ATBUsedValue"]
        or hits["EndAnimNotifyBattleEnableForceUpdateATB"]
        or hits["EnableForceUpdateATB"]
        or accessor_hits["SetATB"]
        or accessor_hits["GetATB"]
    )
    speed_candidate = bool(hits["BPGetPlayerDexterity"])
    resident_reader_candidate = bool(hits["GetResidentParameterFloatBP"])
    hit_gain_candidate = bool(hits["HitBonusATBRecoverAdd"])
    dodge_state_candidate = bool(hits["IsDodge"])
    direct_atb_api_candidate = bool(
        accessor_hits["SetATB"] and accessor_hits["GetATB"]
    )
    atb_max_api_candidate = bool(accessor_hits["GetATBMax"])
    hit_event_granularity_present = bool(
        any(hit_event_hits[name] for name in PER_HIT_EVENT_NEEDLES)
        and any(hit_event_hits[name] for name in ATTACK_LEVEL_HIT_EVENT_NEEDLES)
    )

    set_functions = _functions(function_evidence, ("SetATB",))
    get_functions = _functions(function_evidence, ("GetATB",))
    max_functions = _functions(function_evidence, ("GetATBMax",))
    accumulator_functions = _functions(function_evidence, ACCUMULATOR_NEEDLES)
    speed_functions = _functions(function_evidence, ("BPGetPlayerDexterity",))
    hit_modifier_functions = _functions(function_evidence, ("HitBonusATBRecoverAdd",))
    dodge_functions = _functions(function_evidence, ("IsDodge", "IsDodgeInvincible"))
    direct_api_function_candidate = bool(set_functions and get_functions)
    max_api_function_candidate = bool(max_functions)

    blockers: list[str] = []
    if discovery_errors:
        blockers.append("data-discovery-errors")
    if not accumulator_candidates:
        blockers.append("atb-accumulator-path-unresolved")
    else:
        # A reflected string/xref is not enough to establish accumulator units or
        # whether a function is the central update path rather than debug/UI glue.
        blockers.append("atb-accumulator-semantics-unvalidated")
    if not direct_atb_api_candidate:
        blockers.append("direct-atb-read-write-api-unresolved")
    else:
        blockers.append("direct-atb-read-write-api-semantics-unvalidated")
    if direct_atb_api_candidate and not direct_api_function_candidate:
        blockers.append("direct-atb-read-write-function-path-unresolved")
    elif direct_api_function_candidate and not correlations["setToGet"]:
        blockers.append("direct-atb-read-write-function-link-unvalidated")
    if not atb_max_api_candidate:
        blockers.append("atb-max-unit-contract-unresolved")
    else:
        blockers.append("atb-max-unit-contract-unvalidated")
    if atb_max_api_candidate and not max_api_function_candidate:
        blockers.append("atb-max-function-path-unresolved")
    if not speed_candidate:
        blockers.append("speed-input-path-unresolved")
    else:
        blockers.append("speed-atb-formula-unvalidated")
        if not speed_functions:
            blockers.append("speed-atb-function-path-unresolved")
        elif accumulator_functions and not correlations["speedToAccumulator"]:
            blockers.append("speed-to-accumulator-link-unvalidated")
    if not hit_gain_candidate:
        blockers.append("hit-atb-source-unresolved")
    else:
        blockers.append("hit-atb-formula-unvalidated")
        if not hit_modifier_functions:
            blockers.append("hit-atb-function-path-unresolved")
    if hit_gain_candidate and not hit_event_granularity_present:
        blockers.append("hit-atb-event-granularity-unresolved")
    elif hit_gain_candidate and hit_event_granularity_present:
        blockers.append("hit-atb-event-granularity-unvalidated")
    if not dodge_state_candidate:
        blockers.append("dodge-state-path-unresolved")
    else:
        blockers.append("dodge-transition-edge-unvalidated")
        if not dodge_functions:
            blockers.append("dodge-function-path-unresolved")
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
            "residentContract": "FEndDataTableResidentParameter.ParamInt/ParamFloat keyed by row FName",
            "guardContract": "FEndDataTableBattlePlayerParameter.GuardReaction*AddATB_Array (float arrays)",
            "abilityCostContract": "FEndDataTableBattleAbility.ATB (int32)",
            "battleCharaCandidates": "FEndDataTableBattleCharaSpec.ATB / StartATB (int32; semantics not yet validated)",
            "guardEditableNow": guard_rows > 0 and not discovery_errors,
            "abilityCostsEditableNow": ability_rows > 0 and not discovery_errors,
            "residentSemanticsValidated": False,
            "unitsValidated": False,
            "documentedVanillaReference": dict(DOCUMENTED_VANILLA_ATB_REFERENCES),
            "documentedReferenceValidatedAgainstInstalledRows": False,
        },
        "runtimeResearch": {
            "accumulatorCandidatePresent": accumulator_candidates,
            "accumulatorSemanticsValidated": False,
            "directATBApiCandidatePresent": direct_atb_api_candidate,
            "directATBApiFunctionCandidatePresent": direct_api_function_candidate,
            "atbMaxApiCandidatePresent": atb_max_api_candidate,
            "atbMaxFunctionCandidatePresent": max_api_function_candidate,
            "accessorNeedleHits": accessor_hits,
            "speedCandidatePresent": speed_candidate,
            "residentReaderCandidatePresent": resident_reader_candidate,
            "speedFormulaValidated": False,
            "hitGainCandidatePresent": hit_gain_candidate,
            "hitFormulaValidated": False,
            "hitEventGranularityCandidatePresent": hit_event_granularity_present,
            "hitEventNeedleHits": hit_event_hits,
            "dodgeStateCandidatePresent": dodge_state_candidate,
            "dodgeTransitionValidated": False,
            "movementStateStrategy": "derive from authoritative character movement/velocity only after the ATB accumulator hook is validated",
            "nativeFunctionEvidence": function_evidence,
            "nativeFunctionCorrelations": correlations,
            "nativeFunctionClusters": clusters,
            "crossFamilyFunctionCount": sum(1 for row in clusters if row["crossFamily"]),
        },
        "knownContracts": {
            "setATB": "UEndBattleAPI::SetATB(EPlayerType, float)",
            "setATBAll": "UEndBattleAPI::SetATBAll(float)",
            "getATB": "AEndBattleAIController::GetATB() -> int32",
            "getATBMax": "AEndBattleAIController::GetATBMax() -> int32",
            "resetATB": "AEndBattleAIController::ResetATB()",
            "speedStat": "FEndPlayerStatus.Dexterity / UEndMenuBPAPI::BPGetPlayerDexterity(EPlayerType)",
            "dodgeQuery": "UEndBattleAPI::IsDodge(AEndCharacter*)",
            "hitModifier": "EEndEquipmentSkillEffectType::HitBonusATBRecoverAdd (0x6E)",
            "hitEventEnum": "EEndBattleCountLogType exposes HitSuccess and PerHitSuccess variants separately",
            "startModifier": "EEndEquipmentSkillEffectType::StartATBAdd",
            "displayedBarReference": "community measurement: 1000 internal ATB units per displayed bar; 2000-unit normal gauge",
        },
        "notes": [
            "BattleAbility.ATB is an authored int32 action-cost field; it is not evidence about ATB generation and its mapping to displayed ATB bars must be verified before labeling units.",
            "GuardReaction*AddATB_Array explicitly identifies guard-generated ATB as authored float values and can be edited as data; their conversion to displayed bars is still unvalidated.",
            "Public Remake measurements and ResidentParameter mods independently document 1.0 player passive, 0.35 AI passive, 0.1 guard, 0.0 dodge/action, 1.4 Haste and 0.6 Slow behavior. These are validation fingerprints only until exact installed row tags are correlated.",
            "ResidentParameter rows containing ATB remain candidates until each requested baseline/Speed/hit term is semantically identified on the installed build. GetResidentParameterFloatBP is a useful native reader anchor when present.",
            "BattleCharaSpec declares int32 ATB and StartATB fields; they are retained as explicit research candidates rather than assumed to be player passive generation coefficients.",
            "BPGetPlayerDexterity identifies the runtime stat source corresponding to the player's Speed/Dexterity stat, but not the coefficient used by ATB generation.",
            "HitBonusATBRecoverAdd proves a hit-recovery modifier exists. Exact .pdata/one-hop correlations against attack-level HitSuccess versus PerHitSuccess are now reported separately so installed evidence can discriminate per-action from per-hit paths without guessing.",
            "SetATB/GetATB/GetATBMax provide promising bounded read/write/unit probes for the new dodge reduction, but their numeric conversion and safe call context must be validated before runtime mutation.",
            "IsDodge is a narrow reflected dodge-state query; dodgeToSetATB/dodgeToAccumulator correlations are research leads only, and the implementation must trigger on the dodge transition rather than subtracting ATB every frame while dodge state remains true.",
            "Only exact .pdata function owners and their bounded one-hop targets participate in function correlations. Multi-name direct owners can be reflection registration glue and remain unvalidated.",
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