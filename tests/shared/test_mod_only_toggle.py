"""The shared Mod contents toggle: filter contract and disabled state.

Every game's record list offers the same toggle on its pagination bar.
An unavailable plugin (no vanilla baseline loaded) renders the toggle
disabled with its reason; an available one filters to changed records.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

BUILD = """(spec) => {
  const U = LexeditorUI;
  const rows = [{id: 1, name: 'Kept'}, {id: 2, name: 'Cut'}];
  const view = U.pagedListDetail({
    rows, key: row => row.id, slots: false, noun: 'records',
    splitKey: 'shared-mod-only', rowsKey: 'shared-mod-only',
    page: 0, pageSize: 10, selected: 1,
    modOnly: {
      available: spec.available,
      value: spec.value === true,
      changed: row => row.id === 1,
      unavailableTitle: spec.reason,
      change: value => { window.__modOnly = value; },
    },
    master: ({rows: shown, selected, select}) => U.el('div', {},
      ...shown.map(row => U.el('div', {class: 'lex-list-row', 'data-key': row.id}, row.name))),
    detail: row => U.el('div', {}, 'detail ' + row.id),
  });
  document.querySelector('main').replaceChildren(view);
}"""


def test_an_unavailable_toggle_is_disabled_with_its_reason(page):
    framework(page)
    page.evaluate(BUILD, {'available': False, 'reason': 'No vanilla copy yet.'})
    toggle = page.locator('.lex-pager-toggle input[aria-label="Mod contents only"]')
    assert toggle.count() == 1
    assert toggle.is_disabled()
    assert toggle.locator('xpath=..').get_attribute('title') == 'No vanilla copy yet.'
    assert page.locator('.lex-list-row').count() == 2


def test_an_available_toggle_filters_to_changed_records(page):
    framework(page)
    page.evaluate(BUILD, {'available': True, 'value': True})
    toggle = page.locator('.lex-pager-toggle input[aria-label="Mod contents only"]')
    assert toggle.count() == 1
    assert toggle.is_enabled()
    assert toggle.is_checked()
    rows = page.locator('.lex-list-row')
    assert rows.count() == 1
    assert rows.first.inner_text() == 'Kept'
    toggle.uncheck()
    assert page.evaluate('window.__modOnly') is False
