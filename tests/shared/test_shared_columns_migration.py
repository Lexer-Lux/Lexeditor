"""A retired shared column count moves down into the open subtab's own key.

Each subtab keeps its own manually-set count now. A count saved under
the retired shared key moves into the open subtab's key once and the
shared key goes away from every store; a subtab with its own count
keeps it and leaves the shared key for its siblings; fresh readers
keep the fitted default with nothing written.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page  # noqa: F401,E402

BUILD = """(active) => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  const rows = [{id: 0, name: 'Lot 0'}];
  main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'lot', legacyColumnsKey: 'test-shared-columns', slots: false, pageSize: 6,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
      select: v.select, columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Lot',
      active, tabs: [{id: 'defense', label: 'Defense'}, {id: 'basics', label: 'Basics'}],
      paginate: {unpaged: true},
      content: () => U.detailSection({title: 'Fields', body: [
        U.detailField({label: 'Weight', property: 'w',
          control: U.el('input', {type: 'number', value: 0})})]})})]})}));
}"""

PLAIN_BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  const rows = [{id: 0, name: 'Lot 0'}];
  main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'lot', legacyColumnsKey: 'test-shared-columns', slots: false, pageSize: 6,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
      select: v.select, columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [
      U.detailField({label: 'Weight', property: 'w',
        control: U.el('input', {type: 'number', value: 0})})]})}));
}"""

STATE = """() => {
  const control = document.querySelector('main .lex-detail-column-control .lex-barrel-count');
  const keys = {};
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key.startsWith('lexeditor:columns:'))
      keys[key.slice('lexeditor:'.length)] = localStorage.getItem(key);
  }
  const rendered = [...document.querySelectorAll('main .lex-tweak-column')].filter(c => c.offsetParent).length;
  return {shown: control && Number(control.textContent), rendered, keys};
}"""


def seed(page, entries):
    for key, value in entries.items():
        page.evaluate(f"localStorage.setItem('lexeditor:{key}', '{value}')")


def test_shared_count_moves_into_the_open_subtab(page):
    framework(page)
    seed(page, {'columns:test-shared-columns': 4})
    page.evaluate(BUILD, 'defense')
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['shown'] == 4, state
    assert state['keys'] == {'columns:lot:defense': '4'}, state


def test_own_count_wins_and_leaves_legacy_for_siblings(page):
    framework(page)
    seed(page, {'columns:test-shared-columns': 4, 'columns:lot:defense': 2})
    page.evaluate(BUILD, 'defense')
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['shown'] == 2, state
    assert state['keys'] == {'columns:lot:defense': '2',
                             'columns:test-shared-columns': '4'}, state


def test_shared_count_moves_into_the_base_key_without_subtabs(page):
    framework(page)
    seed(page, {'columns:test-shared-columns': 5})
    page.evaluate(PLAIN_BUILD)
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['shown'] == 5, state
    assert state['keys'] == {'columns:lot': '5'}, state


def test_fresh_reader_keeps_fitted_default_unwritten(page):
    framework(page)
    page.evaluate(BUILD, 'defense')
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['rendered'] >= 1, state
    assert state['keys'] == {}, state
