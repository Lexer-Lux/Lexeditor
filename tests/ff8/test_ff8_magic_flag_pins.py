"""Magic's individual flag pins must add working columns to its master list."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import page, framework, ROOT


def test_magic_flag_pin_and_composite_types(page):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    page.evaluate("document.body.prepend(Object.assign(document.createElement('div'),{id:'toolbar'}))")
    for name in ['core.js', 'records.js', 'party.js']:
        page.add_script_tag(path=str(ROOT / 'plugins/ff8' / name))
    page.add_script_tag(content='''
      const shell={refresh(){}};
      function render(){renderKernel('magic','Magic')}
      const row={id:1,name:'Test spell',fields:[
        {field:'attack_power',label:'Power',group:'General',control:'number',min:0,max:255,value:12},
        {field:'target_info',label:'Targets',group:'General',value:1,
         lookup:{type:'flags',name:'target',entries:[{value:1,name:'Enemies'},{value:2,name:'All targets'}]}}
      ]};
      state.data={settings:{},magic:{rows:[row]}};
      state.vanilla=structuredClone(state.data);
      state.references=[];
      render();
    ''')
    assert page.locator('.magic-detail .lex-detail-section-heading').count() == 0
    assert page.locator('.magic-detail .lex-detail-field-label').filter(has_text='ATTACK DATA').count() == 0
    group=page.locator('.lex-detail-field').filter(has=page.locator('.lex-toggle-row'))
    assert group.get_attribute('data-lex-type') == ''
    toggle=page.locator('[data-lex-toggle="1"]')
    toggle.hover()
    toggle.get_by_role('button', name='Pin Enemies column', exact=True).click()
    page.wait_for_function("state.columnPrefs.magic.isPinned('flag:target_info:1')")
    assert page.evaluate("state.columnPrefs.magic.active().find(c=>c.key==='flag:target_info:1').sortValue(row)") is True
    cell=page.locator('.lex-column-list-cell[data-column-key="flag:target_info:1"]')
    before=cell.inner_text()
    page.get_by_role('checkbox',name='Enemies',exact=True).uncheck()
    page.wait_for_timeout(100)
    assert page.evaluate("row.fields[1].value") == 0
    assert page.evaluate("state.columnPrefs.magic.active().find(c=>c.key==='flag:target_info:1').sortValue(row)") is False
    assert cell.inner_text() != before
    page.get_by_role('tab',name='Junction',exact=False).click()
    assert page.locator('.magic-detail .lex-detail-section-heading').count() == 0
    if os.environ.get('LEX_MAGIC_SCREENSHOT'):
        page.get_by_role('tab',name='Attack data',exact=False).click()
        page.locator('[data-lex-toggle="1"]').hover()
        page.screenshot(path=os.environ['LEX_MAGIC_SCREENSHOT'])
