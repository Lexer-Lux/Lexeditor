"""Growable-list filler rows hold layout but paint no rules.

FF8's slot tables simply end after the last record: a clean slab in the
theme's panel color. DS1's growable lists padded the rest of the page
with ruled filler rows. Both are the same empty space now: fillers keep
the fitted rows from stretching, but paint nothing.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401


def test_filler_rows_hold_layout_but_paint_no_rules(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      document.querySelector('main').replaceChildren(U.pagedListDetail({
        rows: [{id: 1, name: 'One'}], key: row => row.id, slots: false,
        pageSize: 8, page: 0, selected: 1, noun: 'things',
        splitKey: 'filler-clean-check', rowsKey: 'filler-clean-check',
        master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
          columns: [{key: 'name', label: 'Name'}]}),
        detail: row => U.detailPanel({title: row.name, body: []}),
      }));
    }''')
    page.wait_for_selector('.lex-filler-row')
    assert page.locator('.lex-filler-row').count() > 0
    paint = page.locator('.lex-filler-row .lex-column-list-cell').first.evaluate('''cell => {
      const style = getComputedStyle(cell);
      return {bottom: style.borderBottomColor, right: style.borderRightColor, text: style.color};
    }''')
    assert paint == {'bottom': 'rgba(0, 0, 0, 0)', 'right': 'rgba(0, 0, 0, 0)',
                     'text': 'rgba(0, 0, 0, 0)'}, paint
    real = page.locator('.lex-column-list-row:not(.lex-filler-row) .lex-column-list-cell').first.evaluate('''cell => {
      const style = getComputedStyle(cell);
      return [style.borderBottomColor, style.borderBottomWidth];
    }''')
    assert real[1] != '0px' and real[0] != 'rgba(0, 0, 0, 0)', real
