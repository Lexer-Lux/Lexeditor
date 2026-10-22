"""Blanking a record rename puts the shipped name back, never an empty one."""
from test_shared_ui_feedback import page, framework


def test_blank_rename_commits_shipped_name(page):
    framework(page)
    page.evaluate("""() => {
      window.__committed = [];
      const node = LexeditorUI.el('span', {}, 'Mod Sword');
      document.querySelector('main').append(node);
      const input = LexeditorUI.renameValue(node,
        {value: 'Mod Sword', label: 'this record', shipped: 'Longsword',
         commit: name => window.__committed.push(name)});
      input.value = '';
      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    }""")
    assert page.evaluate("window.__committed") == ['Longsword']
    assert page.locator('main span').first.inner_text() == 'Longsword'


def test_blank_rename_without_shipped_commits_nothing(page):
    framework(page)
    page.evaluate("""() => {
      window.__committed = [];
      const node = LexeditorUI.el('span', {}, 'Mod Sword');
      document.querySelector('main').append(node);
      const input = LexeditorUI.renameValue(node,
        {value: 'Mod Sword', label: 'this record',
         commit: name => window.__committed.push(name)});
      input.value = '';
      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    }""")
    assert page.evaluate("window.__committed") == []
    assert page.locator('main span').first.inner_text() == 'Mod Sword'


def test_name_cell_blank_restores_shipped_name(page):
    framework(page)
    page.evaluate("""() => {
      window.__renamed = [];
      const U = LexeditorUI;
      document.querySelector('main').style.cssText = 'height:400px;display:flex';
      document.querySelector('main').replaceChildren(
        U.pagedListDetail({rows: [{id: 1, name: 'Mod Sword', shippedName: 'Longsword'}],
        key: row => row.id, slots: true, pageSize: 10, selected: 1, fit: false,
        splitKey: 'rename-restore-test',
        rename: (row, name) => window.__renamed.push(name),
        shippedName: row => row.shippedName,
        master: view => U.columnList({rows: view.rows, key: row => row.id,
          selected: view.selected, select: view.select,
          columns: [{key: 'id', label: 'ID'}, {key: 'name', label: 'Name'}]}),
        detail: row => U.detailPanel({title: row.name, body: 'detail'})}));
    }""")
    page.locator('.lex-column-list-cell[data-column-key="name"] .lex-column-cell-content').dblclick()
    editor = page.locator('.lex-column-list-cell[data-column-key="name"] input, .lex-column-list-cell[data-column-key="name"] textarea')
    editor.fill('')
    editor.press('Enter')
    page.wait_for_function("window.__renamed.length > 0", timeout=8000)
    assert page.evaluate("window.__renamed") == ['Longsword']
