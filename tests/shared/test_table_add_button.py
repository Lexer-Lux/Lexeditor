"""Every paged table has one round add button in its bottom-right corner.

Lexer: "instead of in the pagination tab, each table tab should have an add
button in the bottom right. partial opacity until hovered over. can be enabled
or disabled. if disabled, it says why... every game, every list should have
it. oh and it should be circular."
"""
import pytest

from test_shared_ui_feedback import page, framework


@pytest.mark.parametrize('kind', ['addable', 'slots', 'unsupported'])
def test_table_add_button(page, kind):
    framework(page)
    page.evaluate('''kind => {
      const U = LexeditorUI, rows = Array.from({length: 20}, (_, id) => ({id, name: 'Row ' + id}));
      U.installControlHelp(document.body);  // the shell does this when it mounts
      window.added = 0;
      document.querySelector('main').style.height = '600px';
      const view = U.pagedListDetail({rows, key: r => r.id, selected: 0, noun: 'rows',
        slots: kind === 'slots', add: kind === 'addable' ? () => { window.added += 1; } : undefined,
        master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
          columns: [{key: 'name', label: 'Name'}]}),
        detail: r => U.detailPanel({title: r.name})});
      document.querySelector('main').append(view);
      view.style.height = '600px';
    }''', kind)
    page.wait_for_timeout(300)
    button = page.locator('.lex-barrelled-master > .lex-table-add')
    assert button.count() == 1
    assert page.locator('.lex-pager .lex-new-button').count() == 0, 'no second add button in the pager'
    shape = button.evaluate('''b => {
      const r = b.getBoundingClientRect(), m = b.parentElement.getBoundingClientRect(), s = getComputedStyle(b);
      return {round: s.borderRadius, rightGap: m.right - r.right, bottomGap: m.bottom - r.bottom,
              opacity: parseFloat(s.opacity), square: Math.abs(r.width - r.height) < 1};
    }''')
    assert shape['round'] == '50%' and shape['square'], shape
    assert 0 <= shape['rightGap'] <= 16 and 0 <= shape['bottomGap'] <= 16, shape
    assert shape['opacity'] == 0, 'out of sight until the table is pointed at'
    page.locator('.lex-barrelled-master').hover(position={'x': 20, 'y': 60})
    page.wait_for_timeout(250)
    assert .2 < float(button.evaluate('b => getComputedStyle(b).opacity')) < .6, 'faint over the table'
    button.hover(force=True)
    page.wait_for_timeout(250)
    assert float(button.evaluate('b => getComputedStyle(b).opacity')) > .8
    button.click(force=True)
    page.wait_for_timeout(200)
    if kind == 'addable':
        assert page.evaluate('window.added') == 1
        assert button.get_attribute('aria-disabled') is None
    else:
        # Pointing at it says why, before any click.
        page.locator('.lex-barrelled-master').hover(position={'x': 20, 'y': 60})
        button.hover(force=True)
        page.wait_for_selector('.lex-hover-tip')
        assert ('fixed set of slots' if kind == 'slots' else 'not supported yet') in page.locator('.lex-hover-tip').inner_text()
        assert page.evaluate('window.added') == 0
        assert button.get_attribute('aria-disabled') == 'true'
        why = page.locator('.lex-toast').last.inner_text()
        assert ('fixed set of slots' if kind == 'slots' else 'not supported yet') in why, why


@pytest.mark.parametrize('enabled', [True, False])
def test_a_plugins_own_add_button_moves_to_the_corner(page, enabled):
    # RDR2 builds its "Create new item" button itself and hands it over with
    # the pager's filters; the table takes that one rather than adding another.
    framework(page)
    page.evaluate('''enabled => {
      const U = LexeditorUI, rows = Array.from({length: 8}, (_, id) => ({id, name: 'Row ' + id}));
      window.created = 0;
      const own = U.newButton({title: 'Create new item', disabled: !enabled, onclick: () => { window.created += 1; }});
      document.querySelector('main').append(U.pagedListDetail({rows, key: r => r.id, selected: 0, slots: false,
        filters: [own], master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected,
          columns: [{key: 'name', label: 'Name'}]}), detail: r => U.detailPanel({title: r.name})}));
    }''', enabled)
    page.wait_for_timeout(300)
    assert page.locator('.lex-new-button').count() == 1
    button = page.locator('.lex-barrelled-master > .lex-table-add')
    assert button.count() == 1
    button.click(force=True)
    page.wait_for_timeout(200)
    assert page.evaluate('window.created') == (1 if enabled else 0)


def test_read_only_vanilla_says_to_create_a_mod(page):
    framework(page)
    page.evaluate('''() => {
      document.documentElement.dataset.lexProjectReadonly = 'true';
      const U = LexeditorUI, rows = Array.from({length: 8}, (_, id) => ({id, name: 'Row ' + id}));
      window.added = 0;
      document.querySelector('main').append(U.pagedListDetail({rows, key: r => r.id, selected: 0, slots: false,
        add: () => { window.added += 1; }, master: v => U.columnList({rows: v.rows, key: r => r.id,
          selected: v.selected, columns: [{key: 'name', label: 'Name'}]}), detail: r => U.detailPanel({title: r.name})}));
    }''')
    page.wait_for_timeout(300)
    page.locator('.lex-table-add').click(force=True)
    page.wait_for_timeout(200)
    assert page.evaluate('window.added') == 0
    assert 'Create a mod' in page.locator('.lex-toast').last.inner_text()
