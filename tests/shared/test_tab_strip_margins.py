"""Page tabs hug their names, share one size, and do not scroll at 1024px.

Lexer: "the amount of side margin on tab names is still obscenely huge. like
on the ff8 tweaks tab, the 'Tweaks' text takes up only like half the width of
the tab!" and "horizontal scroll bar -- this should never happen... one row.
always. no scrollbar." Equal 1fr shares padded short names out to the widest
share, FF8's theme padded each side by .75vw, and a tab added after the fit
kept the theme's base size.
"""
import re

import pytest

from test_shared_ui_feedback import ROOT, page, framework


def _mount(page, width):
    boot = (ROOT / 'plugins/ff8/boot.js').read_text(encoding='utf-8')
    tabs = boot[boot.index('tabs:[['):boot.index('].map(([id,label])=>({id,label}))')]
    labels = [label for key, label in re.findall(r'\["([a-z0-9_]+)","([^"]+)"\]', tabs)
              if key != 'starting']  # New Game is hidden unless a setting shows it
    page.set_viewport_size({'width': width, 'height': 900})
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    page.evaluate('''labels => {
      const U = LexeditorUI;
      document.body.prepend(U.el('div', {id: 'shell'}));
      U.mountShell({host: '#shell', brand: 'LEXEDITOR', plugin: {id: 'fixture', name: 'Fixture'},
        tabs: labels.map(label => ({id: label === 'Tweaks' ? 'settings' : label, label})),
        activeTab: () => 'Cards', navigate() {}});
      U.finishPluginLoading();
    }''', labels)
    page.wait_for_timeout(500)
    return page.evaluate('''() => {
      const nav = document.querySelector('.lex-shell-header nav'), frame = nav.parentElement;
      const buttons = [...nav.querySelectorAll('button[data-tab]')];
      return {scrolls: frame.scrollWidth > frame.clientWidth + 1,
        sizes: [...new Set(buttons.map(b => getComputedStyle(b.querySelector('.lex-tab-label-text')).fontSize))],
        names: buttons.map(b => b.dataset.tab), shares: buttons.map(b => {
          const range = document.createRange();
          range.selectNodeContents(b.querySelector('.lex-tab-label-text'));
          return range.getBoundingClientRect().width / b.getBoundingClientRect().width;
        })};
    }''')


@pytest.mark.parametrize('width,share', [(1024, .4), (1600, .5)])
def test_tabs_fit_in_one_row_with_even_margins(page, width, share):
    strip = _mount(page, width)
    assert not strip['scrolls'], strip
    assert len(strip['sizes']) == 1, strip
    # At 1024 the names are at the readable floor and what room is left is
    # shared evenly, so the shortest name (GFs) gets the most air.
    assert min(strip['shares']) >= share, sorted(zip(strip['shares'], strip['names']))[:4]
