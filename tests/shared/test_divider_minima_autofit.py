"""Pane minimums follow their tables with no drag needed.

A pane holding a table is at least as wide as the table's own columns
at their minimum. Widening the content and refitting (here, a resize)
raises the floor; the split rebalances around it.
"""
import re

from test_shared_ui_feedback import page, framework

ROOT = ".lex-panel-layout[data-autofit-minima]"


def floors(template):
    return [int(value) for value in re.findall(r"minmax\((\d+)px", template)]


def test_pane_minimums_follow_their_tables(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      const list = U.columnList({rows: [{id: 1, name: 'Short'}], key: row => row.id, selected: 1,
        columns: [{key: 'name', label: 'Name'}]});
      const view = U.listDetail(U.el('div', {}, list), U.detailPanel({title: 'Detail'}));
      view.setAttribute('data-autofit-minima', '1');
      view.style.height = '600px';
      document.querySelector('main').append(view);
    }''')
    page.wait_for_timeout(500)
    read = (f"() => document.querySelector('{ROOT}').style"
            ".getPropertyValue('--lex-panel-layout-template')")
    before = page.evaluate(read)
    assert floors(before), before
    page.evaluate(f'''() => {{
      const pane = document.querySelector('{ROOT} > .lex-panel-layout-pane');
      const grid = document.createElement('div');
      grid.className = 'lex-barrel-grid';
      const sample = pane.querySelector('.lex-column-list');
      for (let i = 0; i < 6; i++) grid.append(sample.cloneNode(true));
      pane.append(grid);
    }}''')
    box = page.viewport_size
    page.set_viewport_size({'width': box['width'] - 60, 'height': box['height']})
    page.wait_for_timeout(400)
    after = page.evaluate(read)
    assert floors(after)[0] > floors(before)[0], (before, after)
    page.set_viewport_size(box)
