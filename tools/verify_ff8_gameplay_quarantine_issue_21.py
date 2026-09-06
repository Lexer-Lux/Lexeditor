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


def main() -> None:
    assert gameplay_settings.ACCEPTED_TWEAKS == VISIBLE

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
