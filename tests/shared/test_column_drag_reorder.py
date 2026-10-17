"""A dragged column lands where it is dropped, in either direction.

Dropping a header onto its right-hand neighbor was a no-op: the move
always inserted before the target, so dragging rightward put the column
back where it started. The pinned-columns path already lands after the
target when dragged rightward; the shared preferences do the same now.
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
