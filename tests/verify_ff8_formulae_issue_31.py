"""Static contract for the FF8 Formulae tweaks subtab (GitHub #31)."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import formulae_rework  # noqa: E402


def main() -> int:
    boot = (ROOT / "plugins" / "ff8" / "boot.js").read_text(encoding="utf-8")
    gameplay = (ROOT / "plugins" / "ff8" / "gameplay_settings.py").read_text(encoding="utf-8")

    # Formulae is a subtab under Tweaks now, not a top-level tab.
    assert '["formulae","Formulae"]' not in boot
    assert "formulae:renderFormulae" not in boot
    assert '{id:"formulae",label:"Formulae"}' in boot
    assert "function renderFormulae()" in boot

    # The subtab unlocks only while its owning tweak is enabled.
    assert "disabled:!state.data.settings.formulaeRework" in boot
    assert 'state.settingsTab="formulae";tab="settings"' in boot
    assert "subtabBar({tabs:tweaks.tabs" in boot

    # The owning toggle lives in the Tweaks Gameplay list, unavailable until
    # every advertised formula has a real runtime patch.
    gameplay_section = boot[boot.index("function renderGameplaySettings"):
                            boot.index("function renderPlatformSettings")]
    assert 'aria-label":"Formulae Rework"' in gameplay_section
    assert "checked:settings.formulaeRework" in gameplay_section
    assert "!settings.formulaeReworkAvailable" in gameplay_section
    assert 'row("FORMULAE REWORK"' in gameplay_section
    # One toggle only: the Formulae page itself carries no second switch.
    assert boot.count('aria-label":"Formulae Rework"') == 1

    # The page keeps its transcription, editable terms and live previews.
    assert '"PHYSICAL DAMAGE"' in boot and '"PHYSICAL ACCURACY"' in boot
    assert "Math.trunc((265-Number(f.vitality))*(strength+Math.trunc(strength*strength/16))/256)" in boot
    assert "luckTerm=settings.formulaeRework?Number(f.luck):Math.floor(Number(f.luck)/2)" in boot
    assert '"FLYING EVA BONUS"' in boot and "DEFAULT_FLYING_EVA_BONUS" in boot
    assert "PREVIEW INPUTS" in boot
    assert "function formulaInput(label,key,min,max,step=1)" in boot
    for field in ('"attack_power"', '"str_bonus"', '"hit_rate"', '"melee"'):
        assert f"formulaTerm({field}" in boot
    assert "DAMAGE = floor" in boot and "HIT CHANCE =" in boot

    # The stacked cards still mount in the shared tweaks scroll container.
    formulae = boot[boot.index("function renderFormulae"):]
    assert "lex-tweaks-scroll" in formulae

    # Native routine descriptions live in one backend-owned inventory now. The
    # editor consumes those rows instead of duplicating native addresses/text
    # in JS, so updating one formula cannot silently leave two sources divergent.
    assert '"formulaeReworkFormulas": formulae_rework_contract.rows()' in gameplay
    assert "settings.formulaeReworkFormulas||[]" in boot
    assert 'formula.status==="implemented"?"IMPLEMENTED":"INCOMPLETE"' in boot
    assert 'formula.replacement||"Not specified"' in boot
    assert 'formula.vanilla||"Not documented"' in boot
    assert "settings.formulaeReworkAvailable" in boot

    rows = formulae_rework.rows()
    by_id = {row["id"]: row for row in rows}
    assert {
        "melee_damage", "magic_damage", "status_infliction", "spell_healing",
        "physical_accuracy", "mug_chance",
    } == set(by_id)
    assert "Damage_ComputeMagicAndGF at 0x491AD0" in by_id["magic_damage"]["vanilla"]
    assert "Battle_ApplyStatusWithResistRoll at 0x48F9F0" in by_id["status_infliction"]["vanilla"]
    assert "Damage_ComputeCurativeMagic at 0x493280" in by_id["spell_healing"]["vanilla"]
    assert by_id["spell_healing"]["status"] == formulae_rework.STATUS_IMPLEMENTED
    assert by_id["physical_accuracy"]["status"] == formulae_rework.STATUS_IMPLEMENTED
    assert not formulae_rework.available(), "master toggle must stay unavailable while advertised rows are incomplete"

    print("FF8 Formulae Tweaks-subtab single-source inventory and UI contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
