"""Rendered Effects controls, links, persistence and protected Vanilla."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_effects_fixture import make_effects_archive
from plugins.ds1.formats import ItemDocument
from plugins.ds1.effects import TABLE, RECOVERY_KEY
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv)>1 else Path(tempfile.gettempdir())/"lexeditor-dev"/"ds1-effects"
    output.mkdir(parents=True,exist_ok=True)
    raw=make_effects_archive()
    errors=[]
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-effects-ui-") as folder:
        root=Path(folder);game=root/"game";mod=root/"mod"
        (game/RELATIVE).parent.mkdir(parents=True);(game/RELATIVE).write_bytes(raw)
        mod.mkdir();(mod/MARKER).touch()
        (game.parent/"library").mkdir(exist_ok=True)  # Apply reads an empty library of its own
        env={"LEXEDITOR_DS1_ROOT":str(game),"LEXEDITOR_DS1_PROJECT":str(mod),
             "LEXEDITOR_NO_MOD":"0","LEXEDITOR_MOD_READ_ONLY":"0","LEXEDITOR_DS1_MODS_ROOT":str(game.parent/"library")}
        session=DS1Session(env)
        try:
            session.start()
            with sync_playwright() as play:
                launch={"headless":True}
                if os.environ.get("LEXEDITOR_TEST_CHROMIUM"):
                    launch["executable_path"]=os.environ["LEXEDITOR_TEST_CHROMIUM"]
                browser=play.chromium.launch(**launch)
                try:
                    page=browser.new_page(viewport={"width":1440,"height":900})
                    page.on("pageerror",lambda error:errors.append(str(error)))
                    page.set_default_timeout(10000)
                    page.set_default_navigation_timeout(30000)

                    def ready():
                        page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                        page.wait_for_selector('.lex-plugin-loading-screen',state='detached')
                        page.evaluate('() => document.fonts.ready')

                    def open_effect():
                        page.locator('[data-tab="effects"]').click()
                        page.wait_for_function("state.tab==='effects' && state.row?.table==='SpEffectParam'")
                        page.get_by_role("searchbox",name="Search effects").fill("6890")
                        page.wait_for_function("state.row?.id===6890 && key(state.row)===state.selected")

                    def panel_tabs():
                        return page.locator('.lex-detail .lex-tabbed-panel [data-subtab]')
                    def show_tab(index):
                        tabs=panel_tabs()
                        tab=tabs.nth(index)
                        if tab.get_attribute('aria-selected')=='true':return
                        tab_id=tab.get_attribute('data-subtab')
                        tab.click()
                        page.wait_for_function('(id)=>state.effectTab===id',arg=tab_id)
                    def control(key):
                        tabs=panel_tabs()
                        for index in range(tabs.count()):
                            show_tab(index)
                            found=page.locator(f'[data-field-key="{key}"]:visible')
                            if found.count():return found.first
                        raise AssertionError("Effect property is not reachable: "+key)

                    def edit(key,value):
                        target=control(key)
                        tag=target.evaluate("node=>node.tagName")
                        if target.get_attribute("type")=="checkbox":
                            target.set_checked(bool(value))
                        elif tag=="SELECT":
                            target.select_option(str(value))
                        else:
                            target.fill(str(value));target.press("Tab")
                        page.wait_for_function(
                            "(expected)=>state.pending===0 && state.row.fields.find(f=>f.key===expected.key)?.value===expected.value",
                            arg={"key":key,"value":int(value) if type(value) is bool else value})

                    page.goto(session.url,wait_until="domcontentloaded");ready()
                    open_effect()
                    assert page.locator('.lex-subtab-bar:not(.lex-tabbed-panel .lex-subtab-bar) [data-subtab]').evaluate_all("nodes=>nodes.map(n=>n.dataset.subtab)") == [
                        "effects-all","effects-equipment","effects-items","effects-spells"]
                    units = {}
                    for key in ("maxHpRate", "motionInterval", "changeMpRate",
                                "mpRecoverChangeSpeed", "rayCastPassedTime",
                                "poizonAttackPower", "changeMpPoint"):
                        seen = control(key).evaluate("""node => {
                            const field = node.closest('.lex-detail-field');
                            const unit = field && field.querySelector('.lex-unit');
                            const label = field && field.querySelector('.lex-detail-field-label-text');
                            return [unit && unit.textContent,
                                    unit && unit.classList.contains('lex-unit-multiplier'),
                                    label && label.textContent];
                        }""")
                        units[key] = seen
                    assert units["maxHpRate"] == ["\u00d7", True, "Maximum HP"], units
                    assert units["motionInterval"] == ["s", False, "Trigger interval"], units
                    assert units["changeMpRate"] == ["%", False, "MP damage"], units
                    assert units["mpRecoverChangeSpeed"] == ["/sec", False, "MP recovery adjustment"], units
                    assert units["rayCastPassedTime"] == ["ms", False, "Raycast Passed Time"], units
                    assert units["poizonAttackPower"] == ["pts", False, "Inflict: Poison"], units
                    assert units["changeMpPoint"] == ["pts", False, "Flat MP damage"], units
                    art = control("physicsAttackPower").evaluate(
                        "node => node.closest('.lex-detail-field').getAttribute('data-lex-icon')")
                    assert art == "physical", art
                    art = control("slashDamageCutRate").evaluate(
                        "node => node.closest('.lex-detail-field').getAttribute('data-lex-icon')")
                    assert art == "physicalDef", art
                    changes={"effectEndurance":30,"maxHpRate":1.25,RECOVERY_KEY:4,
                             "disablePoison":True,"spCategory":20,"replaceSpEffectId":6920}
                    edit("effectEndurance",30)
                    page.screenshot(path=str(output/"effects-duration.png"))
                    edit("maxHpRate",1.25);edit(RECOVERY_KEY,4)
                    page.screenshot(path=str(output/"effects-stamina.png"))
                    edit("disablePoison",True)
                    assert control("disablePoison").get_attribute("type")=="checkbox"
                    edit("spCategory",20)
                    assert control("spCategory").evaluate("node=>node.tagName")=="SELECT"
                    # Reference fields edit through the finder, not by typing.
                    control("replaceSpEffectId")
                    page.locator('.ds1-reference-field:has(.ds1-reference-face[data-field-key="replaceSpEffectId"]:visible) button.ds1-find-reference:visible').click()
                    page.get_by_role("searchbox", name="Search effects").fill("")
                    page.wait_for_function("document.querySelectorAll('.lex-search-candidate').length >= 2")
                    pick = page.locator('.lex-search-candidate[data-key="SpEffectParam:6920"]')
                    pick.scroll_into_view_if_needed()
                    box = pick.bounding_box()
                    page.mouse.move(box['x'] + 40, box['y'] + box['height'] / 2)
                    page.mouse.down()
                    page.wait_for_function('document.querySelector(".lex-searcher-bar") === null', timeout=10000)
                    page.mouse.up()
                    page.wait_for_function("state.pending===0 && state.row?.fields?.find(f=>f.key==='replaceSpEffectId')?.value===6920")
                    face = page.locator('.ds1-reference-face[data-field-key="replaceSpEffectId"]:visible')
                    face.wait_for()
                    assert "Mask of the Child" in face.inner_text()
                    page.screenshot(path=str(output/"effects-links.png"))
                    invalid=control(RECOVERY_KEY)
                    invalid.fill("101");invalid.press("Tab")
                    assert not invalid.evaluate("node=>node.checkValidity()")
                    current=request_json(session.url+"api/row?table=SpEffectParam&id=6890")["row"]
                    assert next(f["value"] for f in current["fields"] if f["key"]==RECOVERY_KEY)==4
                    edit(RECOVERY_KEY,4)
                    # Every editable property is reachable through the panel tabs.
                    page.set_viewport_size({"width":1000,"height":700})
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    seen=set()
                    expected=set(page.evaluate("state.row.fields.filter(f=>f.editable).map(f=>f.key)"))
                    tabs=panel_tabs()
                    for index in range(tabs.count()):
                        show_tab(index)
                        visible=page.locator("[data-field-key]:visible").evaluate_all(
                            "nodes=>nodes.map(node=>{node.scrollIntoView({block:'nearest'});const box=node.getBoundingClientRect();return {key:node.dataset.fieldKey,y:box.y,height:box.height};})")
                        for box in visible:
                            assert box["y"]>=0 and box["y"]+box["height"]<=701, box
                            seen.add(box["key"])
                    assert seen==expected, sorted(expected-seen)
                    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                    assert not page.locator('[data-field-key="saveCategory"]').count()
                    control(RECOVERY_KEY).scroll_into_view_if_needed()
                    page.screenshot(path=str(output/"effects-small.png"))
                    page.locator("#global-save").click()
                    page.wait_for_function("state.pending===0 && state.dirty===0")
                    saved=ItemDocument((mod/RELATIVE).read_bytes())
                    for key,value in changes.items():assert saved.value(TABLE,6890,key)==value
                    assert (game/RELATIVE).read_bytes()==raw
                    page.reload(wait_until="domcontentloaded");ready();open_effect()
                    assert float(control(RECOVERY_KEY).input_value().replace(",",""))==4
                    edit(RECOVERY_KEY,7)
                    page.evaluate("discard()")
                    page.wait_for_function("state.dirty===0")
                    assert float(control(RECOVERY_KEY).input_value().replace(",",""))==4
                    # Follow a real item reference beyond the first list page.
                    page.locator('[data-tab="items"]').click()
                    page.locator('[data-subtab="weapons"]').click()
                    page.wait_for_function("state.row?.table==='EquipParamWeapon' && state.row.id===100")
                    # An effect field opens its effect from the Open button beside it.
                    link=page.get_by_role("button",name="Open Grass Crest Shield in Effects",exact=True)
                    item_tabs=page.locator('.lex-detail .lex-tabbed-panel [data-subtab]')
                    for index in range(item_tabs.count()):
                        if link.count() and link.is_visible():break
                        tab=item_tabs.nth(index)
                        if tab.get_attribute('aria-selected')!='true':
                            tab_id=tab.get_attribute('data-subtab')
                            tab.click()
                            page.wait_for_function('(id)=>state.itemTab===id',arg=tab_id)
                    assert link.count() and link.is_visible(),"Item effect link is not reachable"
                    link.click()
                    page.wait_for_function("state.tab==='effects' && state.row?.id===6890 && !state.error")
                    assert page.evaluate("state.page>0")
                    assert page.evaluate("key(state.row)===state.selected")
                    page.screenshot(path=str(output/"effects-from-item.png"))
                    page.locator("#plugin-data-map").click()
                    page.wait_for_function("state.tab==='datamap' && state.dataMap")
                    page.get_by_role("searchbox",name="Search the data map").fill("SpEffectParam")
                    page.get_by_role("button",name="Open Effects",exact=True).wait_for()
                    page.screenshot(path=str(output/"effects-data-map.png"))
                    page.get_by_role("button",name="Open Effects",exact=True).click()
                    page.wait_for_function("state.tab==='effects' && !state.error")
                    session.stop()
                    session=DS1Session({**env,"LEXEDITOR_NO_MOD":"1","LEXEDITOR_MOD_READ_ONLY":"1"})
                    session.start()
                    page.goto(session.url+"?lexNoMod=1",wait_until="domcontentloaded");ready()
                    open_effect()
                    assert control(RECOVERY_KEY).is_disabled()
                    assert float(control(RECOVERY_KEY).input_value().replace(",",""))==10
                    assert (game/RELATIVE).read_bytes()==raw
                    assert not errors,errors
                except Exception:
                    page.screenshot(path=str(output/"failure.png"))
                    raise
                finally:
                    browser.close()
        finally:
            session.stop()
    print(json.dumps({"passed":True,"synthetic":True,"editableFields":153,
                      "screenshots":str(output),"errors":errors}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
