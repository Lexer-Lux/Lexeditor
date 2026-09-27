"""A renamed property is renamed in its table column header too.

Lexer: "i renamed a property but its name in the table column header remained
the same?" A rename was stored for the record's field only; a column header
drew its shipped name.
"""
from test_shared_ui_feedback import framework, page
from test_tab_rename import mount_shell


def headers(page):
    return page.evaluate("[...document.querySelectorAll('.header-label')].map(n=>n.textContent.trim())")


def test_a_rename_reaches_the_column_header(page):
    framework(page)
    mount_shell(page)
    # A name renamed earlier is read back when the table is drawn.
    page.evaluate("""()=>{localStorage.setItem('fixture-items.field.Strength.label','Might');
      const U=LexeditorUI;
      document.querySelector('main').replaceChildren(U.columnList({rows:[{id:1,strength:5,speed:3}],key:r=>r.id,
        template:'1fr 1fr',columns:[{key:'strength',label:'Strength'},{key:'speed',label:'Speed'}]}),
        U.detailField({label:'Speed',control:U.el('input',{value:'3'})}));}""")
    page.wait_for_timeout(150)
    assert headers(page) == ["Might", "Speed"], headers(page)

    # A rename in the field reaches the header already on screen.
    page.locator(".lex-detail-field-label-text").dblclick()
    rename = page.locator(".lex-label-rename")
    rename.wait_for(timeout=3000)
    rename.fill("Haste")
    rename.press("Enter")
    page.wait_for_timeout(150)
    assert headers(page) == ["Might", "Haste"], headers(page)

    # Undo takes the header back with the field.
    page.keyboard.press("Control+z")
    page.wait_for_timeout(150)
    assert headers(page) == ["Might", "Speed"], headers(page)
