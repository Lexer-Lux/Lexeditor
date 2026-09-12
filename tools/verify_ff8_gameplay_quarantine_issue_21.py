"""Regression contract for visible FF8 Tweak persistence after crash repair."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import gameplay_settings


VISIBLE = frozenset({
    "flyingEvaEnabled", "autoSortInventory", "autoSortMagic",
    "enhancedAbilityMenu", "singleGf", "universalItem", "scannedTargetScan",
    "sharedMagicInventory", "partySwitch", "drawOncePerEnemy",
    "streamlinedDraw", "betterCard", "fixedCommandMenu", "trueAtbWait",
    "modernControls", "vibrationConsolidation", "betterTargeting",
    "damageLimitRemoval", "fastStart", "xpBars", "hpBars",
    "flatStatAbilities", "maxSpellEnabled", "gfHpBars", "noMagicConsumption", "dropsAfterMug",
})


EDITOR = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")


def main() -> None:
    # The quarantine is that nothing is accepted and written to the game
    # without also being visible and editable in the Tweaks page. Freezing the
    # exact set made every new tweak fail a check about that rule, so the rule
    # is now checked directly: nothing that was visible may disappear, and
    # anything newly accepted must appear in the editor that shows them.
    missing = sorted(VISIBLE - gameplay_settings.ACCEPTED_TWEAKS)
    assert not missing, f"accepted tweaks lost: {missing}"
    unshown = sorted(key for key in gameplay_settings.ACCEPTED_TWEAKS - VISIBLE
                     if key not in EDITOR)
    assert not unshown, f"tweaks accepted but not shown in the editor: {unshown}"

    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        configured = {
            "autoSortInventory": True,
            "autoSortMagic": True,
            "enhancedAbilityMenu": True,
            "flyingEvaEnabled": True,
            "singleGf": True,
            "universalItem": True,
            "scannedTargetScan": True,
            "partySwitch": True,
            "drawOncePerEnemy": True,
            "streamlinedDraw": True,
            "formulaeRework": True,
            "betterCard": True,
            "fixedCommandMenu": True,
            "trueAtbWait": True,
            "modernControls": True,
            "vibrationConsolidation": True,
            "betterTargeting": True,
            "damageLimitRemoval": True,
            "fastStart": True,
            "xpBars": True,
            "hpBars": True,
            "flatStatAbilities": True,
            "maxSpellEnabled": True,
            "gfHpBars": True, "noMagicConsumption": True, "dropsAfterMug": True,
        }
        gameplay_settings.settings_path(project).write_text(
            json.dumps(configured), encoding="utf-8",
        )
        gameplay_settings.shared_magic_runtime_config.write(
            project, shared_magic_inventory=True,
        )
        loaded = gameplay_settings.load(project)
        for key in VISIBLE:
            assert loaded[key] is True, key
        assert loaded["formulaeRework"] is False

    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(
        encoding="utf-8",
    )
    rendered = editor[editor.index('const view=el("section",{class:"settings-view"}'):
                      editor.index('$("#main").replaceChildren(view);')]
    assert 'row("MONOGAMY"' in rendered
    assert 'row("UNIVERSAL ITEM"' in rendered
    for title in ("XP BARS", "HP BARS", "SHARED PARTY MAGIC INVENTORY",
                  "BETTER TARGETING", "COMMAND MENU REWORK"):
        assert f'row("{title}"' in rendered, title
    assert 'row("ENHANCED SCAN"' in rendered
    assert 'row("FORMULAE REWORK"' not in rendered

    print("FF8 visible Tweak persistence regression check passed")


if __name__ == "__main__":
    main()
