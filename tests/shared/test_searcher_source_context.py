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
