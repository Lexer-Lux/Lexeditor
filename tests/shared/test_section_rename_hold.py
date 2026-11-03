"""A renamed section heading survives a panel rebuild.

Lexer renamed his Effects & references section to Navigation and it kept
coming back. A rename stores a per-tab override; rebuilding the panel (as
a ROWS change does) must show the override, not the shipped title.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401
from test_tab_rename import mount_shell


def test_section_rename_survives_rebuild(page):
    framework(page)
    mount_shell(page, True)
    page.evaluate('''() => {
      const U = LexeditorUI;
      window.draw = () => document.querySelector('main').replaceChildren(
        U.detailPanel({title: 'Record', paginate: {unpaged: true}, body: [
          U.detailSection({title: 'Combat', body: [
            U.detailField({label: 'Weight', property: 'weight',
              control: U.el('input', {value: '0'})})]}),
          U.detailSection({title: 'Effects & references', body: [
            U.detailField({label: 'Help', property: 'help',
              control: U.el('input', {value: 'walk'})})]}),
        ]}));
      draw();
    }''')
    page.locator('[data-lex-layout-section="Effects & references"] '
                 '.lex-detail-section-title-text').dblclick()
    box = page.locator('.lex-label-rename')
    box.fill('Navigation')
    box.press('Enter')
    page.wait_for_timeout(200)
    assert page.locator('[data-lex-layout-section="Effects & references"] '
                        '.lex-detail-section-title-text').inner_text() == 'Navigation'
    page.evaluate('draw()')
    page.wait_for_timeout(200)
    assert page.locator('[data-lex-layout-section="Effects & references"] '
                        '.lex-detail-section-title-text').inner_text() == 'Navigation'
