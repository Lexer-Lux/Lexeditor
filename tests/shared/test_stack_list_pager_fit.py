"""A filled list keeps its stack pager pinned inside the panel."""
from test_shared_ui_feedback import page, framework


def test_filled_list_pins_the_pager(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      const rows = [];
      for (let i = 0; i < 25; i++) rows.push({id: i, name: 'Record ' + i});
      const view = U.stack(
        U.bottomSearch({key: 'probe', value: '', label: 'Search', change: () => {}}),
        U.columnList({rows, key: r => r.id, selected: 0, class: 'lex-list-fill',
          columns: [{key: 'name', label: 'Name', grow: 1}]}),
        U.pager({inline: true, pages: 57, page: 0, total: 1425, pageSize: 25, change: () => {}}));
      view.style.width = '360px';
      view.style.height = '500px';
      view.setAttribute('data-probe', '1');
      document.querySelector('main').append(view);
    }''')
    page.wait_for_timeout(400)
    box = page.evaluate('''() => {
      const panel = document.querySelector('[data-probe]').getBoundingClientRect();
      const pager = document.querySelector('[data-probe] .lex-pager').getBoundingClientRect();
      const list = document.querySelector('[data-probe] .lex-column-list');
      return {panelBottom: panel.bottom, pagerBottom: pager.bottom,
              scroll: list.scrollHeight, client: list.clientHeight};
    }''')
    assert box['pagerBottom'] <= box['panelBottom'] + 1, box
    assert box['scroll'] > box['client'], box
