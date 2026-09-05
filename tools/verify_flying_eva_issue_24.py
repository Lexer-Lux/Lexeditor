"""Static and generated-patch contract for Lexeditor issue 24."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import gameplay_settings  # noqa: E402


def expect_invalid(value) -> None:
    try:
        gameplay_settings.build_hext(value)
    except ValueError:
        return
    raise AssertionError(f"Flying EVA accepted invalid value: {value!r}")


def main() -> int:
    applies = gameplay_settings.flying_bonus_applies
    assert not applies(target_flying=False, attacker_melee=True, attacker_float=False)
    assert not applies(target_flying=True, attacker_melee=False, attacker_float=False)
    assert not applies(target_flying=True, attacker_melee=True, attacker_float=True)
    assert applies(target_flying=True, attacker_melee=True, attacker_float=False)

    effective = gameplay_settings.effective_hit_value
    assert effective(255, 25, target_flying=True,
                     attacker_melee=True, attacker_float=False) == 230
    assert effective(255, 25, target_flying=True,
                     attacker_melee=False, attacker_float=False) == 255
    assert effective(255, 25, target_flying=True,
                     attacker_melee=True, attacker_float=True) == 255

    for invalid in (-1, 101, 1.5, True, None, "twenty-five"):
        expect_invalid(invalid)

    patch = gameplay_settings.build_hext(25)
    assert "492E66 = EB" in patch, "the vanilla 255 always-hit branch still exists"
    assert "492EF5 = E9 06 C0 30 02 90" in patch
    assert "279EF00:43" in patch
    assert "83 C1 19" in patch, "the bounded 25-point bonus was not embedded"
    assert "255 does not bypass" in patch
    disabled = gameplay_settings.build_hext(0)
    assert "492E66 = EB" not in disabled
    assert "279EF00:43" not in disabled

    installed = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII")
    if (installed / "FF8_EN.exe").is_file():
        with tempfile.TemporaryDirectory(prefix="lexeditor-flying-eva-", ignore_cleanup_errors=True) as name:
            project = Path(name)
            result = gameplay_settings.save(
                {"flyingEvaBonus": 25, "flyingEvaEnabled": True},
                game_root=installed, project_root=project,
            )
            assert result["saved"] == 1 and result["enabled"]
            assert json.loads(gameplay_settings.settings_path(project).read_text()) == {
                "autoSortInventory": False,
                "autoSortMagic": False,
                "enhancedAbilityMenu": False,
                "flyingEvaBonus": 25,
                "flyingEvaEnabled": True,
                "singleGf": False,
                "universalItem": False,
                "scannedTargetScan": False,
                "partySwitch": False,
                "drawOncePerEnemy": False,
                "streamlinedDraw": False,
                "betterCard": False,
                "fixedCommandMenu": False,
                "trueAtbWait": False,
                "formulaeRework": False,
                "modernControls": False,
                "vibrationConsolidation": False,
                "betterTargeting": False,
                "damageLimitRemoval": False,
                "fastStart": False,
                "xpBars": False,
                "hpBars": False,
            }
            assert gameplay_settings.patch_path(project).read_text(encoding="utf-8") == patch

    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    server = (ROOT / "games" / "ff8" / "server.py").read_text(encoding="utf-8")
    extractor = (ROOT / "games" / "ff8" / "extractor.py").read_text(encoding="utf-8")
    assert '["settings","Tweaks"]' in editor
    assert 'type:"text",inputmode:"decimal",value:display(value),"data-min":min,"data-max":max,"data-step":step' in editor
    assert 'Math.max(min,Math.min(max,next))' in editor
    assert "A hit rate of 255 does not bypass it." in editor
    assert 'path == "/api/settings"' in server
    assert 'path == "/api/settings/save"' in server
    assert "ensure_gameplay_patch" in extractor

    print("Flying EVA setting, classifications, 255 path, and Hext generation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
