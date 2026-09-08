from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / 'games').is_dir():
    repo = ROOT
else:
    repo = ROOT.parent


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'{label}: insertion point changed')
    path.write_text(text.replace(old, new, 1))

kernel = repo / 'games/ff7/kernel.py'
replace_once(kernel,
'''            Field("cameraMovementId", "Camera movement ID", 0x08, "H", maximum=65535),
            Field("targetData", "Target flags", 0x0C),''',
'''            Field("cameraMovementId", "Camera movement ID", 0x08, "H", maximum=65535),
            Field("restrictions", "Usage restrictions", 0x0A, "H", maximum=0xFFFF),
            Field("targetData", "Target flags", 0x0C),''', 'item restrictions')
replace_once(kernel,
'''            Field("statusFlags", "Status flags", 0x14, "I", maximum=0xFFFFFFFF),
            Field("elementFlags", "Element flags", 0x18, "H", maximum=0xFFFF),
        )),
        Category("weapons",''',
'''            Field("statusFlags", "Status flags", 0x14, "I", maximum=0xFFFFFFFF),
            Field("elementFlags", "Element flags", 0x18, "H", maximum=0xFFFF),
            Field("specialAttackFlags", "Special attack flags", 0x1A, "H", maximum=0xFFFF),
        )),
        Category("weapons",''', 'item special flags')
replace_once(kernel,
'''            Field("accuracyRate", "Accuracy rate", 0x08),
            Field("weaponModelId", "Weapon model ID", 0x09),
            Field("equipableBy", "Equipable-by flags", 0x0E, "H", maximum=0xFFFF),
            Field("attackElements", "Attack element flags", 0x10, "H", maximum=0xFFFF),
        )),''',
'''            Field("accuracyRate", "Accuracy rate", 0x08),
            Field("weaponModelId", "Weapon model ID", 0x09),
            Field("highSoundIdMask", "High sound ID mask", 0x0B),
            Field("equipableBy", "Equipable-by flags", 0x0E, "H", maximum=0xFFFF),
            Field("attackElements", "Attack element flags", 0x10, "H", maximum=0xFFFF),
            *(Field(f"boostedStat{i}", f"Boosted stat {i}", 0x13 + i) for i in range(1, 5)),
            *(Field(f"boostedStat{i}Bonus", f"Stat {i} bonus", 0x17 + i) for i in range(1, 5)),
            *(Field(f"materiaSlot{i}", f"Materia slot {i}", 0x1B + i) for i in range(1, 9)),
            Field("normalHitSoundId", "Normal hit sound ID", 0x24),
            Field("criticalHitSoundId", "Critical hit sound ID", 0x25),
            Field("missedAttackSoundId", "Missed attack sound ID", 0x26),
            Field("impactEffectId", "Impact effect ID", 0x27),
            Field("restrictions", "Usage restrictions", 0x2A, "H", maximum=0xFFFF),
        )),''', 'weapon fields')
replace_once(kernel,
'''            Field("status", "Equipment status", 0x06),
            Field("growthRate", "Materia growth rate", 0x11),''',
'''            Field("status", "Equipment status", 0x06),
            *(Field(f"materiaSlot{i}", f"Materia slot {i}", 0x08 + i) for i in range(1, 9)),
            Field("growthRate", "Materia growth rate", 0x11),''', 'armor materia slots')
replace_once(kernel,
'''            Field("equipableBy", "Equipable-by flags", 0x12, "H", maximum=0xFFFF),
            Field("elementalDefense", "Element defense flags", 0x14, "H", maximum=0xFFFF),
        )),
        Category("accessories",''',
'''            Field("equipableBy", "Equipable-by flags", 0x12, "H", maximum=0xFFFF),
            Field("elementalDefense", "Element defense flags", 0x14, "H", maximum=0xFFFF),
            *(Field(f"boostedStat{i}", f"Boosted stat {i}", 0x17 + i) for i in range(1, 5)),
            *(Field(f"boostedStat{i}Bonus", f"Stat {i} bonus", 0x1B + i) for i in range(1, 5)),
            Field("restrictions", "Usage restrictions", 0x20, "H", maximum=0xFFFF),
        )),
        Category("accessories",''', 'armor bonuses/restrictions')
replace_once(kernel,
'''            Field("statusDefense", "Status defense flags", 0x08, "I", maximum=0xFFFFFFFF),
            Field("equipableBy", "Equipable-by flags", 0x0C, "H", maximum=0xFFFF),
        )),
        Category("materia",''',
'''            Field("statusDefense", "Status defense flags", 0x08, "I", maximum=0xFFFFFFFF),
            Field("equipableBy", "Equipable-by flags", 0x0C, "H", maximum=0xFFFF),
            Field("restrictions", "Usage restrictions", 0x0E, "H", maximum=0xFFFF),
        )),
        Category("materia",''', 'accessory restrictions')

sem = repo / 'games/ff7/semantics.py'
replace_once(sem,
''')

SPECIAL_ATTACK_FLAGS = (''',
''')

RESTRICTION_FLAGS = (
    (0x0001, "Can be sold"), (0x0002, "Can be used in battle"),
    (0x0004, "Can be used from the menu"), (0x0008, "Can be thrown"),
)
MATERIA_SLOTS = (
    (0, "No slot"), (1, "Unlinked — no AP growth"),
    (2, "Linked left — no AP growth"), (3, "Linked right — no AP growth"),
    (5, "Unlinked"), (6, "Linked left"), (7, "Linked right"),
)

SPECIAL_ATTACK_FLAGS = (''', 'equipment semantic constants')
replace_once(sem,
'''        "elementFlags": _field(label="Elements", dataType="flags", flags=flags(*ELEMENTS), group="Effect", help="Elemental tags used by the battle engine."),
        "cameraMovementId": advanced''',
'''        "elementFlags": _field(label="Elements", dataType="flags", flags=flags(*ELEMENTS), group="Effect", help="Elemental tags used by the battle engine."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Where this item is allowed to be sold or used. KERNEL.BIN stores these permission bits inverted."),
        "specialAttackFlags": _field(label="Special attack properties", dataType="flags", flags=flags(*SPECIAL_ATTACK_FLAGS), invertBits=True, bitWidth=16, group="Effect", help="Special battle properties such as reflection, defense bypass or MP damage. KERNEL.BIN stores these bits inverted."),
        "cameraMovementId": advanced''', 'item semantics')
replace_once(sem,
'''        "attackElements": _field(label="Attack elements", dataType="flags", flags=flags(*ELEMENTS), group="Combat", help="Elements applied by the weapon's basic attack."),
        "weaponModelId": advanced("Weapon model ID", "Raw model index used by the battle renderer; no authoritative model-name table is currently exposed."),
    },''',
'''        "attackElements": _field(label="Attack elements", dataType="flags", flags=flags(*ELEMENTS), group="Combat", help="Elements applied by the weapon's basic attack."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Whether this weapon may be sold, used in battle/menu contexts, or thrown. KERNEL.BIN stores these permission bits inverted."),
        "weaponModelId": advanced("Weapon model ID", "Raw model index used by the battle renderer; no authoritative model-name table is currently exposed."),
        "highSoundIdMask": advanced("Sound ID high-bit mask", "Raw high-bit selector used with this weapon's hit/miss sound IDs."),
        "normalHitSoundId": advanced("Normal hit sound ID", "Raw sound-effect selector for a normal weapon hit."),
        "criticalHitSoundId": advanced("Critical hit sound ID", "Raw sound-effect selector for a critical weapon hit."),
        "missedAttackSoundId": advanced("Miss sound ID", "Raw sound-effect selector for a missed weapon attack."),
        "impactEffectId": advanced("Impact effect ID", "Raw impact visual-effect selector for this weapon."),
        **{f"boostedStat{i}": _field(label=f"Stat bonus {i}", dataType="enum", choices=choices(*CHARACTER_STATS), group="Stat bonuses", help=f"Character stat modified by equipment bonus slot {i}.") for i in range(1,5)},
        **{f"boostedStat{i}Bonus": _field(label=f"Stat bonus {i} amount", group="Stat bonuses", help=f"Amount added to equipment stat bonus slot {i}.") for i in range(1,5)},
        **{f"materiaSlot{i}": _field(label=f"Materia slot {i}", dataType="enum", choices=choices(*MATERIA_SLOTS), group="Materia slots", help="Whether this position exists, links to its neighbor, and supports AP growth.") for i in range(1,9)},
    },''', 'weapon semantics')
replace_once(sem,
'''        "elementalDefense": _field(label="Affected elements", dataType="flags", flags=flags(*ELEMENTS), group="Elemental defense", help="Elements affected by Elemental response."),
    },
    "accessories": {''',
'''        "elementalDefense": _field(label="Affected elements", dataType="flags", flags=flags(*ELEMENTS), group="Elemental defense", help="Elements affected by Elemental response."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Whether this armor may be sold, used in battle/menu contexts, or thrown. KERNEL.BIN stores these permission bits inverted."),
        **{f"boostedStat{i}": _field(label=f"Stat bonus {i}", dataType="enum", choices=choices(*CHARACTER_STATS), group="Stat bonuses", help=f"Character stat modified by equipment bonus slot {i}.") for i in range(1,5)},
        **{f"boostedStat{i}Bonus": _field(label=f"Stat bonus {i} amount", group="Stat bonuses", help=f"Amount added to equipment stat bonus slot {i}.") for i in range(1,5)},
        **{f"materiaSlot{i}": _field(label=f"Materia slot {i}", dataType="enum", choices=choices(*MATERIA_SLOTS), group="Materia slots", help="Whether this position exists, links to its neighbor, and supports AP growth.") for i in range(1,9)},
    },
    "accessories": {''', 'armor semantics')
replace_once(sem,
'''        "equipableBy": _field(label="Usable by", dataType="flags", flags=flags(*EQUIPABLE), group="Equipment", help="Characters allowed to equip this accessory."),
    },
}''',
'''        "equipableBy": _field(label="Usable by", dataType="flags", flags=flags(*EQUIPABLE), group="Equipment", help="Characters allowed to equip this accessory."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Whether this accessory may be sold, used in battle/menu contexts, or thrown. KERNEL.BIN stores these permission bits inverted."),
    },
}''', 'accessory semantics')

test = repo / 'tools/verify_ff7_semantic_surface.py'
replace_once(test,
'''            "items":{"targetData":"flags","damageCalculationId":"enum","statusChange":"statusChange","statusFlags":"flags","elementFlags":"flags"},
            "weapons":{"targetData":"flags","damageCalculationId":"enum","growthRate":"enum","equipableBy":"flags","attackElements":"flags"},
            "armor":{"elementDamageModifier":"enum","status":"enum","growthRate":"enum","equipableBy":"flags","elementalDefense":"flags"},
            "accessories":{"boostedStat1":"enum","specialEffect":"enum","elementalDefense":"flags","statusDefense":"flags","equipableBy":"flags"},''',
'''            "items":{"targetData":"flags","damageCalculationId":"enum","statusChange":"statusChange","statusFlags":"flags","elementFlags":"flags","restrictions":"flags","specialAttackFlags":"flags"},
            "weapons":{"targetData":"flags","damageCalculationId":"enum","growthRate":"enum","equipableBy":"flags","attackElements":"flags","boostedStat1":"enum","materiaSlot1":"enum","restrictions":"flags"},
            "armor":{"elementDamageModifier":"enum","status":"enum","growthRate":"enum","equipableBy":"flags","elementalDefense":"flags","boostedStat1":"enum","materiaSlot1":"enum","restrictions":"flags"},
            "accessories":{"boostedStat1":"enum","specialEffect":"enum","elementalDefense":"flags","statusDefense":"flags","equipableBy":"flags","restrictions":"flags"},''', 'semantic expected surface')
replace_once(test,
'''        self.assertTrue(meta["playerAttacks"]["specialAttackFlags"]["invertBits"])
''',
'''        self.assertTrue(meta["playerAttacks"]["specialAttackFlags"]["invertBits"])
        for category in ("items","weapons","armor","accessories"):
            self.assertTrue(meta[category]["restrictions"]["invertBits"],category)
            self.assertEqual(meta[category]["restrictions"]["bitWidth"],16,category)
        self.assertTrue(meta["items"]["specialAttackFlags"]["invertBits"])
        self.assertEqual([c["value"] for c in meta["weapons"]["materiaSlot1"]["choices"]],[0,1,2,3,5,6,7])
''', 'semantic assertions')
