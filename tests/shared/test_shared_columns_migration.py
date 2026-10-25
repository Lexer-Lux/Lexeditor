"""Per-subtab column counts migrate up to the shared key once.

Callers that show the same fields under several subtabs share one count;
counts saved under older per-subtab keys move up on first mount: the
current subtab's wins, else the largest dead one, and the dead keys go
away. A shared count already saved wins over the dead ones, and fresh
readers keep the fitted default with nothing written.
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
    noun: 'lot', columnsKey: 'test-shared-columns', slots: false, pageSize: 6,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
      select: v.select, columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Lot',
      active, tabs: [{id: 'defense', label: 'Defense'}, {id: 'basics', label: 'Basics'}],
      paginate: {unpaged: true},
      content: () => U.detailSection({title: 'Fields', body: [
        U.detailField({label: 'Weight', property: 'w',
          control: U.el('input', {type: 'number', value: 0})})]})})]})}));
}"""

STATE = """() => {
  const control = document.querySelector('main .lex-detail-column-control .lex-barrel-count');
  const keys = {};
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key.startsWith('lexeditor:columns:test-shared-columns'))
      keys[key.slice('lexeditor:'.length)] = localStorage.getItem(key);
  }
  const rendered = [...document.querySelectorAll('main .lex-tweak-column')].filter(c => c.offsetParent).length;
  return {shown: control && Number(control.textContent), rendered, keys};
}"""


def seed(page, entries):
    for key, value in entries.items():
        page.evaluate(f"localStorage.setItem('lexeditor:{key}', '{value}')")


def test_current_subtab_count_wins(page):
    framework(page)
    seed(page, {'columns:test-shared-columns:defense': 4,
                'columns:test-shared-columns:basics': 3})
    page.evaluate(BUILD, 'defense')
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['shown'] == 4, state
    assert state['keys'] == {'columns:test-shared-columns': '4'}, state


def test_largest_dead_count_wins_without_current(page):
    framework(page)
    seed(page, {'columns:test-shared-columns:basics': 3,
                'columns:test-shared-columns:combat': 5})
    page.evaluate(BUILD, 'defense')
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['shown'] == 5, state
    assert state['keys'] == {'columns:test-shared-columns': '5'}, state


def test_saved_shared_count_wins_over_dead(page):
    framework(page)
    seed(page, {'columns:test-shared-columns': 2,
                'columns:test-shared-columns:defense': 4})
    page.evaluate(BUILD, 'defense')
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['shown'] == 2, state
    assert state['keys'] == {'columns:test-shared-columns': '2'}, state


def test_fresh_reader_keeps_fitted_default_unwritten(page):
    framework(page)
    page.evaluate(BUILD, 'defense')
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert state['rendered'] >= 1, state
    assert state['keys'] == {}, state
