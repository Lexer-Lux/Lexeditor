"""Collision authoring uses real routes and keeps its preview through edits."""
import os
import pytest

from playwright.sync_api import sync_playwright

from plugins.ds1 import record_edits
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import RELATIVE
from ds1_fixture import make_archive
from msb_fixture import build_msb
from test_ds1_collision_store import setup,MAP
from test_ds1_collision_write import collision_source
from test_ds1_legacy_collision import legacy_source
from test_ds1_portable_collisions import HEADER,BODY


@pytest.mark.parametrize('source_name,loose',[('collision_source',False),('collision_source',True),('legacy_source',False)])
def test_collision_editor_fields_structure_history_and_preview(request,tmp_path,source_name,loose):
    collision_source=request.getfixturevalue(source_name)
    game,project,store,pair=setup(tmp_path,collision_source)
    for relative,payload in zip((HEADER,BODY),pair):
        low=relative.with_name('l'+relative.name[1:])
        (game/low).write_bytes(payload.replace(b'h0000a10',b'l0000a10').replace(b'h0001a10',b'l0001a10') if relative==HEADER else payload)
    (game/RELATIVE).parent.mkdir(parents=True,exist_ok=True)
    (game/RELATIVE).write_bytes(make_archive())
    (game/'map/MapStudio'/MAP).write_bytes(build_msb(models=(('h0000',5),),
        parts=(('collision',5,0,0,None),)))
    if loose:
        path=project/HEADER.parent/'h0000.hkx'
        path.parent.mkdir(parents=True)
        path.write_bytes(collision_source)
    with DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(project),
                     'LEXEDITOR_DS1_MODS_ROOT':str(tmp_path/'library'),
                     'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0'}) as session:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1600,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                requests=[]
                page.on('request',lambda request:requests.append((request.url,request.post_data)) if request.method=='POST' else None)
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("maps")')
                page.locator('[data-tabstrip-id="collision"]').click()
                page.wait_for_selector('.ds1-collision')
                page.wait_for_selector('[data-viewport-host][data-ready="true"]')
                assert page.evaluate('state.collision.error') == ''
                page.evaluate('window.collisionCanvas=document.querySelector("[data-viewport-host] canvas")')
                page.get_by_text('Vertex 1',exact=True).first.click()
                page.wait_for_function('state.row?.id==="v:1"')
                # A pin rebuilds the master only; the WebGL context stays alive.
                page.locator('[data-lex-auto-pin]').first.click()
                assert page.locator('.lex-barrel-grid').inner_text().count('1, 0, 0') >= 1
                assert page.evaluate('document.querySelector("[data-viewport-host] canvas")===collisionCanvas')
                page.locator('[data-field-key="posX"]').fill('4')
                page.locator('[data-field-key="posX"]').press('Tab')
                page.wait_for_function('state.pending===0&&state.row?.values.posX===4')
                assert page.evaluate('document.querySelector("[data-viewport-host] canvas")===collisionCanvas')
                page.evaluate('fieldHistory.undo()')
                page.wait_for_function('state.row?.values.posX===1')
                page.evaluate('fieldHistory.redo()')
                page.wait_for_function('state.row?.values.posX===4')
                original=page.evaluate('state.collision.rows.length')
                page.get_by_role('button',name='Duplicate collision vertex',exact=True).click()
                page.wait_for_function('(count)=>state.collision.rows.length===count+1&&!state.rowBusy',arg=original)
                page.evaluate('fieldHistory.undo()')
                page.wait_for_function('(count)=>state.collision.rows.length===count',arg=original)
                page.evaluate('fieldHistory.redo()')
                page.wait_for_function('(count)=>state.collision.rows.length===count+1',arg=original)
                page.evaluate('save()')
                page.wait_for_function('state.dirty===0')
                assert (project/record_edits.FILENAME).is_file() is (not loose)
                page.locator('[data-tabstrip-id="faces"]').click()
                page.wait_for_function('state.row?.id.startsWith("f:")')
                assert page.get_by_role('button',name='Change Vertex A',exact=True).is_visible()
                assert 'Vertex 0 (' in page.locator('.lex-detail-panel').inner_text()
                page.get_by_role('button',name='Change Vertex A',exact=True).click()
                candidate=page.locator('.lex-search-candidate').filter(has_text='Vertex 2').first
                candidate.wait_for()
                box=candidate.bounding_box()
                page.mouse.move(box['x']+35,box['y']+box['height']/2)
                page.mouse.down()
                page.wait_for_function('document.querySelector(".lex-searcher-bar")===null')
                page.mouse.move(10,10)
                page.mouse.up()
                page.wait_for_function('state.pending===0&&state.collision.kind==="faces"&&state.row?.values.vertexA===2')
                if page.locator('.lex-important-backdrop').count():
                    pytest.fail(str((page.locator('.lex-important-backdrop').inner_text(),requests)))
                page.get_by_role('button',name='Add collision face',exact=True).click()
                page.wait_for_function('state.collision.rows.length===2&&!state.rowBusy')
                page.get_by_role('button',name='Remove collision face',exact=True).click()
                page.wait_for_function('state.collision.rows.length===1&&!state.rowBusy')
                page.evaluate('commit(state.row,state.row.fields.find(f=>f.key==="vertexA"),0,null)')
                page.wait_for_function('state.pending===0&&state.row?.values.vertexA===0')
                page.get_by_role('combobox',name='Layer',exact=True).select_option('low')
                page.wait_for_function('state.collision.layer==="low"&&state.row?.table.includes("|low|")')
                assert page.evaluate('state.collision.error') == ''
                page.get_by_role('combobox',name='Layer',exact=True).select_option('high')
                page.wait_for_function('state.collision.layer==="high"&&state.row?.table.includes("|high|")')
                page.locator('[data-tabstrip-id="vertices"]').click()
                page.wait_for_function('state.row?.id.startsWith("v:")')
                if os.environ.get('LEX_COLLISION_EDITOR_CAPTURE'):
                    page.screenshot(path=os.environ['LEX_COLLISION_EDITOR_CAPTURE'])
                assert not errors,errors
            finally:
                browser.close()
