"""A divider drag freezes pane minima until release, so the drag stays smooth."""
import re

from test_shared_ui_feedback import page, framework

ROOT = ".lex-panel-layout[data-defer-minima]"


def floors(template):
    return [int(value) for value in re.findall(r"minmax\((\d+)px", template)]


def first_fraction(template):
    return float(re.findall(r"([\d.]+)fr", template)[0])


def test_divider_drag_freezes_minima_until_release(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      const list = U.columnList({rows: [{id: 1, name: 'Short'}], key: row => row.id, selected: 1,
        columns: [{key: 'name', label: 'Name'}]});
      const view = U.listDetail(U.el('div', {}, list), U.detailPanel({title: 'Detail'}));
      view.setAttribute('data-defer-minima', '1');
      view.style.height = '600px';
      document.querySelector('main').append(view);
    }''')
    page.wait_for_timeout(500)
    read = (f"() => document.querySelector('{ROOT}').style"
            ".getPropertyValue('--lex-panel-layout-template')")
    before = page.evaluate(read)
    assert floors(before), before
    divider = page.locator(f'{ROOT} .lex-panel-layout-divider').first.bounding_box()
    x, y = divider['x'] + divider['width'] / 2, divider['y'] + 100
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 120, y, steps=5)
    page.wait_for_timeout(300)
    # Side-by-side lists widen the pane floor: the floors must not follow mid-drag.
    page.evaluate(f'''() => {{
      const pane = document.querySelector('{ROOT} > .lex-panel-layout-pane');
      const grid = document.createElement('div');
      grid.className = 'lex-barrel-grid';
      const sample = pane.querySelector('.lex-column-list');
      for (let i = 0; i < 6; i++) grid.append(sample.cloneNode(true));
      pane.append(grid);
    }}''')
    page.mouse.move(x + 140, y, steps=2)
    page.wait_for_timeout(300)
    during = page.evaluate(read)
    assert floors(during) == floors(before), (before, during)
    assert first_fraction(during) > first_fraction(before), 'the divider still follows the pointer'
    page.mouse.up()
    page.wait_for_timeout(300)
    after = page.evaluate(read)
    assert floors(after)[0] > floors(before)[0], (before, after)
