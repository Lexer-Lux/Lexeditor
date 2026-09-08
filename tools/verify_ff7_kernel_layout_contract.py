"""Pin the original FF7 core KERNEL record layout used by Lexeditor.

This is intentionally independent of the generic byte-preservation regression:
that test derives offsets from games.ff7.kernel.CATEGORIES, while this test
hard-codes the documented offsets so a mistaken table entry cannot validate
itself.

Primary source: Shojy/Elena d85e02678670763c663cd058463f7578b957912e
CommandData.cs, AttackData.cs, ItemData.cs, WeaponData.cs, ArmorData.cs and
AccessoryData.cs. Unknown/unused bytes are deliberately absent.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff7 import kernel


EXPECTED = {
    "commands": (1, 18, 10, 8, (
        ("initialCursorAction", 0x00, "B"),
        ("targetData", 0x01, "B"),
        ("cameraMovementIdSingle", 0x04, "H"),
        ("cameraMovementIdMulti", 0x06, "H"),
    )),
    "playerAttacks": (2, 19, 11, 28, (
        ("accuracyRate", 0x00, "B"),
        ("impactEffectId", 0x01, "B"),
        ("targetHurtActionIndex", 0x02, "B"),
        ("mpCost", 0x04, "H"),
        ("impactSound", 0x06, "H"),
        ("cameraMovementIdSingle", 0x08, "H"),
        ("cameraMovementIdMulti", 0x0A, "H"),
        ("targetData", 0x0C, "B"),
        ("attackEffectId", 0x0D, "B"),
        ("damageCalculationId", 0x0E, "B"),
        ("attackPower", 0x0F, "B"),
        ("conditionSubmenu", 0x10, "B"),
        ("statusChange", 0x11, "B"),
        ("additionalEffects", 0x12, "B"),
        ("additionalEffectsModifier", 0x13, "B"),
        ("statusFlags", 0x14, "I"),
        ("elementFlags", 0x18, "H"),
        ("specialAttackFlags", 0x1A, "H"),
    )),
    "items": (5, 20, 12, 28, (
        ("cameraMovementId", 0x08, "H"),
        ("restrictions", 0x0A, "H"),
        ("targetData", 0x0C, "B"),
        ("attackEffectId", 0x0D, "B"),
        ("damageCalculationId", 0x0E, "B"),
        ("attackPower", 0x0F, "B"),
        ("conditionSubmenu", 0x10, "B"),
        ("statusChange", 0x11, "B"),
        ("additionalEffects", 0x12, "B"),
        ("additionalEffectsModifier", 0x13, "B"),
        ("statusFlags", 0x14, "I"),
        ("elementFlags", 0x18, "H"),
        ("specialAttackFlags", 0x1A, "H"),
    )),
    "weapons": (6, 21, 13, 44, (
        ("targetData", 0x00, "B"),
        ("damageCalculationId", 0x02, "B"),
        ("attackStrength", 0x04, "B"),
        ("status", 0x05, "B"),
        ("growthRate", 0x06, "B"),
        ("criticalRate", 0x07, "B"),
        ("accuracyRate", 0x08, "B"),
        ("weaponModelId", 0x09, "B"),
        ("highSoundIdMask", 0x0B, "B"),
        ("equipableBy", 0x0E, "H"),
        ("attackElements", 0x10, "H"),
        ("boostedStat1", 0x14, "B"),
        ("boostedStat2", 0x15, "B"),
        ("boostedStat3", 0x16, "B"),
        ("boostedStat4", 0x17, "B"),
        ("boostedStat1Bonus", 0x18, "B"),
        ("boostedStat2Bonus", 0x19, "B"),
        ("boostedStat3Bonus", 0x1A, "B"),
        ("boostedStat4Bonus", 0x1B, "B"),
        ("materiaSlot1", 0x1C, "B"),
        ("materiaSlot2", 0x1D, "B"),
        ("materiaSlot3", 0x1E, "B"),
        ("materiaSlot4", 0x1F, "B"),
        ("materiaSlot5", 0x20, "B"),
        ("materiaSlot6", 0x21, "B"),
        ("materiaSlot7", 0x22, "B"),
        ("materiaSlot8", 0x23, "B"),
        ("normalHitSoundId", 0x24, "B"),
        ("criticalHitSoundId", 0x25, "B"),
        ("missedAttackSoundId", 0x26, "B"),
        ("impactEffectId", 0x27, "B"),
        ("restrictions", 0x2A, "H"),
    )),
    "armor": (7, 22, 14, 36, (
        ("elementDamageModifier", 0x01, "B"),
        ("defense", 0x02, "B"),
        ("magicDefense", 0x03, "B"),
        ("evade", 0x04, "B"),
        ("magicEvade", 0x05, "B"),
        ("status", 0x06, "B"),
        ("materiaSlot1", 0x09, "B"),
        ("materiaSlot2", 0x0A, "B"),
        ("materiaSlot3", 0x0B, "B"),
        ("materiaSlot4", 0x0C, "B"),
        ("materiaSlot5", 0x0D, "B"),
        ("materiaSlot6", 0x0E, "B"),
        ("materiaSlot7", 0x0F, "B"),
        ("materiaSlot8", 0x10, "B"),
        ("growthRate", 0x11, "B"),
        ("equipableBy", 0x12, "H"),
        ("elementalDefense", 0x14, "H"),
        ("boostedStat1", 0x18, "B"),
        ("boostedStat2", 0x19, "B"),
        ("boostedStat3", 0x1A, "B"),
        ("boostedStat4", 0x1B, "B"),
        ("boostedStat1Bonus", 0x1C, "B"),
        ("boostedStat2Bonus", 0x1D, "B"),
        ("boostedStat3Bonus", 0x1E, "B"),
        ("boostedStat4Bonus", 0x1F, "B"),
        ("restrictions", 0x20, "H"),
    )),
    "accessories": (8, 23, 15, 16, (
        ("boostedStat1", 0x00, "B"),
        ("boostedStat2", 0x01, "B"),
        ("boostedStat1Bonus", 0x02, "B"),
        ("boostedStat2Bonus", 0x03, "B"),
        ("elementDamageModifier", 0x04, "B"),
        ("specialEffect", 0x05, "B"),
        ("elementalDefense", 0x06, "H"),
        ("statusDefense", 0x08, "I"),
        ("equipableBy", 0x0C, "H"),
        ("restrictions", 0x0E, "H"),
    )),
}


class KernelLayoutContractTests(unittest.TestCase):
    def test_documented_core_record_layouts(self):
        for key, (section, name_section, description_section, record_size, fields) in EXPECTED.items():
            with self.subTest(category=key):
                category = kernel.CATEGORIES[key]
                self.assertEqual(
                    (category.section, category.text_name_section, category.text_description_section, category.record_size),
                    (section, name_section, description_section, record_size),
                )
                self.assertEqual(
                    tuple((field.key, field.offset, field.kind) for field in category.fields),
                    fields,
                )

    def test_no_unreviewed_core_category_sneaks_past_layout_contract(self):
        self.assertEqual(set(kernel.CATEGORIES) - {"materia"}, set(EXPECTED))


if __name__ == "__main__":
    unittest.main(verbosity=2)
