"""Exercise current card/player views with production controls and synthetic records."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]

def run(browser_path=None):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,**({'executable_path':browser_path} if browser_path else {}))
        try:
            page=browser.new_page(viewport={'width':1200,'height':800})
            page.set_default_timeout(5000)
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('http://fixture/',lambda route:route.fulfill(content_type='text/html',body='<main id="main"></main><div id="toolbar"></div>'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT/'ui/framework.css'))
            page.add_script_tag(path=str(ROOT/'ui/framework.js'))
            page.add_script_tag(path=str(ROOT/'plugins/ff8/cards_ui.js'))
            page.evaluate('''() => {
              const U=LexeditorUI,card={id:0,name:'Geezard',top:1,bottom:2,left:3,right:10,element:0,power:5};
              const map={key:'balamb',name:'Balamb',_loaded:true,players:[{id:0,entity:'queen_est',script:'talk',params:[
                {id:0,name:'Deck',value:1,editable:true,mode:'literal'},
                {id:1,name:'Region rule',value:4,editable:false,mode:'variable'}]}]};
              window.state={tab:'cards',activeSource:'mine',data:{cards:{rows:[card],elements:[{id:0,name:'None'}]},fields:{rows:[map]},text:{rows:[]}},
                base:{cards:[structuredClone(card)]},vanilla:{cards:{rows:[structuredClone(card)]},fields:{rows:[structuredClone(map)]}}};
              window.fetch=async url=>{if(url!='/api/card-players')throw Error('Unexpected request '+url);return {json:async()=>({ready:true,players:[{map:'balamb',entity:'queen_est',id:0}]})}};
              window.cardsUI=FF8CardsUI({...U,el:U.el,state,
                rowOf:(data,view,id)=>data[view].rows.find(row=>row.id===id),filtered:()=>state.data.cards.rows,
                showPaged:(view,rows,columns,detail)=>detail(rows[0]),
                numberControl:(value,min,max,step,update,attrs)=>U.el('input',{...attrs,type:'number',value,min,max,step,oninput:e=>update(Number(e.target.value))}),
                selectControl:(value,options,update)=>U.el('select',{onchange:e=>update(Number(e.target.value))},...options.map(o=>U.el('option',{value:o.value,selected:o.value===value},o.name))),
                sourceControl:control=>control,referenceValues:()=>[],shell:{refresh(){}},noteFieldEdit(){},ensureFieldDetail:async()=>{}});
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
            field.fill('7')
            assert page.evaluate('state.data.fields.rows[0].players[0].params[0].value')==7
            page.evaluate('cardsUI.render()')
            assert field.input_value()=='7'
            assert 'Opponent queen_est' not in page.locator('body').inner_text()
            page.evaluate("state.activeSource='vanilla';cardsUI.render()")
            assert field.is_disabled()
            assert not errors,errors
            print('PASS current Cards/Players tabs, rank edits, native identifier, editable literal, protected variable and read-only source')
        finally:browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');run(parser.parse_args().browser)
