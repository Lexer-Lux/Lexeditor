"""The Mods detail header: icons after the name, switch at the far edge.

The enable switch closes the row on the right; the copy, delete and open
buttons sit right after the record name. Every control in the row is a
compact fixed square: the record name owns the heading's width, and a
roomy header no longer grows roomy controls. The sizing lives on the
shared detail-header component, not on a Mods-only rule.
"""
from test_mods_tab import mount
from test_shared_ui_feedback import page  # noqa: F401  (fixture)


def geometry(page):
    return page.evaluate("""() => {
      const rect = el => { const b = el.getBoundingClientRect();
        return {x: b.x, y: b.y, width: b.width, height: b.height}; };
      const actions = document.querySelector('.lex-mods-page .lex-detail-panel-actions');
      return {
        head: rect(document.querySelector('.lex-mods-page .lex-detail-panel-heading')),
        actions: rect(actions),
        icons: [...actions.querySelectorAll(':scope > .lex-header-icon:not(.lex-detail-add-header)')].map(rect),
        box: rect(actions.querySelector(':scope > input[type="checkbox"]')),
        svg: actions.querySelector('.lex-header-icon > svg').getBoundingClientRect().width,
      };
    }""")


def test_switch_is_last_and_controls_are_compact(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("checkbox", name="Mine enabled").wait_for()
    page.wait_for_timeout(300)
    geo = geometry(page)
    box, head, icons = geo["box"], geo["head"], geo["icons"]
    assert len(icons) == 3, geo
    # After the name (the actions lane follows the identity), icons first,
    # then the switch at the far edge.
    for icon in icons:
        assert icon["x"] + icon["width"] <= box["x"] + 1, geo
    assert box["x"] + box["width"] <= head["x"] + head["width"] + 1, geo
    # Compact fixed squares, icons and switch alike, inside the heading.
    for icon in icons:
        assert abs(icon["width"] - 28) <= 1, geo
        assert abs(icon["height"] - 28) <= 1, geo
        assert icon["y"] >= head["y"] - 1, geo
        assert icon["y"] + icon["height"] <= head["y"] + head["height"] + 1, geo
    assert abs(box["width"] - 28) <= 1, geo
    assert abs(box["height"] - 28) <= 1, geo
    # The pictures stay at icon size instead of scaling with the header.
    assert abs(geo["svg"] - 16) <= 1, geo


def test_icons_match_the_switch_in_a_short_header(page):
    # Same contract in a short header: fixed 28px squares, inside the
    # heading, icons the same size as the switch beside them.
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("checkbox", name="Mine enabled").wait_for()
    page.evaluate("""() => {
      const head = document.querySelector(".lex-mods-page .lex-detail-panel-heading");
      head.style.padding = "0";
      head.querySelector(".lex-detail-panel-title").style.fontSize = "10px";
    }""")
    page.wait_for_timeout(200)
    geo = geometry(page)
    for icon in geo["icons"]:
        assert abs(icon["width"] - 28) <= 1, geo
        assert abs(icon["height"] - 28) <= 1, geo
        assert icon["y"] >= geo["head"]["y"] - 1, geo
        assert icon["y"] + icon["height"] <= geo["head"]["y"] + geo["head"]["height"] + 1, geo
        assert abs(icon["height"] - geo["box"]["height"]) <= 2, geo
