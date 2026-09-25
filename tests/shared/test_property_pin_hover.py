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


def test_unpinned_control_group_pin_can_be_found_again(page):
    # FF8's Text tab: Source, Section, Record and Field are parts of one
    # control group. A pinned part's pin showed; once clicked to unpin it,
    # hovering the part never showed it again, so the column could not be
    # pinned back. This goes through the real preferences and a real click.
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      localStorage.removeItem('lexeditor:columns:pin-test');
      window.prefs=U.columnPreferences('pin-test',[
        {key:'source',label:'Source'},{key:'section',label:'Section'}],()=>draw());
      window.draw=()=>document.querySelector('main').replaceChildren(U.controlGroup(
        [['Source','source'],['Section','section']].map(([label,key])=>({label,
          control:U.readonlyField(label),pin:prefs.pinButton(key,label)})),{columns:2,stacked:true}));
      draw();
    }''')
    pin = lambda: page.locator('[data-lex-pin-column="source"]')
    page.wait_for_timeout(150)
    is_pinned = lambda: pin().evaluate('el=>el.classList.contains("pinned")')

    def click_pin():
        """Click the pin and wait for the state it commits.

        A pin drops into place over 220ms before it commits, because the panel
        is rebuilt when the visible columns change. A fixed sleep here made
        this check fail against working code; polling the committed state still
        fails when the click changes nothing.
        """
        was_pinned = is_pinned()
        pin().click()
        page.wait_for_function(
            """wasPinned => {
              const el=document.querySelector('[data-lex-pin-column="source"]');
              return !!el && el.classList.contains("pinned") !== wasPinned;
            }""",
            arg=was_pinned, timeout=3000)

    assert is_pinned()
    click_pin()
    assert not is_pinned()
    page.locator('.lex-detail-part').first.hover()
    page.wait_for_timeout(200)
    assert pin().evaluate('el=>Number(getComputedStyle(el).opacity)') > 0
    click_pin()
    assert is_pinned()
