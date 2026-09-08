"""Read-only research probe for FF7R unscanned-enemy name presentation.

The requested tweak needs two independent facts before a safe runtime patch can
exist: the per-save assessed/scanned state keyed from BattleCharaSpec.EnemyBookID,
and both UI presentation surfaces that render enemy names.  This probe collects
current-build native string/xref candidates and the cooked EnemyStatus/
BattleTarget widget evidence without claiming that authored EnemyBook.ViewState
is the player's scan state.
"""

from __future__ import annotations

from pathlib import Path

from .native_probe import probe_installed_exe
from .raw_asset_probe import probe_installed_assets


EXE_NEEDLES = (
    "EnemyBookID",
    "EnemyBook_IncrementKillCount_BP",
    "ShowBattleEnemyStatusWindow",
    "SetBattleEnemyStatusWindowPosition",
    "ShowBattleTargetIcon",
    "BattleEnemyStatusWidget",
    "BattleTargetWidget",
    "BattleTargetNewWidget",
)

ASSET_TERMS = (
    "menu/resident/battle/enemystatus",
    "menu/resident/battle/battletarget_new",
)

ASSET_STRING_TOKENS = (
    "enemy",
    "name",
    "text",
    "target",
    "status",
    "book",
    "scan",
    "assess",
    "label",
    "widget",
    "visibility",
)


def probe_unscanned_name_surfaces(game_root: Path) -> dict:
    game_root = Path(game_root).resolve()
    native = probe_installed_exe(game_root, needles=EXE_NEEDLES)
    widgets = probe_installed_assets(
        game_root,
        terms=ASSET_TERMS,
        interesting_tokens=ASSET_STRING_TOKENS,
    )
    return {
        "native": native,
        "widgets": widgets,
        "knownContracts": {
            "enemyIdentity": "BattleCharaSpec.EnemyBookID",
            "battleStatusApi": "UEndMenuAPI::ShowBattleEnemyStatusWindow",
            "targetIconApi": "UEndMenuAPI::ShowBattleTargetIcon",
            "authoredEnemyBookWarning": (
                "EnemyBook.ViewState is authored DataObject state and is not treated as proof of the per-save Assessed flag."
            ),
        },
        "notes": [
            "The final hook must query the authoritative per-save scan/assessment state for the current EnemyBookID.",
            "The name suffix must be presentation-only and preserve the installed localized enemy name.",
            "Both normal battle status/name UI and ATB target-selection UI require installed-build validation.",
        ],
    }
