"""Booleans are one wide box by default; a setting brings back the arrow.

Lexer, on seeing FF9's broken booleans: "no arrow and a giant box....actually
i kinda like the style, make it an option in the settings menu (global),
default on. off is the other style with the arrow."
"""
import sys
import tempfile
from pathlib import Path

from test_shared_ui_feedback import ROOT, page, framework

sys.path.insert(0, str(ROOT))
from core.settings_manager import SettingsStore  # noqa: E402


def test_setting_defaults_on_and_round_trips():
    with tempfile.TemporaryDirectory() as folder:
        store = SettingsStore(Path(folder) / 'settings.json', ROOT / 'ui/default_settings.json')
        assert store.snapshot()['booleanBoxStyle'] is True
        store.save('daily', boolean_box_style=False)
        assert store.snapshot()['booleanBoxStyle'] is False
        store.save('daily')
        assert store.snapshot()['booleanBoxStyle'] is False, 'an unrelated save keeps the choice'


def _geometry(page, style):
    page.evaluate('''style => {
      document.documentElement.dataset.lexBooleanStyle = style;
      const U = LexeditorUI, box = U.el('div', {style: 'width:600px'});
      document.querySelector('main').replaceChildren(box);
      box.append(U.detailField({label: 'Number', showType: true, control: U.el('input', {type: 'number', value: 4})}));
      box.append(U.detailField({label: 'Enabled', showType: true, control: U.el('input', {type: 'checkbox', checked: true})}));
    }''', style)
    page.wait_for_timeout(250)
    return page.evaluate('''() => {
      const [number, flag] = document.querySelectorAll('.lex-detail-field');
      const value = number.querySelector('input').getBoundingClientRect();
      const check = flag.querySelector('input[type=checkbox]').getBoundingClientRect();
      const arrow = flag.querySelector('.lex-field-boolean-arrow');
      return {valueLeft: value.left, valueRight: value.right, checkLeft: check.left, checkRight: check.right,
        checkWidth: check.width, arrow: !!arrow && getComputedStyle(arrow).display !== 'none'};
    }''')


def test_box_style_fills_the_value_column_and_arrow_style_does_not(page):
    framework(page)
    box = _geometry(page, 'box')
    assert not box['arrow'], box
    assert abs(box['checkLeft'] - box['valueLeft']) <= 2 and abs(box['checkRight'] - box['valueRight']) <= 12, box
    arrow = _geometry(page, 'arrow')
    assert arrow['arrow'] and arrow['checkWidth'] < 30, arrow
