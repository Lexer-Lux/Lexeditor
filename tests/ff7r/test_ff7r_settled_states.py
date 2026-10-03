"""Full editor empty/error states settle; only active requests show spinners."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.ff7r.ff7r_browser_check import document, new_page


@pytest.fixture
def ff7page():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        context, page, errors = new_page(browser, document(), 1200, 800)
        try:
            yield page, errors
        finally:
            context.close()
            browser.close()


CASES = {
    "characters": "state.tab='characters';state.catalog.assets=[];state.data=null",
    "enemies": "state.tab='enemies';state.catalog.assets=[];state.data=null",
    "abilities": "state.tab='abilities';state.catalog.assets=[];state.data=null",
    "economy-unavailable": "state.tab='item';state.economy={available:false,tables:[]}",
    "economy-unloaded": "state.tab='item';state.economy=null",
    "economy-failed-table": "state.tab='item';state.economy=clone(__fixture.economy);state.economyTable=state.economy.tables[0].asset;state.data=null;state.error='Selected item source failed'",
    "loot-unavailable": "state.tab='loot';state.loot={available:false,reason:'Loot source is missing'}",
    "loot-unloaded": "state.tab='loot';state.loot=null",
    "loot-failed-table": "state.tab='loot';state.loot=clone(__fixture.loot);state.data=null;state.error='Selected loot source failed'",
    "text-absent": "state.tab='text';state.catalog.textAssets=[]",
    "text-unloaded": "state.tab='text';state.textPacks=null",
    "text-failed": "state.tab='text';state.textPacks=null;state.error='Text source failed'",
    "tweaks-absent": "state.tab='tweaks';state.catalog.assets=[]",
    "tweaks-unloaded": "state.tab='tweaks';state.tweaks=null;state.tweaksPending=0",
    "tweaks-failed": "state.tab='tweaks';state.tweaks=null;state.tweaksPending=0;state.tweaksError='Tweak source failed'",
}


@pytest.mark.parametrize("case", CASES)
def test_settled_resource_state_has_visible_message_and_no_busy_spinner(ff7page, case):
    page, errors = ff7page
    page.evaluate("code=>{state.error='';state.busy=false;state.textBusy=false;" +
                  "eval(code);render();}", CASES[case])
    expect(page.locator("#main .lex-panel-loading")).to_have_count(0)
    expect(page.locator("#main .lex-notice").first).to_be_visible()
    assert page.locator("#main .lex-notice").first.inner_text().strip()
    if case == "loot-unavailable" and (folder := os.environ.get("LEXEDITOR_NAV_FAILURE_SHOTS")):
        page.screenshot(path=str(Path(folder)/"ff7r-settled-loot.png"))
    assert page.evaluate("__saveCounter") == 0
    assert errors == []


@pytest.mark.parametrize("tab", ["item", "loot"])
@pytest.mark.parametrize("result", ["empty", "json-error"])
def test_real_navigation_request_shows_loading_then_settles_without_writes(ff7page, tab, result):
    page, errors = ff7page
    page.evaluate("""tab=>{
      window.readPath=tab==='loot'?'/api/loot':'/api/economy';
      window.originalFetch=window.fetch;
      window.fetch=(url,opts)=>String(url).startsWith(readPath)
        ?new Promise(resolve=>window.finishRead=resolve):originalFetch(url,opts);
      state.economyKey='';state.lootKey='';
      window.pending=navigate(tab);
    }""", tab)
    page.wait_for_function("typeof finishRead==='function'")
    expect(page.locator("#main .lex-panel-loading")).to_have_count(1)
    assert page.evaluate("state.busy") is True
    page.evaluate("""async result=>{
      finishRead(new Response(result==='json-error'?'not json':JSON.stringify({available:false,tables:[],reason:'No supported records'}),
        {status:200,headers:{'Content-Type':'application/json'}}));
      await pending;
    }""", result)
    expect(page.locator("#main .lex-panel-loading")).to_have_count(0)
    expect(page.locator("#main .lex-notice").first).to_be_visible()
    if result == "json-error":
        expect(page.locator("#main")).to_contain_text("Invalid JSON response")
    assert page.evaluate("state.busy") is False
    assert page.evaluate("__saveCounter") == 0
    assert errors == []


def test_populated_loot_retains_controls_save_and_reopen_after_consolidation(ff7page):
    page, errors = ff7page
    page.evaluate("navigate('loot')")
    expect(page.locator("#main .lex-panel-loading")).to_have_count(0)
    chance = page.get_by_label("NormalPercent", exact=True)
    expect(chance).to_have_value("60")
    before = page.evaluate("clone(state.data.records[0].values)")
    chance.fill("70")
    expect(page.locator("#global-save")).to_be_enabled()
    page.locator("#global-save").click()
    page.wait_for_function("dirtyCount()===0")
    requests = page.evaluate("__requests.filter(r=>r.path==='/api/save'&&r.method==='POST')")
    assert requests[-1]["body"]["edits"] == [
        {"entry": 0, "property": "NormalPercent_Array", "index": 0, "value": 70}]
    page.evaluate("loadAsset(state.loot.asset)")
    expect(page.get_by_label("NormalPercent", exact=True)).to_have_value("70")
    assert page.evaluate("state.data.records[0].values") == {**before, "NormalPercent_Array": [70]}
    assert errors == []
