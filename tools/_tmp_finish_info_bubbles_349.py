from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Some controller fixtures intentionally exercise field controls with a minimal
# dataset object. Semantic help must degrade to no help rather than assuming the
# complete production catalog object is present.
ff9 = ROOT / 'games/ff9/editor.html'
ff9_text = ff9.read_text('utf-8')
old_semantic = '''  function semanticFieldHelp(data,field){
    if(data.key.startsWith("ability-")&&field.key==="AP")return "AP this character must earn from eligible equipment to permanently learn the linked ability.";
    if(data.key==="item-stats"&&["Dexterity","Strength","Magic","Will"].includes(field.key))return `When a character levels while equipment using this bonus row is equipped, FF9 adds this ${field.key} bonus into the character's accumulated stat-growth bonus.`;
    if(data.key==="item-stats"&&field.key==="AttackElement")return "Element added to physical attacks by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="GuardElement")return "Elements guarded against by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="AbsorbElement")return "Elements converted from damage into healing by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="HalfElement")return "Elements whose incoming damage is halved by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="WeakElement")return "Elements to which equipment using this bonus row makes the wearer weak.";
    if(data.key==="command-sets"&&field.key!=="Id")return field.key.includes("Trance")?"Command ID placed in this battle-menu slot while the character is in Trance.":"Command ID placed in this battle-menu slot in the character's normal state.";
    return FIELD_HELP[`${data.key}:${field.key}`]||"";
  }
'''
new_semantic = '''  function semanticFieldHelp(data,field){
    const dataKey=String(data?.key||"");
    if(dataKey.startsWith("ability-")&&field.key==="AP")return "AP this character must earn from eligible equipment to permanently learn the linked ability.";
    if(dataKey==="item-stats"&&["Dexterity","Strength","Magic","Will"].includes(field.key))return `When a character levels while equipment using this bonus row is equipped, FF9 adds this ${field.key} bonus into the character's accumulated stat-growth bonus.`;
    if(dataKey==="item-stats"&&field.key==="AttackElement")return "Element added to physical attacks by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="GuardElement")return "Elements guarded against by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="AbsorbElement")return "Elements converted from damage into healing by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="HalfElement")return "Elements whose incoming damage is halved by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="WeakElement")return "Elements to which equipment using this bonus row makes the wearer weak.";
    if(dataKey==="command-sets"&&field.key!=="Id")return field.key.includes("Trance")?"Command ID placed in this battle-menu slot while the character is in Trance.":"Command ID placed in this battle-menu slot in the character's normal state.";
    return FIELD_HELP[`${dataKey}:${field.key}`]||"";
  }
'''
if old_semantic not in ff9_text:
    raise SystemExit('FF9 semantic helper anchor missing')
ff9.write_text(ff9_text.replace(old_semantic, new_semantic, 1), 'utf-8')

test = ROOT / 'tests/global_controls_check.py'
text = test.read_text('utf-8')
old = """        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el;window.__value=15;
          const input=e('input',{id:'quantity',type:'number',value:15,min:0,max:100,step:1,oninput:event=>__value=Number(event.target.value)});
          document.querySelector('#main').replaceChildren(U.detailField({label:'Quantity',dataType:'INT',min:0,max:100,control:U.unitField(input,'%')}));
        }''')
        number = page.locator('#quantity')
"""
new = """        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el;window.__value=15;
          const input=e('input',{id:'quantity',type:'number',value:15,min:0,max:100,step:1,oninput:event=>__value=Number(event.target.value)});
          document.querySelector('#main').replaceChildren(U.detailField({label:'Quantity',dataType:'INT',min:0,max:100,control:U.unitField(input,'%')}));
        }''')
        # Type/range metadata stays visible in the rail, but metadata alone must
        # never manufacture a circular semantic-help bubble.
        assert page.locator('.lex-field-type-name').inner_text() == 'INT'
        assert '0-100' in page.locator('.lex-field-type-range').inner_text().replace(' ', '')
        assert page.locator('.lex-info-help').count() == 0
        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el,input=e('input',{id:'semantic-quantity',type:'number',value:15,min:0,max:100,step:1});
          document.querySelector('#main').append(U.detailField({label:'Semantic quantity',dataType:'INT',min:0,max:100,
            help:U.infoHelp('Controls how many copies the game grants when this reward is awarded.'),control:U.unitField(input,'%')}));
        }''')
        semantic_help=page.locator('.lex-info-help').last
        assert semantic_help.get_attribute('aria-label') == 'Controls how many copies the game grants when this reward is awarded.'
        semantic_help.hover();page.locator('.lex-help-popover').wait_for()
        bubble=page.locator('.lex-help-popover').inner_text()
        assert bubble == 'Controls how many copies the game grants when this reward is awarded.'
        assert not any(word in bubble for word in ('Range:', 'Step:', 'Unit:', 'Set Semantic', 'Edit Semantic'))
        number = page.locator('#quantity')
"""
if old not in text:
    raise SystemExit('global_controls detailField test anchor missing')
text = text.replace(old, new, 1)
old_result = "'settings_save_discard_isolation_and_visible_failure':'pass','automatic_control_tooltips':'pass','history_cancellation_and_failure':'pass',"
new_result = "'settings_save_discard_isolation_and_visible_failure':'pass','native_control_tooltips':'pass','semantic_info_bubbles':'pass','history_cancellation_and_failure':'pass',"
if old_result not in text:
    raise SystemExit('global_controls result anchor missing')
text = text.replace(old_result, new_result, 1)
test.write_text(text, 'utf-8')

static = ROOT / 'tests/test_info_bubble_semantics.py'
static.write_text('''\"\"\"Info bubbles explain semantics; visible property metadata stays out of them.\"\"\"\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\ndef text(path):\n    return (ROOT / path).read_text(\"utf-8\")\n\ndef test_detail_field_never_fabricates_info_bubbles_from_metadata():\n    framework = text(\"ui/framework.js\")\n    assert 'options.help || infoHelp(helpText)' not in framework\n    assert 'const helpMarker = options.help || (suppliedHelp ? infoHelp(suppliedHelp) : null);' in framework\n    semantic_block = framework[framework.index('const suppliedHelp = options.help instanceof Element'):framework.index('const typeRail = element(\"div\", {class: \"lex-field-type-rail\"}')]\n    for forbidden in ('Allowed range:', 'Minimum:', 'Maximum:', 'Whole numbers only.', 'Step:', 'Unit:', 'Edit the stored', 'Enable or disable', 'Choose ${labelText}'):\n        assert forbidden not in semantic_block\n\ndef test_manual_defines_semantic_only_contract():\n    manual = text(\"docs/UI-MANUAL.md\")\n    assert \"Info-bubble text explains **meaning and consequences**\" in manual\n    assert \"Never put the property's data type, numeric range, step size, displayed unit\" in manual\n    assert \"If no useful semantic explanation is known, omit the info\" in manual\n\ndef test_known_metadata_filler_is_gone_from_plugins():\n    sources = \"\\n\".join(text(path) for path in (\n        \"games/blank/editor.html\", \"games/ff7/editor.html\", \"games/ff8/editor.html\",\n        \"games/ff9/editor.html\", \"games/rdr/editor.html\", \"games/rdr2/editor.html\",\n    ))\n    for forbidden in (\n        \"Storage range:\", \"Editor range:\", \"This Memoria array is edited as a comma-separated list.\",\n        \"Stored parameter 1.\", \"Stored parameter 2.\", \"These are the exact stored Renzokuken table values.\",\n        \"A bounded whole-number property. Focus it to reveal its type and valid range.\",\n    ):\n        assert forbidden not in sources\n\ndef test_ff9_has_real_semantic_help_for_core_relationships():\n    ff9 = text(\"games/ff9/editor.html\")\n    for key in (\n        '\"characters:Strength\"', '\"characters:Magic\"', '\"leveling:BonusHP\"',\n        '\"leveling:BonusMP\"', '\"items:AbilityIds\"', '\"items:BonusId\"',\n        '\"shops:Items\"', '\"abilities:Gems\"', '\"actions:scriptId\"',\n        '\"status-data:ContiCount(duration)\"',\n    ):\n        assert key in ff9\n    assert 'return FIELD_HELP[`${dataKey}:${field.key}`]||\"\";' in ff9\n\ndef test_rdr2_setting_help_does_not_append_visible_metadata():\n    rdr2 = text(\"games/rdr2/editor.html\")\n    block = rdr2[rdr2.index(\"function settingHelp(section,setting)\"):rdr2.index(\"function settingUnit(section,key)\")]\n    assert \"Editor range:\" not in block\n    assert \"Unit:\" not in block\n    assert \"has no field-specific behavior description\" not in block\n''', 'utf-8')
