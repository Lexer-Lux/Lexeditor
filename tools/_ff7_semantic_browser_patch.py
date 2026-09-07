from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# Existing broad browser test must interact according to the rendered control
# kind now that encounter IDs/ratings are selects rather than raw number boxes.
p=ROOT/'tools/verify_ff7_rendered.py'
s=p.read_text(encoding='utf-8')
old='''                control.fill(value);self.save()
                selected=self.page.evaluate('(g)=>state.selected[g]',group)
'''
new='''                tag=control.evaluate('e=>e.tagName')
                if tag=='SELECT':control.select_option(value)
                elif control.get_attribute('type')=='checkbox':
                    (control.check() if value not in ('0','false','False') else control.uncheck())
                else:control.fill(value)
                self.save()
                selected=self.page.evaluate('(g)=>state.selected[g]',group)
'''
if old not in s:raise SystemExit('rendered broad-edit marker missing')
p.write_text(s.replace(old,new,1),encoding='utf-8')

# Component-only facade now needs the shared toggle-row contract because the
# Character page itself contains semantic flag controls.
p=ROOT/'tools/verify_ff7_ui_neutral.py';s=p.read_text(encoding='utf-8')
old='''const tabbedPanel=o=>{
  const active=(o.tabs||[]).find(tab=>tab.id===o.active);
  return el("section",{},
    subtabBar({tabs:o.tabs,active:o.active,label:o.label,change:o.change}),
    el("section",{role:"tabpanel","aria-label":active?.label||"Panel"},o.content));
};
Object.assign(window.LexeditorUI,{
'''
new='''const tabbedPanel=o=>{
  const active=(o.tabs||[]).find(tab=>tab.id===o.active);
  return el("section",{},
    subtabBar({tabs:o.tabs,active:o.active,label:o.label,change:o.change}),
    el("section",{role:"tabpanel","aria-label":active?.label||"Panel"},o.content));
};
const toggleRow=o=>el("div",{role:"group","aria-label":o.label||"Toggles"},...(o.toggles||[]).map(t=>
  el("label",{},el("input",{type:"checkbox",checked:!!t.checked,disabled:!!t.disabled,"aria-label":t.label,onchange:e=>t.change?.(e.target.checked,e)}),el("span",{},t.label))));
Object.assign(window.LexeditorUI,{
'''
if old not in s:raise SystemExit('neutral facade marker missing')
s=s.replace(old,new,1).replace('''  subtabBar,
  tabbedPanel,
});''','''  subtabBar,
  tabbedPanel,
  toggleRow,
});''',1)
p.write_text(s,encoding='utf-8')

# Real shared-UI acceptance across core KERNEL, characters, scene, encounters
# and shops. This is intentionally representative rather than screenshot-only.
p=ROOT/'tools/verify_ff7_rendered_neutral.py';s=p.read_text(encoding='utf-8')
marker='''target.RenderedTests.open = open_with_neutral
'''
test=r'''
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

    # Save representative semantic edits from different binary families.
    self.navigate("weapons")
    self.page.get_by_label("Materia AP growth for Record0", exact=True).select_option("2")
    self.save()
    status,data=self.backend.request('/api/data');self.assertEqual(status,200)
    self.assertEqual(data['records']['weapons'][0]['values']['growthRate'],2)

    self.navigate("enemyAttacks")
    critical=self.page.get_by_label("Always critical", exact=True)
    # The fixture stores the special mask as zero; logical flags are inverted,
    # so unchecking sets the stored inverse bit while the UI remains semantic.
    critical.uncheck()
    self.save()
    status,data=self.backend.request('/api/data');self.assertEqual(status,200)
    self.assertTrue(data['records']['enemyAttacks'][0]['values']['specialFlags'] & 0x2000)
    self.originals_unchanged()

'''
if marker not in s:raise SystemExit('neutral rendered assignment marker missing')
s=s.replace(marker,test+marker,1)
s=s.replace('''target.RenderedTests.test_materia_uses_human_semantic_controls = test_materia_uses_human_semantic_controls
''','''target.RenderedTests.test_materia_uses_human_semantic_controls = test_materia_uses_human_semantic_controls
target.RenderedTests.test_full_ff7_surface_uses_human_controls = test_full_ff7_surface_uses_human_controls
''',1)
p.write_text(s,encoding='utf-8')
print('semantic browser patch applied')
