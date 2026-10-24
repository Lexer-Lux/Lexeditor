"""Long headers wrap instead of widening their columns past the values.

A pinned column's width used to come from its property's name: headers were
single-line, so a long name forced a wide column. Headers now wrap, the
header row grows taller for them, and the column sizes to its values (or to
the longest header word, whichever runs wider).
"""
from test_shared_ui_feedback import framework, page

BUILD = """() => {
  const U = LexeditorUI;
  localStorage.clear();
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;width:360px;';
  const rows = [{id: 1, a: '1', b: '2', c: '3'}];
  main.replaceChildren(U.columnList({rows, key: row => row.id, selected: 1,
    template: 'minmax(min-content, 1fr) minmax(min-content, 1fr) minmax(min-content, 1fr)',
    columns: [
      {key: 'a', label: 'Equipment Weight Ratio Limit'},
      {key: 'b', label: 'Maximum Durability Threshold Value'},
      {key: 'c', label: 'Vagrant Evil Spirit Encounter Rate'},
    ]}));
}"""

STATE = """() => {
  const list = document.querySelector('.lex-column-list');
  const heads = [...list.querySelectorAll(':scope > .lex-column-list-header > .lex-column-list-head-cell')];
  const range = document.createRange();
  const lines = heads.map(head => {
    const label = head.querySelector('.header-label') || head;
    const walker = document.createTreeWalker(label, NodeFilter.SHOW_TEXT);
    let lines = 0;
    let node = walker.nextNode();
    while (node) {
      if (node.textContent.trim()) {
        range.selectNodeContents(node);
        lines = Math.max(lines,
          [...range.getClientRects()].filter(box => box.width > 1 && box.height > 1).length);
      }
      node = walker.nextNode();
    }
    return lines;
  });
  const full = heads.map(head => {
    const parts = [...head.querySelectorAll('.header-label, .lex-column-sort, .lex-column-heading')];
    const was = parts.map(part => part.style.whiteSpace);
    parts.forEach(part => { part.style.whiteSpace = 'nowrap'; });
    range.selectNodeContents(head.querySelector('.header-label') || head);
    const width = range.getBoundingClientRect().width;
    parts.forEach((part, index) => { part.style.whiteSpace = was[index]; });
    return width;
  });
  return {
    lines,
    widths: heads.map(head => head.getBoundingClientRect().width),
    full: full.map(Math.round),
    overflow: list.scrollWidth - list.clientWidth,
    headingTemplate: list.lexHeadingTemplate,
  };
}"""


def test_long_headers_wrap_and_columns_size_to_values(page):
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)
    state = page.evaluate(STATE)
    assert all(count >= 2 for count in state['lines']), state
    for width, full in zip(state['widths'], state['full']):
        assert width < full - 20, state
    assert state['overflow'] <= 1, state


def test_plain_text_tracks_shrink_to_min_content(page):
    framework(page)
    page.evaluate("""() => {
      const U = LexeditorUI;
      localStorage.clear();
      const main = document.querySelector('main');
      main.replaceChildren(U.columnList({rows: [{id: 1, name: 'x'}], key: row => row.id,
        selected: 1, columns: [{key: 'name', label: 'Name'}, {key: 'note', label: 'Note'}]}));
    }""")
    page.wait_for_timeout(300)
    template = page.evaluate(
        "() => document.querySelector('.lex-column-list').lexHeadingTemplate")
    assert 'minmax(min-content, 1fr)' in template, template
