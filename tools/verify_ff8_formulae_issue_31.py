"""Source contract for the structured FF8 Formulae view."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    require('["formulae","Formulae"]' in editor and "formulae:renderFormulae" in editor,
            "Formulae must be a normal FF8 primary tab")
    require("function renderFormulae()" in editor,
            "Formulae needs a structured renderer")
    require('aria-label":"Formulae Rework"' in editor and
            'checked:settings.formulaeRework' in editor,
            "Formulae must own one unified rework switch")
    tweaks = editor[editor.index("function renderGameplaySettings"):
                    editor.index("function renderPlatformSettings")]
    require("FULL LUCK ACCURACY" not in tweaks and
            "SPELL HEALING REWORK" not in tweaks,
            "formula changes must not return as separate Tweaks")
    require('"PHYSICAL DAMAGE"' in editor and '"PHYSICAL ACCURACY"' in editor,
            "the first Formulae view must cover physical damage and accuracy")
    require("Math.trunc((265-Number(f.vitality))*(strength+Math.trunc(strength*strength/16))/256)" in editor,
            "physical damage must use the verified integer equation")
    require('luckTerm=settings.formulaeRework?Number(f.luck):Math.floor(Number(f.luck)/2)' in editor and
            'fieldValue("hit_rate")+luckTerm-Number(f.eva)-Number(f.targetLuck)-flyingPenalty' in editor,
            "physical accuracy must switch between vanilla and full-LUCK terms")
    require("boost=()=>state.data.settings.flyingEvaEnabled?state.data.settings.flyingEvaBonus:0" in editor,
            "Formulae must use the enabled state and value from the one shared Flying EVA setting")
    require("boost=state.formula" not in editor and
            not re.search(r"formula:\{[^}]*flyingEvaBonus", editor),
            "Formulae must not create an independent Flying EVA value")
    require("A hit rate of 255 receives no bypass" in editor,
            "the chosen no-bypass rule must be explicit")
    require('class:"formula-expression"' in editor,
            "Formulae must show the actual equation, not only test outputs")
    require('class:"formula-terms"' in editor and 'class:"formula-preview-inputs"' in editor,
            "formula terms and preview-only inputs must be visibly separate")
    require('class:"formula-preset"' in editor and '"WEAPON PRESET"' in editor,
            "each formula needs a real weapon-record preset")
    for field in ('"attack_power"', '"str_bonus"', '"hit_rate"', '"melee"'):
        require(f"formulaTerm({field}" in editor,
                f"Formulae does not edit the verified weapon term {field}")
    require('fieldSourceControl(field,"weapons",weapon.id)' in editor,
            "formula terms must share the weapon editor save and reference path")
    require("DAMAGE = floor" in editor and "HIT CHANCE =" in editor,
            "the physical formula cards must show their named calculations")
    require("Not yet transcribed from the game" not in editor,
            "all shipped vanilla formula paths must be transcribed")
    for text in (
        "Damage_ComputeMagicAndGF at 0x491AD0",
        "BASE = trunc((265 − target SPR) × (spell power + caster MAG) / 4)",
        "SCALED = trunc(spell power × BASE / 256)",
        "Battle_ApplyStatusWithResistRoll at 0x48F9F0",
        "status accuracy + trunc(attacker stat / 4) − trunc(target stat / 4) − target status resistance",
        "Damage_ComputeCurativeMagic at 0x493280",
        "HALF = trunc((spell power + caster MAG) / 2)",
        "This routine has no formula-result clamp",
    ):
        require(text in editor, f"vanilla Formulae source is incomplete: {text}")
    require('"FLYING EVA BONUS"' in editor and "DEFAULT_FLYING_EVA_BONUS" in editor,
            "the supported editable formula term needs a bounded restore control")
    require('formulaInput("Attack power"' not in editor and
            'formulaInput("Hit rate"' not in editor and
            'formulaInput("Weapon STR bonus"' not in editor,
            "stored weapon terms must not remain fake preview-only inputs")
    require("PREVIEW INPUTS" in editor,
            "test values must be identified as preview inputs")
    formulae = editor[editor.index("function formulaInput"):
                      editor.index("async function saveAll")]
    require("function formulaInput(label,key,min,max,step=1)" in formulae
            and "numberControl(state.formula[key],min,max,step" in formulae,
            "Formulae must use the shared bounded numeric control")
    require("type:\"text\",inputmode:\"decimal\"" in editor
            and '"data-min":min,"data-max":max,"data-step":step' in editor,
            "formatted numeric controls must retain explicit bounds")
    require("textarea" not in formulae and "contenteditable" not in formulae,
            "unrestricted formula input must not return")
    print("FF8 structured Formulae source contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
