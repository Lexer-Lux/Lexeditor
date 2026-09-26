"""Issue 567: the shared shell locks a game opened without a mod.

The host says the session is vanilla; the shell then disables Save, refuses
record edits, labels the mod menu Vanilla with the way out, and switches a
game that has its own Vanilla reference to it. A normal session is untouched.
"""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

MOUNT = '''(vanilla) => {
  window.pywebview={api:{vanilla_session:async()=>({pluginId:'fixture',vanilla}),
    mod_library_status:async()=>({canManage:true}),
    mod_projects:async()=>({canCreate:true,vanilla,projects:vanilla?[]:
      [{name:'My Mod',path:'C:/Mods/My Mod',valid:true,current:true}]})}};
  window.selected=[];let active='mine';
  document.body.insertAdjacentHTML('afterbegin','<div id="shell"></div>');
  document.querySelector('main').append(LexeditorUI.el('input',{id:'record',value:'10'}));
  LexeditorUI.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],
    activeTab:()=>'',navigate:()=>{},dirtyCount:()=>1,readonly:()=>false,save:async()=>{},
    projectSources:()=>[{key:'vanilla',label:'Vanilla',path:'Installed game'}],
    projectActiveSource:()=>active,
    selectProjectSource:async key=>{active=key;selected.push(key)}});
}'''


@pytest.fixture
def page():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 800})
        page.route('http://fixture/**', lambda r: r.fulfill(
            body='<main id="main"></main>', content_type='text/html'))
        page.goto('http://fixture/')
        page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
        page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
        yield page
        browser.close()


def test_vanilla_session_locks_the_shell(page):
    page.evaluate(MOUNT, True)
    page.wait_for_function("document.documentElement.dataset.lexVanilla==='true'")
    assert page.evaluate("document.documentElement.getAttribute('data-lex-project-readonly')") == 'true'
    assert page.locator('.lex-shell-header button.save, button.save').first.is_disabled()
    page.wait_for_function("selected.includes('vanilla')")
    page.wait_for_function("document.querySelector('.lex-project-name')?.textContent==='Vanilla'")
    assert 'Add a Mod' in page.locator('.lex-project-path').text_content()
    page.locator('#record').click()
    page.keyboard.type('5')
    assert page.locator('#record').input_value() == '10'
    page.get_by_role('button', name='Active mod project', exact=True).click()
    assert page.get_by_role('menuitem', name='➕ Add a Mod').is_visible()
    assert page.get_by_role('menuitem', name='🔍 Find a Mod').is_visible()


def test_normal_session_is_not_locked(page):
    page.evaluate(MOUNT, False)
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.dataset.lexVanilla") is None
    assert page.evaluate("document.documentElement.getAttribute('data-lex-project-readonly')") == 'false'
    assert page.evaluate('selected') == []
    page.locator('#record').click()
    page.keyboard.press('End')
    page.keyboard.type('5')
    assert page.locator('#record').input_value() == '105'
