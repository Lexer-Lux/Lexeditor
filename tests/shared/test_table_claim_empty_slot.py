"""A slot table that knows its empty slots fills the next one from Add.

Lexer: "everything in FF8 has no ability to hit the plus button on the table.
says there's no space. okay, but i distinctly remember you saying that there
were empty slots for things?" A slot table given `empty` and `add` hands Add
its first empty slot, turns Hide empty off so that slot shows, and says why
when every slot is in use.
"""
from test_shared_ui_feedback import page, framework


def mount(page, empties, hide=False):
    page.evaluate('''([empties, hide]) => {
      const U = LexeditorUI, rows = Array.from({length: 12}, (_, id) => ({id, name: empties.includes(id) ? '' : 'Row ' + id}));
      try { hide ? localStorage.setItem('hide-empty:claim-test', '1') : localStorage.removeItem('hide-empty:claim-test'); } catch (_) {}
      window.claimed = [];
      const main = document.querySelector('main');
      main.style.height = '600px';
      main.replaceChildren(U.pagedListDetail({rows, key: r => r.id, selected: 0, noun: 'slots', rowsKey: 'claim-test',
        slots: true, empty: r => !r.name, add: slot => window.claimed.push(slot && slot.id),
        master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
          columns: [{key: 'name', label: 'Name'}]}),
        detail: r => U.detailPanel({title: r.name || 'Empty'})}));
    }''', [empties, hide])
    page.wait_for_timeout(200)


def test_add_hands_over_the_first_empty_slot(page):
    framework(page)
    mount(page, [4, 9])
    button = page.locator('.lex-table-add')
    assert button.get_attribute('aria-disabled') is None
    assert page.locator('.lex-hide-empty').count() == 1
    button.click(force=True)
    assert page.evaluate('window.claimed') == [4]


def test_add_lets_go_of_hide_empty(page):
    framework(page)
    mount(page, [4, 9], hide=True)
    page.locator('.lex-table-add').click(force=True)
    assert page.evaluate('window.claimed') == [4]
    assert page.evaluate("localStorage.getItem('hide-empty:claim-test')") is None


def test_full_slot_table_says_why(page):
    framework(page)
    mount(page, [])
    button = page.locator('.lex-table-add')
    assert button.get_attribute('aria-disabled') == 'true'
    assert 'Every slot in this table is in use' in button.get_attribute('aria-label')
    button.click(force=True)
    assert page.evaluate('window.claimed') == []
