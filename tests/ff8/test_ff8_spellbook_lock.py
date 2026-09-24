import json
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import ROOT, page, framework


@pytest.mark.parametrize('enabled,active,pending',[(False,False,None),(True,False,None),(True,True,None),(False,False,True),(True,True,False)])
def test_spellbook_lock_keeps_help_usable(page,enabled,active,pending):
    page.route('**/api/kernel?*',lambda route:route.fulfill(content_type='application/json',body=json.dumps({
        'rows':[{'id':0,'spellbook':None}],
        'spellbook':{'enabled':enabled,'runtimeActive':active,'magicOptions':[],'abilityOptions':[]}})))
    framework(page)
    if pending is not None:
        page.add_script_tag(content='const state='+json.dumps({'data':{'settings':{
            'gfSpellbooksEnabled':pending,'singleGf':True,'sharedMagicInventory':False}}})+';')
    page.evaluate('''()=>{
      const U=LexeditorUI,host=U.el('div',{id:'gf-detail','data-gf':'0'});
      host.append(U.detailSection({title:'Abilities',attrs:{'data-gf-panel':'abilities'},body:U.el('div',{},'Ability list')}));
      host.lexReplacePanel=(old,next)=>old.replaceWith(next);document.querySelector('main').append(host);
    }''')
    page.add_script_tag(path=str(ROOT/'plugins/ff8/cards_ui.js'))
    tab=page.get_by_role('tab',name='SPELLBOOK')
    tab.wait_for()
    page.wait_for_timeout(150)
    ready=(enabled and active) if pending is None else pending
    assert tab.get_attribute('aria-disabled')==str(not ready).lower()
    # DOM click also checks the callback guard used by keyboard activation.
    tab.evaluate('n=>n.click()')
    assert tab.get_attribute('aria-selected')==str(ready).lower()
    tab.locator('.lex-info-help').hover()
    tooltip=page.get_by_role('tooltip')
    tooltip.wait_for()
    assert 'Tweaks → Gameplay' in tooltip.inner_text()
    assert 'GF Spellbooks' in tooltip.inner_text()
