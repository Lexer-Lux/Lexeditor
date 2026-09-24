"""Home screen: a set-up game that still needs its shader cache purged.

Driven the way tests/warband/wse2_helper_browser_check.py drives it: the real
chooser.html with the shared framework inlined and a stubbed desktop API.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(r"C:\Lexeditor")
NOTICE = {"title": "Purge the shader cache first",
          "message": "Shader Injector can only replace shaders it watches the game compile.",
          "action": "clear_shader_cache", "actionLabel": "Clear shader cache"}
PLUGIN = {"id": "ff7r2", "name": "Final Fantasy VII Rebirth",
          "status": "added", "canOpen": True, "scanInProgress": False,
          "root": "C:/Fixture/Rebirth", "problems": [], "statusText": "Ready", "resident": False,
          "coverArt": {"state": "missing"}, "helperName": "Shader Injector",
          "helperInstalled": True, "helperInstallable": True, "helperNotice": NOTICE}

with sync_playwright() as play:
    browser = play.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    html = (ROOT / "ui/chooser.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    html = html.replace('<link rel="stylesheet" href="framework.css">',
                        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>")
    for name in ("framework.js", "editor-host.js"):
        html = html.replace(f'<script src="{name}"></script>',
                            "<script>" + (ROOT / "ui" / name).read_text(encoding="utf-8") + "</script>")
    page.set_content(html, wait_until="domcontentloaded")
    page.evaluate("""(plugin)=>{
        window.__actions=[];window.__opened=0;window.__cleared=false;
        window.pywebview={api:{
            plugins:async()=>[window.__cleared?Object.assign({},plugin,{helperNotice:null}):plugin],
            window_state:async()=>({maximized:false}),
            lexeditor_settings:async()=>({}),loading_quote:async()=>({quote:''}),
            cover_art_data_uri:async()=>({uri:''}),
            run_helper_action:async(id,action)=>{window.__actions.push([id,action]);window.__cleared=true;
              return {result:{message:'Cleared the shader cache. Rebirth rebuilds it the next time it starts.'}}},
            open_plugin:async()=>{window.__opened++;return {url:'about:blank'}},
        }};
        window.dispatchEvent(new Event('pywebviewready'));
    }""", PLUGIN)
    page.locator('[data-plugin="ff7r2"]').wait_for()
    page.wait_for_timeout(400)
    page.locator('[data-plugin="ff7r2"]').click()
    page.get_by_role("button", name="CLEAR SHADER CACHE", exact=True).wait_for()
    print("title:", page.locator("#dialog-title").inner_text())
    print("message:", page.locator("#dialog-message").inner_text()[:90])
    print("buttons:", page.eval_on_selector_all(".dialog-actions button, #dialog-actions button",
                                                "els=>els.map(e=>e.textContent.trim())"))
    print("opened without asking:", page.evaluate("window.__opened"))
    page.get_by_role("button", name="CLEAR SHADER CACHE", exact=True).click()
    page.wait_for_function("window.__actions.length===1")
    page.get_by_role("button", name="OPEN", exact=True).wait_for()
    print("action sent:", page.evaluate("window.__actions"))
    print("after:", page.locator("#dialog-message").inner_text())
    print("after buttons:", page.eval_on_selector_all(".dialog-actions button, #dialog-actions button",
                                                      "els=>els.map(e=>e.textContent.trim())"))
    page.locator("#dialog-actions button", has_text="CLOSE").first.click()
    page.wait_for_timeout(300)
    page.locator('[data-plugin="ff7r2"]').click()
    page.wait_for_timeout(500)
    print("second click opens the game directly:", page.evaluate("window.__opened"))
    print("page errors:", errors or "none")
    browser.close()
