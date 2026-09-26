"""A sortable column header shows the pointer across the whole cell.

The cell sorts on a click anywhere in it, but only the label text showed the
pointer, so a header read as unclickable - sorted or not.
"""
from test_shared_ui_feedback import page, framework


def test_whole_sortable_header_cell_shows_pointer(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, rows = Array.from({length: 10}, (_, id) => ({id, name: 'Row ' + id, hp: id * 7}));
      const view = U.pagedListDetail({rows, key: r => r.id, selected: 0, pageSize: 10,
        master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
          columns: [{key: 'name', label: 'Name', sort: r => r.name}, {key: 'hp', label: 'HP', sort: r => r.hp}]}),
        detail: r => U.detailPanel({title: r.name})});
      document.querySelector('main').append(view);
      view.style.height = '560px';
    }''')
    page.wait_for_timeout(300)
    cursors = '''() => [...document.querySelectorAll('.lex-column-list-head-cell')].flatMap(cell => {
      const r = cell.getBoundingClientRect(), y = r.top + r.height / 2;
      return [r.left + 4, r.left + r.width / 2, r.right - 6].map(x =>
        getComputedStyle(document.elementFromPoint(x, y)).cursor);
    })'''
    assert set(page.evaluate(cursors)) == {'pointer'}
    page.locator('.lex-column-list-head-cell').nth(1).click(position={'x': 5, 'y': 5})
    page.wait_for_selector('.lex-column-list-head-cell.sorted')
    assert set(page.evaluate(cursors)) == {'pointer'}
