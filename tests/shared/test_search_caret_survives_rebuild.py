"""Typing fast into a search box that is rebuilt keeps every letter in order.

Lexer typed "travelling" into DS1's search and got "ingtravell", three times.
The page rebuilds the box on each keystroke and again when the selected
record arrives. Focusing the rebuilt box fires its focus event before the
caret is put back, so the box was remembered with its caret at 0, and the
second rebuild put the caret at the front.
"""
from test_shared_ui_feedback import page, framework


MOUNT = '''() => {
  const U = LexeditorUI;
  window.query = '';
  const draw = () => document.querySelector('main').replaceChildren(U.bottomSearch({key: 'caret-check',
    value: window.query, label: 'Search records', change: value => {
      window.query = value;
      draw();
      // A second rebuild right after the keystroke, before its key comes up,
      // as DS1's record load does.
      queueMicrotask(draw);
    }}));
  draw();
}'''


def test_fast_typing_survives_late_rebuilds(page):
    framework(page)
    page.evaluate(MOUNT)
    box = page.get_by_role('searchbox', name='Search records')
    box.click()
    box.press_sequentially('travelling', delay=10)
    page.wait_for_timeout(200)
    assert page.evaluate('window.query') == 'travelling'
    assert box.input_value() == 'travelling'
