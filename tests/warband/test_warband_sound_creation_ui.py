"""Shared Add copies a real sound source and hands the saved result to build."""
from pathlib import Path
import os
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests/shared'))
from test_shared_ui_feedback import page, framework
from plugins.warband.module_records import create_sound, dataset_data


def test_sound_creation_add_reopens_real_source(page,tmp_path):
    source=tmp_path/'module_sounds.py'
    original='sounds=[("click",sf_priority_10,["one.wav"])]\n'
    source.write_text(original)
    def route_api(route):
        if route.request.method=='POST':
            body=route.request.post_data_json
            result=create_sound(tmp_path,body['sha256'],body['recordIndex'],body['originalId'],body['id'])
        else:
            result=dataset_data(tmp_path,'sounds')
        route.fulfill(json=result)
    framework(page)
    page.route('http://fixture/api/**',route_api)
    page.add_style_tag(path=str(ROOT/'plugins/warband/editor.css'))
    page.evaluate("document.body.prepend(Object.assign(document.createElement('div'),{id:'toolbar'}))")
    for script in ['field_controls.js','editor.js','module_records.js']:
        page.add_script_tag(path=str(ROOT/'plugins/warband'/script))
    page.evaluate('''()=>{
      window.built=[];window.pending=false;
      moduleRecords=WarbandModuleRecords.create({state,api:async(url,options)=>{
        const response=await fetch(url,options);return response.json();},main:()=>document.querySelector('main'),
        toolbar:()=>document.querySelector('#toolbar'),refreshShell(){},renderApp:()=>moduleRecords.render('sounds'),
        setStatus(){},hasPendingEdits:()=>pending,onCreated:async filename=>built.push(filename),
        dataMapRows:()=>[{dataset:'sounds',filename:'module_sounds.py',recordLabel:'Sounds'}],sourceDraft:()=>false});
      moduleRecords.render('sounds');
    }''')
    add=page.locator('.lex-table-add')
    add.wait_for(state='attached')
    page.evaluate("pending=true;moduleRecords.render('sounds')")
    assert add.get_attribute('aria-disabled')=='true'
    page.evaluate("pending=false;state.activeSource='vanilla';moduleRecords.render('sounds')")
    assert add.get_attribute('aria-disabled')=='true'
    page.evaluate("state.activeSource='mine';moduleRecords.render('sounds')")
    page.locator('.warband-record-list').hover()
    add.click()
    page.get_by_role('textbox',name='New sound ID').fill('custom_click')
    if destination:=os.environ.get('LEXEDITOR_UI_SCREENSHOT_DIR'):
        Path(destination).mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(Path(destination)/'warband-create-sound.png'))
    page.get_by_role('button',name='Create and build',exact=True).click()
    page.wait_for_function("built.length===1")
    assert page.evaluate('built')==['module_sounds.py']
    assert [row['id'] for row in dataset_data(tmp_path,'sounds')['rows']]==['click','custom_click']
    assert source.with_name('module_sounds.py.lexeditor.bak').read_text()==original
    assert page.get_by_role('button',name='Play custom_click',exact=True).count()==1, page.locator('main').inner_text()
