"""Run FF7 rendered tests with framework.css and neutral.css both inlined."""
from __future__ import annotations

import json
import unittest
import verify_ff7_rendered as target


def open_with_neutral(self, edition="ff7"):
    self.page.goto("about:blank")
    html = (target.ROOT / "games/ff7/editor.html").read_text()
    # framework.js resolves optional shared assets relative to document.baseURI.
    # Synthetic set_content() pages otherwise use the non-hierarchical about:blank URL.
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    shared_css = (target.ROOT / "ui/framework.css").read_text() + "\n" + (target.ROOT / "ui/neutral.css").read_text()
    html = html.replace('<link rel="stylesheet" href="/shared/framework.css">', "<style>" + shared_css + "</style>")
    html = html.replace('<link rel="stylesheet" href="/shared/neutral.css">', "")
    code = target.HOST + "\nwindow.__lexeditorPlugin=" + json.dumps({"id":edition,"name":"FF7 fixture","edition":edition}) + ";\n" + (target.ROOT / "ui/framework.js").read_text()
    html = html.replace('<script src="/shared/framework.js"></script>', "<script>" + code + "</script>")
    self.page.set_content(html, wait_until="domcontentloaded")
    self.page.wait_for_function("state.loaded === true")
    self.assertEqual(self.errors, [])


def test_accessory_description_is_editable_game_text(self):
    self.install()
    self.open()
    self.navigate("accessories")
    description = self.page.get_by_label("Description for Record0", exact=True)
    self.assertTrue(description.is_editable())
    self.assertEqual(description.input_value(), "Help0")
    heading = self.page.locator(".ff7-detail .lex-detail-panel-heading").first.inner_text()
    self.assertNotIn("ff7", heading.casefold())
    description.fill("Edited accessory description")
    self.save()
    status, data = self.backend.request("/api/data")
    self.assertEqual(status, 200)
    self.assertEqual(data["records"]["accessories"][0]["description"], "Edited accessory description")

    self.navigate("characters")
    self.assertEqual(self.page.get_by_label("Description for Slot0", exact=True).count(), 0)
    self.assertNotIn("Initial stats, equipment, materia/AP", self.page.locator("main").inner_text())
    self.originals_unchanged()



def test_materia_uses_human_semantic_controls(self):
    self.install()
    self.open()
    self.navigate("materia")

    equip = self.page.get_by_label("Stats while equipped for Record0", exact=True)
    behavior = self.page.get_by_label("Materia behavior for Record0", exact=True)
    element = self.page.get_by_label("Element for Record0", exact=True)
    statuses = self.page.get_by_role("group", name="Status effects for Record0", exact=True)
    self.assertEqual(equip.evaluate("e=>e.tagName"), "SELECT")
    self.assertEqual(behavior.evaluate("e=>e.tagName"), "SELECT")
    self.assertEqual(element.evaluate("e=>e.tagName"), "SELECT")
    self.assertEqual(statuses.locator('input[type="checkbox"]').count(), 24)
    self.assertEqual(self.page.get_by_label("Status flags for Record0", exact=True).count(), 0)
    self.assertEqual(self.page.get_by_label("Materia type byte for Record0", exact=True).count(), 0)

    equip.select_option("6")
    behavior.select_option(str(0x19))
    element.select_option("2")
    self.page.get_by_label("Poison", exact=True).check()
    self.save()

    status, data = self.backend.request("/api/data")
    self.assertEqual(status, 200)
    values = data["records"]["materia"][0]["values"]
    self.assertEqual(values["equipEffect"], 6)
    self.assertEqual(values["materiaType"], 0x19)
    self.assertEqual(values["element"], 2)
    self.assertEqual(values["statusFlags"], 1 << 3)
    self.originals_unchanged()


def test_full_ff7_surface_uses_human_controls(self):
    self.install()
    self.open()

    # Items: bitmask/formula/status bytes are semantic controls.
    self.navigate("items")
    self.assertEqual(self.page.get_by_role("group", name="Targeting for Record0", exact=True).locator('input[type="checkbox"]').count(), 8)
    self.assertEqual(self.page.get_by_label("Damage / healing formula for Record0", exact=True).evaluate("e=>e.tagName"), "SELECT")
    self.assertEqual(self.page.get_by_label("Status change mode for Record0", exact=True).evaluate("e=>e.tagName"), "SELECT")
    self.assertEqual(self.page.get_by_label("Target flags for Record0", exact=True).count(), 0)

    # Equipment: equipability/elements/status/growth are names, not masks/codes.
    self.navigate("weapons")
    self.assertEqual(self.page.get_by_role("group", name="Usable by for Record0", exact=True).locator('input[type="checkbox"]').count(), 11)
    self.assertEqual(self.page.get_by_label("Materia AP growth for Record0", exact=True).evaluate("e=>e.tagName"), "SELECT")
    self.navigate("accessories")
    self.assertEqual(self.page.get_by_label("Automatic / special effect for Record0", exact=True).evaluate("e=>e.tagName"), "SELECT")
    self.assertEqual(self.page.get_by_role("group", name="Protected statuses for Record0", exact=True).locator('input[type="checkbox"]').count(), 32)

    # Characters: cross-dataset IDs are actual named selectors.
    self.navigate("characters")
    weapon=self.page.get_by_label("Starting weapon for Slot0", exact=True)
    row=self.page.get_by_label("Starting row for Slot0", exact=True)
    limits=self.page.get_by_role("group", name="Limits already learned for Slot0", exact=True)
    self.assertEqual(weapon.evaluate("e=>e.tagName"),"SELECT")
    self.assertIn("Record0", weapon.locator("option").all_inner_texts())
    weapon_search=self.page.get_by_label("Search Starting weapon for Slot0", exact=True)
    self.assertEqual(weapon_search.get_attribute("type"),"search")
    before=weapon.locator("option").count()
    weapon_search.fill("Record1")
    self.assertLess(weapon.locator("option").count(),before)
    self.assertTrue(any("Record1" in option for option in weapon.locator("option").all_inner_texts()))
    weapon.select_option("1")
    self.page.get_by_label("Open Starting weapon for Slot0", exact=True).click()
    self.assertEqual(self.page.evaluate("state.tab"),"weapons")
    self.assertEqual(self.page.evaluate("state.selected.weapons"),1)
    self.navigate("characters")
    weapon=self.page.get_by_label("Starting weapon for Slot0", exact=True)
    row=self.page.get_by_label("Starting row for Slot0", exact=True)
    limits=self.page.get_by_role("group", name="Limits already learned for Slot0", exact=True)
    self.assertIn("Front row", row.locator("option").all_inner_texts())
    self.assertEqual(limits.locator('input[type="checkbox"]').count(),7)
    self.assertEqual(self.page.get_by_label("Weapon ID for Slot0", exact=True).count(),0)

    # Scene data: local attack/enemy IDs resolve by name; inverted masks are
    # shown as logical checklists.
    self.navigate("enemies")
    action=self.page.get_by_label("Action 1 attack for Enemy0", exact=True)
    self.assertEqual(action.evaluate("e=>e.tagName"),"SELECT")
    self.assertIn("Action0", action.locator("option").all_inner_texts())
    self.assertEqual(self.page.get_by_role("group", name="Status immunities for Enemy0", exact=True).locator('input[type="checkbox"]').count(),32)

    self.navigate("enemyAttacks")
    self.assertEqual(self.page.get_by_label("Damage / healing formula for Action0", exact=True).evaluate("e=>e.tagName"),"SELECT")
    specials=self.page.get_by_role("group", name="Special attack properties for Action0", exact=True)
    self.assertGreaterEqual(specials.locator('input[type="checkbox"]').count(),10)

    # Field/world and shops no longer ask for anonymous battle/product IDs.
    self.navigate("fieldEncounters")
    encounter=self.page.get_by_label("Normal 1 battle ID for field1 / table 0", exact=True)
    enabled=self.page.get_by_label("Random encounters for field1 / table 0", exact=True)
    self.assertEqual(encounter.evaluate("e=>e.tagName"),"SELECT")
    self.assertEqual(enabled.get_attribute("type"),"checkbox")

    self.navigate("shops")
    shop_type=self.page.get_by_label("Shop type for Shop 0", exact=True)
    product=self.page.get_by_label("Slot 1 product for Shop 0", exact=True)
    self.assertEqual(shop_type.evaluate("e=>e.tagName"),"SELECT")
    self.assertEqual(product.evaluate("e=>e.tagName"),"SELECT")
    self.assertTrue(any("Record" in value for value in product.locator("option").all_inner_texts()))
    product_search=self.page.get_by_label("Search Slot 1 product for Shop 0", exact=True)
    product_search.fill("Record1")
    self.assertTrue(any("Record1" in value for value in product.locator("option").all_inner_texts()))

    # Save representative semantic edits from different binary families.
    self.navigate("weapons")
    weapon_id=self.page.evaluate("state.selected.weapons")
    self.page.get_by_label(f"Materia AP growth for Record{weapon_id}", exact=True).select_option("2")
    self.save()
    status,data=self.backend.request('/api/data');self.assertEqual(status,200)
    self.assertEqual(data['records']['weapons'][weapon_id]['values']['growthRate'],2)

    self.navigate("enemyAttacks")
    critical=self.page.get_by_label("Always critical", exact=True)
    # The fixture stores the special mask as zero; logical flags are inverted,
    # so unchecking sets the stored inverse bit while the UI remains semantic.
    critical.uncheck()
    self.save()
    status,data=self.backend.request('/api/data');self.assertEqual(status,200)
    self.assertTrue(data['records']['enemyAttacks'][0]['values']['specialFlags'] & 0x2000)
    self.originals_unchanged()



def test_holistic_ff7_concept_views_and_new_game_data(self):
    self.install(); self.open()
    self.navigate("initialState")
    self.assertEqual(self.page.get_by_label("Party member 1 for New game defaults", exact=True).evaluate("e=>e.tagName"), "SELECT")
    self.navigate("initialInventory")
    self.assertEqual(self.page.get_by_label("Item / equipment for Slot 1 — Unknown item 421", exact=True).evaluate("e=>e.tagName"), "SELECT")
    self.navigate("magicOrder")
    self.assertEqual(self.page.get_by_label("Magic-menu section for Record0", exact=True).evaluate("e=>e.tagName"), "SELECT")

    for tab, concept in (("growthCurves","growth-curve"),("growthBonuses","growth-bonuses"),("characters","character-growth-curves"),("weapons","equipment-materia-slots"),("enemies","enemy-loot"),("encounters","formation-slots"),("shops","shop-inventory"),("fieldEncounters","weighted-encounters")):
        self.navigate(tab)
        self.assertEqual(self.page.locator(f'[data-concept="{concept}"]').count(),1,(tab,concept))

    self.navigate("growthCurves")
    self.assertEqual(self.page.get_by_role("img", name="Primary stat curve 0 curve preview").count(),1)
    self.assertEqual(self.page.get_by_label("Growth curve brackets").locator("input").count(),16)
    self.navigate("enemies")
    self.assertEqual(self.page.get_by_label("Loot slot 1 method / chance for Enemy0", exact=True).evaluate("e=>e.tagName"),"SELECT")
    self.assertEqual(self.page.get_by_label("Back-attack damage multiplier for Enemy0", exact=True).get_attribute("step"),"0.125")
    self.originals_unchanged()


def test_refined_master_and_detail_ux(self):
    self.install(); self.open()

    self.navigate("materia")
    progression = self.page.get_by_label("Materia AP level progression", exact=True)
    self.assertEqual(progression.count(), 1)
    self.assertEqual(progression.locator('input[type="number"]').count(), 4)
    self.assertEqual(self.page.locator('[data-concept="editable-description"] textarea').count(), 1)

    self.navigate("items")
    self.assertGreaterEqual(self.page.get_by_text("Power", exact=True).count(), 1)
    self.assertGreaterEqual(self.page.get_by_text("Formula", exact=True).count(), 1)

    self.navigate("characterAI")
    row_name = self.page.evaluate("state.records.characterAI.find(r=>r.id===state.selected.characterAI).name")
    event = self.page.get_by_label(f"AI event for {row_name}", exact=True)
    self.assertEqual(event.evaluate("e=>e.tagName"), "SELECT")
    self.assertEqual(event.locator("option").count(), 16)
    self.assertEqual(self.page.locator(".ff7-detail textarea").count(), 1)
    self.assertEqual(self.page.locator('[data-concept="ai-event-editor"]').count(), 1)
    self.assertIn("Cloud AI", self.page.locator("main").inner_text())
    self.assertGreaterEqual(self.page.get_by_text("Scripts", exact=True).count(), 1)
    self.assertEqual(self.page.get_by_text("EVENTS", exact=True).count(), 1)
    event.select_option("1")
    main_label = self.page.evaluate("state.data.categories.find(c=>c.id==='characterAI').fields.find(f=>f.key==='script1').label")
    self.assertEqual(self.page.get_by_label(f"{main_label} for {row_name}", exact=True).count(), 1)
    self.assertEqual(self.page.locator(".ff7-detail textarea").count(), 1)

    self.navigate("encounters")
    self.assertEqual(self.page.evaluate("state.sort.encounters || null"), None)
    main_text = self.page.locator("main").inner_text()
    self.assertIn("Battle 2", main_text)
    self.assertLess(main_text.find("Battle 2"), main_text.find("Battle 10"))
    self.originals_unchanged()

target.RenderedTests.open = open_with_neutral
target.RenderedTests.test_materia_uses_human_semantic_controls = test_materia_uses_human_semantic_controls
target.RenderedTests.test_full_ff7_surface_uses_human_controls = test_full_ff7_surface_uses_human_controls
target.RenderedTests.test_accessory_description_is_editable_game_text = test_accessory_description_is_editable_game_text
target.RenderedTests.test_holistic_ff7_concept_views_and_new_game_data = test_holistic_ff7_concept_views_and_new_game_data
target.RenderedTests.test_refined_master_and_detail_ux = test_refined_master_and_detail_ux

if __name__ == "__main__":
    unittest.main(module=target, verbosity=2)
