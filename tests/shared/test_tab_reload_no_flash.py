"""Re-rendering a list and detail page never shows a half-empty detail panel.

Lexer: "click the 'models' tab in ff8 while already on the tab, the entire
bottom 80% of the details panel disappears for a flash". The table's fit ran
before the fresh page was attached, read its grid as stacked, pinned no
heights and still marked the page as a pinned full-table page, which turns
off the rule that stretches the panes. The detail panel shrank to its content
until the next fit.
"""
from test_shared_ui_feedback import page, framework


def test_detail_panel_fills_its_row_from_the_first_frame(page):
    framework(page)
    page.evaluate('''() => {
      document.querySelector('main').style.height = '800px';
      const U = LexeditorUI, rows = Array.from({length: 120}, (_, id) => ({id, name: 'Model ' + id}));
      let state = {page: 0, selected: 3};
      window.render = () => {
        const view = U.pagedListDetail({id: 'flash-probe', rows, key: r => r.id, selected: state.selected,
          page: state.page, fit: {minRowHeight: 34}, change: next => { state = next; render(); },
          master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
            columns: [{key: 'name', label: 'Name'}]}),
          detail: r => U.detailPanel({title: r.name, body: [U.detailSection({title: 'DATA',
            body: Array.from({length: 10}, (_, i) => U.detailField({label: 'Field ' + i,
              control: U.el('input', {type: 'number', value: i})}))})]})});
        document.querySelector('main').replaceChildren(view);
        view.style.height = '800px';
      };
      render();
    }''')
    page.wait_for_timeout(1200)
    frames = page.evaluate('''async () => {
      const out = [];
      render();
      for (let i = 0; i < 8; i++) {
        await new Promise(resolve => requestAnimationFrame(resolve));
        const detail = document.querySelector('.lex-paged-list-detail > .lex-detail-panel');
        const master = document.querySelector('.lex-paged-list-detail > .lex-barrelled-master');
        out.push([Math.round(detail.getBoundingClientRect().height), Math.round(master.getBoundingClientRect().height)]);
      }
      return out;
    }''')
    for detail, master in frames:
        assert detail >= master - 2, frames
