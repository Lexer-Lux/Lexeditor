"""Property icons read beside their labels instead of as specks."""
from test_shared_ui_feedback import page, framework, ROOT


def test_shared_type_glyph_is_22px(page):
    framework(page)
    page.evaluate('''() => {
      const label = document.createElement('span');
      label.className = 'lex-pinned-header-label';
      label.append(LexeditorUI.typeGlyph('fire'), 'Fire');
      document.querySelector('main').append(label);
    }''')
    glyph = page.locator('.lex-type-glyph')
    assert glyph.count() == 1
    box = glyph.bounding_box()
    assert box['width'] == 22
    assert box['height'] == 22
    assert glyph.locator('svg').evaluate('''n => {
      const box = n.getBoundingClientRect(), host = n.parentElement.getBoundingClientRect();
      return Math.abs(box.width - host.width) < 1 && Math.abs(box.height - host.height) < 1;
    }''')


def test_ds1_label_art_is_22px(page):
    page.add_style_tag(path=str(ROOT / 'plugins/ds1/editor.css'))
    framework(page)
    page.evaluate('''() => {
      const art = document.createElement('img');
      art.className = 'lex-ds1-label-art';
      document.querySelector('main').append(art);
    }''')
    box = page.locator('.lex-ds1-label-art').bounding_box()
    assert box['width'] == 22
    assert box['height'] == 22
