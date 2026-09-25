"""Each property owns its pin even inside a grouped detail field."""
from test_shared_ui_feedback import page, framework


PANEL = '''() => {
  const U=LexeditorUI;
  const main=document.querySelector('main');
  // A narrow panel puts the value box's right edge where the panel body ends,
  // which is the width at which the mark was being cut.
  main.style.cssText='position:absolute;inset:0;padding:20px;width:520px';
  const prefs=U.columnPreferences('pin-mark',[
    {key:'alpha',label:'Alpha'},{key:'beta',label:'Beta',pinned:false}],()=>{});
  const number=value=>U.element('input',{type:'number',value});
  main.replaceChildren(U.detailPanel({title:'Probe',body:[
    U.detailField({label:'Alpha',control:number(3),pin:prefs.pinButton('alpha','Alpha')}),
    U.detailField({label:'Beta',control:number(4),pin:prefs.pinButton('beta','Beta')})]}));
}'''


def _pin_mark(page, key):
    """Colour and opacity of one pin, as the screen draws them."""
    return page.locator(f'[data-lex-pin-column="{key}"]').evaluate(
        'el=>{const s=getComputedStyle(el);return [s.color, Number(s.opacity)];}')


def test_a_pinned_pin_keeps_its_own_mark_when_its_row_is_hovered(page):
    """The ghost belongs to a pin that is not in the column.

    Pointing at a row used to dim the pin that was already stuck in, so the
    mark that said "this property is in the table" looked exactly like the mark
    that said it was not. The two states are measured rather than compared as
    images, because the same icon draws both.
    """
    framework(page)
    page.evaluate(PANEL)
    page.wait_for_timeout(200)
    alpha_rest, beta_rest = _pin_mark(page, 'alpha'), _pin_mark(page, 'beta')
    page.get_by_text('Alpha', exact=True).hover()
    page.wait_for_timeout(200)
    alpha_hover = _pin_mark(page, 'alpha')
    page.get_by_text('Beta', exact=True).hover()
    page.wait_for_timeout(200)
    beta_hover = _pin_mark(page, 'beta')

    assert alpha_rest[1] == 1 and beta_rest[1] == 0, (alpha_rest, beta_rest)
    assert alpha_hover == alpha_rest, (alpha_rest, alpha_hover)
    assert beta_hover[1] > 0 and beta_hover != alpha_hover, (alpha_hover, beta_hover)


def test_a_hidden_pin_is_drawn_inside_its_own_row(page):
    """The mark leans up and to the right of its tip.

    With the tip on the value box's own right edge, the mark hung past the edge
    of the panel body, which clips its overflow, and the pin lost its right
    side - so half of it was missing exactly while it was being pointed at.
    """
    framework(page)
    page.evaluate(PANEL)
    page.get_by_text('Beta', exact=True).hover()
    page.wait_for_timeout(250)
    overflow = page.locator('[data-lex-pin-column="beta"]').evaluate('''el=>{
      const ink=el.querySelector('svg').getBoundingClientRect();
      const control=el.closest('.lex-detail-field-control');
      const box=control.getBoundingClientRect();
      const body=control.closest('.lex-detail-panel-body');
      return {overRow:Math.round(ink.right-(box.left+control.clientWidth)),
        overPanel:body?Math.round(ink.right-(body.getBoundingClientRect().left+body.clientWidth)):0};
    }''')
    assert overflow['overRow'] <= 0, overflow
    assert overflow['overPanel'] <= 0, overflow


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
