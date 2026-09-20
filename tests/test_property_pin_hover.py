"""Each property owns its pin even inside a grouped detail field."""
from test_shared_ui_feedback import page, framework


def test_group_hover_does_not_reveal_child_pins(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      const pin=key=>U.element('button',{class:'lex-column-pin',
        'data-lex-pin-column':key},'Pin');
      const group=U.toggleRow({toggles:[
        {key:'zombie',label:'Zombie',pin:pin('zombie')},
        {key:'flying',label:'Flying',pin:pin('flying')},
        {key:'hp',label:'Hide HP',pin:pin('hp')}]});
      document.querySelector('main').append(
        U.detailField({label:'Flags',control:group}),
        U.detailField({label:'AP',control:U.element('input',{type:'number',value:5}),pin:pin('ap')}));
      document.querySelector('[data-lex-pin-column="hp"]').classList.add('pinned');
    }''')

    def opacity(key):
        page.wait_for_timeout(200)
        return page.locator(f'[data-lex-pin-column="{key}"]').evaluate(
            'el=>Number(getComputedStyle(el).opacity)')

    page.get_by_text('Flags', exact=True).hover()
    assert opacity('zombie') == 0
    assert opacity('flying') == 0
    assert opacity('hp') == 1
    page.locator('[data-lex-toggle="zombie"]').hover()
    assert opacity('zombie') > 0
    assert opacity('flying') == 0
    page.locator('[data-lex-toggle="flying"]').hover()
    assert opacity('zombie') == 0
    assert opacity('flying') > 0
    page.get_by_text('AP', exact=True).hover()
    assert opacity('ap') > 0
    assert opacity('flying') == 0
    page.locator('[data-lex-pin-column="zombie"]').focus()
    assert opacity('zombie') > 0
