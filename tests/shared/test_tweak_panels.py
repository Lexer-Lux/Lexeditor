"""Tweak panels: a mod with nothing to change has no panel.

The Mods tab renders a SETTINGS section whenever a tweak mod (or bundle)
yields panels, so an empty schema must yield none - otherwise the section
header sits over blank space.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401


def test_fields_only_skips_a_mod_with_an_empty_schema(page):
    framework(page)
    count = page.evaluate("""() => LexeditorUI.tweakModPanels({fieldsOnly: true,
      rows: [{id: 'plain', name: 'Plain', enabled: true,
        schema: {fields: []}, values: {}}]}).panels.length""")
    assert count == 0


def test_fields_only_keeps_errors_blockers_and_visible_fields(page):
    framework(page)
    count = page.evaluate("""() => LexeditorUI.tweakModPanels({fieldsOnly: true, rows: [
      {id: 'broken', name: 'Broken', enabled: true, error: 'Schema failed to load',
        schema: {fields: []}, values: {}},
      {id: 'blocked', name: 'Blocked', enabled: true, schema: {blocker: 'Needs the game'}, values: {}},
      {id: 'knobs', name: 'Knobs', enabled: false,
        schema: {fields: [{key: 'size', label: 'Size', type: 'number', min: 1, max: 9}]},
        values: {size: 3}}]}).panels.length""")
    assert count == 3


def test_tweaks_page_still_hides_switched_off_mods(page):
    framework(page)
    count = page.evaluate("""() => LexeditorUI.tweakModPanels({rows: [
      {id: 'off', name: 'Off', enabled: false,
        schema: {fields: [{key: 'size', label: 'Size', type: 'number', min: 1, max: 9}]},
        values: {size: 3}}]}).panels.length""")
    assert count == 0


def test_integer_tables_resize_independently_and_preserve_edited_entries(page):
    framework(page)
    page.evaluate("""() => {
      window.costRow = {id:'tables', name:'Tables', enabled:true,
        schema:{fields:['regular','ashen'].map(key => ({key,label:key,type:'intList',
          min:1,max:7,minLength:0,maxLength:99,entryDefault:1,countLabel:'Levels',indexPrefix:'+'}))},
        values:{regular:[1,2],ashen:[3]}};
      document.querySelector('main').append(...LexeditorUI.tweakModPanels({
        rows:[costRow],change:() => {window.lastCosts=structuredClone(costRow.values);}}).panels);
    }""")
    page.get_by_label('regular +2', exact=True).fill('5')
    page.get_by_label('regular +2', exact=True).dispatch_event('change')
    page.get_by_label('regular Levels', exact=True).fill('3')
    page.get_by_label('regular Levels', exact=True).dispatch_event('change')
    assert page.get_by_label('regular +3', exact=True).input_value() == '1'
    assert page.evaluate('lastCosts') == {'regular': [1, 5, 1], 'ashen': [3]}
    page.get_by_label('regular Levels', exact=True).fill('0')
    page.get_by_label('regular Levels', exact=True).dispatch_event('change')
    assert page.get_by_label('regular +1', exact=True).count() == 0
    assert page.evaluate('lastCosts') == {'regular': [], 'ashen': [3]}
