"""Real rendered attack controls, monster links, hover previews, shared impact and save."""
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
                    def open_monster(identity,attacks=True):
                        page.locator('[data-tab="enemies"]').click()
                        page.wait_for_function('state.tab==="enemies" && state.row?.table==="NpcParam"')
                        page.get_by_role('searchbox',name='Search monsters').fill(str(identity))
                        page.wait_for_function('(id)=>state.row?.id===id && state.monsterAttacks',arg=identity)
                        if attacks:
                            page.locator('.lex-tabbed-panel [data-subtab="attacks"]').click()
                            page.wait_for_function('state.monsterTab==="attacks"')
                    def follow(link):
                        link.click()
                        page.wait_for_function('state.tab==="attacks" && state.row?.table==="AtkParam_Npc" && state.selected===`AtkParam_Npc:${state.row.id}`')
                    page.goto(session.url); page.wait_for_selector('body[data-ds1-ready="true"]')
                    open_monster(120000)
                    links=page.locator('.lex-hoverable[data-hover-target-type="ds1-attack"]')
                    assert links.count()==len(refs.list(120000)['rows'])
                    links.first.hover()
                    preview=page.locator('.lex-hover-preview')
                    preview.wait_for()
                    assert f'#{first_attack}' in preview.inner_text() and 'Physical' in preview.inner_text()
                    if output: page.wait_for_timeout(250); page.screenshot(path=str(output/'monster-attack-preview.png'))
                    follow(links.first)
                    assert page.evaluate('state.row.id')==first_attack
                    assert page.locator('.lex-hover-preview').count()==0
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
                    # The preview reads the live document, unsaved edits included.
                    open_monster(120000); links.first.hover(); preview.wait_for()
                    # Values are the shared read-only fields: inputs, so read their values.
                    assert '321' in preview.locator('input').evaluate_all('n=>n.map(x=>x.value)')
                    page.mouse.move(0,0)
                    page.locator('#global-save').click(); page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload(); page.wait_for_selector('body[data-ds1-ready="true"]')
                    reopened=ItemDocument((mod/RELATIVE).read_bytes())
                    for key,value in changes.items(): assert reopened.value('AtkParam_Npc',first_attack,key)==value
                    open_monster(ranged['id'])
                    follow(links.filter(has_text='Projectile').first)
                    assert any('Bullet' in p for p in page.evaluate('state.row.impact.paths'))
                    if output: page.screenshot(path=str(output/'attacks-projectile.png'))
                    open_monster(shared['id'])
                    attack=next(r['id'] for r in refs.list(shared['id'])['rows'] if len(refs.impact(r['id'])['variants'])>1)
                    follow(links.filter(has_text=f'#{attack} ').first)
                    page.get_by_text('Shared attack damage',exact=True).wait_for()
                    page.set_viewport_size({'width':1000,'height':700}); page.wait_for_timeout(400)
                    assert page.locator('[data-field-key="atkPhys"]').evaluate('n=>n.clientWidth')>=70
                    if output: page.screenshot(path=str(output/'attacks-shared-small.png'))
                    page.locator('.lex-detail-panel-title .lex-info-help').hover()
                    page.wait_for_timeout(250)
                    if output: page.screenshot(path=str(output/'attacks-shared-help.png'))
                    page.set_viewport_size({'width':1100,'height':800})
                    page.locator('[data-tab="attacks"]').click()
                    page.wait_for_function('state.tab==="attacks"')
                    assert page.evaluate('state.rows.length')==len(refs.attack_ids)
                    orphan=next(a for a in sorted(refs.attack_ids,reverse=True) if not refs.impact(a)['variants'])
                    page.get_by_role('searchbox',name='Search attacks').fill(str(orphan))
                    page.wait_for_function('(id)=>state.row?.id===id',arg=orphan)
                    page.get_by_text('Unresolved attack ownership',exact=True).wait_for()
                    if output: page.screenshot(path=str(output/'attacks-unassigned.png'))
                    for table,key,value in [('AtkParam_Npc','atkPhys',10000),('AtkParam_Npc','atkAttribute',5),('AtkParam_Npc','atkPhysCorrection',1),('Bullet','atkId_Bullet',1)]:
                        try:
                            request_json(session.url+'api/edit',{'table':table,'id':first_attack,'field':key,'value':value})
                            raise AssertionError('Invalid edit accepted')
                        except HTTPError as error: assert error.code==400
                    open_monster(120000,attacks=False)
                    assert page.evaluate('state.monsterTab')=='attacks'
                    page.locator('.lex-tabbed-panel [data-subtab="resistances"]').click()
                    page.wait_for_function('state.monsterTab==="resistances"')
                    assert len(page.evaluate('state.row.fields'))==18
                    assert page.locator('[data-field-key="def_phys"]:visible').count()==1
                    if output: page.screenshot(path=str(output/'monster-resistances.png'))
                    session.stop(); session=DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),'LEXEDITOR_NO_MOD':'1','LEXEDITOR_MOD_READ_ONLY':'1'})
                    session.start()
                    page.goto(session.url+'?lexNoMod=1'); page.wait_for_selector('body[data-ds1-ready="true"]'); open_monster(120000,attacks=False)
                    assert page.locator('#global-save').is_disabled()
                    # A disabled Vanilla control still offers Create a mod when pressed.
                    control=page.locator('[data-field-key="def_phys"]:visible')
                    assert control.is_disabled()
                    control.click(force=True)
                    page.get_by_text('Create a mod to edit?',exact=True).wait_for()
                    if output: page.screenshot(path=str(output/'vanilla-create-mod-prompt.png'))
                    page.get_by_role('button',name='Cancel',exact=True).click()
                    try:
                        request_json(session.url+'api/edit',{'table':'AtkParam_Npc','id':first_attack,'field':'atkPhys','value':1})
                        raise AssertionError('Vanilla edit accepted')
                    except HTTPError as error: assert error.code==403
                    assert not errors,errors
                finally: browser.close()
        finally: session.stop()
        assert hashlib.sha256((game/RELATIVE).read_bytes()).hexdigest()==digest
    if source: assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    print(json.dumps({'attackFieldsSavedReloaded':len(edited),'hoverPreview':True,'projectileLinks':True,'sharedImpact':True,'allRecords':len(refs.attack_ids),'unresolvedOwnership':True,'vanillaCreateModPrompt':True,'originalUnchanged':True,'browserErrors':errors}))


if __name__=='__main__':main()
