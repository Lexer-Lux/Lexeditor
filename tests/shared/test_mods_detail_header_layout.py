"""The Mods detail header: icons after the name, switch at the far edge.

The enable switch closes the row on the right; the copy, delete and open
buttons sit right after the record name. Every one of them fills the header
the same way: stretched to the actions area, square, with equal margins, so
a roomy header gets roomy controls. The scaling lives on the shared
detail-header component, not on a Mods-only rule.
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
        icons: [...actions.querySelectorAll(':scope > .lex-header-icon')].map(rect),
        box: rect(actions.querySelector(':scope > input[type="checkbox"]')),
        svg: actions.querySelector('.lex-header-icon > svg').getBoundingClientRect().width,
      };
    }""")


def test_switch_is_last_and_icons_fill_the_header(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("checkbox", name="Mine enabled").wait_for()
    page.wait_for_timeout(300)
    geo = geometry(page)
    box, head, actions, icons = geo["box"], geo["head"], geo["actions"], geo["icons"]
    assert len(icons) == 3, geo
    # After the name (the actions lane follows the identity), icons first,
    # then the switch at the far edge.
    for icon in icons:
        assert icon["x"] + icon["width"] <= box["x"] + 1, geo
    assert box["x"] + box["width"] <= head["x"] + head["width"] + 1, geo
    # Square, filling the header like the switch: actions height minus the
    # 5px margins top and bottom, centred with equal margins.
    for icon in icons:
        assert icon["width"] == icon["height"] > 0, geo
        assert abs(actions["height"] - 10 - icon["height"]) <= 2, geo
        top = icon["y"] - actions["y"]
        bottom = actions["y"] + actions["height"] - icon["y"] - icon["height"]
        assert abs(top - bottom) <= 2, geo
        assert icon["y"] >= head["y"] - 1, geo
        assert icon["y"] + icon["height"] <= head["y"] + head["height"] + 1, geo
    # The pictures scale with their buttons instead of sitting at 16px.
    assert geo["svg"] >= 20, geo


def test_icons_match_the_switch_in_a_short_header(page):
    # Same contract as the switch test: square, inside the heading, and the
    # same size as the switch beside them.
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
        assert icon["width"] == icon["height"] > 0, geo
        assert icon["y"] >= geo["head"]["y"] - 1, geo
        assert icon["y"] + icon["height"] <= geo["head"]["y"] + geo["head"]["height"] + 1, geo
        assert abs(icon["height"] - geo["box"]["height"]) <= 2, geo
