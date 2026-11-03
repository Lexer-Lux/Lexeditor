"""Typing a row count in the pager and pressing Enter visibly does something.

Lexer: "if i enter a different number in the rows number on the pagination
bar then hit enter...nothing happens". A count over what fits was saved
and quietly capped, so Enter looked dead. The box now takes 5 to 80 rows;
more rows than fit shrink to fit without scrolling, and one Enter commits once.
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
      const U = LexeditorUI, rows = Array.from({length: 200}, (_, id) => ({id, name: 'Row ' + id}));
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


def test_row_count_applies_once_and_allows_above_the_fit(page):
    _table(page)
    rows = lambda: page.locator('.lex-column-list-row').count()
    _type_rows(page, 8)
    assert rows() == 8
    assert page.evaluate('changes') == ['table-rows:8'], 'one Enter, one commit'

    _type_rows(page, 60)
    assert rows() == 60, 'a high count applies instead of capping to the fit'
    height = page.locator('.lex-column-list-row').first.bounding_box()['height']
    assert height < 33, f'rows shrink to fit, got {height}'
    # Paginated content never scrolls: squeezed rows must not gain an
    # overflow that can render a scrollbar (sub-pixel residue aside).
    overflows = page.evaluate('''() => {
      const lists = [...document.querySelectorAll('.lex-column-list')];
      return lists.filter(n => n.querySelectorAll('.lex-column-list-row').length == 60)
        .map(n => { const s = getComputedStyle(n); return s.overflowY + '/' + s.overflowX; });
    }''')
    assert overflows and all(value in ('visible/visible', 'hidden/hidden')
                               for value in overflows), overflows

    box = page.locator('.lex-page-row-override input')
    assert box.get_attribute('max') == '80', 'the box runs to 80, not the fit'
    assert box.input_value() == '60'


def test_row_count_over_80_clamps_with_an_explanation(page):
    _table(page)
    _type_rows(page, 120)
    assert page.locator('.lex-column-list-row').count() == 80
    toasts = page.locator('.lex-toast').all_text_contents()
    assert toasts and 'At most 80 rows' in toasts[-1], toasts
    assert page.locator('.lex-page-row-override input').input_value() == '80'
