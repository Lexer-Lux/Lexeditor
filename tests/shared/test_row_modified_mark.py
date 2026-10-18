"""Changed rows are marked everywhere: color plus a delta, new rows keep the pen."""
from test_shared_ui_feedback import page, framework

MOUNT = '''() => {
  const U = LexeditorUI;
  document.querySelector('main').append(U.columnList({
    columns: [{key: 'name', label: 'Name'}],
    rows: [{id: 1, name: 'Plain'}, {id: 2, name: 'Edited', modified: true},
      {id: 3, name: 'Added', created: true, modified: true}],
    key: row => row.id, selected: null, select: () => {}}));
}'''


def row_named(page, name):
    return page.locator('.lex-list-row', has_text=name)


def test_modified_row_wears_color_and_delta(page):
    framework(page)
    page.evaluate(MOUNT)
    row = row_named(page, 'Edited')
    assert 'lex-record-modified' in (row.get_attribute('class') or '')
    mark = row.locator('.lex-record-source')
    assert mark.count() == 1
    assert mark.first.inner_text() == '\u0394'
    assert mark.first.get_attribute('title') == 'Changed from vanilla'


def test_created_row_keeps_pen_not_delta(page):
    framework(page)
    page.evaluate(MOUNT)
    mark = row_named(page, 'Added').locator('.lex-record-source')
    assert mark.count() == 1
    assert mark.first.inner_text() == '\u2712\ufe0f'


def test_plain_row_has_no_mark(page):
    framework(page)
    page.evaluate(MOUNT)
    row = row_named(page, 'Plain')
    assert 'lex-record-modified' not in (row.get_attribute('class') or '')
    assert row.locator('.lex-record-source').count() == 0


def test_modified_predicate_marks_without_row_flags(page):
    framework(page)
    page.evaluate('''() => {
      document.querySelector('main').append(LexeditorUI.columnList({
        columns: [{key: 'name', label: 'Name'}],
        rows: [{id: 1, name: 'Plain'}, {id: 2, name: 'Edited'}],
        modified: row => row.id === 2,
        key: row => row.id, selected: null, select: () => {}}));
    }''')
    row = row_named(page, 'Edited')
    assert 'lex-record-modified' in (row.get_attribute('class') or '')
    assert row.locator('.lex-record-source').first.inner_text() == '\u0394'
    assert row_named(page, 'Plain').locator('.lex-record-source').count() == 0
