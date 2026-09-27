"""A record's name wraps between words or at an identifier's own separators.

Names such as ADVERT_WHR_QUARTER_SHOES have no space, so a narrow heading
clipped them at the 14px floor; the name now breaks after `_` and `.`, and a
single word too long for the heading shrinks instead of being cut or split.
"""
from test_shared_ui_feedback import page, framework


def test_long_names_neither_clip_nor_break_inside_words(page):
    framework(page)
    names = ['ADVERT_WHR_QUARTER_SHOES', 'Mods.ExampleMod.Custom.Greeting',
             'Tri-Point Superlative Magic Cannon', 'Uncharacteristically']
    page.evaluate('''names => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start';
      for (const width of [180, 260]) for (const name of names) {
        const host = U.el('div', {style: `width:${width}px`});
        host.append(U.detailPanel({title: name, identity: '#115', body: []}));
        main.append(host);
      }
    }''', names)
    page.wait_for_timeout(400)
    rows = page.locator('.lex-detail-panel-name').evaluate_all('''nodes => nodes.map(node => {
      const text = node.textContent, panel = node.closest('.lex-detail-panel').getBoundingClientRect();
      const words = [];
      // Each run of letters must sit on one line.
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      for (let t; (t = walker.nextNode());) {
        const re = /[A-Za-z]+/g;
        for (let m; (m = re.exec(t.data));) {
          const range = document.createRange();
          range.setStart(t, m.index); range.setEnd(t, m.index + m[0].length);
          const tops = new Set([...range.getClientRects()].map(r => Math.round(r.top)));
          if (tops.size > 1) words.push(m[0]);
        }
      }
      const box = node.getBoundingClientRect();
      return {text, split: words, size: parseFloat(getComputedStyle(node).fontSize),
        clipped: node.scrollWidth > node.clientWidth + 1 || box.right > panel.right + 1};
    })''')
    assert [row['text'] for row in rows] == names * 2
    assert not [row for row in rows if row['split'] or row['clipped']], rows
    # An identifier wraps at its separators rather than shrinking to the floor.
    assert all(row['size'] >= 14 for row in rows if row['text'] != 'Uncharacteristically'), rows
