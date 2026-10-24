"""One column converges and stays put: no refit loop, no churning deal.

Reducing the detail to a single column used to flicker. The deal now
lands every section in the one lane, repeated refits change nothing,
and the page sits still afterwards: no refits, no mutations.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page  # noqa: F401,E402
from test_tab_rename import mount_shell  # noqa: E402
from test_detail_field_columns import set_columns  # noqa: E402

BUILD = """() => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  const rows = Array.from({length: 6}, (_, id) => ({id, name: 'Lot ' + id}));
  const fields = (tag, count) => Array.from({length: count}, (_, i) => U.detailField({
    label: `${tag} field ${i + 1} with a longish name`, property: `${tag}-${i + 1}`,
    control: U.el('input', {type: 'number', value: 0})}));
  const sections = () => [U.detailSection({title: 'Drop 1', body: fields('one', 8)}),
    U.detailSection({title: 'Drop 2', body: fields('two', 6)}),
    U.detailSection({title: 'Drop 3', body: fields('three', 6)}),
    U.detailSection({title: 'Drop 4', body: fields('four', 6)})];
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'lot', splitKey: 'one-column-settles', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Lot details',
      active: 'drops',
      tabs: [{id: 'drops', label: 'Drops'}],
      paginate: {unpaged: true}, content: sections()})]})}));
}"""

SECTIONS = """() => [...document.querySelectorAll('main .lex-tweaks-paged .lex-tweak-column')]
  .map(column => [...column.children]
    .map(section => section.querySelector('.lex-detail-section-title-text')?.textContent.trim()))"""


def test_one_column_deal_converges_and_settles(page):
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)
    set_columns(page, 1)
    assert page.evaluate(SECTIONS) == [["Drop 1", "Drop 2", "Drop 3", "Drop 4"]]
    before = page.evaluate(SECTIONS)
    page.evaluate("() => document.querySelector('main .lex-tweaks-paged').lexFitPage()")
    page.evaluate("() => document.querySelector('main .lex-tweaks-paged').lexFitPage()")
    assert page.evaluate(SECTIONS) == before
    page.evaluate("""() => {
      window.__fits = 0; window.__mut = 0;
      const pager = document.querySelector('main .lex-tweaks-paged');
      const fit = pager.lexFitPage.bind(pager);
      pager.lexFitPage = (...args) => { window.__fits++; return fit(...args); };
      new MutationObserver(records => { window.__mut += records.length; })
        .observe(document.querySelector('main'), {childList: true, subtree: true, attributes: true});
    }""")
    page.wait_for_timeout(1500)
    assert page.evaluate("({fits: window.__fits, mut: window.__mut})") == {"fits": 0, "mut": 0}
