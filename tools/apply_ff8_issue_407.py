"""One-shot guarded source migration for FF8 issue #407.

This exists because the FF8 editor is intentionally a monolithic HTML artifact.
Every replacement is exact and single-occurrence; abort rather than partially
editing if concurrent work changed any integration seam.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one integration seam, found {count}")
    return text.replace(old, new, 1)


def patch_settings() -> None:
    path = ROOT / "games/ff8/gameplay_settings.py"
    text = path.read_text(encoding="utf-8")
    replacements = [
        (
            "from . import mug_drops\n",
            "from . import mug_drops\nfrom . import drop_chance\n",
            "drop_chance import",
        ),
        (
            '    "flatStatAbilities", "maxSpellEnabled", "noMagicConsumption", "dropsAfterMug",\n',
            '    "flatStatAbilities", "maxSpellEnabled", "noMagicConsumption", "dropsAfterMug",\n'
            '    "dropChance",\n',
            "accepted tweak",
        ),
        (
            '    drops_after_mug = data.get("dropsAfterMug") is True\n',
            '    drops_after_mug = data.get("dropsAfterMug") is True\n'
            '    drop_chance_enabled = data.get("dropChance") is True\n',
            "load setting",
        ),
        (
            '        "noMagicConsumption": no_magic_consumption,\n'
            '        "dropsAfterMug": drops_after_mug,\n'
            '        "flatStatAbilities": flat_stat_abilities_enabled,\n'
            '        "maxSpellEnabled": max_spell_enabled,\n'
            '        "maxSpell": max_spell_value,\n'
            '        "maxSpellMinimum": max_spell.MIN_MAX_SPELL,\n',
            '        "noMagicConsumption": no_magic_consumption,\n'
            '        "dropsAfterMug": drops_after_mug,\n'
            '        "dropChance": drop_chance_enabled,\n'
            '        "dropChanceWeights": drop_chance.metadata(),\n'
            '        "flatStatAbilities": flat_stat_abilities_enabled,\n'
            '        "maxSpellEnabled": max_spell_enabled,\n'
            '        "maxSpell": max_spell_value,\n'
            '        "maxSpellMinimum": max_spell.MIN_MAX_SPELL,\n',
            "load payload",
        ),
        (
            '        mug_drops.verify_executable(stream)\n',
            '        mug_drops.verify_executable(stream)\n'
            '        drop_chance.verify_executable(stream)\n',
            "executable verification",
        ),
        (
            '               flying_eva_enabled: bool = True,\n'
            '               drops_after_mug: bool = False) -> str:\n',
            '               flying_eva_enabled: bool = True,\n'
            '               drops_after_mug: bool = False,\n'
            '               drop_chance_enabled: bool = False,\n'
            '               drop_chance_plan=None) -> str:\n',
            "build signature",
        ),
        (
            '    drops_after_mug = _boolean(drops_after_mug, "Drops After Mug")\n',
            '    drops_after_mug = _boolean(drops_after_mug, "Drops After Mug")\n'
            '    drop_chance_enabled = _boolean(drop_chance_enabled, "Drop Chance")\n',
            "build validation",
        ),
        (
            '    mug_drop_patch = mug_drops.build_hext(drops_after_mug)\n'
            '    if mug_drop_patch:\n'
            '        lines.extend(mug_drop_patch.rstrip().splitlines())\n'
            '    max_spell_patch = max_spell.build_hext(max_spell_enabled, max_spell_value)\n',
            '    mug_drop_patch = mug_drops.build_hext(drops_after_mug)\n'
            '    if mug_drop_patch:\n'
            '        lines.extend(mug_drop_patch.rstrip().splitlines())\n'
            '    drop_chance_patch = drop_chance.build_hext(drop_chance_enabled, drop_chance_plan)\n'
            '    if drop_chance_patch:\n'
            '        lines.extend(drop_chance_patch.rstrip().splitlines())\n'
            '    else:\n'
            '        lines.append("# Drop Chance is disabled; regular drops and Mug use vanilla slot weights.")\n'
            '    max_spell_patch = max_spell.build_hext(max_spell_enabled, max_spell_value)\n',
            "build patch",
        ),
        (
            '        "dropsAfterMug": False,\n'
            '        "flatStatAbilities": False,\n',
            '        "dropsAfterMug": False,\n'
            '        "dropChance": False,\n'
            '        "flatStatAbilities": False,\n',
            "project defaults",
        ),
        (
            '    drops_after_mug = _boolean(data.get("dropsAfterMug", False), "Drops After Mug")\n',
            '    drops_after_mug = _boolean(data.get("dropsAfterMug", False), "Drops After Mug")\n'
            '    drop_chance_enabled = _boolean(data.get("dropChance", False), "Drop Chance")\n',
            "save setting",
        ),
        (
            '    _verify_executable(game)\n'
            '    hext = build_hext(\n',
            '    executable = _verify_executable(game)\n'
            '    drop_chance_plan = (\n'
            '        drop_chance.discover_path(executable) if drop_chance_enabled else None\n'
            '    )\n'
            '    hext = build_hext(\n',
            "verified selector plan",
        ),
        (
            '        flying_eva_enabled=flying_enabled,\n'
            '        drops_after_mug=drops_after_mug,\n'
            '    )\n',
            '        flying_eva_enabled=flying_enabled,\n'
            '        drops_after_mug=drops_after_mug,\n'
            '        drop_chance_enabled=drop_chance_enabled,\n'
            '        drop_chance_plan=drop_chance_plan,\n'
            '    )\n',
            "build invocation",
        ),
        (
            '        "dropsAfterMug": drops_after_mug,\n'
            '        "flatStatAbilities": flat_stat_abilities_enabled,\n'
            '        "maxSpellEnabled": max_spell_enabled,\n'
            '        "maxSpell": max_spell_value,\n'
            '    }\n',
            '        "dropsAfterMug": drops_after_mug,\n'
            '        "dropChance": drop_chance_enabled,\n'
            '        "flatStatAbilities": flat_stat_abilities_enabled,\n'
            '        "maxSpellEnabled": max_spell_enabled,\n'
            '        "maxSpell": max_spell_value,\n'
            '    }\n',
            "saved settings",
        ),
    ]
    for old, new, label in replacements:
        text = replace_once(text, old, new, label)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_editor() -> None:
    path = ROOT / "games/ff8/editor.html"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'noMagicConsumption:state.data.settings.noMagicConsumption,dropsAfterMug:state.data.settings.dropsAfterMug,flatStatAbilities:',
        'noMagicConsumption:state.data.settings.noMagicConsumption,dropsAfterMug:state.data.settings.dropsAfterMug,dropChance:state.data.settings.dropChance,flatStatAbilities:',
        "settings payload",
    )
    text = replace_once(
        text,
        '    const dropsAfterMug=el("input",{type:"checkbox",checked:settings.dropsAfterMug,"aria-label":"Drops After Mug",onchange:event=>{settings.dropsAfterMug=event.target.checked;shell.refresh()}});\n',
        '    const dropsAfterMug=el("input",{type:"checkbox",checked:settings.dropsAfterMug,"aria-label":"Drops After Mug",onchange:event=>{settings.dropsAfterMug=event.target.checked;shell.refresh()}});\n'
        '    const dropChance=el("input",{type:"checkbox",checked:settings.dropChance,"aria-label":"Drop Chance",onchange:event=>{settings.dropChance=event.target.checked;shell.refresh()}});\n',
        "drop chance control",
    )
    text = replace_once(
        text,
        '      row("DROPS AFTER MUG","A successfully Mugged enemy still rolls its normal death drops. Mugging the same enemy twice remains prohibited, and normal drop probabilities are unchanged.",dropsAfterMug,"boolean"),\n',
        '      row("DROPS AFTER MUG","A successfully Mugged enemy still rolls its normal death drops. Mugging the same enemy twice remains prohibited; its item-slot distribution follows the current Drop Chance setting.",dropsAfterMug,"boolean"),\n'
        '      row("DROP CHANCE","Reweights all four item slots for both normal enemy drops and Mug. Normal: 137/256 (53.52%), 68/256 (26.56%), 34/256 (13.28%), 17/256 (6.64%). Rare Item: 94/256 (36.72%), 70/256 (27.34%), 53/256 (20.70%), 39/256 (15.23%).",dropChance,"boolean"),\n',
        "drop chance row",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    patch_settings()
    patch_editor()
    print("Applied guarded FF8 issue #407 integration migration")
