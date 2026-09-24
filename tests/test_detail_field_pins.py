"""B-1: detail-field pins are present, positioned and hover-revealed."""
from test_shared_ui_feedback import page, framework

BUILD = '''() => {
  const U = LexeditorUI;
  const prefs = U.columnPreferences('probe-cols',
    [{key: 'name', label: 'Name'}, {key: 'value', label: 'Value'}], () => {});
  const main = document.querySelector('main');
  main.append(U.detailField({label: 'NAME',
    control: U.provenanceControl({control: U.element('input', {value: 'a'}),
      current: () => 'a', vanilla: 'b', apply: () => {}}),
    pin: prefs.pinButton('name', 'Name')}));
  main.append(U.detailField({label: 'VALUE',
    control: U.element('input', {value: '1'}),
    pin: prefs.pinButton('value', 'Value')}));
}'''


def test_pins_present_and_hover_revealed(page):
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_selector('.lex-detail-field .lex-column-pin')
    page.wait_for_timeout(300)
    pins = page.locator('.lex-detail-field .lex-column-pin')
    assert pins.count() == 2
    for index in range(2):
        field = page.locator('.lex-detail-field').nth(index)
        field.hover()
        page.wait_for_timeout(200)
        state = pins.nth(index).evaluate('''n => {
          const r = n.getBoundingClientRect(), cs = getComputedStyle(n);
          const f = n.closest('.lex-detail-field').getBoundingClientRect();
          return {opacity: cs.opacity, w: r.width, h: r.height,
            inside: r.left >= f.left - 40 && r.right <= f.right + 40 &&
              r.top >= f.top - 40 && r.bottom <= f.bottom + 40};
        }''')
        assert state['opacity'] != '0', (index, state)
        assert state['w'] > 0 and state['h'] > 0, (index, state)
        assert state['inside'], (index, state)
