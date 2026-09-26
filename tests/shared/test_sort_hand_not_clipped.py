"""A picture sort mark is drawn whole, even in a table's leftmost column.

Lexer, on FF8: "the pointer finger still doesn't fucking show when i click the
column", and on Field exits, "i can only see a few pixels of the finger
pointer b/c it's cut off". FF8 marks the sorted column with its pointing hand,
hung to the left of the header's label. In the leftmost column it hung off
the table's edge, and with a help mark the label and its sort button clipped
it as well.
"""
from test_shared_ui_feedback import ROOT, page, framework


def test_hand_fits_inside_the_table_and_is_not_clipped(page):
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, rows = Array.from({length: 5}, (_, id) => ({id, name: 'Row ' + id}));
      document.querySelector('main').append(U.columnList({rows, key: r => r.id, selected: 0,
        sortState: {key: 'group', dir: 1}, sort() {},
        columns: [{key: 'group', label: 'Group', help: 'Which group.', sort: r => r.id, align: 'start'},
                  {key: 'name', label: 'Name', sort: r => r.name}]}));
    }''')
    page.wait_for_timeout(200)
    geometry = page.evaluate('''() => {
      const hand = document.querySelector('.lex-column-list-head-cell.sorted .lex-sort-indicator');
      const table = hand.closest('.lex-column-list').getBoundingClientRect(), r = hand.getBoundingClientRect();
      const clips = [hand.closest('.header-label'), hand.closest('.lex-column-sort'), hand.closest('.lex-column-list-head-cell')]
        .filter(Boolean).map(node => {
          const box = node.getBoundingClientRect(), style = getComputedStyle(node);
          const room = style.overflow === 'visible' ? Infinity : parseFloat(style.overflowClipMargin) || 0;
          return r.left >= box.left - room - 1;
        });
      return {inTable: r.left >= table.left - 1 && r.right <= table.right + 1, width: r.width, unclipped: clips.every(Boolean)};
    }''')
    assert geometry['inTable'] and geometry['unclipped'] and geometry['width'] > 15, geometry
