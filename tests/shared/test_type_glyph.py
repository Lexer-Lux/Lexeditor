from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import page, framework

KINDS = ['physical', 'magic', 'fire', 'lightning', 'slash', 'strike', 'thrust',
         'poison', 'toxic', 'bleed', 'curse', 'divine', 'occult', 'abyssal',
         'str', 'dex', 'int', 'fth']


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



def test_pinned_header_icon_sits_before_the_label(page):
    framework(page)
    page.evaluate("""() => {
      const U = LexeditorUI;
      localStorage.clear();
      const rows = [{id: 1, name: 'Dagger', values: {fire: 5, power: 70}, display: {}}];
      const render = () => document.querySelector('main').replaceChildren(U.pagedListDetail({
        rows, key: row => row.id, selected: 1, slots: false, noun: 'weapons',
        rowsKey: 'icon-pins', change: () => render(),
        master: ({rows: listed, selected, select}) => U.columnList({rows: listed, key: row => row.id, selected, select,
          columns: [{key: 'id', label: 'ID'}, {key: 'name', label: 'Name'}]}),
        detail: row => U.detailPanel({title: row.name, body: [
          U.detailField({label: 'Fire', property: 'fire', icon: 'fire', control: U.el('span', {}, '5')}),
          U.detailField({label: 'Power', property: 'power', control: U.el('span', {}, '70')})]}),
      }));
      render();
    }""")
    page.wait_for_timeout(200)
    page.locator('[data-lex-pin-column="fire"]').click(force=True)
    page.locator('[data-lex-pin-column="power"]').click(force=True)
    page.wait_for_timeout(200)
    header = page.locator('[role="columnheader"] span.lex-pinned-header-label')
    assert header.count() == 1
    assert header.evaluate('node => node.firstElementChild.className') == 'lex-type-glyph'
    assert 'Fire' in header.inner_text()
    plain = page.locator('[role="columnheader"]', has_text='Power')
    assert plain.locator('.lex-type-glyph').count() == 0
