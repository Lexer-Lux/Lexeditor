"""Production navigation shows failed reads instead of indefinite spinners."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.shared.test_shared_ui_feedback import ROOT, framework, page


def screenshot(page, name):
    if folder := os.environ.get("LEXEDITOR_NAV_FAILURE_SHOTS"):
        page.screenshot(path=str(Path(folder) / name))


@pytest.mark.parametrize("failure", ["http", "json", "sync"])
def test_rdr2_page_failure_retry_preserves_drafts(page, failure):
    core = (ROOT / "plugins/rdr2/core.js").read_text(encoding="utf-8")
    renderer = core[core.index("let renderRevision="):core.index("function refreshGlobalSave()")]
    api = core[core.index("async function api("):core.index("// ---------- reference datasets")]
    framework(page)
    page.evaluate("""()=>{
      document.body.insertAdjacentHTML('afterbegin','<nav><button data-tab="ai">AI</button><button data-tab="items">Items</button></nav><div id="toolbar"></div>');
      window.failedRequests=true;window.contexts=0;
    }""")

    def response(route):
        if page.evaluate("failedRequests"):
            route.fulfill(status=500, body="not json" if failure == "json" else '{"error":"Missing AI source"}', content_type="application/json")
        else:
            route.fulfill(json={"text": "Reopened AI records"})

    page.route("http://fixture/api/page*", response)
    page.add_script_tag(content="""
      const $=s=>document.querySelector(s),el=LexeditorUI.el;
      const state={booting:false,tab:'ai',ds:'mine',filters:{},priceEdits:{untouched:'123'}};
      const refreshGlobalSave=()=>{},installTabContext=()=>contexts++;
      const TABS={ai:async()=>{
        if(window.failureMode==='sync'&&failedRequests)throw new Error('Synchronous page failure');
        const data=await api('/api/page');$('#main').textContent=data.text;
      },items:()=>{$('#main').textContent='Selected item';}};
    """ + api + renderer)
    page.evaluate("mode=>{window.failureMode=mode;return render();}", failure)
    expect(page.locator("#main .lex-panel-loading")).to_have_count(0)
    expect(page.locator("#main .lex-notice")).to_contain_text("Could not load editor data")
    expect(page.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    assert page.evaluate("state.priceEdits") == {"untouched": "123"}
    if failure == "http":
        screenshot(page, "rdr2-page-failure.png")
    page.evaluate("failedRequests=false")
    page.get_by_role("button", name="Retry", exact=True).click()
    expect(page.locator("#main")).to_have_text("Reopened AI records")
    assert page.evaluate("state.priceEdits") == {"untouched": "123"}
    assert page.evaluate("state.pageError") is False


def test_delayed_rdr2_failure_does_not_replace_new_page(page):
    core = (ROOT / "plugins/rdr2/core.js").read_text(encoding="utf-8")
    renderer = core[core.index("let renderRevision="):core.index("function refreshGlobalSave()")]
    framework(page)
    page.evaluate("document.body.insertAdjacentHTML('afterbegin','<div id=toolbar></div>')")
    page.add_script_tag(content="""
      const $=s=>document.querySelector(s),el=LexeditorUI.el;
      const state={booting:false,tab:'ai',ds:'mine',filters:{},priceEdits:{untouched:'123'}};
      let rejectRead;window.contexts=0;
      const refreshGlobalSave=()=>{},installTabContext=()=>contexts++;
      const TABS={ai:()=>new Promise((resolve,reject)=>{rejectRead=reject}),
        items:()=>{$('#main').textContent='Selected item';$('#toolbar').textContent='Item tools';}};
    """ + renderer)
    page.evaluate("window.pending=render();undefined")
    page.wait_for_function("typeof rejectRead==='function'")
    page.evaluate("async()=>{state.tab='items';await render();rejectRead(new Error('Delayed missing source'));await pending;}")
    expect(page.locator("#main")).to_have_text("Selected item")
    expect(page.locator("#toolbar")).to_have_text("Item tools")
    assert page.evaluate("contexts") == 1
    assert page.evaluate("state.pageError") is False


@pytest.mark.parametrize("failure", ["http", "json", "shape"])
def test_stardew_startup_failure_survives_navigation_and_retries(page, failure):
    framework(page)
    page.evaluate("document.body.insertAdjacentHTML('afterbegin','<header id=lexeditor-shell></header>');window.failStartup=true")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def response(route):
        if route.request.url.endswith("/dashboard") and failure != "shape" and page.evaluate("failStartup"):
            route.fulfill(status=500, body="not json" if failure == "json" else '{"error":"Missing Stardew data export"}', content_type="application/json")
        elif route.request.url.endswith("/dashboard"):
            route.fulfill(json={"project": {"root": "Authored project"}})
        elif route.request.url.endswith("/datamap"):
            route.fulfill(json={"rows": []})
        elif failure == "shape" and page.evaluate("failStartup"):
            route.fulfill(json={"rows": None})
        else:
            route.fulfill(json={"rows": [], "sha256": "authored", "baseSource": {"available": True}})

    page.route("http://fixture/api/**", response)
    page.add_style_tag(path=str(ROOT / "plugins/stardew_valley/editor.css"))
    page.add_script_tag(path=str(ROOT / "plugins/stardew_valley/editor.js"))
    expect(page.locator("#main .lex-notice")).to_contain_text("Could not load Stardew Valley project")
    page.evaluate("navigate('datamap')")
    expect(page.locator("#main .lex-panel-loading")).to_have_count(0)
    expect(page.locator("#main .lex-notice")).to_contain_text("Could not load Stardew Valley project")
    page.evaluate("navigate('objects')")
    expect(page.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    if failure == "http":
        screenshot(page, "stardew-startup-failure.png")
    page.evaluate("failStartup=false")
    page.get_by_role("button", name="Retry", exact=True).click()
    expect(page.locator("#main .lex-panel-loading")).to_have_count(0)
    expect(page.locator("#main .lex-notice")).not_to_contain_text("Could not load Stardew Valley project")
    assert page.evaluate("state.dashboard.project.root") == "Authored project"
    assert page.evaluate("state.loadError") == ""
    assert page.evaluate("dirtyCount()") == 0
    assert errors == []
