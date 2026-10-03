"""DS1's real Data Map links and read-only archive browsing."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive,make_text_archive
from plugins.ds1 import texts
from plugins.ds1.formats import TABLES,ItemDocument
from plugins.ds1.store import RELATIVE,MARKER,ItemStore
from plugins.ds1.data_map import payload
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-map-') as temporary:
        root=Path(temporary);game=root/'game';mod=root/'mod';mod.mkdir();(mod/MARKER).touch()
        archives={RELATIVE:make_archive(),texts.RELATIVE:make_text_archive()}
        for relative,data in archives.items():
            path=game/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        store=ItemStore(game,mod,False)
        document=store.get()
        document.members['Unreviewed.param']=object()
        unknown=next(row for row in payload(store)['rows'] if row['filename']=='Unreviewed.param')
        assert unknown['coverage']=='unavailable' and unknown['status']=='not-integrated'
        assert not unknown['openable'] and 'target' not in unknown
        del document.members['Unreviewed.param']
        document.texts.entries.append(SimpleNamespace(name='extra/Unreviewed.fmg'))
        unknown=next(row for row in payload(store)['rows'] if row['filename']=='Unreviewed.fmg')
        assert unknown['coverage']=='unavailable' and not unknown['openable']
        document.texts=None
        names=[row for row in payload(store)['rows'] if row['id'].startswith('name:')]
        assert len(names)==5 and all(not row['openable'] and row['coverage']=='unavailable' for row in names)
        with DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),
                         'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0'}) as session:
            rows=request_json(session.url+'api/data-map')['rows']
            members=set(ItemDocument(archives[RELATIVE]).members)
            assert {row['filename'] for row in rows if row['id'].startswith('param:')}==members
            assert len({row['id'] for row in rows})==len(rows)==len(members)+5
            assert all(row['status']=='partial' for row in rows if row['openable'])
            by_file={row['filename']:row for row in rows}
            assert by_file['BehaviorParam.param']['coverage']=='view'
            assert by_file['Bullet.param']['coverage']=='view'
            assert by_file['NpcParam.param']['target']=='enemies'
            assert by_file['AtkParam_Npc.param']['target']=='attacks'
            assert by_file['EquipParamWeapon.param']['sub']=='weapons'
            assert by_file['EquipParamAccessory.param']['sub']=='rings'
            with sync_playwright() as play:
                browser=play.chromium.launch(headless=True)
                try:
                    page=browser.new_page(viewport={'width':1200,'height':800});errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(session.url);page.wait_for_selector('body[data-ds1-ready="true"]')
                    for filename,target,sub in [('EquipParamWeapon.param','items','weapons'),
                            ('NpcParam.param','enemies','monsters'),('AtkParam_Npc.param','attacks','attacks'),
                            ('Accessory_name_.fmg','items','rings')]:
                        page.get_by_role('button',name='Open Dark Souls Data Map',exact=True).click()
                        page.wait_for_selector('.lex-data-map-table')
                        page.evaluate('''filename=>{state.mapQuery=filename;state.mapPage=0;render()}''',filename)
                        page.locator('.lex-data-map-table .lex-column-list-row').filter(has_text=filename).click()
                        page.locator('.lex-data-map-open').click()
                        page.wait_for_function('''({target,sub})=>state.tab===target&&state.sub===sub&&state.rows.length>0&&!state.error''',arg={'target':target,'sub':sub})
                    assert request_json(session.url+'api/state')['dirtyCount']==0
                    page.get_by_role('button',name='Open Dark Souls Data Map',exact=True).click()
                    page.wait_for_selector('.lex-data-map-table')
                    page.evaluate('state.mapQuery="";render()')
                    shot=Path(tempfile.gettempdir())/'lexeditor-dev'/'ds1-data-map.png'
                    shot.parent.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(shot))
                    assert not errors,errors
                finally:browser.close()
            assert not (mod/RELATIVE).exists() and not (mod/texts.RELATIVE).exists()
            assert sorted(path.name for path in mod.iterdir())==[MARKER]
            for relative,data in archives.items():assert (game/relative).read_bytes()==data
    print('DS1 Data Map coverage, real-service links, missing/unknown protection and unchanged archives passed.')


if __name__=='__main__':main()
