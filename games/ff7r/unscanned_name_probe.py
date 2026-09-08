"""Read-only installed-build research for FF7R's unscanned-name suffix tweak.

Issue #424 is a runtime presentation change: append ``?`` to an enemy's normal
localized display name until that EnemyBook entry has actually been Assessed.
The generated Remake surface gives us a trustworthy BattleCharaSpec ->
EnemyBookID relationship and dedicated battle/target UI settings, but it does
not expose a trustworthy per-save "is assessed" query. This probe therefore
keeps state and presentation evidence separate and fails closed until both are
identified in the installed build.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .native_probe import probe_installed_exe
from .raw_asset_probe import probe_installed_assets


ASSET_TERMS = (
    "battleenemy",
    "battletarget",
    "enemybook",
    "libra",
)

BATTLE_NAME_ANCHORS = (
    "BattleEnemyStatusWidget",
    "ShowBattleEnemyStatusWindow",
)
ATB_TARGET_ANCHORS = (
    "BattleTargetWidget",
    "BattleTargetNewWidget",
    "ShowBattleTargetIcon",
)
PRESENTATION_ANCHORS = (*BATTLE_NAME_ANCHORS, *ATB_TARGET_ANCHORS)
TEXT_PRESENTATION_TERMS = (
    "Text",
    "TextBlock",
    "Name",
    "Label",
    "EnemyName",
    "TargetName",
    "GetString",
)
STATE_LINK_ANCHORS = (
    "EnemyBookID",
    "EnemyBookIDPlus",
)
# These are intentionally only discovery needles. None is treated as an
# authoritative query unless installed behavior validates its semantics.
STATE_QUERY_CANDIDATE_NEEDLES = (
    "IsEnemyBook",
    "GetEnemyBook",
    "EnemyBook_Is",
    "EnemyBook_Get",
)
KNOWN_NON_QUERY_ANCHORS = (
    "EnemyBook_IncrementKillCount_BP",
    "ViewState",
    "Libra",
)
INTERESTING_TOKENS = (
    *PRESENTATION_ANCHORS,
    *TEXT_PRESENTATION_TERMS,
    *STATE_LINK_ANCHORS,
    *STATE_QUERY_CANDIDATE_NEEDLES,
    *KNOWN_NON_QUERY_ANCHORS,
)
NATIVE_NEEDLES = (
    *STATE_LINK_ANCHORS,
    *STATE_QUERY_CANDIDATE_NEEDLES,
    "EnemyBook_IncrementKillCount_BP",
    "BattleEnemyStatusWidget",
    "BattleTargetWidget",
    "BattleTargetNewWidget",
    "ShowBattleEnemyStatusWindow",
    "ShowBattleTargetIcon",
    "Libra",
)


def _flatten_strings(asset: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file_row in asset.get("files", ()):
        suffix = str(file_row.get("suffix", ""))
        path = str(file_row.get("path", ""))
        for string_row in file_row.get("interestingStrings", ()):
            rows.append({"suffix": suffix, "path": path, **string_row})
    return rows


def _flatten_objects(asset: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file_row in asset.get("files", ()):
        suffix = str(file_row.get("suffix", ""))
        path = str(file_row.get("path", ""))
        for kind in ("resolvedImports", "resolvedExports"):
            for object_row in file_row.get(kind, ()):
                rows.append({
                    "suffix": suffix,
                    "path": path,
                    "objectKind": "import" if kind == "resolvedImports" else "export",
                    **object_row,
                })
    return rows


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    folded = value.casefold()
    return any(str(term).casefold() in folded for term in terms)


def _object_searchable(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("objectName", "objectPath", "outerPath", "className", "classPath", "classPackage")
    )


def _requested_surface(value: str) -> tuple[bool, bool]:
    folded = value.casefold()
    battle = any(token in folded for token in ("battleenemy", "enemystatus"))
    target = any(token in folded for token in ("battletarget", "targetnew"))
    return battle, target


def _resolved_text_children(asset: dict[str, Any], objects: Iterable[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Return text/name-like object rows scoped to requested battle/target UI assets."""
    battle_rows: list[dict] = []
    target_rows: list[dict] = []
    asset_name = str(asset.get("asset", ""))
    asset_battle, asset_target = _requested_surface(asset_name)
    for row in objects:
        child = " ".join((str(row.get("objectName") or ""), str(row.get("className") or "")))
        if not _contains_any(child, TEXT_PRESENTATION_TERMS):
            continue
        ownership = " ".join((
            asset_name,
            str(row.get("objectPath") or ""),
            str(row.get("outerPath") or ""),
        ))
        row_battle, row_target = _requested_surface(ownership)
        if asset_battle or row_battle:
            battle_rows.append(row)
        if asset_target or row_target:
            target_rows.append(row)
    return battle_rows, target_rows


def rank_unscanned_name_assets(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank cooked UI candidates without conflating EnemyBook data with UI."""
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        strings = _flatten_strings(asset)
        objects = _flatten_objects(asset)
        presentation = [
            row for row in strings
            if _contains_any(str(row.get("text", "")), PRESENTATION_ANCHORS)
        ]
        text_fields = [
            row for row in strings
            if _contains_any(str(row.get("text", "")), TEXT_PRESENTATION_TERMS)
        ]
        state_links = [
            row for row in strings
            if _contains_any(str(row.get("text", "")), STATE_LINK_ANCHORS)
        ]
        non_query = [
            row for row in strings
            if _contains_any(str(row.get("text", "")), KNOWN_NON_QUERY_ANCHORS)
        ]
        resolved_presentation = [
            row for row in objects
            if _contains_any(_object_searchable(row), PRESENTATION_ANCHORS)
        ]
        resolved_battle_children, resolved_target_children = _resolved_text_children(asset, objects)
        asset_battle, asset_target = _requested_surface(str(asset.get("asset", "")))
        resolved_battle_owner = bool(
            any(_contains_any(_object_searchable(row), BATTLE_NAME_ANCHORS) for row in resolved_presentation)
            or (asset_battle and resolved_battle_children)
        )
        resolved_target_owner = bool(
            any(_contains_any(_object_searchable(row), ATB_TARGET_ANCHORS) for row in resolved_presentation)
            or (asset_target and resolved_target_children)
        )

        if not presentation and not resolved_presentation and not resolved_battle_owner and not resolved_target_owner:
            continue

        score = (
            len(resolved_presentation) * 5000
            + len(resolved_battle_children) * 1800
            + len(resolved_target_children) * 1800
            + len(presentation) * 1400
            + min(len(text_fields), 32) * 45
        )
        if text_fields:
            score += 1800
        if resolved_battle_owner:
            score += 3500
        if resolved_target_owner:
            score += 3500
        # Useful correlation evidence, but never enough to imply save-state
        # ownership or an assessed-state query.
        score += min(len(state_links), 8) * 120

        ranked.append({
            **asset,
            "presentationAnchorHits": presentation,
            "textPresentationHits": text_fields,
            "enemyBookLinkHits": state_links,
            "nonQueryStateHits": non_query,
            "resolvedPresentationOwners": resolved_presentation,
            "resolvedBattleNameChildren": resolved_battle_children,
            "resolvedAtbTargetNameChildren": resolved_target_children,
            "resolvedBattleNameOwnerEvidence": resolved_battle_owner,
            "resolvedAtbTargetOwnerEvidence": resolved_target_owner,
            "strongPresentationCandidate": bool(
                (presentation and text_fields)
                or resolved_battle_owner
                or resolved_target_owner
            ),
            "score": score,
        })

    return sorted(
        ranked,
        key=lambda row: (-int(row["score"]), str(row.get("asset", "")).casefold()),
    )


def _needle_hits(native: dict[str, Any], needle: str) -> list[dict[str, Any]]:
    for row in native.get("needles", ()):
        if str(row.get("needle", "")) == needle:
            return list(row.get("hits", ()))
    return []


def _caller_rvas(inbound: dict[str, Any] | None) -> set[int]:
    return {
        int(row["sourceFunctionRva"])
        for row in (inbound or {}).get("refs", ())
        if row.get("sourceFunctionRva") is not None
    }


def _native_function_evidence(
    native: dict[str, Any], needles: Iterable[str]
) -> dict[str, dict[str, list[int]]]:
    """Collect only exact .pdata owners, bounded one-hop targets, and callers."""
    result: dict[str, dict[str, list[int]]] = {}
    for needle in needles:
        direct: set[int] = set()
        next_hops: set[int] = set()
        callers: set[int] = set()
        for hit in _needle_hits(native, needle):
            for xref in hit.get("leaRipXrefs", ()):
                if xref.get("candidateFunctionSource") != "pdata":
                    continue
                function_rva = xref.get("candidateFunctionRva")
                if function_rva is not None:
                    direct.add(int(function_rva))
                callers.update(_caller_rvas(xref.get("candidateFunctionInboundCodeRefs")))
                for code_ref in (xref.get("candidateFunctionCodeRefs") or {}).get("refs", ()):
                    target = code_ref.get("targetFunctionRva")
                    if target is not None:
                        next_hops.add(int(target))
                    callers.update(_caller_rvas(code_ref.get("targetFunctionInboundCodeRefs")))
        result[needle] = {
            "directPdataFunctions": sorted(direct),
            "nextHopPdataFunctions": sorted(next_hops),
            "expandedPdataFunctions": sorted(direct | next_hops),
            "inboundCallerFunctions": sorted(callers),
        }
    return result


def _functions(evidence: dict[str, dict[str, list[int]]], needles: Iterable[str]) -> set[int]:
    functions: set[int] = set()
    for needle in needles:
        functions.update(evidence.get(needle, {}).get("expandedPdataFunctions", ()))
    return functions


def _callers(evidence: dict[str, dict[str, list[int]]], needles: Iterable[str]) -> set[int]:
    callers: set[int] = set()
    for needle in needles:
        callers.update(evidence.get(needle, {}).get("inboundCallerFunctions", ()))
    return callers


def assess_unscanned_name_evidence(
    *,
    native: dict[str, Any],
    candidates: Iterable[dict[str, Any]],
    scan_errors: Iterable[str] = (),
) -> dict[str, Any]:
    """Fail closed until an actual assessed-state query and both UI paths exist."""
    candidates = list(candidates)
    errors = [str(error) for error in scan_errors]
    query_hits = {
        needle: len(_needle_hits(native, needle))
        for needle in STATE_QUERY_CANDIDATE_NEEDLES
    }
    link_hits = {
        needle: len(_needle_hits(native, needle))
        for needle in STATE_LINK_ANCHORS
    }
    presentation_hits = {
        needle: len(_needle_hits(native, needle))
        for needle in PRESENTATION_ANCHORS
    }
    function_evidence = _native_function_evidence(
        native,
        (*STATE_LINK_ANCHORS, *STATE_QUERY_CANDIDATE_NEEDLES, *PRESENTATION_ANCHORS),
    )
    query_functions = _functions(function_evidence, STATE_QUERY_CANDIDATE_NEEDLES)
    link_functions = _functions(function_evidence, STATE_LINK_ANCHORS)
    battle_functions = _functions(function_evidence, BATTLE_NAME_ANCHORS)
    target_functions = _functions(function_evidence, ATB_TARGET_ANCHORS)
    query_callers = _callers(function_evidence, STATE_QUERY_CANDIDATE_NEEDLES)
    link_callers = _callers(function_evidence, STATE_LINK_ANCHORS)
    battle_callers = _callers(function_evidence, BATTLE_NAME_ANCHORS)
    target_callers = _callers(function_evidence, ATB_TARGET_ANCHORS)
    function_correlations = {
        "queryToEnemyBookLink": sorted(query_functions & link_functions),
        "queryToBattleName": sorted(query_functions & battle_functions),
        "queryToAtbTarget": sorted(query_functions & target_functions),
        "queryToEnemyBookLinkCallers": sorted(query_callers & link_callers),
        "queryToBattleNameCallers": sorted(query_callers & battle_callers),
        "queryToAtbTargetCallers": sorted(query_callers & target_callers),
    }

    # String presence is only a discovery lead. An exact function owner/next-hop
    # is stronger navigation evidence, but still cannot establish what one
    # query-like name means for the current save or which bit/record it reads.
    state_query_candidate_present = any(query_hits.values())
    state_query_function_candidate_present = bool(query_functions)
    state_query_validated = False
    battle_name_path_candidate = bool(
        presentation_hits.get("BattleEnemyStatusWidget")
        or presentation_hits.get("ShowBattleEnemyStatusWindow")
        or any(
            row.get("resolvedBattleNameOwnerEvidence")
            or any(
                _contains_any(str(hit.get("text", "")), BATTLE_NAME_ANCHORS)
                for hit in row.get("presentationAnchorHits", ())
            )
            for row in candidates
        )
    )
    atb_target_path_candidate = bool(
        presentation_hits.get("BattleTargetWidget")
        or presentation_hits.get("BattleTargetNewWidget")
        or presentation_hits.get("ShowBattleTargetIcon")
        or any(
            row.get("resolvedAtbTargetOwnerEvidence")
            or any(
                _contains_any(str(hit.get("text", "")), ATB_TARGET_ANCHORS)
                for hit in row.get("presentationAnchorHits", ())
            )
            for row in candidates
        )
    )
    battle_name_child_candidate = any(
        row.get("resolvedBattleNameChildren") for row in candidates
    )
    atb_target_name_child_candidate = any(
        row.get("resolvedAtbTargetNameChildren") for row in candidates
    )

    blockers: list[str] = []
    if errors:
        blockers.append("scan-errors")
    if not any(link_hits.values()):
        blockers.append("enemy-book-link-not-found-in-native-probe")
    if not state_query_candidate_present:
        blockers.append("assessed-state-query-not-found")
    elif not state_query_function_candidate_present:
        blockers.append("assessed-state-query-function-unresolved")
    else:
        blockers.append("assessed-state-query-function-semantics-unvalidated")
    # Even if a guessed query-like symbol exists and has exact function evidence,
    # discovery/navigation is not live-save semantic validation.
    if state_query_candidate_present and not state_query_validated:
        blockers.append("assessed-state-query-unvalidated")
    if not battle_name_path_candidate:
        blockers.append("battle-name-presentation-path-unresolved")
    elif not battle_name_child_candidate:
        blockers.append("battle-name-text-child-unresolved")
    if not atb_target_path_candidate:
        blockers.append("atb-target-presentation-path-unresolved")
    elif not atb_target_name_child_candidate:
        blockers.append("atb-target-name-text-child-unresolved")

    return {
        "implementationReady": False,
        "blockers": blockers,
        "enemyBookLink": {
            "needleHits": link_hits,
            "authoritativeAuthoredField": "BattleCharaSpec.EnemyBookID",
            "secondaryAuthoredField": "BattleCharaSpec.EnemyBookIDPlus",
        },
        "assessedState": {
            "candidateNeedleHits": query_hits,
            "candidatePresent": state_query_candidate_present,
            "functionCandidatePresent": state_query_function_candidate_present,
            "validated": state_query_validated,
            "explicitlyNotAcceptedAsState": [
                "FEndDataTableEnemyBook.ViewState",
                "UEndDataBaseAPI.EnemyBook_IncrementKillCount_BP",
                "EEndMenuLockonMarkerType.Libra",
            ],
        },
        "presentation": {
            "nativeNeedleHits": presentation_hits,
            "battleNamePathCandidate": battle_name_path_candidate,
            "atbTargetPathCandidate": atb_target_path_candidate,
            "battleNameTextChildCandidate": battle_name_child_candidate,
            "atbTargetNameTextChildCandidate": atb_target_name_child_candidate,
            "resolvedBattleOwnerCandidates": sum(
                bool(row.get("resolvedBattleNameOwnerEvidence")) for row in candidates
            ),
            "resolvedAtbTargetOwnerCandidates": sum(
                bool(row.get("resolvedAtbTargetOwnerEvidence")) for row in candidates
            ),
            "rankedCandidateCount": len(candidates),
        },
        "nativeFunctionEvidence": function_evidence,
        "nativeFunctionCorrelations": function_correlations,
        "scanErrors": errors,
        "knownContracts": {
            "battleStatusSetting": "UEndMenuSettings::BattleEnemyStatusWidget",
            "battleTargetSetting": "UEndMenuSettings::BattleTargetWidget",
            "battleTargetNewSetting": "UEndMenuSettings::BattleTargetNewWidget",
        },
        "notes": [
            "BattleCharaSpec.EnemyBookID/EnemyBookIDPlus are authored identity links, not proof that the enemy has been Assessed in this save.",
            "EnemyBook.ViewState is static table data and is deliberately not treated as per-save Assess state.",
            "EnemyBook_IncrementKillCount_BP mutates kill-count bookkeeping and is not treated as an Assess query.",
            "Query-like reflected names now require exact .pdata function evidence before becoming function candidates; padding-heuristic owners cannot strengthen them.",
            "Shared exact functions or inbound callers between a query-like name, EnemyBook identity, and battle/target presentation are navigation leads only. Reflection registration glue and generic dispatchers can legitimately produce these correlations.",
            "Resolved cooked object-table evidence can narrow the name-bearing UI children for both requested presentation surfaces, but does not supply the missing per-save Assessed predicate.",
            "The final suffix must wrap the game's localized display string at runtime; no localized EnemyBook text is rewritten by this probe.",
        ],
    }


def probe_unscanned_name_sources(game_root: Path) -> dict[str, Any]:
    """Collect installed state/presentation evidence without modifying the game."""
    raw = probe_installed_assets(
        Path(game_root),
        terms=ASSET_TERMS,
        interesting_tokens=INTERESTING_TOKENS,
    )
    candidates = rank_unscanned_name_assets(raw.get("assets", ()))
    native = probe_installed_exe(Path(game_root), needles=NATIVE_NEEDLES)
    assessment = assess_unscanned_name_evidence(
        native=native,
        candidates=candidates,
        scan_errors=raw.get("scanErrors", ()),
    )
    return {
        "candidates": candidates,
        "native": native,
        **assessment,
    }
