"""Typing a row count in the pager and pressing Enter visibly does something.

Lexer: "if i enter a different number in the rows number on the pagination
bar then hit enter...nothing happens". A count under what fits applied; a
count over it was saved and quietly capped, so Enter looked dead. The box is
now bounded by what fits and says so when it clamps, and one Enter commits once.
"""
from test_shared_ui_feedback import page, framework


def _table(page):
    framework(page)
    page.evaluate('''() => {
      document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
      LexeditorUI.mountShell({host: '#shell', plugin: {id: 'fixture', name: 'Fixture'}, tabs: [],
        activeTab: () => '', navigate: () => {}});
      dispatchEvent(new CustomEvent('lexeditor-settings-changed',
        {detail: {developerMode: true, tableRowsPerPage: 15, viewPreferences: {}}}));
      const U = LexeditorUI, rows = Array.from({length: 80}, (_, id) => ({id, name: 'Row ' + id}));
      window.changes = [];
      let state = {page: 0, selected: 0};
      const render = () => {
        const view = U.pagedListDetail({id: 'rows-probe', rows, key: r => r.id,
          selected: state.selected, page: state.page, fit: {minRowHeight: 34},
          change: next => { changes.push(next.reason + ':' + next.pageSize); state = next; render(); },
          master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
            columns: [{key: 'name', label: 'Name'}]}),
          detail: r => U.detailPanel({title: r.name})});
        document.querySelector('main').replaceChildren(view);
        view.style.height = '700px';
      };
      render();
    }''')
    page.wait_for_timeout(600)


def _type_rows(page, value):
    box = page.locator('.lex-page-row-override input')
    box.click()
    box.fill(str(value))
    box.press('Enter')
    page.wait_for_timeout(600)


def test_row_count_applies_once_and_explains_a_cap(page):
    _table(page)
    rows = lambda: page.locator('.lex-column-list-row').count()
    _type_rows(page, 8)
    assert rows() == 8
    assert page.evaluate('changes') == ['table-rows:8'], 'one Enter, one commit'

    _type_rows(page, 60)
    fits = rows()
    assert 8 < fits < 60
    toasts = page.locator('.lex-toast').all_text_contents()
    assert toasts and f'Only {fits} rows fit' in toasts[-1], toasts

    box = page.locator('.lex-page-row-override input')
    assert box.get_attribute('max') == str(fits), 'the box is bounded by what fits'
    assert box.input_value() == str(fits)
