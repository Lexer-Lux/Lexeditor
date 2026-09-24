"""Prebuilt help controls must not become the contents of another popup."""
from test_shared_ui_feedback import page, framework


def test_panel_reuses_help_button(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(U.detailPanel({title:'Direct Mode Path',
        help:U.infoHelp('Folder that contains the loose replacement game files.'),body:[]}));
    }''')
    assert page.locator('.lex-info-help').count()==1
    page.locator('.lex-info-help').hover()
    assert page.get_by_role('tooltip').inner_text()=='Folder that contains the loose replacement game files.'
    assert page.get_by_role('tooltip').locator('.lex-info-help').count()==0
