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
        env={"LEXEDITOR_DS1_ROOT":str(game),"LEXEDITOR_DS1_PROJECT":str(mod),
             "LEXEDITOR_NO_MOD":"0","LEXEDITOR_MOD_READ_ONLY":"0"}
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

                    def open_effect():
                        page.locator('[data-tab="effects"]').click()
                        page.wait_for_function("state.tab==='effects' && state.row?.table==='SpEffectParam'")
                        page.get_by_role("searchbox",name="Search effects").fill("6890")
                        page.wait_for_function("state.row?.id===6890 && key(state.row)===state.selected")

                    def control(key):
                        first=page.locator(".lex-tweaks-pages").get_by_role("button",name="First page",exact=True)
                        if first.count() and first.is_enabled():first.evaluate("button=>button.click()")
                        for _ in range(60):
                            found=page.locator(f'[data-field-key="{key}"]:visible')
                            if found.count():return found.first
                            following=page.locator(".lex-tweaks-pages").get_by_role("button",name="Next page",exact=True)
                            if not following.count() or not following.is_enabled():break
                            following.evaluate("button=>button.click()")
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

                    page.goto(session.url);page.wait_for_selector('body[data-ds1-ready="true"]')
                    open_effect()
                    assert page.locator('[data-subtab]').evaluate_all("nodes=>nodes.map(n=>n.dataset.subtab)") == [
                        "effects-all","effects-equipment","effects-spells","effects-items"]
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
                    edit("replaceSpEffectId",6920)
                    assert "Mask of the Child" in control("replaceSpEffectId").locator('option[value="6920"]').inner_text()
                    page.screenshot(path=str(output/"effects-links.png"))
                    invalid=control(RECOVERY_KEY)
                    invalid.fill("101");invalid.press("Tab")
                    assert not invalid.evaluate("node=>node.checkValidity()")
                    current=request_json(session.url+"api/row?table=SpEffectParam&id=6890")["row"]
                    assert next(f["value"] for f in current["fields"] if f["key"]==RECOVERY_KEY)==4
                    edit(RECOVERY_KEY,4)
                    # Long groups use the shared scrolling fallback, with a fixed pager.
                    page.set_viewport_size({"width":1000,"height":700})
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    control("effectEndurance")
                    seen=set()
                    expected=set(page.evaluate("state.row.fields.filter(f=>f.editable).map(f=>f.key)"))
                    for _ in range(60):
                        visible=page.locator("[data-field-key]:visible").evaluate_all(
                            "nodes=>nodes.map(node=>{node.scrollIntoView({block:'nearest'});const box=node.getBoundingClientRect();return {key:node.dataset.fieldKey,y:box.y,height:box.height};})")
                        for box in visible:
                            assert box["y"]>=0 and box["y"]+box["height"]<=701, box
                            seen.add(box["key"])
                        next_page=page.locator(".lex-tweaks-pages").get_by_role("button",name="Next page",exact=True)
                        if not next_page.count() or not next_page.is_enabled():break
                        next_page.evaluate("button=>button.click()")
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
                    page.reload();page.wait_for_selector('body[data-ds1-ready="true"]');open_effect()
                    assert float(control(RECOVERY_KEY).input_value().replace(",",""))==4
                    edit(RECOVERY_KEY,7)
                    page.evaluate("discard()")
                    page.wait_for_function("state.dirty===0")
                    assert float(control(RECOVERY_KEY).input_value().replace(",",""))==4
                    # Follow a real item reference beyond the first list page.
                    page.locator('[data-tab="items"]').click()
                    page.locator('[data-subtab="weapons"]').click()
                    page.wait_for_function("state.row?.table==='EquipParamWeapon' && state.row.id===100")
                    link=page.get_by_role("button",name="Grass Crest Shield",exact=True)
                    for _ in range(60):
                        if link.count() and link.is_visible():break
                        next_page=page.locator(".lex-tweaks-pages").get_by_role("button",name="Next page",exact=True)
                        assert next_page.count() and next_page.is_enabled(),"Item effect link is not reachable"
                        next_page.evaluate("button=>button.click()")
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
                    page.goto(session.url+"?lexNoMod=1");page.wait_for_selector('body[data-ds1-ready="true"]')
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
