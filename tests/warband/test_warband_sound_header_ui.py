"""Sound samples use the shared heading player and scrubber."""
from pathlib import Path
import io
import os
import sys
import wave

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests/shared'))
from test_shared_ui_feedback import page, framework
from plugins.warband.module_records import dataset_data


def test_sound_header_plays_and_selects_variations(page,tmp_path):
    (tmp_path/'module_sounds.py').write_text('sounds=[("click",0,["one.wav",("two.wav",sf_priority_10)])]')
    stream=io.BytesIO()
    with wave.open(stream,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(b'\0\0'*16000)
    requests=[]
    def sound(route):
        requests.append(route.request.url)
        route.fulfill(body=stream.getvalue(),content_type='audio/wav')
    page.route('http://fixture/api/sound-sample?*',sound)
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/warband/editor.css'))
    page.evaluate("document.body.prepend(Object.assign(document.createElement('div'),{id:'toolbar'}))")
    for script in ['field_controls.js','editor.js','module_records.js']:
        page.add_script_tag(path=str(ROOT/'plugins/warband'/script))
    page.evaluate('''data=>{
      moduleRecords=WarbandModuleRecords.create({state,api:async()=>data,main:()=>document.querySelector('main'),
        toolbar:()=>document.querySelector('#toolbar'),refreshShell(){},renderApp:()=>moduleRecords.render('sounds'),
        setStatus(){},dataMapRows:()=>[{dataset:'sounds',filename:'module_sounds.py',recordLabel:'Sounds'}],sourceDraft:()=>false});
      moduleRecords.render('sounds');
    }''',dataset_data(tmp_path,'sounds'))
    play=page.get_by_role('button',name='Play click',exact=True)
    play.wait_for()
    page.wait_for_function("Number(document.querySelector('.lex-audio-scrub').max)===2")
    play.click()
    page.get_by_role('button',name='Pause click',exact=True).wait_for()
    page.get_by_role('button',name='Pause click',exact=True).click()
    page.get_by_role('slider',name='Position in click',exact=True).fill('1')
    page.get_by_role('combobox',name='Preview sample',exact=True).select_option('two.wav')
    page.wait_for_function("Number(document.querySelector('.lex-audio-scrub').max)===2")
    assert any('name=one.wav' in url for url in requests)
    assert any('name=two.wav' in url for url in requests)
    assert page.locator('.lex-detail-panel-icon .lex-audio-play').count()==1
    assert page.locator('.lex-detail-panel-heading .lex-audio-scrub').count()==1
    if destination:=os.environ.get('LEXEDITOR_UI_SCREENSHOT_DIR'):
        Path(destination).mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(Path(destination)/'warband-sound-header.png'))
