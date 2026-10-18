"""Crafting quantities reject lossy edits and preserve the last saved file."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from plugins.rdr2 import server as service
from plugins.rdr2 import custom_crafting as storage
from rdr2_browser_check import document
from playwright.sync_api import sync_playwright

RECIPE={'recipe_id':'quantity_fixture','title':'Fixture','category':'CI_CATEGORY_CONSUMABLE',
        'description':'','station':'CUSTOM_ANY','unlock':'','output_item':'CONSUMABLE_BRANDY',
        'output_quantity':2,'ingredients':[{'item':'CONSUMABLE_RUM','quantity':3}]}

def service_check():
    with tempfile.TemporaryDirectory(prefix='lexeditor-crafting-') as temporary:
        root=Path(temporary);mine=root/'mine';mine.mkdir();vanilla=root/'vanilla.tsv'
        storage.save_recipes(vanilla,[])
        target=root/'custom.tsv'
        with patch.multiple(service,CUSTOM_CRAFTING_FILE=target,VANILLA_CRAFTING_FILE=vanilla,
                            DATASETS={'mine':{'dir':mine,'readonly':False}},_files={}):
            server=service.create_server(0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def save(recipes):
                request=Request(f'http://127.0.0.1:{server.server_port}/api/custom-crafting',
                    data=json.dumps({'recipes':recipes}).encode(),method='PUT',
                    headers={'Content-Type':'application/json'})
                try:
                    with urlopen(request) as response:return response.status,json.load(response)
                except HTTPError as error:return error.code,json.load(error)
            try:
                assert save([RECIPE])==(200,{'saved':1})
                before=target.read_bytes();source=vanilla.read_bytes()
                for field in ('output','ingredient'):
                    for value in (True,False,1.5,'1.5',float('nan'),float('inf'),0,-1,None):
                        invalid=copy.deepcopy(RECIPE)
                        if field=='output':invalid['output_quantity']=value
                        else:invalid['ingredients'][0]['quantity']=value
                        first=copy.deepcopy(RECIPE);first['recipe_id']='earlier_valid_edit'
                        first['output_quantity']=8
                        code,body=save([first,invalid])
                        assert code==400,(field,value,code,body)
                        assert target.read_bytes()==before
                        assert vanilla.read_bytes()==source
                        assert sorted(p.name for p in root.iterdir())==['custom.tsv','mine','vanilla.tsv']
                malformed=copy.deepcopy(RECIPE);malformed['ingredients'].append('invalid')
                assert save([malformed])[0]==400
                assert target.read_bytes()==before
                valid=copy.deepcopy(RECIPE);valid['output_quantity']=7;valid['ingredients'][0]['quantity']=9
                assert save([valid])==(200,{'saved':1})
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/custom-crafting') as response:
                    assert json.load(response)['custom']==[valid]
                assert storage.load_recipes(target)[0].ingredients[0].quantity==9
                bad=storage.Recipe(**{k:v for k,v in RECIPE.items() if k!='ingredients'},
                    ingredients=[storage.Ingredient('CONSUMABLE_RUM',1.5)])
                before=target.read_bytes()
                try:storage.save_recipes(target,[bad])
                except ValueError:pass
                else:raise AssertionError('direct storage accepted a fractional ingredient')
                assert target.read_bytes()==before
            finally:
                server.shutdown();server.server_close();thread.join()

def browser_check():
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1400,'height':900});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/*',lambda route:route.abort())
            page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''recipe=>{
                state.customCrafting={available:true,custom:[recipe],vanilla:[],errors:[]};
                state.customCraftingDraft=JSON.parse(JSON.stringify([recipe]));state.customCraftingDirty=false;
                state.filters.craftMode='custom';state.filters.craftSelCustom=recipe.output_item;
                navigate('crafting');
            }''',RECIPE)
            sys.path.insert(0,str(ROOT/'tests/shared'))
            from paged_detail import reveal
            output=page.get_by_role('spinbutton',name='Output quantity for quantity_fixture',exact=True)
            ingredient=page.get_by_role('spinbutton',name='Ingredient quantity for CONSUMABLE_RUM',exact=True)
            for control,expression in ((output,'state.customCraftingDraft[0].output_quantity'),
                    (ingredient,'state.customCraftingDraft[0].ingredients[0].quantity')):
                reveal(page,control)
                assert control.get_attribute('min')=='1' and control.get_attribute('step')=='1'
                control.fill('1.5');control.blur()
                assert page.evaluate(expression)=='1.5'
                assert not control.evaluate('e=>e.validity.valid')
                result=page.evaluate('''async()=>{try{await saveCustomCrafting();return 'saved'}catch(error){return error.message}}''')
                assert 'positive whole number' in result,result
                assert page.evaluate("window.__requests.filter(r=>r.path==='/api/custom-crafting'&&r.method==='PUT').length")==0
                # Save's validation redraw must keep the invalid draft rather
                # than discarding it or applying shared blur repair.
                assert page.evaluate(expression)=='1.5'
                reveal(page,control).fill('7');control.blur()
                assert page.evaluate(expression)==7
            assert page.evaluate('customCraftingValidation().errors')==[]
            page.evaluate('''()=>{const previous=window.fetch;window.fetch=async(url,options={})=>{
                if(url.split('?')[0]==='/api/custom-crafting'&&options.method==='PUT'){
                    const recipes=JSON.parse(options.body).recipes;window.__saved=recipes;
                    return new Response(JSON.stringify({saved:recipes.length}),{status:200});
                }return previous(url,options);
            }}''')
            assert page.evaluate('saveCustomCrafting()')==1
            assert page.evaluate('window.__saved[0].output_quantity')==7
            assert page.evaluate('window.__saved[0].ingredients[0].quantity')==7
            assert not page.evaluate('state.customCraftingDirty')
            shot=Path(tempfile.gettempdir())/'lexeditor-dev'/'rdr2-crafting-quantities.png'
            shot.parent.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(shot))
            assert not errors,errors
        finally:browser.close()

if __name__=='__main__':
    service_check();browser_check()
    print('Crafting quantity rejection, atomic batch preservation, reload and browser Save passed.')
