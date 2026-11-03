"""Hover glow can never stick, and a slider drag always ends.

A glow whose pointerout goes missing (a drag swallowing boundary
events, a node replaced mid-hover) used to stay lit: the next hover
anywhere drops it now, and window blur, gesture cancel and native
drags clear it outright. A value-slider drag that ends off-window
never sees its pointerup, so losing the window ends it too instead
of letting the slider follow the pointer and swallow its hovers.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:600px';
  const field = (label, property, attrs) => U.detailField({label, property,
    control: U.el('input', Object.assign({type: 'number', value: 0}, attrs || {}))});
  main.replaceChildren(
    U.columnList({rows: [{id: 0, name: 'Armor 0', price: 5}], key: row => row.id,
      selected: 0, select: () => {},
      columns: [{key: 'name', label: 'Name'}, {key: 'pin:price', label: 'Price'}]}),
    U.el('div', {id: 'fields'}, field('Price', 'price'), field('Level', 'level', {min: 1, max: 99})));
}"""

HEAD = '.lex-column-list-head-cell[data-column-key="pin:price"]'
FIELD = '[data-lex-property="price"]'
LIT = '.lex-column-lit,.lex-self-hover'


def build(page):
    page.set_viewport_size({"width": 1280, "height": 800})
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


def lit(page):
    return page.locator(LIT).count()


def test_blur_unlights_a_hover(page):
    build(page)
    page.locator(HEAD).hover()
    page.wait_for_timeout(200)
    assert page.locator(HEAD + ".lex-column-lit").count() == 1
    assert page.locator(FIELD + ".lex-column-lit").count() == 1
    page.evaluate("() => window.dispatchEvent(new Event('blur'))")
    assert lit(page) == 0


def test_pointercancel_unlights_a_hover(page):
    build(page)
    page.locator(FIELD).hover()
    page.wait_for_timeout(200)
    assert lit(page) > 0
    page.evaluate(
        "() => document.dispatchEvent(new Event('pointercancel', {bubbles: true}))")
    assert lit(page) == 0


def test_dragstart_unlights_a_hover(page):
    build(page)
    page.locator(FIELD).hover()
    page.wait_for_timeout(200)
    assert lit(page) > 0
    page.evaluate(
        "() => document.dispatchEvent(new Event('dragstart', {bubbles: true}))")
    assert lit(page) == 0


def test_next_hover_drops_a_stuck_glow(page):
    # A glow left behind without its pointerout (a node replaced
    # mid-hover) clears the moment anything else hovers.
    build(page)
    page.locator(HEAD).hover()
    page.wait_for_timeout(200)
    assert lit(page) > 0
    page.evaluate(f"() => document.querySelector({HEAD!r}).remove()")
    page.locator('[data-lex-property="level"]').hover()
    page.wait_for_timeout(200)
    assert page.locator(HEAD).count() == 0
    assert lit(page) == 1


def test_slider_drag_ends_when_the_window_blurs(page):
    build(page)
    handle = page.locator('[data-lex-property="level"] .lex-value-handle')
    assert handle.count() == 1
    box = handle.bounding_box()
    page.mouse.move(box["x"] + 2, box["y"] + 2)
    page.mouse.down()
    page.wait_for_timeout(200)
    assert page.locator(".lex-value-dragging").count() == 1
    page.evaluate("() => window.dispatchEvent(new Event('blur'))")
    assert page.locator(".lex-value-dragging").count() == 0
    assert page.evaluate(
        "() => !!document.querySelector('[data-lex-property=\"level\"] input').lexValueSliderDragging") is False
    page.mouse.up()
