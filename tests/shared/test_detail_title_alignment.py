"""G13: an editable detail title aligns with the subtitle below it."""
from test_shared_ui_feedback import page, framework


def test_rename_title_aligns_with_meta(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      document.querySelector('main').append(U.detailPanel({
        title: 'Record Name', renameRecord: () => {}, meta: 'subtitle line'}));
      document.querySelector('main').append(U.detailPanel({
        title: 'Plain Record', meta: 'plain subtitle'}));
    }''')
    page.wait_for_selector('.lex-detail-panel-rename input')
    boxes = page.evaluate('''() => {
      const panels = [...document.querySelectorAll('.lex-detail-panel')];
      const textLeft = n => {
        const r = n.getBoundingClientRect(), cs = getComputedStyle(n);
        return r.left + parseFloat(cs.borderLeftWidth) + parseFloat(cs.paddingLeft);
      };
      return panels.map(p => ({
        title: textLeft(p.querySelector('.lex-detail-panel-title input')
          || p.querySelector('.lex-detail-panel-title')),
        meta: textLeft(p.querySelector('.lex-detail-panel-meta')),
      }));
    }''')
    assert len(boxes) == 2
    for row in boxes:
        assert abs(row['title'] - row['meta']) <= 1, boxes
