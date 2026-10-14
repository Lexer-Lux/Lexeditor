from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import page, framework

KINDS = ['physical', 'magic', 'fire', 'lightning', 'slash', 'strike', 'thrust',
         'poison', 'toxic', 'bleed', 'curse', 'divine', 'occult', 'abyssal']


def test_type_glyph_draws_every_known_kind(page):
    framework(page)
    drawn = page.evaluate('''(kinds) => {
      return kinds.map(kind => {
        const glyph = LexeditorUI.typeGlyph(kind);
        if (!glyph) return null;
        document.querySelector('main').append(glyph);
        const svg = glyph.querySelector('svg');
        return svg && svg.viewBox.baseVal.width === 16 && svg.childNodes.length > 0;
      });
    }''', arg=KINDS)
    assert drawn == [True] * len(KINDS)


def test_type_glyph_unknown_kind_draws_nothing(page):
    framework(page)
    assert page.evaluate('LexeditorUI.typeGlyph("bananas") === null')
    assert page.evaluate('LexeditorUI.typeGlyph("") === null')
    assert page.evaluate('LexeditorUI.typeGlyph() === null')


def test_detail_field_icon_sits_before_the_label(page):
    framework(page)
    page.evaluate('''() => {
      document.querySelector('main').append(LexeditorUI.detailField(
        {label: 'Fire', icon: 'fire', control: LexeditorUI.el('span', {}, '0')}));
    }''')
    glyph = page.locator('.lex-detail-field-label > .lex-type-glyph')
    assert glyph.count() == 1
    assert glyph.evaluate('node => node.nextElementSibling.textContent') == 'Fire'
