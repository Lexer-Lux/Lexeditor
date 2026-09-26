"""Exercise current card/player views with production controls and synthetic records."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]

def run(browser_path=None,screenshot=None):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,**({'executable_path':browser_path} if browser_path else {}))
        try:
            page=browser.new_page(viewport={'width':1200,'height':800})
            page.set_default_timeout(5000)
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/*',lambda route:route.abort())
            page.route('http://fixture/',lambda route:route.fulfill(content_type='text/html',body='<main id="main"></main><div id="toolbar"></div>'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT/'ui/framework.css'))
            page.add_script_tag(path=str(ROOT/'ui/framework.js'))
            page.add_script_tag(path=str(ROOT/'plugins/ff8/cards_ui.js'))
            page.evaluate('''() => {
              const U=LexeditorUI,card={id:0,name:'Geezard',top:1,bottom:2,left:3,right:10,element:0,power:5};
              const map={id:12,key:'balamb',name:'Balamb',_loaded:true,players:[{id:0,entity:'queen_est',script:'talk',params:[
                {id:0,name:'Deck',value:1,editable:true,mode:'literal'},
                {id:1,name:'Region rule',value:4,editable:false,mode:'variable'},
                {id:3,name:'Rare card chance',value:30,editable:true,mode:'literal'},
                {id:6,name:'Card levels',value:1,editable:true,mode:'literal'},
                {id:4,name:'Unknown setting 1',value:17,editable:true,mode:'literal'},
                {id:5,name:'Unknown setting 2',value:23,editable:true,mode:'literal'}]},
                {id:1,entity:'student',params:[{id:0,name:'Deck',value:1,editable:true,mode:'literal'}]}]};
              window.state={tab:'cards',activeSource:'mine',selected:{},filters:{fields:'old search'},data:{cards:{rows:[card],elements:[{id:0,name:'None'}]},fields:{rows:[map]},text:{rows:[]}},
                base:{cards:[structuredClone(card)]},vanilla:{cards:{rows:[structuredClone(card)]},fields:{rows:[structuredClone(map)]}}};
              window.fetch=async url=>{if(url!='/api/card-players')throw Error('Unexpected request '+url);return {json:async()=>({ready:true,players:[{map:'balamb',entity:'queen_est',id:0,deckMode:'literal',deckId:1},{map:'balamb',entity:'student',id:1,deckMode:'literal',deckId:1}]})}};
              window.cardsUI=FF8CardsUI({...U,el:U.el,state,
                rowOf:(data,view,id)=>data[view].rows.find(row=>row.id===id),filtered:()=>state.data.cards.rows,
                showPaged:(view,rows,columns,detail)=>detail(rows[0]),
                numberControl:(value,min,max,step,update,attrs)=>U.el('input',{...attrs,type:'number',value,min,max,step,oninput:e=>update(Number(e.target.value))}),
                selectControl:(value,options,update)=>U.el('select',{onchange:e=>update(Number(e.target.value))},...options.map(o=>U.el('option',{value:o.value,selected:o.value===value},o.name))),
                sourceControl:control=>control,referenceValues:()=>[],shell:{refresh(){}},noteFieldEdit(){},ensureFieldDetail:async()=>{},navigate:tab=>window.lastNavigation=tab});
              cardsUI.render();U.finishPluginLoading();
            }''')
            assert page.locator('.lex-tab-label-text').all_text_contents()==['CARDS','PLAYERS']
            assert page.locator('.lex-stat-card > img').get_attribute('src')=='/assets/cards/0.png'
            assert page.get_by_role('button',name='Right, currently A',exact=True).inner_text()=='A'
            page.get_by_role('button',name='Top, currently 1',exact=True).click()
            assert page.evaluate('cardsUI.edits()')==[{'id':0,'field':'top','value':2}]
            page.get_by_role('tab',name='PLAYERS',exact=True).click()
            field=page.get_by_label('queen_est Deck',exact=True);field.wait_for()
            assert page.get_by_label('queen_est Region rule',exact=True).is_disabled()
            for label, value in [('Unknown setting 1', '17'), ('Unknown setting 2', '23')]:
                protected = page.locator('.lex-detail-field').filter(has=page.get_by_text(label, exact=True))
                assert value in protected.inner_text()
                assert protected.locator('input:not([readonly]),select,textarea').count() == 0
            assert page.get_by_label('queen_est Rare card chance',exact=True).locator('..').inner_text()=='%'
            assert page.get_by_label('queen_est card level 1',exact=True).is_checked()
            assert page.locator('.lex-record-card').count()==1
            page.get_by_label('queen_est card level 2',exact=True).check()
            assert page.evaluate('state.data.fields.rows[0].players[0].params[3].value')==3
            page.wait_for_timeout(150)
            bounds=page.evaluate("""() => {
              const section=document.querySelector('section[aria-label="CARD LEVELS"]');
              const pool=document.querySelector('section[aria-label="COMMON CARD POOL"]');
              return {bottom:Math.max(...[...section.querySelectorAll('label')].map(n=>n.getBoundingClientRect().bottom)),top:pool.getBoundingClientRect().top};
            }""")
            assert bounds['bottom']<=bounds['top'],bounds
            if screenshot:page.screenshot(path=screenshot)
            page.get_by_role('button',name='Open student',exact=True).click()
            page.get_by_label('student Deck',exact=True).wait_for()
            page.get_by_role('button',name='Open queen_est',exact=True).click()
            page.get_by_role('button',name='Open Balamb',exact=True).click()
            assert page.evaluate('[lastNavigation,state.selected.fields,state.filters.fields]')==['fields',12,'']
            field.fill('7')
            assert page.evaluate('state.data.fields.rows[0].players[0].params[0].value')==7
            page.evaluate('cardsUI.render()')
            assert field.input_value()=='7'
            assert page.get_by_role('button',name='Open student',exact=True).count()==0
            assert 'Opponent queen_est' not in page.locator('body').inner_text()
            page.evaluate("state.activeSource='vanilla';cardsUI.render()")
            assert field.is_disabled()
            assert page.get_by_label('queen_est card level 1',exact=True).is_disabled()
            assert not errors,errors
            print('PASS current Cards/Players tabs, rank edits, native identifier, editable literal, protected variable and read-only source')
        finally:browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--screenshot')
    args=parser.parse_args();run(args.browser,args.screenshot)
