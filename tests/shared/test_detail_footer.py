"""Paginated detail flows: one page needs no footer pager.

FF8's item details showed a stray "1-2/2" block under sections that all
fit on one page. The footer pager exists to turn pages; with a single
page and no search it carries only a summary, so it renders nothing.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401

BUILD = """([count, mainHeight]) => {
  const U = LexeditorUI;
  const section = title => U.detailSection({title,
    body: [U.detailField({label: title, control: U.el('input', {value: 1})})]});
  const main = document.querySelector('main');
  main.style.cssText = `display:block;height:${mainHeight}px`;
  const panel = U.detailPanel({title: 'Record',
    body: Array.from({length: count}, (_, index) => section('Section ' + index))});
  panel.style.height = '100%';
  main.replaceChildren(panel);
}"""


def test_a_single_page_detail_renders_no_footer_pager(page):
    framework(page)
    page.evaluate(BUILD, [2, 760])
    page.wait_for_selector(".lex-tweaks-paged")
    page.wait_for_timeout(400)
    assert page.locator(".lex-detail-panel .lex-pager").count() == 0


def test_a_multi_page_detail_keeps_its_footer_pager(page):
    framework(page)
    page.evaluate(BUILD, [30, 300])
    page.wait_for_selector(".lex-detail-panel .lex-pager", timeout=5000)
