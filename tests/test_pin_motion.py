"""Pin movement must finish before a column change rebuilds its panel."""
from test_shared_ui_feedback import ROOT, page, framework


def mount(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;window.changes=0;
      const host=document.querySelector('main');
      window.prefs=U.columnPreferences('pin-motion',[{key:'value',label:'Value',pinned:false}],()=>{changes++;render()});
      function render(){host.replaceChildren(U.el('div',{class:'lex-pinnable-property',style:'position:relative;margin:80px;width:180px;height:80px'},prefs.pinButton('value')))}
      render();
    }''')


def test_pin_moves_before_panel_rebuild(page):
    mount(page)
    for inserting in [True,False]:
        page.locator('.lex-pinnable-property').hover()
        page.locator('.lex-column-pin').click()
        movement=page.locator('.lex-column-pin').evaluate('''b=>{
          const a=b.querySelector('svg').getAnimations().find(a=>a.effect.getKeyframes().some(k=>k.translate));
          a.pause();a.currentTime=110;
          return {moving:b.dataset.pinMoving,translation:getComputedStyle(b.querySelector('svg')).translate,
            visible:getComputedStyle(b.querySelector('path')).display};
        }''')
        assert movement['moving']=='true' and movement['visible']!='none'
        assert movement['translation'] not in ('0px','0px 0px','6px -6px'),movement
        assert page.evaluate("prefs.isPinned('value')") is not inserting
        # Repeated activation during movement must not toggle a second time.
        page.locator('.lex-column-pin').dispatch_event('click')
        page.locator('.lex-column-pin').evaluate("b=>b.querySelector('svg').getAnimations().forEach(a=>a.finish())")
        page.wait_for_function("expected=>prefs.isPinned('value')===expected",arg=inserting)
    assert page.evaluate('changes')==2


def test_reduced_motion_pin_updates_without_animation(page):
    page.emulate_media(reduced_motion='reduce')
    mount(page)
    page.locator('.lex-pinnable-property').hover()
    page.locator('.lex-column-pin').click()
    assert page.evaluate("prefs.isPinned('value')")
    assert page.locator('[data-pin-moving]').count()==0


def test_readonly_lock_does_not_shift_field_pin(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const prefs=U.columnPreferences('pin-corners',[
        {key:'buy',label:'Buy',pinned:true},{key:'sell',label:'Sell',pinned:true}],()=>{});
      document.querySelector('main').replaceChildren(...[
        ['buy',U.el('input',{type:'number',value:50000})],
        ['sell',U.readonlyField(12500)]
      ].map(([key,input])=>U.detailField({label:key,control:U.unitField(input,'G'),pin:prefs.pinButton(key)})));
    }''')
    page.wait_for_function("[...document.querySelectorAll('.lex-column-pin')].every(p=>p.style.left)")
    assert page.locator('.lex-field-readonly-lock').count()==1
    for width in [1200,600]:
        page.set_viewport_size({'width':width,'height':800})
        page.wait_for_timeout(100)
        offsets=page.locator('.lex-detail-field').evaluate_all('''rows=>rows.map(row=>{
          const field=row.querySelector('input').getBoundingClientRect();
          const pin=row.querySelector('.lex-column-pin').getBoundingClientRect();
          return {x:pin.left+pin.width*3.71/24-field.right,
                  y:pin.top+pin.height*21.71/24-field.top};
        })''')
        assert abs(offsets[0]['x']-offsets[1]['x'])<1,offsets
        assert abs(offsets[0]['y']-offsets[1]['y'])<1,offsets
