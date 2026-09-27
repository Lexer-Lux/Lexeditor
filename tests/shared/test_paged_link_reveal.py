"""A link into a paged list reveals its record, even from a list sharing the key.

FF8's World subtabs share one list key. A link from the Cells page (page 16)
to ground type 24 (page 2 of another list) rendered page 0 and dropped the
selection, because the page change read as the reader paging on purpose. A
link now passes page null: no page was asked for, so the record is shown.
"""
from test_shared_ui_feedback import page, framework


def render(page, rows, selected, start_page):
    return page.evaluate('''([count, selected, startPage]) => {
      const U = LexeditorUI, rows = Array.from({length: count}, (_, id) => ({id, name: 'Row ' + id}));
      const host = document.querySelector('main');
      host.replaceChildren(U.pagedListDetail({rows, key: r => r.id, selected, page: startPage, pageSize: 10,
        splitKey: 'shared-key', slots: false, search: {value: '', input() {}},
        master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
          columns: [{key: 'name', label: 'Name'}]}),
        detail: r => U.detailPanel({title: r.name})}));
      return document.querySelector('.lex-detail-panel-title').textContent;
    }''', [rows, selected, start_page])


def test_null_page_reveals_the_linked_record(page):
    framework(page)
    render(page, 300, 165, 16)          # the first list, on a late page
    assert render(page, 30, 24, None).startswith('Row 24')


def test_a_page_the_reader_chose_still_wins(page):
    framework(page)
    render(page, 300, 165, 16)
    assert not render(page, 30, 24, 0).startswith('Row 24')
