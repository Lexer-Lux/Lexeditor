"""A slider spans the whole accepted range, with no second scale.

A field's slider used to move in a narrower data span (sell value: the
slider moved in 0 to 1,250 while typing accepted -1 to 100,000,000),
which read as a second range. The handle now moves in exactly what the
field accepts, and the rail prints no span label: hovering keeps the
type name, focusing shows the range. Stale span options are ignored.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

BUILD = """() => {
  const U = LexeditorUI;
  document.querySelector('main').replaceChildren(
    U.detailField({label: 'Sell value', property: 'sellvalue',
      min: -1, max: 100000000, sliderMin: 0, sliderMax: 1250,
      control: U.el('input', {type: 'number', value: 1000, min: -1, max: 100000000})}));
}"""


def build(page):
    page.set_viewport_size({"width": 1280, "height": 800})
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


def opacity(page, selector):
    return page.locator(selector).evaluate("n => getComputedStyle(n).opacity")


def test_no_span_label_beside_the_range(page):
    build(page)
    field = '[data-lex-layout-field="sellvalue"]'
    assert page.locator(field + " .lex-field-type-span").count() == 0
    assert page.locator(field + " .lex-field-type-range").text_content() == "(-1-100,000,000)"


def test_fill_ratio_spans_the_whole_range(page):
    build(page)
    ratio = page.locator('[data-lex-layout-field="sellvalue"] .lex-value-fill').evaluate(
        "n => parseFloat(n.style.getPropertyValue('--lex-value-ratio'))")
    assert ratio == abs(1000 - -1) / abs(100000000 - -1), ratio


def test_hover_keeps_the_name_and_focus_shows_the_range(page):
    build(page)
    field = page.locator('[data-lex-layout-field="sellvalue"]')
    field.hover()
    page.wait_for_timeout(300)
    assert opacity(page, '[data-lex-layout-field="sellvalue"] .lex-field-type-name') == "1"
    field.locator("input").click()
    page.wait_for_timeout(300)
    assert opacity(page, '[data-lex-layout-field="sellvalue"] .lex-field-type-range') == "1"
