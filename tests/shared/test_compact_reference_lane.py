"""Tiny boxes keep their digits, not their reference rail.

A provenance box under 120px cannot fit its value, its unit, its
vanilla reference and its stepper at a readable size (a one-row vector
axis is about 50px, a drop count lane is 3em). Those boxes compact,
with a unit through followUnit and without one through the provenance
control itself: the rail and stepper hide, the value takes the box,
and right-click still restores vanilla. Wide boxes are untouched.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

BUILD = """(width) => {
  const U = LexeditorUI;
  const input = U.el('input', {type: 'number', value: '3.5', step: 'any'});
  const control = U.provenanceControl({control: U.unitField(input, 'm'),
    vanilla: 1, current: 3.5});
  document.querySelector('main').replaceChildren(U.el('div', {style: `width:${width}px`},
    U.detailField({label: 'Position X', control})));
}"""

BUILD_BARE = """(width) => {
  const U = LexeditorUI;
  const input = U.el('input', {type: 'number', value: '30', step: '1'});
  const control = U.provenanceControl({control: input, vanilla: 25,
    current: 30});
  document.querySelector('main').replaceChildren(U.el('div', {style: `width:${width}px`},
    U.detailField({label: 'Position X', control})));
}"""

STATE = """() => {
  const root = document.querySelector('.lex-source-control-internal');
  const input = root.querySelector('input');
  const rail = root.querySelector('.lex-reference-values');
  const stepper = root.querySelector('.lex-stepper');
  return {compact: root.classList.contains('lex-compact-box'),
    railShown: !!rail && getComputedStyle(rail).display !== 'none',
    stepperShown: !!stepper && getComputedStyle(stepper).display !== 'none',
    padRight: getComputedStyle(input).paddingRight,
    w: input.clientWidth, sw: input.scrollWidth};
}"""


def build(page, width):
    page.set_viewport_size({"width": 900, "height": 600})
    framework(page)
    page.evaluate(BUILD, width)
    page.wait_for_timeout(500)


def test_narrow_box_hides_its_rail_and_fits_its_digits(page):
    build(page, 220)
    state = page.evaluate(STATE)
    assert state["compact"], state
    assert not state["railShown"], state
    assert state["sw"] <= state["w"] + 1, state


def test_wide_box_keeps_its_rail(page):
    build(page, 700)
    state = page.evaluate(STATE)
    assert not state["compact"], state
    assert state["railShown"], state
    assert state["sw"] <= state["w"] + 1, state


def build_bare(page, width):
    page.set_viewport_size({"width": 900, "height": 600})
    framework(page)
    page.evaluate(BUILD_BARE, width)
    page.wait_for_timeout(500)


def test_narrow_bare_box_hides_rail_and_stepper(page):
    build_bare(page, 220)
    state = page.evaluate(STATE)
    assert state["compact"], state
    assert not state["railShown"], state
    assert not state["stepperShown"], state
    assert state["sw"] <= state["w"] + 1, state


def test_wide_bare_box_keeps_rail_and_stepper(page):
    build_bare(page, 700)
    state = page.evaluate(STATE)
    assert not state["compact"], state
    assert state["railShown"], state
    assert state["stepperShown"], state
    assert state["sw"] <= state["w"] + 1, state
