"""Visible invalid numeric drafts must not save a prior valid value."""
import os
from playwright.sync_api import sync_playwright

import ff7r_browser_check as fixture


def test_exact_integer_drafts_save_undo_and_bounded_chances(tmp_path):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        context, page, errors = fixture.new_page(browser, fixture.document(), 1200, 800)
        try:
            power = page.get_by_label("Power", exact=True)
            assert power.get_attribute("type") == "number"
            assert power.get_attribute("step") == "1"
            assert power.get_attribute("min") == "-2147483648"
            assert power.get_attribute("max") == "2147483647"
            power.fill("77")
            assert page.evaluate("state.data.records[0].values.Power") == 77
            for invalid in ["1.5", "2147483648", "-2147483649", ""]:
                power.fill(invalid)
                assert power.input_value() == invalid
                assert page.evaluate("state.data.records[0].values.Power") == 77
                failure = page.evaluate("async()=>{try{await save();return null}catch(error){return error.message}}")
                assert "Correct Power" in failure
                assert not page.evaluate("window.__requests.some(row=>row.path==='/api/save'&&row.method==='POST')")
                assert power.input_value() == invalid
            power.fill("88")
            page.locator("#global-undo").click()
            power = page.get_by_label("Power", exact=True)
            assert power.input_value() == "10"
            page.locator("#global-redo").click()
            assert page.get_by_label("Power", exact=True).input_value() == "88"
            page.locator("#global-save").click()
            page.wait_for_function("dirtyCount()===0")
            requests = page.evaluate("window.__requests.filter(row=>row.path==='/api/save'&&row.method==='POST')")
            assert requests[-1]["body"]["edits"] == [{"entry": 0, "property": "Power", "value": 88}]
            page.evaluate("loadAsset(state.asset)")
            page.wait_for_function("state.data&&!state.busy")
            assert page.get_by_label("Power", exact=True).input_value() == "88"

            # Render the real array control in the real detail-field layout.
            page.evaluate("""()=>{
              const row={id:0,tag:'Chance fixture',values:{NormalItemPercent_Array:[50]}};
              const prop={name:'NormalItemPercent_Array',label:'Chance',type:'BYTE',array:true,editable:true,min:0,max:255};
              window.__chanceRow=row;
              document.querySelector('#main').replaceChildren(detailPanel({title:'Chance',body:[detailField({label:'Chance',control:percentInput(row,prop,0)})]}));
            }""")
            chance = page.get_by_label("Chance", exact=True)
            assert chance.get_attribute("min") == "0" and chance.get_attribute("max") == "100"
            chance.fill("75")
            assert page.evaluate("window.__chanceRow.values.NormalItemPercent_Array[0]") == 75
            before = page.evaluate("window.__requests.length")
            for invalid in ["75.5", "101", "-1", ""]:
                chance.fill(invalid)
                assert page.evaluate("window.__chanceRow.values.NormalItemPercent_Array[0]") == 75
                failure = page.evaluate("async()=>{try{await save();return null}catch(error){return error.message}}")
                assert "Correct Chance" in failure
                assert page.evaluate("window.__requests.length") == before
                assert chance.input_value() == invalid
            chance.fill("100")
            assert page.evaluate("window.__chanceRow.values.NormalItemPercent_Array[0]") == 100
            page.evaluate("""()=>{
              const row={id:0,tag:'Float fixture',values:{Multiplier:0.5}};
              const prop={name:'Multiplier',label:'Multiplier',type:'FLOAT',editable:true,min:0,max:2};
              window.__floatRow=row;
              document.querySelector('#main').append(detailPanel({title:'Float',body:[detailField({label:'Multiplier',control:numericInput(row,prop)})]}));
            }""")
            multiplier = page.get_by_label("Multiplier", exact=True)
            assert multiplier.get_attribute("type") == "number"
            assert multiplier.get_attribute("step") == "any"
            multiplier.fill("0.75")
            assert page.evaluate("window.__floatRow.values.Multiplier") == 0.75
            for invalid in ["2.1", "-0.1", "", "1e309"]:
                multiplier.fill(invalid)
                assert page.evaluate("window.__floatRow.values.Multiplier") == 0.75
                failure = page.evaluate("async()=>{try{await save();return null}catch(error){return error.message}}")
                assert "Correct Multiplier" in failure
                assert page.evaluate("window.__requests.length") == before
            multiplier.fill("1.25")
            assert page.evaluate("window.__floatRow.values.Multiplier") == 1.25
            page.screenshot(path=os.environ.get("LEX_FF7R_NUMERIC_SCREENSHOT", str(tmp_path / "ff7r-numeric-controls.png")))
            assert not errors
        finally:
            context.close()
            browser.close()


def test_invalid_only_draft_survives_redraw_record_switch_and_discard():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        context, page, errors = fixture.new_page(browser, fixture.document(), 1200, 800)
        try:
            page.get_by_label("Power", exact=True).fill("10.5")
            assert page.evaluate("dirtyCount()") == 1
            page.evaluate("render()")
            assert page.get_by_label("Power", exact=True).input_value() == "10.5"
            assert page.evaluate("state.data.records[0].values.Power") == 10
            page.evaluate("()=>{state.selected=1;render()}")
            assert page.get_by_label("Power", exact=True).input_value() == "11"
            failure = page.evaluate("async()=>{try{await save();return null}catch(error){return error.message}}")
            assert "Correct Power in MISC_000" in failure
            assert not page.evaluate("window.__requests.some(row=>row.path==='/api/save'&&row.method==='POST')")
            page.evaluate("()=>{state.selected=0;render()}")
            assert page.get_by_label("Power", exact=True).input_value() == "10.5"
            page.evaluate("discard()")
            assert page.get_by_label("Power", exact=True).input_value() == "10"
            assert page.evaluate("dirtyCount()") == 0
            assert not errors
        finally:
            context.close()
            browser.close()
