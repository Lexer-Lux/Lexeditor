"""FF7 editor language: Perms, lock-to-one-side help, DMG/Heal Formula."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui  # noqa: E402
from plugins.ff7 import semantics  # noqa: E402
from test_shared_ui_feedback import framework, page  # noqa: E402,F401  (pytest fixture)


class FF7LabelTests(unittest.TestCase):
    def test_restrictions_are_perms(self):
        for category in ("items", "weapons", "armor", "accessories"):
            field = semantics.metadata_for(category, "restrictions")
            self.assertEqual(field["label"], "Perms", category)
            self.assertEqual(field["group"], "Perms", category)
            self.assertEqual(
                [flag["label"] for flag in field["flags"]],
                ["Sellable", "Usable in battle", "Usable in menu", "Throwable"],
                category,
            )
            self.assertIn("sold", field["help"])
            self.assertIn("thrown", field["help"])

    def test_lock_to_one_side_has_plain_help(self):
        field = semantics.metadata_for("playerAttacks", "targetData")
        flag = next(f for f in field["flags"] if f["value"] == 0x10)
        self.assertEqual(flag["label"], "Lock to one side")
        self.assertIn("one side", flag["help"])
        self.assertIn("cursor", flag["help"])
        # Every Targeting field shares the same flag table.
        for category, key in (("commands", "targetData"), ("items", "targetData"),
                              ("weapons", "targetData"), ("enemyAttacks", "target")):
            other = semantics.metadata_for(category, key)
            match = next(f for f in other["flags"] if f["value"] == 0x10)
            self.assertEqual(match.get("help"), flag["help"], (category, key))

    def test_damage_formula_is_dmg_heal_formula(self):
        for category, key in (("playerAttacks", "damageCalculationId"),
                              ("items", "damageCalculationId"),
                              ("weapons", "damageCalculationId"),
                              ("limitBreaks", "damageCalculationId"),
                              ("enemyAttacks", "formula")):
            self.assertEqual(
                semantics.metadata_for(category, key)["label"],
                "DMG/Heal Formula", (category, key))

    def test_old_labels_are_gone_from_ui(self):
        ui = plugin_ui("ff7")
        self.assertIn("DMG/Heal Formula", ui)
        for old in ("Damage / healing formula", "Damage formula",
                    "damage/healing formula", "Availability / permissions",
                    "Can be sold", "Can be used in battle",
                    "Can be used from the menu", "Can be thrown"):
            self.assertNotIn(old, ui, old)

    def test_old_labels_are_gone_from_served_metadata(self):
        from plugins.ff7 import kernel
        from plugins.ff7.battle import ATTACK_FIELDS
        seen = []
        for key, category in kernel.CATEGORIES.items():
            for field in semantics.apply(key, category.fields):
                seen.append((key, field))
        for field in semantics.apply("enemyAttacks", ATTACK_FIELDS):
            seen.append(("enemyAttacks", field))
        labels = [f["label"] for _, f in seen]
        self.assertIn("DMG/Heal Formula", labels)
        self.assertIn("Perms", labels)
        blob = repr(seen)
        for old in ("Damage / healing formula", "Availability / permissions",
                    "Can be sold", "Can be used in battle",
                    "Can be used from the menu", "Can be thrown"):
            self.assertNotIn(old, blob, old)


def test_lock_to_one_side_renders_help_bubble(page):
    flag = next(f for f in semantics.metadata_for("playerAttacks", "targetData")["flags"]
                if f["value"] == 0x10)
    framework(page)
    page.evaluate("""help => {
      document.querySelector('main').append(LexeditorUI.toggleRow({label: 'Targeting',
        toggles: [{label: 'Lock to one side', checked: false, help}]}));
    }""", flag["help"])
    rail = page.locator('.lex-toggle-rail .lex-info-help')
    assert rail.count() == 1
    page.locator('.lex-toggle-rail').hover()
    rail.focus()
    page.wait_for_selector('.lex-help-popover')
    assert 'one side' in page.locator('.lex-help-popover').inner_text()


if __name__ == "__main__":
    unittest.main()
