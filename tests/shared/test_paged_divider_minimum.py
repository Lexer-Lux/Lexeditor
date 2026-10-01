"""Slow and fast drags reach the same reversible minimum on paged lists."""
import pytest

from test_shared_ui_feedback import page, framework


@pytest.mark.parametrize('steps', [12, 1])
def test_paged_list_returns_to_the_same_minimum(page, steps):
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
    divider = page.locator('.lex-panel-layout-divider').first.bounding_box()
    x, y = divider['x'] + divider['width'] / 2, divider['y'] + 200
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(5, y, steps=steps)
    page.mouse.up()
    page.wait_for_timeout(300)
    width = page.locator('.lex-barrelled-master').bounding_box()['width']
    assert width < divider['x'], 'the drag reaches the declared minimum'
    handle=page.get_by_role('separator').first
    handle.press('End')
    assert page.locator('.lex-barrelled-master').bounding_box()['width']>width+20
    handle.press('Home')
    assert page.locator('.lex-barrelled-master').bounding_box()['width']==pytest.approx(width,abs=1)
