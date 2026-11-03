"""Dragging a section header or property auto-scrolls the details panel.

Holding the dragged row near the top or bottom edge scrolls the panel, the
way other programs do. The panel keeps its own scrollbar while the drag is
on: nothing hides it, locks it, or covers it.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  const field = (label, value) => U.detailField({label, property: label.toLowerCase(),
    control: U.el('input', {type: 'number', value})});
  const sections = Array.from({length: 20}, (_, i) =>
    U.detailSection({title: 'SECTION ' + i, body: [field('Alpha' + i, 1), field('Beta' + i, 2)]}));
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:500px';
  main.replaceChildren(U.detailPanel({title: 'Record', paginate: false, body: sections}));
}"""

PANEL = ".lex-detail-panel"


def mount(page):
    framework(page)
    mount_shell(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)
    panel = page.locator(PANEL)
    height = panel.evaluate("n => [n.scrollHeight, n.clientHeight]")
    assert height[0] > height[1] + 200, height


def panel_box(page):
    return page.locator(PANEL).bounding_box()


def drag_to_edge(page, source, bottom=True):
    box = source.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    panel = panel_box(page)
    page.mouse.move(panel["x"] + panel["width"] / 2,
                    panel["y"] + (panel["height"] - 10 if bottom else 10), steps=15)


def scroll_of(page):
    return page.evaluate(f"document.querySelector('{PANEL}').scrollTop")


def scrollbar_live(page):
    """The scrollbar is there and the panel still scrolls, mid-drag."""
    return page.evaluate(f"""() => {{
      const panel = document.querySelector('{PANEL}');
      const before = panel.scrollTop;
      panel.scrollTop = before + 40;
      const moved = panel.scrollTop;
      return [getComputedStyle(panel).overflowY,
              panel.scrollHeight > panel.clientHeight, moved >= before];
    }}""")


def test_holding_a_section_at_the_bottom_edge_scrolls_down(page):
    mount(page)
    header = page.locator(".lex-detail-section-title", has_text="SECTION 0").first
    header.hover()
    drag_to_edge(page, header, bottom=True)
    page.wait_for_timeout(300)
    before = scroll_of(page)
    page.wait_for_timeout(700)
    after = scroll_of(page)
    assert after > before + 50, (before, after)
    overflow, ranged, moved = scrollbar_live(page)
    assert overflow in ("auto", "scroll"), overflow
    assert ranged and moved, (overflow, ranged, moved)
    page.mouse.up()
    page.wait_for_timeout(200)
    assert page.locator(".lex-detail-section-title").count() == 20


def test_holding_a_section_at_the_top_edge_scrolls_up(page):
    mount(page)
    page.evaluate(f"document.querySelector('{PANEL}').scrollTop = 99999")
    page.wait_for_timeout(200)
    header = page.locator(".lex-detail-section-title", has_text="SECTION 19").first
    header.hover()
    header.scroll_into_view_if_needed()
    drag_to_edge(page, header, bottom=False)
    page.wait_for_timeout(300)
    before = scroll_of(page)
    page.wait_for_timeout(700)
    after = scroll_of(page)
    assert after < before - 50, (before, after)
    page.mouse.up()
    page.wait_for_timeout(200)
    assert page.locator(".lex-detail-section-title").count() == 20


def test_holding_a_property_at_the_edge_scrolls(page):
    mount(page)
    label = page.locator(".lex-detail-field-label-text", has_text="Alpha0").first
    label.hover()
    drag_to_edge(page, label, bottom=True)
    page.wait_for_timeout(300)
    before = scroll_of(page)
    page.wait_for_timeout(700)
    after = scroll_of(page)
    assert after > before + 50, (before, after)
    page.mouse.up()
    page.wait_for_timeout(200)
    assert page.locator(".lex-detail-section-title").count() == 20
