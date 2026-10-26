"""Developer property moves retain controls and persist across record redraws."""
from test_shared_ui_feedback import framework, page
from test_tab_rename import mount_shell


def mount_properties(page, developer=True):
    framework(page)
    mount_shell(page, developer)
    page.evaluate('''() => {
      const U=LexeditorUI;
      window.changes=[];
      window.drawProperties=(title='First record')=>{
        const field=(label,value)=>U.detailField({label,property:label.toLowerCase(),
          control:U.el('input',{type:'number',min:0,max:100,value,
            oninput:e=>changes.push([label,e.target.value])})});
        document.querySelector('main').replaceChildren(U.detailPanel({title,body:[
          U.detailSection({title:'ATTACK',body:[field('Power',10),field('Accuracy',20)]}),
          U.detailSection({title:'DEFENCE',body:[field('Armour',30)]}),
          U.detailSection({title:'EXTRA',body:[]})]}));
      };
      drawProperties();
    }''')
    page.wait_for_timeout(150)


def label(page, name):
    return page.locator('.lex-detail-field-label-text').filter(has_text=name)


def order(page, section):
    return page.locator(f'[data-lex-layout-section="{section}"] .lex-detail-field').evaluate_all(
        'ns=>ns.map(n=>n.dataset.lexLayoutField)')


def drag(page, name, target, bottom=False):
    source=label(page,name)
    source.hover()
    source.drag_to(target, target_position={'x':10,'y':target.bounding_box()['height']-2 if bottom else 2})
    page.wait_for_timeout(100)


def inside(page, section):
    """A drop target inside a section: the title is the escape hatch to
    the bare panel beside the section, not the way in."""
    fields = page.locator(f'[data-lex-layout-section="{section}"] .lex-detail-field')
    if fields.count():
        return fields.last
    return page.locator(f'[data-lex-layout-section="{section}"] .lex-detail-section-content')


def test_reorder_move_redraw_and_undo(page, tmp_path):
    mount_properties(page)
    drag(page,'Accuracy',page.locator('[data-lex-layout-field="power"]'))
    assert order(page,'ATTACK')==['accuracy','power']
    drag(page,'Power',inside(page,'DEFENCE'),bottom=True)
    assert order(page,'ATTACK')==['accuracy']
    assert order(page,'DEFENCE')==['armour','power']
    page.get_by_role('spinbutton',name='Power',exact=True).fill('42')
    assert page.evaluate('changes')==[['Power','42']]
    assert len(page.evaluate('savedCalls'))==2
    page.screenshot(path=str(tmp_path/'property-layout.png'))
    page.evaluate("drawProperties('Second record')")
    page.wait_for_timeout(150)
    assert order(page,'DEFENCE')==['armour','power']
    # Undo applies to the newly drawn record, not only the discarded DOM nodes.
    page.get_by_role('spinbutton',name='Power',exact=True).blur()
    page.keyboard.press('Control+z')
    page.wait_for_timeout(150)
    assert order(page,'ATTACK')==['accuracy','power']
    assert order(page,'DEFENCE')==['armour']
    page.keyboard.press('Control+Shift+z')
    page.wait_for_timeout(150)
    assert order(page,'DEFENCE')==['armour','power']
    # An empty section takes a title drop inside: its content has no box.
    drag(page,'Power',page.locator('[data-lex-layout-section="EXTRA"] h3'))
    assert order(page,'EXTRA')==['power']
    # A title drop on a lived-in section escapes beside it instead.
    drag(page,'Power',page.locator('[data-lex-layout-section="EXTRA"] h3'),bottom=True)
    assert order(page,'EXTRA')==[]
    bare = page.evaluate("""() => {
      const field = document.querySelector('[data-lex-layout-field="power"]');
      return field && !field.closest('[data-lex-layout-section]') ? 'bare' : 'sectioned';
    }""")
    assert bare == 'bare', bare


def test_readers_use_saved_layout_but_cannot_drag(page):
    mount_properties(page)
    drag(page,'Power',inside(page,'DEFENCE'),bottom=True)
    page.evaluate("dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{developerMode:false}})); drawProperties('Reader')")
    page.wait_for_timeout(150)
    assert order(page,'DEFENCE')==['armour','power']
    label(page,'Power').hover()
    # A property is dragged by its row; a reader's row never drags.
    assert label(page,'Power').evaluate("n=>n.closest('.lex-detail-field').getAttribute('draggable')")=='false'
    assert len(page.evaluate('savedCalls'))==1


def test_cancel_and_other_panel_do_not_change_layout(page):
    mount_properties(page)
    page.evaluate('''()=>document.querySelector('main').append(LexeditorUI.detailPanel({
      title:'Other panel',body:LexeditorUI.detailSection({title:'OTHER',body:[
        LexeditorUI.detailField({label:'Other',control:LexeditorUI.el('input',{value:'unchanged'})})]})}))''')
    drag(page,'Power',page.locator('[data-lex-layout-section="OTHER"] h3'))
    assert order(page,'ATTACK')==['power','accuracy']
    assert page.evaluate('savedCalls')==[]
    source=label(page,'Power')
    source.hover()
    box=source.bounding_box()
    page.mouse.move(box['x']+3,box['y']+3)
    page.mouse.down()
    page.mouse.move(box['x']+30,box['y']+35,steps=6)
    page.keyboard.press('Escape')
    page.mouse.up()
    assert order(page,'ATTACK')==['power','accuracy']
    assert page.evaluate('savedCalls')==[]


def test_layout_is_scoped_to_field_schema_and_page(page):
    mount_properties(page)
    drag(page,'Power',page.locator('[data-lex-layout-section="DEFENCE"] h3'))
    page.evaluate('''()=>{
      drawProperties();
      document.querySelector('[data-lex-layout-field="power"]').dataset.lexLayoutField='anotherPower';
    }''')
    page.wait_for_timeout(150)
    assert order(page,'ATTACK')==['anotherPower','accuracy']
    page.evaluate('''()=>{
      document.querySelector('nav button.active').classList.remove('active');
      document.querySelector('nav button[data-tab="magic"]').classList.add('active');
      drawProperties();
    }''')
    page.wait_for_timeout(150)
    assert order(page,'ATTACK')==['power','accuracy']
