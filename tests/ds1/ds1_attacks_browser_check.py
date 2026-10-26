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
from plugins.ds1.formats import BULLET_EDITABLE, ItemDocument
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
    pc_attack=doc.list_rows('player-attacks')[0]['id']
    ranged=next((m for m in monsters if any('projectile' in r['route'].lower() for r in refs.list(m['id'])['rows'])))
    shared=next(m for m in monsters if any(len(refs.impact(r['id'])['variants'])>1 for r in refs.list(m['id'])['rows']))
    errors=[]; changes={'atkPhys':321,'atkMag':123,'atkFire':234,'atkThun':345,'atkAttribute':3,'hit0_Radius':2.5,'hitSourceType':1}
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
                    # DS1 shows no record IDs (Lexer: "dont show the id values in ds1").
                    assert f'#{first_attack}' not in preview.inner_text() and 'Physical' in preview.inner_text()
                    if output: page.wait_for_timeout(250); page.screenshot(path=str(output/'monster-attack-preview.png'))
                    follow(links.first)
                    assert page.evaluate('state.row.id')==first_attack
                    assert page.locator('.lex-hover-preview').count()==0
                    edited=set()
                    for index in range(10):
                        for key,value in changes.items():
                            field=page.locator(f'[data-field-key="{key}"]:visible')
                            if not field.count() or key in edited: continue
                            if key in ('atkAttribute','hitSourceType'):
                                assert field.evaluate('n=>n.tagName')=='SELECT'
                                if key=='atkAttribute':
                                    assert field.locator('option').all_text_contents()==['Standard','Slash','Strike','Thrust','Push']
                                else:
                                    assert field.locator('option').count()==34
                                field.select_option(str(value))
                            elif key=='hit0_Radius':
                                assert field.evaluate('n=>n.tagName')=='INPUT'
                                field.fill(str(value)); field.press('Tab')
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
                    page.locator('[data-tab="attacks"]').click()
                    page.wait_for_function('state.tab==="attacks"')
                    box=page.get_by_role('searchbox',name='Search attacks')
                    box.click(); box.press('ControlOrMeta+a'); box.press('Backspace'); box.fill(str(first_attack))
                    page.wait_for_function('(id)=>state.row?.id===id',arg=first_attack)
                    page.get_by_role('button',name='Open viewer').first.click()
                    page.wait_for_function('state.tab==="enemies" && state.selected==="NpcParam:120000"')
                    page.wait_for_selector('.lex-model-preview-open .lex-chr-viewer')
                    viewer=page.locator('.lex-chr-viewer-fields')
                    viewer.locator('[data-field-key="hit0_Radius"]').wait_for()
                    assert viewer.locator('[data-field-key="hit0_Radius"]').input_value()=='2.5'
                    assert viewer.locator('input[data-hit-slot-status="0"]').input_value()==(
                        'Live: sphere, radius 2.5 m on anchor 0.')
                    assert viewer.locator('input[data-hit-slot-status="1"]').input_value()==(
                        'Idle: radius 0 strikes nothing.')
                    open_monster(ranged['id'])
                    ranged_attack = next(r['id'] for r in refs.list(ranged['id'])['rows'] if 'projectile' in r['route'].lower())
                    follow(page.locator(f'.lex-hoverable[data-hover-target-type="ds1-attack"][data-hover-target-id="{ranged_attack}"]').first)
                    assert any('Bullet' in p for p in page.evaluate('state.row.impact.paths'))
                    if output: page.screenshot(path=str(output/'attacks-projectile.png'))
                    open_monster(shared['id'])
                    attack=next(r['id'] for r in refs.list(shared['id'])['rows'] if len(refs.impact(r['id'])['variants'])>1)
                    follow(page.locator(f'.lex-hoverable[data-hover-target-type="ds1-attack"][data-hover-target-id="{attack}"]').first)
                    page.locator('.lex-detail-panel-title .lex-info-help').wait_for()
                    assert page.locator('.lex-detail-panel-meta').count() == 0
                    assert 'changes every use' in (page.locator('.lex-detail-panel-title .lex-info-help').get_attribute('aria-label') or '')
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
                    page.locator('.lex-detail-panel-title .lex-info-help').wait_for()
                    assert page.locator('.lex-detail-panel-meta').count() == 0
                    assert 'Ownership is unresolved' in (page.locator('.lex-detail-panel-title .lex-info-help').get_attribute('aria-label') or '')
                    if output: page.screenshot(path=str(output/'attacks-unassigned.png'))
                    page.locator('[data-subtab="player-attacks"]').click()
                    page.wait_for_function('state.sub==="player-attacks" && state.rows.length>0 && state.rows.every(r=>r.table==="AtkParam_Pc")')
                    box=page.get_by_role('searchbox',name='Search attacks')
                    box.click(); box.press('ControlOrMeta+a'); box.press('Backspace'); box.fill(str(pc_attack))
                    page.wait_for_function('(id)=>state.row?.id===id && state.row.table==="AtkParam_Pc"',arg=pc_attack)
                    field=page.locator('[data-field-key="atkPhys"]:visible')
                    field.fill('321'); field.press('Tab')
                    page.wait_for_function('state.pending===0 && state.row.fields.find(f=>f.key==="atkPhys").value===321')
                    assert 'Physical (%)' in page.evaluate('state.row.fields.find(f=>f.key==="atkPhys").label')
                    assert 'Motion values' in page.evaluate('state.row.fields.find(f=>f.key==="atkPhys").group')
                    preview_html=page.evaluate('(id)=>attackPreview(id,"AtkParam_Pc").then(n=>n.outerHTML)',arg=pc_attack)
                    assert 'motion value' in preview_html and 'Physical (%)' in preview_html
                    page.evaluate('(id)=>openAttack(id,"AtkParam_Pc")',arg=pc_attack)
                    page.wait_for_function('(id)=>state.tab==="attacks" && state.sub==="player-attacks" && state.selected===`AtkParam_Pc:${id}`',arg=pc_attack)
                    if output: page.screenshot(path=str(output/'attacks-player.png'))
                    box.click(); box.press('ControlOrMeta+a'); box.press('Backspace')
                    page.locator('[data-subtab="projectiles"]').click()
                    page.wait_for_function('state.sub==="projectiles" && state.rows.length>0 && state.rows.every(r=>r.table==="Bullet") && state.row?.table==="Bullet" && !state.error')
                    assert {f['key'] for f in page.evaluate('state.row.fields')}==set(BULLET_EDITABLE)
                    control=page.locator('input[data-field-key][type="number"][min]:visible').first
                    if not control.count(): control=page.locator('input[data-field-key][type="text"][min]:visible').first
                    key=control.get_attribute('data-field-key')
                    old=float(control.input_value() or 0)
                    low,high=float(control.get_attribute('min')),float(control.get_attribute('max'))
                    value=min(max(old+1,low),high)
                    if value==old: value=max(low,old-1)
                    control.fill(str(int(value)) if value.is_integer() else str(value)); control.press('Tab')
                    page.wait_for_function('(x)=>state.pending===0 && state.row.fields.find(f=>f.key===x.key).value===x.value',arg={'key':key,'value':value})
                    if output: page.screenshot(path=str(output/'attacks-projectiles.png'))
                    for table,key,value in [('AtkParam_Npc','atkPhys',10000),('AtkParam_Npc','atkAttribute',5),('Bullet','sfxId_Hit',1),('AtkParam_Pc','atkPhys',10000),('AtkParam_Npc','atkPhysCorrection',60001),('AtkParam_Pc','atkMagCorrection',-1)]:
                        try:
                            request_json(session.url+'api/edit',{'table':table,'id':first_attack,'field':key,'value':value})
                            raise AssertionError('Invalid edit accepted')
                        except HTTPError as error: assert error.code==400
                    open_monster(120000,attacks=False)
                    assert page.evaluate('state.monsterTab')=='attacks'
                    page.locator('.lex-tabbed-panel [data-subtab="defense"]').click()
                    page.wait_for_function('state.monsterTab==="defense"')
                    assert len(page.evaluate('state.row.fields'))==67  # 21 resistances, 45 reviewed stats, effective HP
                    assert page.locator('[data-field-key]:visible').count()>0
                    if output: page.screenshot(path=str(output/'monster-defense.png'))
                    session.stop(); session=DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),'LEXEDITOR_NO_MOD':'1','LEXEDITOR_MOD_READ_ONLY':'1'})
                    session.start()
                    page.goto(session.url+'?lexNoMod=1'); page.wait_for_selector('body[data-ds1-ready="true"]'); open_monster(120000,attacks=False)
                    assert page.locator('#global-save').is_disabled()
                    # A disabled Vanilla control still offers Create a mod when pressed.
                    control=page.locator('[data-field-key="def_phys"]:visible')
                    if not control.count(): control=page.locator('[data-field-key]:visible').first
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
    print(json.dumps({'attackFieldsSavedReloaded':len(edited),'hoverPreview':True,'projectileLinks':True,'sharedImpact':True,'viewerLink':True,'allRecords':len(refs.attack_ids),'unresolvedOwnership':True,'playerAttacks':True,'projectiles':True,'vanillaCreateModPrompt':True,'originalUnchanged':True,'browserErrors':errors}))


if __name__=='__main__':main()
