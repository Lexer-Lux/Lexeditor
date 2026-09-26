"""A subtab with a help mark keeps its full text size when there is room.

On FF8's GFs, Attack, Defaults, Leveling and Spellbook were drawn at the 8.66px
floor in tabs ten times wider than their names, beside ABILITIES at 16.66px.
A tab with a help mark hugs its label to the text, and the fitter measured the
text against that same box, 3px short of which it could never fit.
"""
from test_shared_ui_feedback import page, framework


def test_help_marked_subtab_labels_are_not_shrunk_in_a_wide_bar(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, box = U.el('div', {style: 'width:700px'});
      document.querySelector('main').append(box);
      box.append(U.subtabBar({active: 'plain', change() {}, tabs: [
        {id: 'plain', label: 'Abilities'},
        {id: 'helped', label: 'Spellbook', help: 'What the spellbook holds.'}]}));
    }''')
    page.wait_for_timeout(500)
    sizes = page.evaluate('''() => [...document.querySelectorAll('.lex-subtab-button .lex-tab-label-text')]
      .map(label => parseFloat(getComputedStyle(label).fontSize))''')
    assert len(sizes) == 2 and abs(sizes[0] - sizes[1]) < .5, sizes
