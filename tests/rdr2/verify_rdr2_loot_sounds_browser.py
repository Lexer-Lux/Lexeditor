"""Production pickup routing screen with synthetic data; no installed files touched."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1000,'height':750});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',lambda route:route.abort())
            page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1),wait_until='domcontentloaded')
            expect(page.locator('.lex-inline-label').filter(has_text='Drunkenness').locator('input')).to_have_count(1)
            page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
            page.evaluate('''async()=>{
              window.__responses['/api/loot-sounds']={available:true,rows:Array.from({length:522},(_,i)=>({id:`0:Sounds:${i}:ITEM_${i}`,map:0,section:'Sounds',key:`ITEM_${i}`,value:'AMMO'})),categories:['AMMO','WATCH'],soundSets:['PICKUP_SOUNDSET']};
              const previous=window.fetch;window.fetch=async(url,options={})=>{
                if(url.split('?')[0]==='/api/loot-sounds/save'){
                  if(window.__soundSaveFails)return new Response(JSON.stringify({error:'Disk full'}),{status:500});
                  for(const edit of JSON.parse(options.body).edits)__responses['/api/loot-sounds'].rows.find(row=>row.id===edit.id).value=edit.value;
                  return new Response(JSON.stringify({saved:1}),{status:200});
                }return previous(url,options);
              };
              state.tab='loot';state.lootFile='__sounds';await renderLoot();
            }''')
            listing=page.locator('#main .lex-column-list')
            rows=listing.locator('.lex-list-row')
            expect(rows.first).to_be_visible()
            assert 0 < rows.count() < 522
            page.get_by_role('button',name='Last page',exact=True).click()
            rows.filter(has_text='ITEM_521').click()
            assert page.evaluate('state.lootSoundSelected')=='0:Sounds:521:ITEM_521'
            search=page.get_by_role('searchbox',name='Find pickup sound')
            search.fill('ITEM_521');search.press('Tab')
            expect(rows).to_have_count(1)
            control=page.get_by_role('combobox',name='Sound category',exact=True)
            control.select_option('WATCH');assert page.evaluate('dirtyCount()')==1
            page.evaluate('window.__soundSaveFails=true')
            result=page.evaluate('async()=>{try{await saveLootSounds();return null}catch(error){return error.message}}')
            assert 'Disk full' in result and page.evaluate('dirtyCount()')==1
            page.evaluate('window.__soundSaveFails=false');page.evaluate('saveLootSounds()')
            assert page.evaluate('dirtyCount()')==0 and control.input_value()=='WATCH'
            assert page.evaluate('state.lootSoundSelected')=='0:Sounds:521:ITEM_521'
            page.evaluate("async()=>{state.ds='vanilla';await renderLootSounds()}")
            assert control.is_disabled()
            search.fill('');search.press('Tab')
            expect(rows.nth(1)).to_be_visible()
            expect(rows.filter(has_text='ITEM_521')).to_be_visible()
            assert page.evaluate('state.lootSoundSelected')=='0:Sounds:521:ITEM_521'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors,errors
            output=Path(__import__("tempfile").gettempdir()) / "lexeditor-dev" / 'loot-sounds';output.mkdir(parents=True,exist_ok=True)
            page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            expect(rows.filter(has_text='ITEM_521')).to_be_visible()
            expect(control).to_be_disabled()
            page.screenshot(path=str(output/'routing.png'))
        finally:browser.close()
    print('PASS: routing controls, global dirty count, failed-save retention, save/reload and read-only reference')


if __name__=='__main__':main()
