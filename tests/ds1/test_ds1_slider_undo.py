"""Undo after a slider drag undoes exactly that drag.

A drag leaves focus on the page body (its handle is not focusable), so Ctrl+Z
reached two handlers - the plugin's and the shell's - and undid twice, while an
undo racing the commit queue popped an older entry. One Ctrl+Z now undoes one
edit wherever focus sits.
"""
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

DRAG = """(share) => {
  const input = document.querySelector('input[data-field-key="weight"]');
  const handle = input.closest('.lex-detail-field').querySelector('.lex-value-handle');
  const box = input.getBoundingClientRect(), grip = handle.getBoundingClientRect();
  handle.setPointerCapture = () => {};
  const at = clientX => ({bubbles: true, buttons: 1, pointerId: 41,
    clientX, clientY: box.top + box.height / 2});
  handle.dispatchEvent(new PointerEvent('pointerdown', {...at(grip.left + grip.width / 2),
    cancelable: true, button: 0}));
  for (let i = 1; i <= 12; i++)
    handle.dispatchEvent(new PointerEvent('pointermove', at(box.left + box.width * share * i / 12)));
  handle.dispatchEvent(new PointerEvent('pointerup', {...at(box.left + box.width * share),
    buttons: 0, button: 0}));
  return input.value;
}"""

STACKS = '({undo: fieldHistory.undoStack.length, redo: fieldHistory.redoStack.length})'
SETTLED = """(expected) => Math.abs(parseFloat(document.querySelector('input[data-field-key="weight"]').value) - expected) < 1e-4"""
VALUE = '''document.querySelector('input[data-field-key="weight"]').value'''


def test_one_undo_after_a_slider_drag_undoes_that_drag(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / texts.RELATIVE).parent.mkdir(parents=True)
    (game / texts.RELATIVE).write_bytes(make_text_archive())
    (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
    errors = []
    session.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.wait_for_function('!document.documentElement.classList.contains("lex-loading-live")')
                page.wait_for_selector('.lex-plugin-loading-screen', state='detached')
                page.wait_for_function('state.sub === "consumables" && state.row && state.row.id === 100')
                control = page.locator('input[data-field-key="weight"]')
                assert float(control.input_value()) == pytest.approx(0.0)
                assert page.evaluate(STACKS) == {'undo': 0, 'redo': 0}
                # T1: a typed edit plus a settled drag, then one body-focus
                # Ctrl+Z undoes only the drag.
                control.fill('0.2')
                control.press('Tab')
                page.wait_for_function('state.pending === 0 && fieldHistory.undoStack.length === 1')
                page.evaluate('document.activeElement.blur()')
                dragged = float(page.evaluate(DRAG, 0.9))
                assert abs(dragged - 0.2) > 0.01
                page.wait_for_function('state.pending === 0 && fieldHistory.undoStack.length === 2')
                assert page.evaluate('document.activeElement === document.body')
                page.keyboard.press('Control+Z')
                page.wait_for_function('fieldHistory.undoStack.length === 1 && fieldHistory.redoStack.length === 1')
                page.wait_for_function(SETTLED, arg=0.2)
                assert float(page.evaluate(VALUE)) == pytest.approx(0.2)
                # T2: an undo in the same task as a drag still undoes the
                # drag; the earlier entry survives.
                page.evaluate('''() => {
                  const input = document.querySelector('input[data-field-key="weight"]');
                  const handle = input.closest('.lex-detail-field').querySelector('.lex-value-handle');
                  const box = input.getBoundingClientRect(), grip = handle.getBoundingClientRect();
                  handle.setPointerCapture = () => {};
                  const at = clientX => ({bubbles: true, buttons: 1, pointerId: 41,
                    clientX, clientY: box.top + box.height / 2});
                  handle.dispatchEvent(new PointerEvent('pointerdown', {...at(grip.left + grip.width / 2),
                    cancelable: true, button: 0}));
                  handle.dispatchEvent(new PointerEvent('pointermove',
                    at(box.left + box.width * 0.5)));
                  handle.dispatchEvent(new PointerEvent('pointerup',
                    {...at(box.left + box.width * 0.5), buttons: 0, button: 0}));
                  return fieldHistory.undo();
                }''')
                page.wait_for_function('fieldHistory.undoStack.length === 1 && fieldHistory.redoStack.length === 1')
                page.wait_for_function(SETTLED, arg=0.2)
                assert float(page.evaluate(VALUE)) == pytest.approx(0.2)
                # T3: Ctrl+Z inside the input consumes exactly one entry.
                control.focus()
                page.keyboard.press('Control+Z')
                page.wait_for_function('fieldHistory.undoStack.length === 0')
                page.wait_for_function(SETTLED, arg=0.0)
                assert float(page.evaluate(VALUE)) == pytest.approx(0.0)
                assert page.evaluate(STACKS) == {'undo': 0, 'redo': 2}
                # T3b: Ctrl+Y with body focus redoes exactly one entry.
                page.evaluate('document.activeElement.blur()')
                page.keyboard.press('Control+Y')
                page.wait_for_function('fieldHistory.undoStack.length === 1 && fieldHistory.redoStack.length === 1')
                page.wait_for_function(SETTLED, arg=0.2)
                assert float(page.evaluate(VALUE)) == pytest.approx(0.2)
                # T4: the Undo button restores a dragged value too.
                page.evaluate(DRAG, 0.3)
                page.wait_for_function('state.pending === 0 && fieldHistory.undoStack.length === 2')
                page.locator('#global-undo').click()
                page.wait_for_function('fieldHistory.undoStack.length === 1 && fieldHistory.redoStack.length === 1')
                page.wait_for_function(SETTLED, arg=0.2)
                assert float(page.evaluate(VALUE)) == pytest.approx(0.2)
                page.locator('#global-save').click()
                page.wait_for_function('state.dirty === 0 && state.pending === 0')
            finally:
                browser.close()
    finally:
        session.stop()
    assert errors == []
