"""Coordinate triples are one row at any width.

Position, Rotation and Scale render through multiNumberRow with nowrap:
X, Y and Z read as one value. An earlier container query stacked the
axes one per row below 340px of control; Lexer vetoed that repeatedly,
so nowrap means nowrap and narrow panels shrink the boxes instead.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

BUILD = """() => {
  const U = LexeditorUI;
  const box = (label, value) => ({label,
    control: U.el('input', {value, 'aria-label': label})});
  document.querySelector('main').replaceChildren(U.el('div', {style: 'width:250px'},
    U.detailField({label: 'Position',
      control: U.multiNumberRow([box('X', '-107.75'), box('Y', '-62.38'), box('Z', '-9.51')],
        {columns: 3, nowrap: true})})));
}"""


def build(page):
    page.set_viewport_size({"width": 900, "height": 600})
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


def test_nowrap_triple_stays_one_row_in_a_narrow_panel(page):
    build(page)
    tops = page.evaluate(
        "[...document.querySelectorAll('.lex-detail-part')].map(node => node.offsetTop)")
    assert len(tops) == 3 and len(set(tops)) == 1, tops
    tracks = page.evaluate(
        "getComputedStyle(document.querySelector('.lex-detail-parts-nowrap'))"
        ".gridTemplateColumns.split(' ').length")
    assert tracks == 3, tracks
