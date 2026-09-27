"""The picker occupies the tab row; its source view cannot be edited."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page
from test_tab_rename import mount_shell


def test_searcher_keeps_menu_visible_and_source_locked(page):
    framework(page)
    mount_shell(page, developer=False)
    page.evaluate('''() => {
      LexeditorUI.beginSearcher({type:'items',prompt:'select Item for a recipe',
        origin:()=>document.querySelector('main').replaceChildren(LexeditorUI.el('input',{'aria-label':'Source value',value:12})),
        target:()=>document.querySelector('main').replaceChildren(LexeditorUI.el('p',{},'Candidates'))});
    }''')
    bar = page.locator('.lex-searcher-bar')
    command = page.locator('.lex-shell-command-row')
    assert bar.bounding_box()['y'] >= command.bounding_box()['y'] + command.bounding_box()['height']
    assert command.is_visible()
    page.locator('.lex-searcher-context').click()
    assert page.locator('main').evaluate('e=>e.inert')
    assert 'blue return button' in bar.inner_text()
    assert page.locator('.lex-searcher-context').evaluate('e=>getComputedStyle(e).animationName') == 'lex-searcher-return-pulse'
    if os.environ.get('LEXEDITOR_TEST_SHOTS'):
        page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS']) / 'searcher-source.png'))
    page.locator('.lex-searcher-context').click()
    assert not page.locator('main').evaluate('e=>e.inert')
    assert page.locator('main').inner_text() == 'Candidates'
    page.locator('.lex-searcher-context').click()
    page.get_by_role('button', name='Cancel selection', exact=True).click()
    assert not page.locator('main').evaluate('e=>e.inert')
    assert page.get_by_role('textbox', name='Source value').is_editable()
    assert page.locator('.lex-nav-frame').is_visible()


def test_searcher_locks_candidate_edits_through_rerender_and_restores_them(page):
    framework(page)
    mount_shell(page, developer=False)
    page.evaluate('''()=>{
      const U=LexeditorUI;window.accepted=[];
      window.showCandidates=()=>{
        const field=U.detailField({label:'Price',control:U.el('input',{type:'number',value:12})});
        const existing=U.detailField({label:'Already locked',control:U.el('input',{value:'fixed'})});existing.inert=true;
        const candidate=U.decorateSearchCandidate(U.el('button',{},'Candidate'),{type:'items',value:7});
        document.querySelector('main').replaceChildren(U.el('input',{type:'search','aria-label':'Filter'}),candidate,
          U.el('div',{class:'lex-pager'},U.el('button',{class:'lex-table-add'},'Add')),
          U.detailPanel({title:'Item',actions:[U.el('button',{},'Delete')],body:[field,existing]}));
      };
      U.beginSearcher({type:'items',holdMs:150,target:showCandidates,
        origin:()=>{},accept:value=>accepted.push(value)});
    }''')
    page.get_by_role('searchbox',name='Filter').fill('item')
    assert page.locator('.lex-detail-field').evaluate_all('nodes=>nodes.every(n=>n.inert)')
    assert page.locator('.lex-detail-panel-actions').evaluate('n=>n.inert')
    assert page.locator('.lex-table-add').evaluate('n=>n.inert')
    page.evaluate("window.editShortcutCalls=0;document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='z')editShortcutCalls++})")
    page.keyboard.press('Control+z')
    assert page.evaluate('editShortcutCalls')==0
    page.evaluate('showCandidates()')
    page.wait_for_function("[...document.querySelectorAll('.lex-detail-field')].every(n=>n.inert)")
    candidate=page.get_by_role('button',name='Candidate',exact=True)
    candidate.hover()
    page.mouse.down()
    page.wait_for_function('accepted.length===1')
    page.mouse.up()
    assert page.evaluate('accepted')==[7]
    assert page.locator('.lex-detail-field').evaluate_all('nodes=>nodes.map(n=>n.inert)')==[False,True]
    assert not page.locator('.lex-detail-panel-actions').evaluate('n=>n.inert')


def test_a_short_click_shows_a_candidate_and_a_hold_picks_it(page):
    """Lexer: in the finder he could hold a group to pick it, but a click did
    nothing, so he could not look inside a group before choosing it."""
    framework(page)
    mount_shell(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;window.accepted=[];window.shown=[];
      window.showCandidates=()=>{
        const candidate=U.decorateSearchCandidate(U.el('button',{onclick:()=>shown.push(7)},'Candidate'),{type:'groups',value:7});
        document.querySelector('main').replaceChildren(candidate);
      };
      U.beginSearcher({type:'groups',holdMs:200,target:showCandidates,origin:()=>{},accept:v=>accepted.push(v)});
    }''')
    candidate = page.get_by_role('button', name='Candidate', exact=True)
    candidate.click()
    assert page.evaluate('shown') == [7]
    assert page.evaluate('accepted') == []
    assert page.locator('.lex-searcher-bar').count() == 1
    candidate.hover()
    page.mouse.down()
    page.wait_for_function('accepted.length===1')
    page.mouse.up()
    assert page.evaluate('accepted') == [7]
    assert page.evaluate('shown') == [7]
