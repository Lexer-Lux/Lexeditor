"""R2-3: one shared square add button and a legible remove X everywhere."""
import re
from pathlib import Path

from test_shared_ui_feedback import page, framework

ROOT = Path(__file__).resolve().parents[1]


def test_add_buttons_square_and_identical(page):
    page.add_style_tag(path=str(ROOT / 'plugins/rdr2/editor.css'))
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      const main = document.querySelector('main');
      main.append(U.element('div', {class: 'lex-pager-left'}, U.newButton({class: 'lex-pager-add'})));
      main.append(U.element('div', {class: 'lex-detail-actions'}, U.newButton({})));
      main.append(U.closeButton({title: 'Remove thing'}));
    }''')
    page.wait_for_selector('.lex-new-button')
    boxes = page.locator('.lex-new-button').evaluate_all(
        'ns => ns.map(n => { const r = n.getBoundingClientRect(); return {w: r.width, h: r.height}; })')
    assert len(boxes) == 2, boxes
    for box in boxes:
        assert box['w'] == box['h'] == 32, boxes
    assert boxes[0] == boxes[1], boxes
    mark = page.locator('.lex-close-button .lex-close-icon').evaluate(
        'n => ({w: getComputedStyle(n, "::before").width, h: getComputedStyle(n, "::before").borderTopWidth})')
    assert mark == {'w': '16px', 'h': '2px'}, mark


def test_no_adhoc_remove_buttons_in_rdr2():
    pattern = re.compile(',\s*"' + chr(0xd7) + r'"\s*\)')
    offenders = []
    for js in sorted((ROOT / 'plugins/rdr2').glob('*.js')):
        for i, line in enumerate(js.read_text(encoding='utf-8').splitlines(), 1):
            if pattern.search(line):
                offenders.append(f'{js.name}:{i}')
    assert offenders == []
