"""A dragged column lands where it is dropped, in either direction.

Dropping a header onto its right-hand neighbor was a no-op: the move
always inserted before the target, so dragging rightward put the column
back where it started. The pinned-columns path already lands after the
target when dragged rightward; the shared preferences do the same now.

Pinned columns reorder through the same move, and the guide marks the
slot the drop would take: a pin lands on the guide in either direction,
a pin drops left of a fixed column, and a fixed column moves too.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

PAGE = """(viewKey) => {
  const U = LexeditorUI;
  const rows = [{id: 1, a: 'A1', b: 'B1', c: 'C1'}];
  const defs = [{key: 'a', label: 'A'}, {key: 'b', label: 'B'}, {key: 'c', label: 'C'}];
  const prefs = U.columnPreferences(viewKey, defs, () => render());
  window.__prefs = prefs;
  const render = () => document.querySelector('main').replaceChildren(U.columnList(
    {rows, key: r => r.id, columns: prefs.active(), columnPreferences: prefs}));
  render();
}"""

ORDER = """() => [...document.querySelectorAll('[role="columnheader"]')]
  .map(n => n.dataset.columnKey).filter(k => ['a', 'b', 'c'].includes(k))"""


def test_move_lands_after_the_target_when_dragged_rightward(page):
    framework(page)
    page.evaluate(PAGE, 'drag-reorder-right')
    page.evaluate("window.__prefs.move('a', 'b')")
    assert page.evaluate("window.__prefs.active().map(c => c.key).filter(k => k !== 'enabled')") == ['b', 'a', 'c']
    page.evaluate("window.__prefs.move('b', 'c')")
    assert page.evaluate("window.__prefs.active().map(c => c.key).filter(k => k !== 'enabled')") == ['a', 'c', 'b']


def test_move_lands_before_the_target_when_dragged_leftward(page):
    framework(page)
    page.evaluate(PAGE, 'drag-reorder-left')
    page.evaluate("window.__prefs.move('c', 'a')")
    assert page.evaluate("window.__prefs.active().map(c => c.key).filter(k => k !== 'enabled')") == ['c', 'a', 'b']


def test_header_drag_drops_rightward_onto_its_neighbor(page):
    framework(page)
    page.evaluate(PAGE, 'drag-reorder-pointer')
    assert page.evaluate(ORDER) == ['a', 'b', 'c']
    head = page.locator('[role="columnheader"][data-column-key="a"]')
    target = page.locator('[role="columnheader"][data-column-key="b"]')
    box, goal = head.bounding_box(), target.bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.mouse.down()
    page.mouse.move(goal['x'] + goal['width'] / 2, goal['y'] + goal['height'] / 2, steps=8)
    page.mouse.up()
    page.wait_for_function(
        "() => [...document.querySelectorAll('[role=\"columnheader\"]')]"
        ".map(n => n.dataset.columnKey).filter(k => ['a', 'b', 'c'].includes(k))"
        ".join(',') === 'b,a,c'")
    assert page.evaluate(ORDER) == ['b', 'a', 'c']

PIN_PAGE = """(pins) => {
  const U = LexeditorUI;
  localStorage.setItem('lexeditor:pins:drag-reorder-pins', JSON.stringify(pins));
  localStorage.removeItem('lexeditor:header-order:drag-reorder-pins');
  window.state = {selected: 1, page: 0};
  const rows = [
    {id: 1, name: 'Alpha', values: {power: 70}},
    {id: 2, name: 'Beta', values: {power: 90}},
  ];
  const picture = () => U.el('span', {class: 'probe-picture'}, '#');
  let view = null;
  const render = () => {
    view = U.pagedListDetail({
      rows, key: row => row.id, selected: state.selected, slots: false, noun: 'probes',
      page: state.page, rowsKey: 'drag-reorder-pins',
      change: next => {
        if (next.reason === 'pins' && view?.refreshMaster) view.refreshMaster();
        else { state.page = next.page; render(); }
      },
      master: ({rows: listed, selected, select}) => U.columnList({rows: listed,
        key: row => row.id, selected, select, columns: [{key: 'name', label: 'Name'}]}),
      describePinnedCell: key => key === 'icon'
        ? {editable: false, label: '', sortable: false, width: '36px',
           render: row => U.el('span', {class: 'probe-cell'}, picture())}
        : {editable: false, label: key},
      detail: row => U.detailPanel({title: row.name, icon: picture(),
        previewPin: {key: 'icon', label: 'Icon'},
        body: [U.detailSection({title: 'Stats', body: [
          U.detailField({label: 'Power', property: 'power',
            control: U.el('input', {value: row.values.power})})]})]}),
    });
    document.querySelector('main').replaceChildren(view);
  };
  render();
}"""

PIN_ORDER = """() => [...document.querySelectorAll('.lex-column-list-head-cell')]
  .map(h => h.dataset.columnKey)"""

GUIDE = """() => {
  const guide = document.querySelector('.lex-column-list-head-cell.drag-target');
  return guide ? {key: guide.dataset.columnKey,
    index: [...guide.parentNode.children].indexOf(guide)} : null;
}"""


def drag_hold(page, src, dst):
    """Hold a header drag over its target and report the guide slot."""
    head = page.locator(f'.lex-column-list-head-cell[data-column-key="{src}"]')
    target = page.locator(f'.lex-column-list-head-cell[data-column-key="{dst}"]')
    box, goal = head.bounding_box(), target.bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.mouse.down()
    page.mouse.move(goal['x'] + goal['width'] / 2, goal['y'] + goal['height'] / 2, steps=8)
    page.wait_for_timeout(150)
    return page.evaluate(GUIDE)


def pin_order_is(order):
    return ("() => [...document.querySelectorAll('.lex-column-list-head-cell')]"
            f".map(h => h.dataset.columnKey).join(',') === '{','.join(order)}'")


def test_pin_drop_lands_on_the_guide_when_dragged_rightward(page):
    framework(page)
    page.evaluate(PIN_PAGE, [{'key': 'icon', 'label': 'Icon'}, {'key': 'power', 'label': 'Power'}])
    page.wait_for_timeout(500)
    assert page.evaluate(PIN_ORDER) == ['name', 'pin:icon', 'pin:power']
    guide = drag_hold(page, 'pin:icon', 'pin:power')
    assert guide == {'key': 'pin:power', 'index': 2}
    page.mouse.up()
    page.wait_for_function(pin_order_is(['name', 'pin:power', 'pin:icon']))
    assert page.evaluate(PIN_ORDER).index('pin:icon') == guide['index']


def test_pin_drop_lands_on_the_guide_when_dragged_leftward(page):
    framework(page)
    page.evaluate(PIN_PAGE, [{'key': 'power', 'label': 'Power'}, {'key': 'icon', 'label': 'Icon'}])
    page.wait_for_timeout(500)
    assert page.evaluate(PIN_ORDER) == ['name', 'pin:power', 'pin:icon']
    guide = drag_hold(page, 'pin:icon', 'pin:power')
    assert guide == {'key': 'pin:power', 'index': 1}
    page.mouse.up()
    page.wait_for_function(pin_order_is(['name', 'pin:icon', 'pin:power']))
    assert page.evaluate(PIN_ORDER).index('pin:icon') == guide['index']


def test_pin_drop_left_of_a_fixed_column_lands_on_the_guide(page):
    framework(page)
    page.evaluate(PIN_PAGE, [{'key': 'icon', 'label': 'Icon'}])
    page.wait_for_timeout(500)
    assert page.evaluate(PIN_ORDER) == ['name', 'pin:icon']
    guide = drag_hold(page, 'pin:icon', 'name')
    assert guide == {'key': 'name', 'index': 0}
    page.mouse.up()
    page.wait_for_function(pin_order_is(['pin:icon', 'name']))
    assert page.evaluate(PIN_ORDER).index('pin:icon') == guide['index']


def test_fixed_drop_right_of_a_pin_lands_on_the_guide(page):
    framework(page)
    page.evaluate(PIN_PAGE, [{'key': 'icon', 'label': 'Icon'}])
    page.wait_for_timeout(500)
    assert page.evaluate(PIN_ORDER) == ['name', 'pin:icon']
    guide = drag_hold(page, 'name', 'pin:icon')
    assert guide == {'key': 'pin:icon', 'index': 1}
    page.mouse.up()
    page.wait_for_function(pin_order_is(['pin:icon', 'name']))
    assert page.evaluate(PIN_ORDER).index('name') == guide['index']
