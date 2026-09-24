"""Pins, hover marks and shortcut hints share one interaction contract."""
from test_shared_ui_feedback import ROOT, page, framework


def test_tab_badges_only_appear_while_control_is_held(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture'},tabs:[{id:'a',label:'Alpha'},{id:'b',label:'Beta'}],activeTab:()=> 'a',navigate(){}});
      U.finishPluginLoading();
      document.querySelector('main').append(U.subtabBar({tabs:[{id:1,label:'One'},{id:2,label:'Two'}],active:1,change(){}}));}''')
    for selector in ['nav button:last-child','.lex-subtab-button:last-child']:
        tab=page.locator(selector)
        tab.hover()
        badge=tab.locator('.lex-tab-shortcut')
        assert not badge.is_visible()
        page.keyboard.down('Control')
        assert badge.is_visible()
        page.keyboard.up('Control')
        assert not badge.is_visible()


def test_part_pins_and_text_pin_follow_input_corner(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI,pin=()=>U.el('button',{class:'lex-column-pin'},'P');
      document.querySelector('main').append(U.controlGroup([
        {label:'Source',control:U.readonlyField('Kernel'),pin:pin()},
        {label:'Section',control:U.readonlyField('32'),pin:pin()}],{columns:2,stacked:true}),
        U.detailField({label:'',showType:false,className:'lex-text-editor',
          control:U.textArea({style:'height:500px'}),pin:pin()}));}''')
    page.wait_for_timeout(150)
    assert page.locator('.lex-detail-part .lex-column-pin').count()==2
    assert page.locator('.lex-text-editor .lex-field-type-rail').count()==0
    pin=page.locator('.lex-text-editor .lex-column-pin').bounding_box()
    box=page.locator('textarea').bounding_box()
    assert abs(pin['y']-box['y'])<30
    assert abs(pin['x']-box['x']-box['width'])<30


def test_hover_has_no_box_or_dashed_spelling_like_line(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(
      U.hoverable({content:'Ability',targetId:1}),U.columnList({rows:[{name:'Belhelmel'}],
      columns:[{key:'name',label:'Name',edit(){}}]}));}''')
    link=page.locator('.lex-hoverable');link.hover()
    assert link.evaluate("n=>getComputedStyle(n).outlineStyle")=='none'
    cell=page.locator('.lex-cell-editable');cell.hover()
    assert cell.locator('.lex-column-cell-content').evaluate('n=>parseFloat(getComputedStyle(n).borderBottomWidth)')==0
    assert not page.evaluate('document.documentElement.spellcheck')
    cell.dblclick()
    entry=cell.locator('input')
    assert entry.evaluate('n=>n.spellcheck')
