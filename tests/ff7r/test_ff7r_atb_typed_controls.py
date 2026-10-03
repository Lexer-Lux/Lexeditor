"""Per-record source schemas reach both generic detail and tweak-card controls."""
import os

from playwright.sync_api import sync_playwright

from plugins.ff7r.atb_tweaks import ATB_RESIDENT_ASSET
from plugins.ff7r.plugin import FF7RSession
import test_ff7r_atb_tweaks as fixtures


def test_mixed_resident_types_use_source_bounds_and_real_save_reload(tmp_path):
    fixture_root = tmp_path / "fixtures"
    fixtures._index(fixture_root)
    game, project = tmp_path / "game", tmp_path / "project"
    (game / "End/Content/Paks").mkdir(parents=True)
    project.mkdir()
    with FF7RSession({
        "LEXEDITOR_FF7R_ROOT": str(game), "LEXEDITOR_FF7R_DATA_ROOT": str(tmp_path / "data"),
        "LEXEDITOR_FF7R_PROJECT": str(project), "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture_root),
        "LEXEDITOR_MOD_READ_ONLY": "0", "LEXEDITOR_NO_MOD": "0",
    }) as session, sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 950})
            posts = []
            page.on("request", lambda request: posts.append(request.post_data_json)
                    if request.method == "POST" and request.url.endswith("/api/save") else None)
            page.goto(session.url)
            page.wait_for_function("state.catalog&&state.data&&!state.busy")
            page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
            page.evaluate("async asset=>{await loadAsset(asset);state.tab='misc';state.selected=state.data.records.find(row=>row.tag.endsWith('|ParamInt')).id;render()}", ATB_RESIDENT_ASSET)
            integer = page.get_by_label("ATB Override", exact=True)
            assert integer.get_attribute("type") == "number"
            assert integer.get_attribute("step") == "1"
            assert integer.get_attribute("min") == "-2147483648"
            assert integer.get_attribute("max") == "2147483647"
            for invalid in ["1.5", "2147483648", ""]:
                integer.fill(invalid)
                failure = page.evaluate("async()=>{try{await save();return null}catch(error){return error.message}}")
                assert "Correct ATB Override" in failure
                assert not posts
                assert page.evaluate("selectedRecord().values.OverrideValue") == 0
            integer.fill("1.5")
            page.evaluate("render()")
            assert page.get_by_label("ATB Override", exact=True).input_value() == "1.5"
            page.evaluate("()=>{state.selected=state.data.records.find(row=>row.tag.endsWith('|ParamFloat')).id;render()}")
            failure = page.evaluate("async()=>{try{await save();return null}catch(error){return error.message}}")
            assert "Correct ATB Override in ATB_Player|ParamInt" in failure
            assert not posts
            page.evaluate("()=>{state.selected=state.data.records.find(row=>row.tag.endsWith('|ParamInt')).id;render()}")
            integer = page.get_by_label("ATB Override", exact=True)
            assert integer.input_value() == "1.5"
            integer.fill("2147483647")
            page.evaluate("save()")
            assert posts[-1]["edits"][0]["value"] == 2147483647
            page.evaluate("loadAsset(state.asset)")
            page.wait_for_function("state.data&&!state.busy")
            page.evaluate("()=>{state.selected=state.data.records.find(row=>row.tag.endsWith('|ParamInt')).id;render()}")
            assert page.get_by_label("ATB Override", exact=True).input_value() == "2147483647"

            page.evaluate("()=>{state.selected=state.data.records.find(row=>row.tag.endsWith('|ParamFloat')).id;render()}")
            floating = page.get_by_label("ATB Override", exact=True)
            assert floating.get_attribute("step") == "any"
            assert float(floating.get_attribute("max")) == 3.4028234663852886e38
            floating.fill("0.125")
            page.evaluate("save()")
            page.evaluate("loadAsset(state.asset)")
            page.wait_for_function("state.data&&!state.busy")
            page.evaluate("()=>{state.selected=state.data.records.find(row=>row.tag.endsWith('|ParamFloat')).id;render()}")
            assert page.get_by_label("ATB Override", exact=True).input_value() == "0.125"

            # Both callers consume the same per-record schemas.
            page.evaluate("()=>{document.querySelector('#main').replaceChildren(tweakCard({item:{name:'ATB Resident',asset:state.asset},data:state.data}))}")
            controls = page.get_by_label("ATB Override", exact=True)
            schemas = page.evaluate("state.data.records.map(row=>row.propertyOverrides.OverrideValue)")
            assert controls.count() == len(schemas)
            for i, schema in enumerate(schemas):
                assert controls.nth(i).get_attribute("step") == ("1" if schema["type"] == "INT32" else "any")
                assert float(controls.nth(i).get_attribute("min")) == schema["min"]
                assert float(controls.nth(i).get_attribute("max")) == schema["max"]
            if os.environ.get("LEX_ATB_TYPED_SCREENSHOT"):
                page.screenshot(path=os.environ["LEX_ATB_TYPED_SCREENSHOT"])
            integer_index = page.evaluate("state.data.records.findIndex(row=>row.tag.endsWith('|ParamInt'))")
            page.evaluate("""()=>{
              const entry={item:{name:'ATB Resident',asset:state.asset},data:state.data,baseline:clone(state.data)};
              state.tweaks={[state.asset]:entry};state.data=null;
              document.querySelector('#main').replaceChildren(tweakCard(entry));
            }""")
            page.get_by_label("ATB Override", exact=True).nth(integer_index).fill("2.5")
            page.evaluate("()=>{document.querySelector('#main').replaceChildren(tweakCard(state.tweaks[state.asset]))}")
            assert page.get_by_label("ATB Override", exact=True).nth(integer_index).input_value() == "2.5"
            before = len(posts)
            page.evaluate("()=>{document.querySelector('#main').replaceChildren(detailPanel({title:'Other view',body:[]}))}")
            failure = page.evaluate("async()=>{try{await save();return null}catch(error){return error.message}}")
            assert "Correct ATB Override in ATB_Player|ParamInt" in failure
            assert len(posts) == before
            page.evaluate("discard()")
            assert page.evaluate("numericDraftEntries(state.tweaks[state.asset].data).length") == 0
            assert page.evaluate("dirtyCount()") == 0
        finally:
            browser.close()
