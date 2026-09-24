"""Compact record controls must keep their contents inside each cell."""
from test_shared_ui_feedback import ROOT, page, framework


def test_quantity_is_one_row_at_each_panel_width(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''() => {
      const U=LexeditorUI;
      const choice=U.choiceField(U.inlineLabel(U.el('span',{},'Potion')),U.el('button',{},U.selectionIcon()));
      const quantity=U.provenanceControl({control:U.el('input',{type:'number',value:255}),current:()=>255,vanilla:255});
      document.querySelector('main').append(U.quantityChoice(choice,quantity));
    }''')
    gaps=[]
    for width in [125,200,350]:
        page.locator('main').evaluate('(n,w)=>n.style.width=w+"px"',width)
        boxes=page.locator('.lex-quantity-choice').evaluate('''n=>({w:n.clientWidth,sw:n.scrollWidth,
          children:[...n.children].map(c=>c.getBoundingClientRect().toJSON())})''')
        assert boxes['sw']<=boxes['w']+1
        a,x,q=boxes['children']
        assert a['right']<=x['left'] and x['right']<=q['left']
        assert abs((x['top']+x['bottom'])/2-(q['top']+q['bottom'])/2)<1
        gaps.append(round(q['left']-x['right'],2))
    assert len(set(gaps))==1


def test_help_circle_and_portrait_tabs_keep_shape(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''() => {
      const U=LexeditorUI,src='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="60"><rect width="40" height="60" fill="red"/></svg>';
      const tabs=U.subtabBar({images:true,shortcuts:false,active:0,tabs:Array.from({length:16},(_,id)=>({id,label:U.el('img',{src,alt:'GF '+id})}))});
      document.querySelector('main').append(U.toolbar('Alexander',tabs,'#10'),U.columnList({rows:[{}],columns:[{key:'a',label:'GF',help:'Compatibility',render:()=>0}]}));
    }''')
    for width in [1000,1500]:
        page.set_viewport_size({'width':width,'height':800})
        boxes=page.locator('.lex-subtab-bar-images img').evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().toJSON())')
        assert len({round(b['y']) for b in boxes})==1
        assert len({round(b['height']) for b in boxes})==1
        assert min(b['height'] for b in boxes)>40
    circle=page.locator('.lex-info-help').bounding_box()
    assert abs(circle['width']-circle['height'])<1


def test_figure_art_fits_narrow_choice(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI,img=U.el('img',{src:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="250"><rect width="200" height="250" fill="red"/></svg>'});
      const button=U.el('button',{},U.figureGrid([{media:U.iconSlot({content:img}),caption:'Wendigo'}]));
      button.style.width='110px';document.querySelector('main').append(button);
    }''')
    button=page.locator('main > button').bounding_box();art=page.locator('img').bounding_box()
    assert art['x']>=button['x'] and art['x']+art['width']<=button['x']+button['width']


def test_three_tier_controls_stay_in_one_row(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      const row=U.multiNumberRow(['Low','Mid','High'].map(label=>({label,control:U.el('select',{},U.el('option',{},'Immune'))})),{columns:3,stacked:true});
      document.querySelector('main').append(row);
    }''')
    for width in [350,600,900]:
        page.locator('main').evaluate('(n,w)=>n.style.width=w+"px"',width)
        boxes=page.locator('select').evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().toJSON())')
        assert len({round(box['y']) for box in boxes})==1
        assert boxes[0]['right']<=boxes[1]['left'] and boxes[1]['right']<=boxes[2]['left']


def test_gallery_reference_stays_below_the_card(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      const content=U.stack({fill:false},U.el('button',{},'Card'));
      const control=U.provenanceControl({control:content,current:()=>1,vanilla:255,format:()=>"Immune"});
      document.querySelector('main').append(control);
    }''')
    content=page.locator('.lex-stack').bounding_box()
    reference=page.locator('.lex-reference-values').bounding_box()
    assert reference['y']>=content['y']+content['height']
