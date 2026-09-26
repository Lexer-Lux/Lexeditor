"""A record's header picture can be pinned as a table column.

Lexer: "thumbnail thing should have pin. right click to place/remove. that
means column in table that show the thumbanil needs to be possible."
"""
from test_shared_ui_feedback import page, framework


def test_right_click_on_the_thumbnail_pins_a_picture_column(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      const rows = [{id: 0, name: 'Alpha'}, {id: 1, name: 'Beta'}];
      const picture = () => U.el('span', {class: 'probe-picture'}, '#');
      const columns = [{key: 'name', label: 'Name'}, {key: 'icon', label: 'Icon', pinned: false, render: picture}];
      let prefs;
      const render = () => {
        main.replaceChildren(
          U.columnList({rows, key: r => r.id, selected: 0, columns, columnPreferences: prefs}),
          U.detailPanel({title: 'Alpha', icon: picture(), iconPin: prefs.pinButton('icon', 'Icon')}));
      };
      prefs = U.columnPreferences('thumbnail-pin-probe', columns, () => render());
      try { localStorage.removeItem('lexeditor:columns:thumbnail-pin-probe'); } catch (_) {}
      render();
    }''')
    page.wait_for_timeout(200)
    heads = lambda: page.locator('.lex-column-list-head-cell').all_inner_texts()
    assert not any('Icon' in text for text in heads())
    pin = page.locator('.lex-detail-panel-icon > .lex-column-pin')
    assert pin.count() == 1 and 'pinned' not in (pin.get_attribute('class') or '')
    page.locator('.lex-detail-panel-icon').click(button='right')
    page.wait_for_timeout(500)  # the pin moves before it commits
    assert any('Icon' in text for text in heads())
    assert page.locator('.lex-column-list .probe-picture').count() == 2
    assert 'pinned' in page.locator('.lex-detail-panel-icon > .lex-column-pin').get_attribute('class')
    page.locator('.lex-detail-panel-icon').click(button='right')
    page.wait_for_timeout(500)  # the pin moves before it commits
    assert not any('Icon' in text for text in heads())
