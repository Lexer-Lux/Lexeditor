"""Item battle fields map to real records and share the normal save flow."""
import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from plugins.ff8 import formats
from test_shared_ui_feedback import ROOT, page, framework


@pytest.fixture
def game_files():
    root=Path(os.environ['LOCALAPPDATA'])/'Lexeditor/game-data/ff8/baseline/en'
    files={name:root/path for name,path in [('kernel.bin','main/kernel.bin'),('price.bin','menu/price.bin')]}
    if not all(p.exists() for p in files.values()):
        pytest.skip('Requires extracted FF8 baseline')
    return files


def test_item_and_battle_saves_preserve_other_bytes(game_files,tmp_path):
    for name,path in game_files.items():
        (tmp_path/name).write_bytes(path.read_bytes())
    with patch.object(formats,'source_path',side_effect=lambda name,*a:tmp_path/name),patch.object(formats,'output_path',side_effect=lambda name:tmp_path/name):
        before=(tmp_path/'kernel.bin').read_bytes()
        formats.save_items([{'id':1,'buyPrice':1230,'sellMultiplier':5}])
        formats.save_kernel(8,[{'id':1,'field':'attack_power','value':37}])
        formats.save_kernel(22,[{'id':7,'field':'attack_power','value':71}])
        assert formats.item_rows()['rows'][1]['buyPrice']==1230
        for section,index,value in [(8,1,37),(22,7,71)]:
            row=formats.kernel_rows(section)['rows'][index]
            assert next(f['value'] for f in row['fields'] if f['field']=='attack_power')==value
        after=(tmp_path/'kernel.bin').read_bytes()
        allowed={int.from_bytes(before[s*4:s*4+4],'little')+i*24+7 for s,i in [(8,1),(22,7)]}
        assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(before,after)))
        assert len(before)==len(after)


def test_items_render_and_save_battle_and_ammo(page,game_files):
    with patch.object(formats,'source_path',side_effect=lambda name,*a:game_files[name]):
        battle=formats.kernel_rows(8)
        ammo=formats.kernel_rows(22)
    core=(ROOT/'plugins/ff8/core.js').read_text()
    names=json.loads(re.search(r'const editableDatasets=(\[.*?\]);',core).group(1))
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''({names,battle,ammo})=>{
      window.state={data:Object.fromEntries(names.map(n=>[n,{rows:[]}])),base:{},tab:'items',selected:{items:1}};
      state.data.battleItems=battle;state.data.ammoEffects=ammo;
      state.data.items={rows:[{id:1,buyPrice:100,sellMultiplier:5}]};
      for(const n of names)state.base[n]=structuredClone(state.data[n].rows);
      window.calls=[];
    }''',dict(names=names,battle=battle,ammo=ammo))
    page.add_script_tag(content='''
      const {detailSection,detailField,infoHelp}=LexeditorUI;
      const signature=JSON.stringify,post=body=>({body:JSON.stringify(body)});
      const api=async(url,options)=>{calls.push({url,...JSON.parse(options.body)});return {saved:1}};
      const reloadEditable=async()=>{},shell={history:{clear(){}}},setStatus=()=>{},render=()=>{},platformChanges=()=>({});
      const showAlert=()=>{};
      function fieldSourceControl(field){return LexeditorUI.el('input',{type:'number',value:field.value,'aria-label':field.label,oninput:e=>field.value=Number(e.target.value)})}
    ''')
    records=(ROOT/'plugins/ff8/records.js').read_text()
    page.add_script_tag(content=records[:records.index('  function renderItems(')])
    boot=(ROOT/'plugins/ff8/boot.js').read_text()
    page.add_script_tag(content=boot[boot.index('  async function saveAll()'):boot.index('  function post(')])
    assert page.evaluate('itemBattleSections(0).length')==0
    assert page.evaluate('itemBattleSections(33).length')==0
    for item in (1,32,101,108):
        assert page.evaluate('id=>itemBattleSections(id).length',item)==1
    page.evaluate("document.querySelector('main').replaceChildren(...itemBattleSections(1))")
    page.get_by_label('Attack power',exact=True).fill('37')
    page.evaluate('state.data.items.rows[0].buyPrice=1230')
    page.evaluate("document.querySelector('main').replaceChildren(...itemBattleSections(108))")
    page.get_by_label('Attack power',exact=True).fill('71')
    page.evaluate('saveAll()')
    calls=page.evaluate('calls')
    assert next(c for c in calls if c['url']=='/api/items/save')['edits'][0]['buyPrice']==1230
    for section,value in ((8,37),(22,71)):
        request=next(c for c in calls if c.get('section')==section)
        assert request['edits'][0]['value']==value
    import tempfile
    page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-item-shot-effect.png'))


def test_actual_battle_controls(page,game_files):
    with patch.object(formats,'source_path',side_effect=lambda name,*a:game_files[name]):
        data={'battleItems':formats.kernel_rows(8),'ammoEffects':formats.kernel_rows(22)}
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.add_script_tag(path=str(ROOT/'plugins/ff8/core.js'))
    page.add_script_tag(content='const shell={refresh(){}};function render(){}')
    page.add_script_tag(path=str(ROOT/'plugins/ff8/party.js'))
    records=(ROOT/'plugins/ff8/records.js').read_text()
    page.add_script_tag(content=records[:records.index('  function renderItems(')])
    page.evaluate('''data=>{Object.assign(state.data,data);state.vanilla=structuredClone(data);
      document.querySelector('main').replaceChildren(...itemBattleSections(1));}''',data)
    assert page.get_by_label(re.compile('^Attack type$',re.I)).evaluate('n=>n.tagName',timeout=2000)=='SELECT'
    page.get_by_label('Attack power',exact=True).fill('37')
    assert page.evaluate("state.data.battleItems.rows[1].fields.find(f=>f.field==='attack_power').value")==37
    assert page.locator('input[type=checkbox]').count()>0
    import tempfile
    page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-item-battle-controls.png'))
