"""A detail heading has no copy button: its glyph read as a second
duplicate button next to the real one. Name, help and finder only."""
from test_shared_ui_feedback import page, framework


def test_heading_name_has_no_copy_button(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      document.querySelector('main').append(U.detailPanel({
        title: 'Plain Record', identity: '12', meta: 'plain subtitle', help: 'Help text.'}));
      document.querySelector('main').append(U.detailPanel({
        title: 'Record Name', renameRecord: () => {}, meta: 'subtitle line'}));
    }''')
    panels = page.locator('.lex-detail-panel')
    for index in range(2):
        title = panels.nth(index).locator('.lex-detail-panel-title')
        assert title.locator(':scope > .lex-copy-value').count() == 0
        title.hover()
    assert panels.nth(0).locator('.lex-detail-panel-name').inner_text().strip() == 'Plain Record'
    assert panels.nth(0).locator('.lex-info-help').count() == 1


def test_heading_order_is_name_help_then_finder(page):
    """Lexer: title text, info bubble, then the thing finder (no copy button)."""
    framework(page)
    page.evaluate('''()=>{window.found=0;document.querySelector('main').replaceChildren(
      LexeditorUI.detailPanel({title:'Encounter group',help:'Help text',identity:'#12',
        find:()=>window.found++,findTitle:'Choose another group',body:[]}))}''')
    order = page.evaluate('''()=>{const t=document.querySelector('.lex-detail-panel-title');
      const x=s=>t.querySelector(s).getBoundingClientRect().left;
      return [x('.lex-detail-panel-name'),x('.lex-info-help'),x('.lex-title-finder')]}''')
    assert order == sorted(order), order
    assert page.locator('.lex-detail-panel-title .lex-copy-value').count() == 0
    page.get_by_role('button', name='Choose another group').click()
    assert page.evaluate('window.found') == 1
