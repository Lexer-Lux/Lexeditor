"""Real rendered attack controls, shared impact, projectile navigation and save."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


def main():
    output=Path(sys.argv[1]) if len(sys.argv)>1 else None
    if output: output.mkdir(parents=True,exist_ok=True)
    source=Path(os.environ['LEXEDITOR_DS1_ACCEPTANCE_ROOT'])/RELATIVE if os.environ.get('LEXEDITOR_DS1_ACCEPTANCE_ROOT') else None
    raw=source.read_bytes() if source else make_archive()
    digest=hashlib.sha256(raw).hexdigest()
    doc=ItemDocument(raw); refs=doc.attack_references(); monsters=doc.list_rows('monsters')
    first_attack=120000 if source else 100
    ranged=next((m for m in monsters if any('projectile' in r['route'].lower() for r in refs.list(m['id'])['rows'])))
    shared=next(m for m in monsters if any(len(refs.impact(r['id'])['variants'])>1 for r in refs.list(m['id'])['rows']))
    errors=[]; changes={'atkPhys':321,'atkMag':123,'atkFire':234,'atkThun':345,'atkAttribute':3}
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-attacks-') as temp:
        game,mod=Path(temp)/'game',Path(temp)/'mod'
        (game/RELATIVE).parent.mkdir(parents=True); (game/RELATIVE).write_bytes(raw)
        mod.mkdir(); (mod/MARKER).touch()
        session=DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser=play.chromium.launch(headless=True)
                try:
                    page=browser.new_page(viewport={'width':1100,'height':800})
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    def open_monster(identity):
                        page.locator('[data-tab="enemies"]').click()
                        page.wait_for_function('state.row?.table==="NpcParam" && !state.monster')
                        page.get_by_role('searchbox',name='Search monsters').fill(str(identity))
                        try: page.wait_for_function('(id)=>state.row?.id===id',arg=identity)
                        except Exception:
                            print('NAVIGATION',page.evaluate('({tab:state.tab,selected:state.selected,query:state.query,row:state.row?.id,error:state.error})'),flush=True)
                            if output: page.screenshot(path=str(output/'navigation-error.png'))
                            raise
                        page.get_by_role('button',name='Attacks',exact=True).click()
                        page.wait_for_function('state.row?.table==="AtkParam_Npc"')
                    page.goto(session.url); page.wait_for_selector('body[data-ds1-ready="true"]')
                    open_monster(120000)
                    assert page.evaluate('state.row.id')==first_attack
                    edited=set()
                    for index in range(10):
                        for key,value in changes.items():
                            field=page.locator(f'[data-field-key="{key}"]:visible')
                            if not field.count() or key in edited: continue
                            if key=='atkAttribute':
                                assert field.evaluate('n=>n.tagName')=='SELECT'
                                assert field.locator('option').all_text_contents()==['Standard','Slash','Strike','Thrust','Push']
                                field.select_option(str(value))
                            else:
                                assert field.get_attribute('min')=='0' and field.get_attribute('max')=='9999'
                                field.fill(str(value)); field.press('Tab')
                            page.wait_for_function('(x)=>state.pending===0 && state.row.fields.find(f=>f.key===x.key).value===x.value',arg={'key':key,'value':value})
                            edited.add(key)
                        if output: page.screenshot(path=str(output/f'attacks-{index}.png'))
                        nxt=page.locator('.lex-tweaks-pages').get_by_role('button',name='Next page',exact=True)
                        if not nxt.count() or not nxt.is_enabled():break
                        nxt.click()
                    assert edited==changes.keys()
                    page.locator('#global-save').click(); page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload(); page.wait_for_selector('body[data-ds1-ready="true"]'); open_monster(120000)
                    reopened=ItemDocument((mod/RELATIVE).read_bytes())
                    for key,value in changes.items(): assert reopened.value('AtkParam_Npc',first_attack,key)==value
                    open_monster(ranged['id'])
                    assert any('projectile' in r['route'].lower() for r in page.evaluate('state.rows'))
                    attack=next(r['id'] for r in page.evaluate('state.rows') if 'projectile' in r['route'].lower())
                    page.get_by_role('searchbox',name='Search attacks').fill(str(attack))
                    page.wait_for_function('(id)=>state.row?.id===id',arg=attack)
                    assert any('Bullet' in p for p in page.evaluate('state.row.impact.paths'))
                    if output:
                        following=page.locator('.lex-tweaks-pages').get_by_role('button',name='Next page',exact=True)
                        if following.count() and following.is_enabled():following.click()
                        page.wait_for_timeout(350)
                        page.screenshot(path=str(output/'attacks-projectile.png'))
                    open_monster(shared['id'])
                    attack=next(r['id'] for r in page.evaluate('state.rows') if len(refs.impact(r['id'])['variants'])>1)
                    page.get_by_role('searchbox',name='Search attacks').fill(str(attack))
                    page.wait_for_function('(id)=>state.row?.id===id',arg=attack)
                    page.get_by_text('Shared attack damage',exact=True).wait_for()
                    page.set_viewport_size({'width':1000,'height':700}); page.wait_for_timeout(400)
                    assert page.locator('[data-field-key="atkPhys"]').evaluate('n=>n.clientWidth')>=70
                    if output: page.screenshot(path=str(output/'attacks-shared-small.png'))
                    page.locator('.lex-detail-panel-title .lex-info-help').hover()
                    page.wait_for_timeout(250)
                    if output: page.screenshot(path=str(output/'attacks-shared-help.png'))
                    page.locator('[data-subtab="all"]').click()
                    page.wait_for_function('state.allAttacks && state.rows.length>10' if source else 'state.allAttacks && state.rows.length===3')
                    assert page.evaluate('state.rows.length')==len(refs.attack_ids)
                    # A slow earlier scope response must not replace the latest list.
                    page.evaluate('''async () => {
                      const original=window.fetch;
                      window.fetch=async (...args)=>{
                        if(String(args[0]).includes('/api/attacks?')&&String(args[0]).includes('all=0'))
                          await new Promise(resolve=>setTimeout(resolve,200));
                        return original(...args);
                      };
                      try { await Promise.all([openAttacks(state.monster,false),openAttacks(state.monster,true)]); }
                      finally { window.fetch=original; }
                    }''')
                    assert page.evaluate('state.allAttacks && state.rows.length')==len(refs.attack_ids)
                    orphan=next(a for a in sorted(refs.attack_ids,reverse=True) if not refs.impact(a)['variants'])
                    page.get_by_role('searchbox',name='Search attacks').fill(str(orphan))
                    page.wait_for_function('(id)=>state.row?.id===id',arg=orphan)
                    page.get_by_text('Unresolved attack ownership',exact=True).wait_for()
                    assert page.evaluate('state.rows.find(r=>r.id===state.row.id).route')=='Not linked'
                    if output: page.screenshot(path=str(output/'attacks-unassigned.png'))
                    for table,key,value in [('AtkParam_Npc','atkPhys',10000),('AtkParam_Npc','atkAttribute',5),('AtkParam_Npc','atkPhysCorrection',1),('Bullet','atkId_Bullet',1)]:
                        try:
                            request_json(session.url+'api/edit',{'table':table,'id':first_attack,'field':key,'value':value})
                            raise AssertionError('Invalid edit accepted')
                        except HTTPError as error: assert error.code==400
                    page.get_by_role('button',name='Back to monsters',exact=True).click()
                    page.wait_for_function('!state.monster && state.row?.table==="NpcParam"')
                    assert len(page.evaluate('state.row.fields'))==18
                    session.stop(); session=DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),'LEXEDITOR_NO_MOD':'1','LEXEDITOR_MOD_READ_ONLY':'1'})
                    session.start()
                    page.goto(session.url+'?lexNoMod=1'); page.wait_for_selector('body[data-ds1-ready="true"]'); open_monster(120000)
                    assert page.locator('#global-save').is_disabled()
                    try:
                        request_json(session.url+'api/edit',{'table':'AtkParam_Npc','id':first_attack,'field':'atkPhys','value':1})
                        raise AssertionError('Vanilla edit accepted')
                    except HTTPError as error: assert error.code==403
                    assert not errors,errors
                finally: browser.close()
        finally: session.stop()
        assert hashlib.sha256((game/RELATIVE).read_bytes()).hexdigest()==digest
    if source: assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    print(json.dumps({'attackFieldsSavedReloaded':len(edited),'projectileLinks':True,'sharedImpact':True,'allRecords':len(refs.attack_ids),'unresolvedOwnership':True,'vanillaReadOnly':True,'originalUnchanged':True,'browserErrors':errors}))


if __name__=='__main__':main()
