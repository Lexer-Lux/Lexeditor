"""Read-only installed-build research for FF7R's unscanned-name suffix tweak.

Issue #424 is a runtime presentation change: append ``?`` to an enemy's normal
localized display name until that EnemyBook entry has actually been Assessed.
The generated Remake surface gives us a trustworthy BattleCharaSpec ->
EnemyBookID relationship and dedicated battle/target UI settings, but it does
not expose a trustworthy per-save "is assessed" query.  This probe therefore
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

PRESENTATION_ANCHORS = (
    "BattleEnemyStatusWidget",
    "BattleTargetWidget",
    "BattleTargetNewWidget",
    "ShowBattleEnemyStatusWindow",
    "ShowBattleTargetIcon",
)
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
# authoritative query unless the installed executable actually contains it and
# later function-level research validates its semantics.
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


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    folded = value.casefold()
    return any(str(term).casefold() in folded for term in terms)


def rank_unscanned_name_assets(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank cooked UI candidates without conflating EnemyBook data with UI."""
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        strings = _flatten_strings(asset)
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
        if not presentation:
            continue

        score = len(presentation) * 1400 + min(len(text_fields), 32) * 45
        if text_fields:
            score += 1800
        # Useful correlation evidence, but never enough to imply save-state
        # ownership or an assessed-state query.
        score += min(len(state_links), 8) * 120

        ranked.append({
            **asset,
            "presentationAnchorHits": presentation,
            "textPresentationHits": text_fields,
            "enemyBookLinkHits": state_links,
            "nonQueryStateHits": non_query,
            "strongPresentationCandidate": bool(presentation and text_fields),
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

    # String presence is only a discovery lead. A candidate query must still be
    # semantically validated against live save/progression behavior before a
    # runtime hook can consume it.
    state_query_candidate_present = any(query_hits.values())
    state_query_validated = False
    battle_name_path_candidate = bool(
        presentation_hits.get("BattleEnemyStatusWidget")
        or presentation_hits.get("ShowBattleEnemyStatusWindow")
        or any(
            any(
                _contains_any(str(hit.get("text", "")), ("BattleEnemyStatusWidget", "ShowBattleEnemyStatusWindow"))
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
            any(
                _contains_any(
                    str(hit.get("text", "")),
                    ("BattleTargetWidget", "BattleTargetNewWidget", "ShowBattleTargetIcon"),
                )
                for hit in row.get("presentationAnchorHits", ())
            )
            for row in candidates
        )
    )

    blockers: list[str] = []
    if errors:
        blockers.append("scan-errors")
    if not any(link_hits.values()):
        blockers.append("enemy-book-link-not-found-in-native-probe")
    if not state_query_candidate_present:
        blockers.append("assessed-state-query-not-found")
    # Even if a guessed query-like symbol exists, discovery is not validation.
    if state_query_candidate_present and not state_query_validated:
        blockers.append("assessed-state-query-unvalidated")
    if not battle_name_path_candidate:
        blockers.append("battle-name-presentation-path-unresolved")
    if not atb_target_path_candidate:
        blockers.append("atb-target-presentation-path-unresolved")

    return {
        "implementationReady": False,
        "blockers": blockers,
        "enemyBookLink": {
            "needleHits": link_hits,
            "authoritativeAuthoredField": "BattleCharaSpec.EnemyBookID",
        },
        "assessedState": {
            "candidateNeedleHits": query_hits,
            "candidatePresent": state_query_candidate_present,
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
            "rankedCandidateCount": len(candidates),
        },
        "scanErrors": errors,
        "notes": [
            "BattleCharaSpec.EnemyBookID is an authored identity link, not proof that the enemy has been Assessed in this save.",
            "EnemyBook.ViewState is static table data and is deliberately not treated as per-save Assess state.",
            "EnemyBook_IncrementKillCount_BP mutates kill-count bookkeeping and is not treated as an Assess query.",
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
