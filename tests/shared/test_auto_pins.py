"""Every property of a list-and-detail page can be pinned as a table column.

Lexer: "THERE ARE NO FUCKING PINS ANYWHERE. ON ANY PROPERTIES." Pins existed
only where a plugin wired its own column preferences. The paged list now gives
every property one, and its table shows pinned properties as columns from the
row's values (row.values / row.display).
"""
from test_shared_ui_feedback import framework, page

PAGE = """(ownPins) => {
  const U = LexeditorUI;
  localStorage.clear();
  window.state = {selected: 1, page: 0};
  const rows = [
    {id: 1, name: 'Dagger', values: {power: 70, kind: 3}, display: {kind: 'Slash'}},
    {id: 2, name: 'Club', values: {power: 90, kind: 1}, display: {kind: 'Strike'}},
  ];
  const prefs = ownPins ? U.columnPreferences('own', [{key: 'id', label: 'ID'}, {key: 'name', label: 'Name'}]) : null;
  const render = () => document.querySelector('main').replaceChildren(U.pagedListDetail({
    rows, key: row => row.id, selected: state.selected, slots: false, noun: 'weapons',
    page: state.page, rowsKey: 'weapons', change: next => { state.page = next.page; render(); },
    master: ({rows: listed, selected, select}) => U.columnList({rows: listed, key: row => row.id, selected, select,
      columnPreferences: prefs || undefined,
      columns: [{key: 'id', label: 'ID'}, {key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.detailSection({title: 'Stats', body: [
      U.detailField({label: 'Power', property: 'power', control: U.el('input', {type: 'number', value: row.values.power})}),
      U.detailField({label: 'Kind', property: 'kind', control: U.el('input', {value: row.display.kind})})]})]}),
  }));
  render();
}"""


def headers(page):
    return [text.strip() for text in page.locator('[role="columnheader"]').all_inner_texts()]


def test_a_property_pins_into_the_table_with_its_shown_value(page):
    framework(page)
    page.evaluate(PAGE, False)
    page.wait_for_timeout(200)
    pins = page.locator('.lex-detail-field .lex-column-pin')
    assert pins.count() == 2
    page.locator('[data-lex-pin-column="kind"]').click(force=True)
    page.wait_for_timeout(200)
    assert "Kind" in headers(page), headers(page)
    assert page.locator('.lex-column-list').get_by_text("Strike").count() == 1
    assert page.locator('[data-lex-pin-column="kind"]').get_attribute("aria-pressed") == "true"
    # Unpinning takes the column away again.
    page.locator('[data-lex-pin-column="kind"]').click(force=True)
    page.wait_for_timeout(200)
    assert "Kind" not in headers(page)


def test_a_plugin_that_wires_its_own_pins_keeps_them(page):
    framework(page)
    page.evaluate(PAGE, True)
    page.wait_for_timeout(200)
    # Its own pins are its business; the paged list adds none, so none is dead.
    assert page.locator('[data-lex-auto-pin]').count() == 0
