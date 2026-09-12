"""Browser contract for the FF8 Cards redesign and NPC Players subtab."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(browser_path: str | None) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, **({'executable_path': browser_path} if browser_path else {}))
        try:
            page = browser.new_page(viewport={'width': 1200, 'height': 800})
            page.set_default_timeout(5000)
            errors: list[str] = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_content('<!doctype html><html><head><base href="http://localhost/"></head><body><main id="main"></main><div id="toolbar"></div></body></html>')
            page.add_script_tag(content=(ROOT / 'ui/framework.js').read_text(encoding='utf-8'))
            page.add_script_tag(content=(ROOT / 'games/ff8/cards_ui.js').read_text(encoding='utf-8'))
            page.evaluate(r'''() => {
              const el = LexeditorUI.el;
              window.cardSave = null;
              window.fetch = async (url, options={}) => {
                if (String(url).startsWith('/api/field?')) return {
                  ok: true,
                  json: async () => ({
                    key: 'balamb',
                    players: [{id:0, entity:'Queen', script:'talk', params:[
                      {id:0, name:'Rare card', value:1, editable:true, mode:'literal'},
                      {id:1, name:'Region rule', value:4, editable:false, mode:'variable'}
                    ]}]
                  })
                };
                if (String(url) === '/api/field/save') {
                  window.cardSave = JSON.parse(options.body);
                  return {ok:true, json:async()=>({saved:true})};
                }
                throw new Error(`Unexpected fetch: ${url}`);
              };
              const card={id:0,name:'Geezard',top:1,bottom:2,left:3,right:10,element:0,power:5};
              const state={
                tab:'cards',
                data:{
                  cards:{rows:[card],elements:[{id:0,name:'None'}]},
                  fields:{rows:[{key:'balamb',name:'Balamb'}]},
                  text:{rows:[]}
                },
                base:{cards:[structuredClone(card)]},
                vanilla:{cards:{rows:[structuredClone(card)]}},
              };
              let capturedDetail=null, capturedMount=null;
              const rowOf=(dataset,_view,id)=>(dataset.cards?.rows||[]).find(row=>row.id===id);
              const filtered=()=>state.data.cards.rows;
              const showPaged=(_view,_rows,_columns,detail,_template,_layout,mount)=>{
                capturedDetail=detail;capturedMount=mount;
                return el('div',{class:'fake-paged'},'CARDS LIST');
              };
              const detailField=({control})=>el('div',{class:'test-field'},control);
              const detailSection=({title,body})=>el('section',{},el('h3',{},title),...(Array.isArray(body)?body:[body]));
              const sharedDetail=(_row,_prefs,sections)=>el('div',{class:'test-detail'},...sections);
              const numberControl=(value,_min,_max,_step,update,attrs={})=>el('input',{...attrs,type:'number',value,oninput:event=>update(event.target.value)});
              const selectControl=(value,options,update)=>el('select',{value,onchange:event=>update(event.target.value)},...options.map(option=>el('option',{value:option.value,selected:Number(option.value)===Number(value)},option.name)));
              const sourceControl=control=>control;
              const referenceValues=()=>[];
              const infoHelp=()=>null;
              const shell={refresh(){}};
              const noteFieldEdit=()=>{};
              window.cardsContract={state,get capturedMount(){return capturedMount;},get capturedDetail(){return capturedDetail;}};
              window.cardsUI=FF8CardsUI({
                el,state,rowOf,filtered,showPaged,sharedDetail,detailSection,detailField,
                numberControl,selectControl,sourceControl,referenceValues,infoHelp,shell,noteFieldEdit,
                subtabBar:LexeditorUI.subtabBar,
                detailPanel:LexeditorUI.detailPanel,
                recordId:LexeditorUI.recordId,
                columnList:LexeditorUI.columnList,
              });
              cardsUI.render();
            }''')

            assert not errors, errors
            assert page.evaluate('cardsContract.capturedMount') is False
            assert page.locator('#main > .ff8-card-root').count() == 1
            labels = page.locator('.lex-subtab-bar button .lex-tab-label-text').all_text_contents()
            assert labels == ['CARDS', 'PLAYERS'], labels
            assert page.locator('.fake-paged').count() == 1

            page.evaluate('''() => {
              const node=cardsContract.capturedDetail(cardsContract.state.data.cards.rows[0],{});
              document.body.append(node);
            }''')
            assert page.locator('.ff8-card-preview').count() == 1
            assert page.locator('.ff8-card-preview img').get_attribute('src') == '/assets/cards/0.png'
            assert page.locator('.ff8-card-rank.right').inner_text() == 'A'
            print('PASS card list stays mounted and artwork/rank preview uses production classes')

            page.get_by_role('button', name='PLAYERS').click()
            page.wait_for_selector('.ff8-card-players .lex-column-list-row')
            rows = page.locator('.ff8-card-players .lex-column-list-row')
            assert rows.count() == 2
            first_text = rows.nth(0).inner_text()
            assert 'Queen' in first_text and 'talk' in first_text and 'Rare card' in first_text and 'Literal' in first_text
            inputs = page.locator('.ff8-card-players .lex-column-list-row input[type=number]')
            assert inputs.count() == 2
            assert inputs.nth(1).is_disabled()
            inputs.nth(0).fill('7')
            page.get_by_role('button', name='SAVE PLAYERS').click()
            page.wait_for_function('window.cardSave !== null')
            assert page.evaluate('window.cardSave') == {'edits':[{'map':'balamb','player':0,'param':0,'value':7}]}
            assert 'Saved 1 CARDGAME parameter change.' in page.locator('.ff8-card-player-state').last.inner_text()
            print('PASS Players subtab loads CARDGAME parameters, preserves read-only variables, and saves edits')
            assert not errors, errors
        finally:
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser')
    args = parser.parse_args()
    run(args.browser)
