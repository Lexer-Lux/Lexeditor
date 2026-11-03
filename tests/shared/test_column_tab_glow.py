"""A column header and its property light each other.

Hovering a header lights the matching detail field when that field is
showing, and hovering the field lights its header back. Only the
active panel tab renders, so a property on another tab has no field
to light: its tab button glows instead, with the same background wash
as the header, showing where to find it. Pinned columns carry a pin:
prefix their property does not share; matching compares the property
underneath, both directions.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

BUILD = """(active) => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:600px';
  const field = (label, property) => U.detailField({label, property,
    control: U.el('input', {type: 'number', value: 0})});
  main.replaceChildren(
    U.columnList({rows: [{id: 0, name: 'Armor 0', price: 5}], key: row => row.id,
      selected: 0, select: () => {},
      columns: [{key: 'name', label: 'Name'}, {key: 'pin:price', label: 'Price'}]}),
    U.tabbedPanel({label: 'Item details', active,
      tabs: [{id: 'basics', label: 'Basics'}, {id: 'other', label: 'Other'}],
      fieldTabs: {members: {basics: ['name'], other: ['price']}},
      change: () => {},
      content: tab => tab === 'other' ? [field('Price', 'price')] : [field('Name', 'name')]}));
}"""

HEAD = '.lex-column-list-head-cell[data-column-key="pin:price"]'
FIELD = '[data-lex-property="price"]'
TAB = '.lex-tabbed-panel-tabs .lex-subtab-button[data-subtab="other"]'


def build(page, active, head=HEAD):
    page.set_viewport_size({"width": 1280, "height": 800})
    framework(page)
    page.evaluate(BUILD, active)
    page.wait_for_timeout(300)
    page.locator(head).hover()
    page.wait_for_timeout(200)


def test_off_tab_property_glows_its_tab_button(page):
    build(page, "basics")
    assert page.locator(FIELD).count() == 0
    assert page.locator(HEAD + ".lex-column-lit").count() == 1
    assert page.locator(TAB + ".lex-column-lit").count() == 1


def test_on_tab_property_glows_the_field_not_the_tab(page):
    build(page, "other")
    assert page.locator(FIELD + ".lex-column-lit").count() == 1
    assert page.locator(TAB + ".lex-column-lit").count() == 0


def test_leaving_the_header_unlights_the_tab(page):
    build(page, "basics")
    assert page.locator(TAB + ".lex-column-lit").count() == 1
    page.locator('[data-lex-layout-field="name"]').hover()
    page.wait_for_timeout(200)
    assert page.locator(TAB + ".lex-column-lit").count() == 0


def test_unprefixed_header_still_lights_its_field(page):
    build(page, "basics", '.lex-column-list-head-cell[data-column-key="name"]')
    assert page.locator('[data-lex-property="name"].lex-column-lit').count() == 1
def test_field_hover_lights_its_header_back(page):
    build(page, "other", FIELD)
    assert page.locator(FIELD + ".lex-column-lit").count() == 1
    assert page.locator(HEAD + ".lex-column-lit").count() == 1
    assert page.locator(TAB + ".lex-column-lit").count() == 0


def test_lit_tab_uses_the_header_glow(page):
    build(page, "basics")
    assert page.locator(TAB + ".lex-column-lit").count() == 1
    tab, head = page.evaluate("""() => [
      getComputedStyle(document.querySelector(
        '.lex-tabbed-panel-tabs .lex-subtab-button[data-subtab="other"]')),
      getComputedStyle(document.querySelector(
        '.lex-column-list-head-cell[data-column-key="pin:price"]')),
    ].map(style => [style.backgroundColor, style.outlineStyle])""")
    # The hovered header also carries self-hover (8%) over its lit wash;
    # the tab keeps the lit wash itself: same highlight hue at the
    # header-lit's 7%, and no outline box.
    assert tab[0].rsplit('/', 1)[0] == head[0].rsplit('/', 1)[0], (tab, head)
    assert tab[0].endswith('/ 0.07)'), tab
    assert tab[1] == 'none', tab
