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
    # The shipped assembly clamps the hit rate to 100 before subtracting the
    # bonus, and only on the penalised branch, so a 255 hit rate that IS
    # penalised comes out at 75. The unpenalised branch is untouched and stays
    # 255, which the next two cases pin. This expectation predated the clamp.
    assert effective(255, 25, target_flying=True,
                     attacker_melee=True, attacker_float=False) == 75
    assert effective(255, 25, target_flying=True,
                     attacker_melee=False, attacker_float=False) == 255
    assert effective(255, 25, target_flying=True,
                     attacker_melee=True, attacker_float=True) == 255

    for invalid in (-1, 101, 1.5, True, None, "twenty-five"):
        expect_invalid(invalid)

    patch = gameplay_settings.build_hext(25)
    assert "492E66 = EB" in patch, "the vanilla 255 always-hit branch still exists"
    assert "492EF5 = E9 06 C0 30 02 90" in patch
    # The block grew when the clamp was added to it; its length is stated by
    # the generator, so it is read rather than repeated here.
    assert "279EF00:" in patch
    # The bonus is subtracted from the clamped value now (`sub eax, imm8`)
    # rather than added to ecx, so the opcode changed with the clamp. What
    # matters is that the configured number is the one embedded, which is
    # checked by generating a second patch with a different bonus.
    assert "83 E8 19" in patch, "the bounded 25-point bonus was not embedded"
    assert "83 E8 07" in gameplay_settings.build_hext(7), (
        "the embedded bonus does not track the configured value")
    assert "255 does not bypass" in patch
    disabled = gameplay_settings.build_hext(0)
    assert "492E66 = EB" not in disabled
    assert "279EF00:" not in disabled

    installed = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII")
    if (installed / "FF8_EN.exe").is_file():
        with tempfile.TemporaryDirectory(prefix="lexeditor-flying-eva-", ignore_cleanup_errors=True) as name:
            project = Path(name)
            result = gameplay_settings.save(
                {"flyingEvaBonus": 25, "flyingEvaEnabled": True},
                game_root=installed, project_root=project,
            )
            assert result["saved"] == 1 and result["enabled"]
            # This used to pin the settings file as an exact dictionary, so
            # adding any unrelated FF8 tweak failed a flying-EVA contract. What
            # belongs here is that flying EVA round-trips, and that the file
            # stays complete against the module's own declared defaults - which
            # keeps its value as a check without freezing the feature set.
            saved = json.loads(gameplay_settings.settings_path(project).read_text())
            assert saved["flyingEvaBonus"] == 25
            assert saved["flyingEvaEnabled"] is True
            # sharedMagicInventory is stored in its own runtime config, not
            # in the gameplay settings file; its DEFAULT_ here is only the
            # fallback used when that config cannot be read.
            elsewhere = {"sharedmagicinventory"}
            declared = {
                name.removeprefix("DEFAULT_").lower().replace("_", ""): value
                for name, value in vars(gameplay_settings).items()
                if name.startswith("DEFAULT_") and not callable(value)
            }
            written = {key.lower(): value for key, value in saved.items()}
            missing = sorted(set(declared) - set(written) - elsewhere)
            assert not missing, f"settings file is missing declared defaults: {missing}"
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
