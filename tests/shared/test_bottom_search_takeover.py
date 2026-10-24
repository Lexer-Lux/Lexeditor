"""A bottomSearch box rebuilt mid-delay adopts the dead box's keystrokes.

A delayed search (FF8's 110ms) whose box is replaced before its timer
fires must carry the typed value into the new box and report it: without
the takeover, the keystrokes vanish with the detached box and the search
never hears about them. A box the reader left deliberately (blurred while
still on the page) adopts nothing.
"""
from test_shared_ui_feedback import page, framework  # noqa: F401


MOUNT = """() => {
  const host = LexeditorUI.el("main", {id: "takeover-host"});
  document.querySelector("main").replaceWith(host);
  window.takeoverChanges = [];
  host.append(LexeditorUI.bottomSearch({key: "takeover-fixture", label: "Search", value: "",
    delay: 60000, change: value => window.takeoverChanges.push(value)}));
  return document.querySelector('[data-lex-bottom-search="takeover-fixture"]') !== null;
}"""

SWAP = """() => {
  const old = document.querySelector('[data-lex-bottom-search="takeover-fixture"]');
  const label = old.closest("label");
  label.replaceWith(LexeditorUI.bottomSearch({key: "takeover-fixture", label: "Search", value: "",
    delay: 60000, change: value => window.takeoverChanges.push(value)}));
  return document.querySelectorAll('[data-lex-bottom-search="takeover-fixture"]').length;
}"""


def test_rebuilt_box_adopts_dead_box_keystrokes(page):
    framework(page)
    assert page.evaluate(MOUNT) is True
    box = page.get_by_role("searchbox", name="Search")
    box.click()
    box.press("a")
    box.press("b")
    assert page.evaluate("window.takeoverChanges") == []
    assert page.evaluate(SWAP) == 1
    page.wait_for_timeout(100)
    assert page.evaluate("window.takeoverChanges") == ["ab"]
    assert box.input_value() == "ab"
    assert page.evaluate("document.activeElement.dataset.lexBottomSearch") == "takeover-fixture"


def test_stale_keystrokes_do_not_adopt(page):
    framework(page)
    assert page.evaluate(MOUNT) is True
    box = page.get_by_role("searchbox", name="Search")
    box.click()
    box.press("a")
    box.press("b")
    # A query carried from another tab under a reused key is long stale:
    # navigating must not leak it into the new tab's box.
    page.wait_for_timeout(1200)
    assert page.evaluate(SWAP) == 1
    page.wait_for_timeout(100)
    assert page.evaluate("window.takeoverChanges") == []
    assert box.input_value() == ""


def test_deliberately_left_box_adopts_nothing(page):
    framework(page)
    assert page.evaluate(MOUNT) is True
    box = page.get_by_role("searchbox", name="Search")
    box.click()
    box.press("a")
    box.press("b")
    page.evaluate("document.activeElement.blur()")
    # Renders land on a later task, after the blur cleanup forgets the box.
    page.wait_for_timeout(100)
    assert page.evaluate(SWAP) == 1
    page.wait_for_timeout(100)
    assert page.evaluate("window.takeoverChanges") == []
    assert box.input_value() == ""
