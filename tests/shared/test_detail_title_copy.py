"""A detail heading's name copies from a button on its right, shown on hover."""
from test_shared_ui_feedback import page, framework


def test_heading_name_has_copy_button(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      window.__copied = [];
      Object.defineProperty(navigator, 'clipboard', {configurable: true,
        value: {writeText: async text => { window.__copied.push(text); }}});
      document.querySelector('main').append(U.detailPanel({
        title: 'Plain Record', identity: '12', meta: 'plain subtitle', help: 'Help text.'}));
      document.querySelector('main').append(U.detailPanel({
        title: 'Record Name', renameRecord: () => {}, meta: 'subtitle line'}));
    }''')
    panels = page.locator('.lex-detail-panel')
    for index, expected in enumerate(['Plain Record', 'Record Name']):
        panel = panels.nth(index)
        title = panel.locator('.lex-detail-panel-title')
        button = title.locator(':scope > .lex-copy-value')
        assert button.count() == 1
        assert float(button.evaluate('b => getComputedStyle(b).opacity')) == 0
        title.hover()
        page.wait_for_function('b => getComputedStyle(b).opacity > 0.5', arg=button.element_handle())
        geometry = page.evaluate('''([title, button]) => {
          const name = title.querySelector('.lex-detail-panel-name, input');
          const n = name.getBoundingClientRect(), b = button.getBoundingClientRect();
          const help = title.querySelector('.lex-info-help')?.getBoundingClientRect();
          return {nameRight: n.right, buttonLeft: b.left, buttonRight: b.right,
                  helpLeft: help ? help.left : null, width: b.width, titleRight: title.getBoundingClientRect().right};
        }''', [title.element_handle(), button.element_handle()])
        assert geometry['buttonLeft'] >= geometry['nameRight'] - 0.5, geometry
        assert geometry['buttonRight'] <= geometry['titleRight'] + 0.5, geometry
        assert geometry['width'] >= 12, geometry
        if geometry['helpLeft'] is not None:
            assert geometry['helpLeft'] >= geometry['buttonRight'] - 0.5, geometry
        button.click()
        page.wait_for_function('n => window.__copied.length === n', arg=index + 1)
        assert page.evaluate('window.__copied.at(-1)') == expected
    # One toast per copy, not a generic one stacked under the specific one.
    assert page.locator('.lex-toast').count() == 2
    assert title.inner_text().strip() == ''  # the rename heading's text lives in its input
    assert panels.nth(0).locator('.lex-detail-panel-name').inner_text().strip() == 'Plain Record'
    import os
    if os.environ.get('LEX_SHOT'):
        panels.nth(0).locator('.lex-detail-panel-title').hover()
        page.locator('main').screenshot(path=os.environ['LEX_SHOT'])
