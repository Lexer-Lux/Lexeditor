"""Filters handed to the pager stay on one row inside the bar.

Handed back by the RDR2 lane: below about 1350px the three item filters
wrapped into a stack that ran past the top and bottom of the pagination bar.
The right side of the bar was held to a half-width column and the filters'
row was allowed to wrap.
"""
import pytest

from test_shared_ui_feedback import page, framework


@pytest.mark.parametrize('width', [1100, 1280])
def test_three_filters_stay_inside_the_bar(page, width):
    page.set_viewport_size({'width': width, 'height': 800})
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, rows = Array.from({length: 400}, (_, id) => ({id, name: 'Row ' + id}));
      const choice = (label, options) => U.el('select', {'aria-label': label},
        ...options.map(text => U.el('option', {}, text)));
      const filters = U.actionRow(choice('Category', ['All categories', 'Weapons']),
        choice('Group', ['All groups', 'Rifles']), choice('Source', ['All source states', 'Confirmed']));
      document.querySelector('main').append(U.pagedListDetail({rows, key: r => r.id, selected: 0,
        slots: false, search: {value: '', input() {}}, filters: [filters],
        master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
          columns: [{key: 'name', label: 'Name'}]}), detail: r => U.detailPanel({title: r.name})}));
    }''')
    page.wait_for_timeout(400)
    outside = page.evaluate('''() => {
      const bar = document.querySelector('.lex-pager').getBoundingClientRect();
      return [...document.querySelectorAll('.lex-pager select')].map(select => select.getBoundingClientRect())
        .filter(box => box.top < bar.top - 1 || box.bottom > bar.bottom + 1 || box.right > bar.right + 1).length;
    }''')
    assert outside == 0
    rows = page.evaluate("new Set([...document.querySelectorAll('.lex-pager select')].map(s => Math.round(s.getBoundingClientRect().top))).size")
    assert rows == 1
