from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path, old, new, label):
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{label} anchor changed")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Keep info bubbles semantic: merged master deliberately removed generic
# storage/type filler, so the FF7 semantic pass must not reintroduce it.
for path, filler in (
    ("games/ff7/semantics.py", '        value.setdefault("help", "Numeric game value. Lexeditor writes the original FF7 field directly and preserves unrelated bytes.")\n'),
    ("games/ff7/kernel.py", '            metadata.setdefault("help", "Numeric game value. Lexeditor writes the original FF7 field directly and preserves unrelated bytes.")\n'),
):
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if filler in text:
        target.write_text(text.replace(filler, "", 1), encoding="utf-8")

editor_path = ROOT / "games/ff7/editor.html"
editor = editor_path.read_text(encoding="utf-8")
style_anchor = '  <link rel="stylesheet" href="/shared/neutral.css">\n'
style = '''  <style>\n    .lex-semantic-reference-control{display:grid;grid-template-columns:2rem minmax(8rem,.8fr) minmax(11rem,1.2fr);align-items:center;gap:6px;width:100%;min-width:0}\n    .lex-semantic-reference-control:not(.searchable){grid-template-columns:2rem minmax(0,1fr)}\n    .lex-semantic-reference-control input,.lex-semantic-reference-control select{width:100%;min-width:0}\n    .lex-semantic-reference-open{display:grid;width:2rem;height:2rem;min-width:2rem;padding:0;place-items:center;font:inherit;line-height:1}\n    @media(max-width:860px){.lex-semantic-reference-control.searchable{grid-template-columns:2rem minmax(0,1fr)}.lex-semantic-reference-control.searchable .lex-semantic-reference-search{grid-column:1/-1;grid-row:1}.lex-semantic-reference-control.searchable .lex-semantic-reference-open{grid-row:2}.lex-semantic-reference-control.searchable select{grid-row:2}}\n  </style>\n'''
if 'lex-semantic-reference-control' not in editor:
    if style_anchor not in editor:
        raise SystemExit('FF7 editor stylesheet anchor changed')
    editor = editor.replace(style_anchor, style_anchor + style, 1)

start = editor.index('  function selectControl(row,field,choiceFactory){')
end = editor.index('  function booleanControl(row,field){', start)
replacement = '''  function referenceSearchText(choice){\n    const value=Number(choice.value),hex=Number.isInteger(value)?`0x${value.toString(16).toUpperCase()}`:"";\n    return `${choice.label||""} ${choice.value} #${choice.value} ${hex}`.toLocaleLowerCase();\n  }\n  function selectControl(row,field,choiceFactory){\n    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);\n    const current=Number(row.values[field.key]);\n    const choices=choiceFactory();\n    if(field.emptyValue!==undefined&&!choices.some(c=>Number(c.value)===Number(field.emptyValue)))choices.unshift({value:Number(field.emptyValue),label:"None"});\n    for(const value of [current,vanilla])if(!choices.some(c=>Number(c.value)===value))choices.push({value,label:semanticChoiceSummary(choices,value,field.emptyValue)});\n    const select=el("select",{disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,onchange:event=>{\n      if(readonly())return;row.values[field.key]=Number(event.target.value);field.rerenderOnChange?render():shellRefresh();\n    }});\n    const selectedChoice=()=>choices.find(choice=>Number(choice.value)===Number(row.values[field.key]));\n    const openButton=el("button",{type:"button",class:"lex-semantic-reference-open",title:`Open selected ${field.label.toLowerCase()}`,"aria-label":`Open ${field.label} for ${row.name}`,disabled:true,onclick:event=>{\n      event.preventDefault();event.stopPropagation();const choice=selectedChoice();if(!choice?.category||choice.recordId===undefined)return;state.selected[choice.category]=Number(choice.recordId);navigate(choice.category);\n    }},"↗");\n    const rebuild=(query="")=>{\n      const needle=String(query).trim().toLocaleLowerCase(),selected=Number(row.values[field.key]);\n      let visible=needle?choices.filter(choice=>referenceSearchText(choice).includes(needle)):choices.slice();\n      const currentChoice=choices.find(choice=>Number(choice.value)===selected);\n      if(currentChoice&&!visible.some(choice=>Number(choice.value)===selected))visible.unshift(currentChoice);\n      select.replaceChildren(...visible.map(choice=>el("option",{value:choice.value},choice.label)));\n      select.value=String(selected);\n      const choice=selectedChoice();openButton.disabled=!(choice?.category&&choice.recordId!==undefined);\n    };\n    const searchable=choices.length>=12;\n    const search=searchable?el("input",{type:"search",class:"lex-semantic-reference-search",placeholder:`Search ${field.label.toLowerCase()}…`,disabled:readonly(),"aria-label":`Search ${field.label} for ${row.name}`,oninput:event=>rebuild(event.target.value)}):null;\n    rebuild();\n    const root=el("div",{class:`lex-semantic-reference-control${searchable?" searchable":""}`},...(search?[openButton,search,select]:[openButton,select]));\n    return provenanceControl({control:root,current:()=>row.values[field.key],vanilla,internal:true,format:value=>semanticChoiceSummary(choices,value,field.emptyValue),apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});\n  }\n  function referenceControl(row,field){return selectControl(row,field,()=>referenceChoices(field,row))}\n  function inventoryReferenceControl(row,field){return selectControl(row,field,()=>inventoryChoices(true))}\n  function shopReferenceControl(row,field){return selectControl(row,field,()=>Number(row.values[field.kindField])===1?(state.records.materia||[]).map(record=>({value:Number(record.id),label:candidateLabel(record),category:"materia",recordId:Number(record.id)})):inventoryChoices(false))}\n'''
editor = editor[:start] + replacement + editor[end:]
old_reference = 'function referenceChoices(field,row){return referenceRows(field,row).map(candidate=>({value:candidateValue(field,candidate),label:candidateLabel(candidate)}))}'
new_reference = 'function referenceChoices(field,row){return referenceRows(field,row).map(candidate=>({value:candidateValue(field,candidate),label:candidateLabel(candidate),category:field.referenceCategory,recordId:Number(candidate.id)}))}'
if old_reference not in editor:
    raise SystemExit('FF7 reference choices anchor changed')
editor = editor.replace(old_reference, new_reference, 1)
old_inventory = 'return specs.flatMap(([category,offset])=>(state.records[category]||[]).map(record=>({value:offset+Number(record.id),label:`${candidateLabel(record)} — ${labels[category]||category}`})));'
new_inventory = 'return specs.flatMap(([category,offset])=>(state.records[category]||[]).map(record=>({value:offset+Number(record.id),label:`${candidateLabel(record)} — ${labels[category]||category}`,category,recordId:Number(record.id)})));'
if old_inventory not in editor:
    raise SystemExit('FF7 inventory choices anchor changed')
editor = editor.replace(old_inventory, new_inventory, 1)
old_help = '''  function semanticHelp(field){\n    if(field.help)return field.help;\n    if(field.dataType==="text")return "English game text. Use byte escapes for control codes; unsupported characters and oversized text are refused on save.";\n    return "Numeric game value. Lexeditor writes the documented FF7 value directly and preserves unrelated bytes.";\n  }'''
new_help = '''  function semanticHelp(field){\n    if(field.help)return field.help;\n    if(field.dataType==="text")return "This is game-visible text. Byte escapes preserve FF7 control codes; unsupported characters or text that cannot fit are refused on save rather than corrupting the kernel.";\n    return "";\n  }'''
if old_help not in editor:
    raise SystemExit('FF7 semantic help anchor changed')
editor = editor.replace(old_help, new_help, 1)
old_fields = 'body.push(...groups.map(group=>detailSection({title:group.toUpperCase(),body:metadata.fields.filter(field=>(field.group||"Kernel data")===group).map(field=>detailField({className:"ff7-field",label:field.label,help:infoHelp(semanticHelp(field)),control:semanticControl(row,field),dataType:semanticType(field),min:field.minimum,max:field.maximum}))})));'
new_fields = 'body.push(...groups.map(group=>detailSection({title:group.toUpperCase(),body:metadata.fields.filter(field=>(field.group||"Kernel data")===group).map(field=>{const help=semanticHelp(field);return detailField({className:"ff7-field",label:field.label,help:help?infoHelp(help):null,control:semanticControl(row,field),dataType:semanticType(field),min:field.minimum,max:field.maximum})})})));'
if old_fields not in editor:
    raise SystemExit('FF7 semantic field help anchor changed')
editor = editor.replace(old_fields, new_fields, 1)
editor_path.write_text(editor, encoding="utf-8")

rendered_path = ROOT / "tools/verify_ff7_rendered_neutral.py"
rendered = rendered_path.read_text(encoding="utf-8")
needle = '''    self.assertEqual(weapon.evaluate("e=>e.tagName"),"SELECT")\n    self.assertIn("Record0", weapon.locator("option").all_inner_texts())\n    self.assertIn("Front row", row.locator("option").all_inner_texts())\n'''
insert = '''    self.assertEqual(weapon.evaluate("e=>e.tagName"),"SELECT")\n    self.assertIn("Record0", weapon.locator("option").all_inner_texts())\n    weapon_search=self.page.get_by_label("Search Starting weapon for Slot0", exact=True)\n    self.assertEqual(weapon_search.get_attribute("type"),"search")\n    before=weapon.locator("option").count()\n    weapon_search.fill("Record1")\n    self.assertLess(weapon.locator("option").count(),before)\n    self.assertTrue(any("Record1" in option for option in weapon.locator("option").all_inner_texts()))\n    weapon.select_option("1")\n    self.page.get_by_label("Open Starting weapon for Slot0", exact=True).click()\n    self.assertEqual(self.page.evaluate("state.tab"),"weapons")\n    self.assertEqual(self.page.evaluate("state.selected.weapons"),1)\n    self.navigate("characters")\n    weapon=self.page.get_by_label("Starting weapon for Slot0", exact=True)\n    row=self.page.get_by_label("Starting row for Slot0", exact=True)\n    limits=self.page.get_by_role("group", name="Limits already learned for Slot0", exact=True)\n    self.assertIn("Front row", row.locator("option").all_inner_texts())\n'''
if needle not in rendered:
    raise SystemExit('Rendered semantic character assertion anchor changed')
rendered = rendered.replace(needle, insert, 1)
shop_needle = '''    self.assertEqual(shop_type.evaluate("e=>e.tagName"),"SELECT")\n    self.assertEqual(product.evaluate("e=>e.tagName"),"SELECT")\n    self.assertTrue(any("Record" in value for value in product.locator("option").all_inner_texts()))\n'''
shop_insert = shop_needle + '''    product_search=self.page.get_by_label("Search Slot 1 product for Shop 0", exact=True)\n    product_search.fill("Record1")\n    self.assertTrue(any("Record1" in value for value in product.locator("option").all_inner_texts()))\n'''
if shop_needle not in rendered:
    raise SystemExit('Rendered semantic shop assertion anchor changed')
rendered_path.write_text(rendered.replace(shop_needle, shop_insert, 1), encoding="utf-8")

semantic_test_path = ROOT / "tools/verify_ff7_semantic_surface.py"
semantic_test = semantic_test_path.read_text(encoding="utf-8")
anchor = '    def test_scene_records_expose_reference_identity_without_changing_bytes(self):\n'
extra = '''    def test_help_is_semantic_not_generic_storage_filler(self):\n        collections=[*(semantics.apply(key,spec["fields"]) for key,spec in battle.SCENE_CATEGORIES.items()),semantics.apply("shops",extended.SHOP_FIELDS)]\n        for fields in collections:\n            for field in fields:\n                self.assertNotIn("Numeric game value",str(field.get("help", "")),field)\n        editor=(Path(__file__).resolve().parents[1]/"games/ff7/editor.html").read_text(encoding="utf-8")\n        self.assertIn('return "";',editor)\n        self.assertNotIn("help:infoHelp(semanticHelp(field))",editor)\n\n'''
if 'test_help_is_semantic_not_generic_storage_filler' not in semantic_test:
    if anchor not in semantic_test:
        raise SystemExit('Semantic verifier insertion anchor changed')
    semantic_test = semantic_test.replace(anchor, extra + anchor, 1)
semantic_test_path.write_text(semantic_test, encoding="utf-8")

workflow_path = ROOT / ".github/workflows/ff7-data-regressions.yml"
workflow = workflow_path.read_text(encoding="utf-8")
ci_needle = '          python tools/verify_ff7_accessories.py\n'
if 'python tools/verify_ff7_semantic_surface.py' not in workflow:
    if ci_needle not in workflow:
        raise SystemExit('FF7 workflow verifier anchor changed')
    workflow = workflow.replace(ci_needle, ci_needle + '          python tools/verify_ff7_semantic_surface.py\n', 1)
workflow_path.write_text(workflow, encoding="utf-8")
