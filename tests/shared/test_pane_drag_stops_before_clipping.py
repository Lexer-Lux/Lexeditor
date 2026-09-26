"""Dragging a divider never shrinks a pane until its text clips.

Lexer: "you shouldn't be able to make panels so small shit gets cut off". The
pane floor was a fixed 240px whatever the pane held, so FF8's item list could
be dragged until every name was cut to nothing. A drag now stops at the last
width where the shrinking pane's text is clipped by no more pixels than
before.
"""
import pytest

from test_shared_ui_feedback import page, framework


@pytest.mark.parametrize('steps', [12, 1])
def test_list_pane_keeps_its_names(page, steps):
    framework(page)
    page.evaluate('''() => {
      document.querySelector('main').style.height = '760px';
      const U = LexeditorUI, rows = Array.from({length: 30}, (_, id) => ({id,
        name: 'A rather long record name ' + id, buy: 1000 * id, sell: 500 * id}));
      const view = U.pagedListDetail({id: 'drag-clip', rows, key: r => r.id, selected: 0,
        master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected, columns: [
          {key: 'name', label: 'Name', render: r => U.el('span', {style: 'display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'}, r.name)},
          {key: 'buy', label: 'Buy'}, {key: 'sell', label: 'Sell'}]}),
        detail: r => U.detailPanel({title: r.name})});
      document.querySelector('main').append(view);
      view.style.height = '760px';
    }''')
    page.wait_for_timeout(500)
    before = page.evaluate('''() => [...document.querySelectorAll('.lex-barrelled-master .lex-column-cell-content *')]
      .filter(node => node.clientWidth && node.scrollWidth > node.clientWidth + 1)
      .reduce((sum, node) => sum + node.scrollWidth - node.clientWidth, 0)''')
    divider = page.locator('.lex-panel-layout-divider').first.bounding_box()
    x, y = divider['x'] + divider['width'] / 2, divider['y'] + 200
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(5, y, steps=steps)
    page.mouse.up()
    page.wait_for_timeout(300)
    after = page.evaluate('''() => [...document.querySelectorAll('.lex-barrelled-master .lex-column-cell-content *')]
      .filter(node => node.clientWidth && node.scrollWidth > node.clientWidth + 1)
      .reduce((sum, node) => sum + node.scrollWidth - node.clientWidth, 0)''')
    assert after <= before + 1, (before, after)
    width = page.locator('.lex-barrelled-master').bounding_box()['width']
    assert width < divider['x'], 'the drag still moved the divider as far as the names allow'
