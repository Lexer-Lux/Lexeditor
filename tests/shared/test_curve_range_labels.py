"""A graph's end values are large enough to read and are not haloed.

Lexer: "min/max numbers in graphs are too small. and have this weird gigantic
white drop shadow?" and "the graph lines are still aliased". The end values
were 10px with a drop shadow in the panel colour - a pale halo on FF8's grey
- and a theme's line shadow was a CSS filter that re-rasterised the path.
"""
from test_shared_ui_feedback import ROOT, page, framework


def test_range_values_are_legible_and_the_shadow_is_a_stroke(page):
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.cssText = 'width:480px;height:320px';
      main.append(U.curveGrid(U.curveEditor({title: 'HP', domain: {min: 1, max: 100},
        range: {min: 0, max: 7835}, evaluate: level => 300 + level * 70,
        formula: U.mathFormula('HP(L)=C+L*A')})));
    }''')
    page.wait_for_function("document.querySelector('.lex-curve-range-high')?.textContent")
    page.wait_for_timeout(300)
    label = page.evaluate('''() => {
      const text = document.querySelector('.lex-curve-range-high'), style = getComputedStyle(text);
      return {size: parseFloat(style.fontSize), filter: style.filter, stroke: style.stroke, order: style.paintOrder};
    }''')
    assert label['size'] >= 13 and label['filter'] == 'none' and label['order'].startswith('stroke'), label
    line = page.evaluate('''() => ({filter: getComputedStyle(document.querySelector('.lex-curve-line')).filter,
      shadow: document.querySelector('.lex-curve-line-shadow')?.getAttribute('d') ===
              document.querySelector('.lex-curve-line').getAttribute('d')})''')
    assert line == {'filter': 'none', 'shadow': True}, line
