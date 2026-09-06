"""Offline Chromium UI checks using production HTML/CSS/JS and synthetic API data.

No game data, fonts, installed mods, HTTP navigation, or native WebView2 host is
used. History URLs are inert in this about:blank fixture; this does not test
navigation. The real editor renderers, controls and save handlers are executed.
"""
from pathlib import Path
import argparse
import json
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def document(*, unavailable=False):
    names = ('RUM', 'BRANDY', 'MOONSHINE')
    items = [dict(key='CONSUMABLE_'+key, nameKey='NAME_'+key, descriptionKey='',
                  category='CI_CATEGORY_CONSUMABLE', group='Consumables',
                  buy=[], sell=[], carry=[], effects=[], textures=[], model='',
                  tags=[{'key':'CI_TAG_ITEM_ALCOHOL', 'type':0}]) for key in names]
    vanilla = {'CONSUMABLE_RUM':0.17, 'CONSUMABLE_BRANDY':0.17, 'CONSUMABLE_MOONSHINE':0.3}
    alcohol = {'available':not unavailable, 'vanilla':vanilla if not unavailable else {},
               'overrides':{'CONSUMABLE_MOONSHINE':1},
               # A stale flattened response must not flatten the displayed baselines.
               'entries':{key:1 for key in vanilla}, 'reason':'Synthetic missing baseline'}
    datasets = {key:dict(label=key, dir='synthetic/'+key, readonly=key!='mine',
                        catalog=key=='mine', lootFiles=[]) for key in ('mine','vanilla','kiddos','prices1899')}
    responses = {'/api/config':{'datasets':datasets}, '/api/labels':{},
                 '/api/localization':{'values':{'NAME_'+key:key.title() for key in names}, 'vanilla':{}},
                 '/api/catalog':{'items':items,'effects':[]},
                 '/api/alcohol-strengths':alcohol,
                 '/api/custom-crafting':{'available':False,'custom':[]},
                 '/api/quick-select':{'available':False,'items':{},'slotsByGroup':{}}}
    fixture = """
window.__requests=[];window.__responses=RESPONSES;window.__failSave=false;
// This fixture deliberately excludes navigation/host integration.
history.replaceState=()=>{};history.pushState=()=>{};
window.fetch=async function(url,options={}) {
 const path=url.split('?')[0],body=options.body?JSON.parse(options.body):null;
 window.__requests.push({path,method:options.method||'GET',body});
 let data=window.__responses[path]||{},status=200;
 if(path==='/api/alcohol-strengths/save') {
  if(window.__failSave){data={error:'Synthetic CSV write failure'};status=500;}
  else {
   Object.assign(window.__responses['/api/alcohol-strengths'].overrides,body.entries);
   Object.assign(window.__responses['/api/alcohol-strengths'].entries,body.entries);
   data={saved:Object.keys(body.entries).length};
  }
 }
 if(path==='/api/catalog/save')data={saved:0};
 return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
};
""".replace('RESPONSES',json.dumps(responses))
    html=(ROOT/'games/rdr2/editor.html').read_text(encoding='utf-8')
    html=html.replace('<link rel="stylesheet" href="/shared/framework.css">',
                      '<style>'+(ROOT/'ui/framework.css').read_text(encoding='utf-8')+'</style>')
    html=html.replace('<script src="/shared/framework.js"></script>',
                      '<script>'+fixture+'</script><script>'+(ROOT/'ui/framework.js').read_text(encoding='utf-8')+'</script>')
    return html


def run(output: Path, executable: str | None):
    output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as playwright:
        options={'headless':True}
        if executable: options['executable_path']=executable
        browser=playwright.chromium.launch(**options)
        try:
            for case in ('save','failure','unavailable'):
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.route('**/*',lambda route:route.abort())
                page.set_content(document(unavailable=case=='unavailable'),wait_until='domcontentloaded')
                control=page.locator('.alcohol-strength input')
                expect(control).to_have_count(1)
                expect(page.locator('.loot-item')).to_have_count(3)
                page.wait_for_timeout(150)
                assert not errors,errors
                if case=='unavailable':
                    expect(control).to_be_disabled()
                    expect(control).to_have_value('')
                    expect(control).to_have_attribute('placeholder','Unavailable')
                    control.scroll_into_view_if_needed()
                    page.screenshot(path=str(output/'unavailable.png'),full_page=True)
                else:
                    expect(control).to_have_value('0.17')
                    page.locator('.loot-item').filter(has_text='CONSUMABLE_MOONSHINE').click()
                    expect(control).to_have_value('1')
                    page.locator('.loot-item').filter(has_text='CONSUMABLE_BRANDY').click()
                    expect(control).to_have_value('0.17')
                    control.scroll_into_view_if_needed()
                    page.screenshot(path=str(output/'baseline.png'),full_page=True)
                    if case=='failure':page.evaluate('window.__failSave=true')
                    control.fill('0.23');control.press('Tab')
                    expect(page.locator('#global-save')).to_be_enabled()
                    page.locator('#global-save').click()
                    page.wait_for_function("window.__requests.some(row=>row.path==='/api/alcohol-strengths/save')")
                    requests=page.evaluate("window.__requests.filter(row=>row.path==='/api/alcohol-strengths/save')")
                    assert requests==[{'path':'/api/alcohol-strengths/save','method':'POST','body':{'entries':{'CONSUMABLE_BRANDY':0.23}}}],requests
                    if case=='save':
                        page.wait_for_function('Object.keys(state.alcoholEdits).length===0')
                        expect(control).to_have_value('0.23')
                        expect(page.locator('#global-save')).to_be_disabled()
                        assert page.evaluate("state.alcohol.overrides.CONSUMABLE_MOONSHINE")==1
                    else:
                        expect(page.get_by_text('Synthetic CSV write failure',exact=True)).to_be_visible()
                        assert page.evaluate('state.alcoholEdits')=={'CONSUMABLE_BRANDY':0.23}
                        assert 'All changes saved' not in page.locator('#toast').inner_text()
                    if case=='save':control.scroll_into_view_if_needed()
                    page.screenshot(path=str(output/(case+'.png')),full_page=True)
                assert not errors,errors
                page.close()
                print('PASS: rendered offline editor '+case)
        finally:browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots',type=Path,default=ROOT/'artifacts/rdr2-browser')
    parser.add_argument('--chromium',default=None,help='optional installed Chromium executable')
    args=parser.parse_args()
    run(args.screenshots,args.chromium)
