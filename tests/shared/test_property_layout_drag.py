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


def mount_columns(page):
    framework(page)
    mount_shell(page, True)
    page.set_viewport_size({'width': 1400, 'height': 800})
    page.evaluate('''() => {
      const U=LexeditorUI;
      window.drawColumns=(title='First record')=>{
        const field=(tag,i)=>U.detailField({label:`${tag} field ${i}`,property:`${tag}-${i}`,
          control:U.el('input',{type:'number',value:0})});
        document.querySelector('main').replaceChildren(U.detailPanel({title,paginate:{unpaged:true},body:[
          U.detailSection({title:'ONE',body:[field('one',1),field('one',2),field('one',3),
            field('one',4),field('one',5),field('one',6)]}),
          U.detailSection({title:'TWO',body:[field('two',1),field('two',2)]}),
          U.detailSection({title:'THREE',body:[field('three',1),field('three',2)]}),
          U.detailSection({title:'FOUR',body:[field('four',1),field('four',2)]})]}));
        // The divider's COLUMNS control sets this attribute, then refits.
        document.querySelector('main').dataset.lexDetailColumns='3';
        document.querySelector('.lex-tweaks-paged').lexFitPage();
      };
      drawColumns();
    }''')
    page.wait_for_timeout(200)


def field_lane(page, name):
    return page.evaluate("""name => {
      const field = [...document.querySelectorAll('.lex-detail-field')]
        .find(node => node.textContent.includes(name));
      const columns = [...document.querySelectorAll('.lex-tweak-column')];
      return columns.indexOf(field.closest('.lex-tweak-column'));
    }""", name)


def test_property_drop_into_empty_lane_below_its_top_strip(page):
    # The header-drop twin: an emptied lane takes a dragged property
    # anywhere in its span, and the pin survives a record redraw.
    mount_columns(page)
    # Vacate a lane: FOUR and THREE join ONE's lane, so one of the
    # three lanes must empty whatever the opening deal was.
    for name in ('FOUR', 'THREE'):
        head = page.locator(f'[data-lex-layout-section="{name}"] h3')
        first = page.locator('[data-lex-layout-section="ONE"]')
        box = first.bounding_box()
        head.drag_to(first, target_position={'x': 10, 'y': box['height'] - 4})
        page.wait_for_timeout(200)
    counts = page.evaluate(
        "() => [...document.querySelectorAll('.lex-tweak-column')].map(column => column.childElementCount)")
    empty = next((i for i, count in enumerate(counts) if count == 0), -1)
    assert empty >= 0, counts
    lane = page.locator('.lex-tweak-column').nth(empty)
    box = lane.bounding_box()
    # Past the old 96px strip: pre-fix this aim hit the grid and refused.
    assert box['height'] > 160, box
    point = [box['x'] + box['width'] / 2, box['y'] + 160]
    hit = page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.className', point)
    assert hit == 'lex-tweak-column', hit
    label(page, 'two field 1').drag_to(
        lane, target_position={'x': box['width'] / 2, 'y': 160})
    page.wait_for_timeout(200)
    assert field_lane(page, 'two field 1') == empty
    page.evaluate("drawColumns('Second record')")
    page.wait_for_timeout(200)
    assert field_lane(page, 'two field 1') == empty


def test_property_drop_into_lane_gap_beside_empty_lane(page):
    # The gap between lanes is grid, not a column box: aiming into the
    # gap beside an empty lane still drops the property there, by span.
    mount_columns(page)
    for name in ('FOUR', 'THREE'):
        head = page.locator(f'[data-lex-layout-section="{name}"] h3')
        first = page.locator('[data-lex-layout-section="ONE"]')
        box = first.bounding_box()
        head.drag_to(first, target_position={'x': 10, 'y': box['height'] - 4})
        page.wait_for_timeout(200)
    counts = page.evaluate(
        "() => [...document.querySelectorAll('.lex-tweak-column')].map(column => column.childElementCount)")
    empty = next((i for i, count in enumerate(counts) if count == 0), -1)
    assert empty >= 0, counts
    lane = page.locator('.lex-tweak-column').nth(empty)
    box = lane.bounding_box()
    # Three pixels into the gap from the empty lane's edge: nearer to it
    # than to any neighbor, and past the old 96px strip vertically.
    aim = box['width'] + 3 if empty < len(counts) - 1 else -3
    point = [box['x'] + aim, box['y'] + 160]
    hit = page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.className', point)
    assert 'lex-tweak-card-grid' in hit and 'lex-tweak-column' not in hit, hit
    # The gap point is grid, so the grid is the drag target: aiming at
    # the lane with an out-of-box offset fails actionability instead.
    grid = page.locator('main .lex-tweak-card-grid').bounding_box()
    label(page, 'two field 1').drag_to(
        page.locator('main .lex-tweak-card-grid'),
        target_position={'x': point[0] - grid['x'], 'y': point[1] - grid['y']})
    page.wait_for_timeout(200)
    assert field_lane(page, 'two field 1') == empty
    page.evaluate("drawColumns('Second record')")
    page.wait_for_timeout(200)
    assert field_lane(page, 'two field 1') == empty
