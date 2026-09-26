"""A multi-word property name widens its lane instead of wrapping and shrinking.

The lane widened only for a single word too long to fit, so "MDEF (RIGHT)" in
FF9's card values broke over two clipped 13px lines while the value box beside
it took the rest of a 780px panel. A name that only fits by wrapping now asks
for the room first; the grid still caps the lane at half the row.
"""
from test_shared_ui_feedback import page, framework


def test_wrapped_names_widen_the_lane_and_stay_on_one_line(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.width = '780px';
      const field = label => U.detailField({label, showType: true, help: U.infoHelp('Help for ' + label),
        control: U.el('input', {type: 'number', value: 3, min: 0, max: 10})});
      main.append(U.detailPanel({title: 'Goblin', body: [U.detailSection({title: 'CARD VALUES',
        body: ['ATK (UP)', 'MDEF (RIGHT)', 'MATK (DOWN)', 'PDEF (LEFT)'].map(field)})]}));
    }''')
    page.wait_for_timeout(800)
    labels = page.evaluate('''() => [...document.querySelectorAll('.lex-detail-field-label-text')].map(text => {
      const css = getComputedStyle(text);
      return {name: text.textContent, size: parseFloat(css.fontSize),
        lines: Math.round(text.getBoundingClientRect().height / parseFloat(css.lineHeight)),
        left: text.getBoundingClientRect().left};
    })''')
    assert all(label['lines'] == 1 for label in labels), labels
    assert len({label['size'] for label in labels}) == 1, 'one size for every name in the panel'
    assert len({round(label['left']) for label in labels}) == 1, labels
