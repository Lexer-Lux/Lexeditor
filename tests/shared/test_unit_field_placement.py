"""Unit suffixes clear the value's ink and park short of the reserved lane.

The suffix travels with the number, placed just after its last glyph. An
italic value leans past its advance width, so advance-measured placement
paints the unit over the last digit (DS1's AI tab: the "m" ate every "5").
Long values park against the reserved lane; the reserve is in em, not px.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;width:600px;';
  window.makeUnit = (value, fontSize, wrapWidth) => {
    const input = U.el('input', {type: 'number', value});
    input.style.font = `italic 400 ${fontSize}px "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif`;
    const wrap = U.el('div', {style: `width:${wrapWidth}px`}, U.detailField(
      {label: 'Distance', property: 'dist', control: U.unitField(input, 'm')}));
    main.replaceChildren(wrap);
    return {input, field: wrap.querySelector('.lex-unit-field'),
      unit: wrap.querySelector(':scope .lex-unit, .lex-unit')};
  };
}"""

MEASURE = """({input, field, unit}) => {
  const canvas = document.createElement('canvas').getContext('2d');
  const style = getComputedStyle(input);
  canvas.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  const ink = canvas.measureText(input.value).actualBoundingBoxRight
    ?? canvas.measureText(input.value).width;
  const box = field.getBoundingClientRect();
  const pad = parseFloat(style.paddingLeft) || 0;
  const border = parseFloat(style.borderLeftWidth) || 0;
  return {left: unit.getBoundingClientRect().left - box.left,
    inkEnd: border + pad + ink,
    right: unit.getBoundingClientRect().right - box.left,
    lane: field.clientWidth - parseFloat(getComputedStyle(field)
      .getPropertyValue('--lex-unit-reserve')) * (parseFloat(style.fontSize) || 16)};
}"""


def mount(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(BUILD)


def test_unit_clears_italic_ink(page):
    # DS1's AI configuration: a readonly (italic) Palatino value with a
    # unit. The suffix must leave real air after the ink, not a subpixel
    # sliver the italic lean reads as touching.
    mount(page)
    page.evaluate("window.probe = makeUnit('75', 19, 300)")
    page.wait_for_timeout(400)
    got = page.evaluate(f"(() => {{ const probe = window.probe; return ({MEASURE})(probe); }})()")
    assert got['left'] - got['inkEnd'] >= 1.5, got


def test_unit_parks_short_of_reserved_lane(page):
    mount(page)
    page.evaluate("window.probe = makeUnit('123456789012345678901234567890', 16, 150)")
    page.wait_for_timeout(400)
    got = page.evaluate(f"(() => {{ const probe = window.probe; return ({MEASURE})(probe); }})()")
    assert got['right'] <= got['lane'] + 1.0, got
