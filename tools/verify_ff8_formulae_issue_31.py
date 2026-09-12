"""Static contract for the FF8 Formulae page (GitHub #31)."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formulae_rework  # noqa: E402


def main() -> int:
    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    gameplay = (ROOT / "games" / "ff8" / "gameplay_settings.py").read_text(encoding="utf-8")

    assert '["formulae","Formulae"]' in editor and "formulae:renderFormulae" in editor
    assert "function renderFormulae()" in editor
    assert 'aria-label":"Formulae Rework"' in editor and 'checked:settings.formulaeRework' in editor
    tweaks = editor[editor.index("function renderGameplaySettings"):
                    editor.index("function renderPlatformSettings")]
    assert "FULL LUCK ACCURACY" not in tweaks and "SPELL HEALING REWORK" not in tweaks
    assert '"PHYSICAL DAMAGE"' in editor and '"PHYSICAL ACCURACY"' in editor
    assert "Math.trunc((265-Number(f.vitality))*(strength+Math.trunc(strength*strength/16))/256)" in editor
    assert 'luckTerm=settings.formulaeRework?Number(f.luck):Math.floor(Number(f.luck)/2)' in editor
    assert 'fieldValue("hit_rate")+luckTerm-Number(f.eva)-Number(f.targetLuck)-flyingPenalty' in editor
    assert "boost=()=>state.data.settings.flyingEvaEnabled?state.data.settings.flyingEvaBonus:0" in editor
    assert "A hit rate of 255 receives no bypass" in editor
    assert 'class:"formula-expression"' in editor
    assert 'class:"formula-terms"' in editor and 'class:"formula-preview-inputs"' in editor
    assert 'class:"formula-preset"' in editor and '"WEAPON PRESET"' in editor
    for field in ('"attack_power"', '"str_bonus"', '"hit_rate"', '"melee"'):
        assert f"formulaTerm({field}" in editor
    assert 'fieldSourceControl(field,"weapons",weapon.id)' in editor
    assert "DAMAGE = floor" in editor and "HIT CHANCE =" in editor

    # Native routine descriptions live in one backend-owned inventory now. The
    # editor consumes those rows instead of duplicating native addresses/text in
    # HTML, so updating one formula cannot silently leave two sources divergent.
    assert '"formulaeReworkFormulas": formulae_rework_contract.rows()' in gameplay
    assert 'const formulaRows=settings.formulaeReworkFormulas||[];' in editor
    assert 'const rework=formulaRows.map(reworkCard);' in editor
    assert 'formula.status==="implemented"?"IMPLEMENTED":"INCOMPLETE"' in editor
    assert 'formula.replacement||"Not specified"' in editor
    assert 'formula.vanilla||"Not documented"' in editor
    assert 'formula.blocker?el("p",{class:"readonly-note"}' in editor
    assert 'settings.formulaeReworkAvailable' in editor

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

    assert '"FLYING EVA BONUS"' in editor and "DEFAULT_FLYING_EVA_BONUS" in editor
    assert 'formulaInput("Attack power"' not in editor
    assert 'formulaInput("Hit rate"' not in editor
    assert 'formulaInput("Weapon STR bonus"' not in editor
    assert "PREVIEW INPUTS" in editor
    formulae = editor[editor.index("function formulaInput"):
                      editor.index("async function saveAll")]
    assert "function formulaInput(label,key,min,max,step=1)" in formulae
    assert "numberControl(state.formula[key],min,max,step" in formulae
    assert "type:\"text\",inputmode:\"decimal\"" in editor
    assert '"data-min":min,"data-max":max,"data-step":step' in editor
    assert "textarea" not in formulae and "contenteditable" not in formulae

    print("FF8 Formulae Rework single-source inventory and UI contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
