"""Chromium interaction tests for FF7 page logic with component contract doubles.

Runs the actual editor script and HTTP API with synthetic game data. Shared
component implementations, native browser networking, audio, OS process discovery and game execution are
outside this test; this is not visual acceptance. Requires playwright + Chromium.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_ff7_datasets import HttpTests, PATHS, CONFIG, Kernel, server, write_kernel
from playwright.sync_api import sync_playwright

# Deliberately small public-component contract facade. Real DOM inputs retain
# browser validation/disabled behavior; business logic is the production page.
FRAMEWORK = r'''
(()=>{
function el(tag, attrs={}, ...children){
  const node=document.createElement(tag);
  for(const [key,value] of Object.entries(attrs||{})){
    if(key.startsWith("on")&&typeof value==="function")node.addEventListener(key.slice(2),value);
    else if(key==="class"||key==="className")node.className=value;
    else if(["value","disabled","checked","type"].includes(key))node[key]=value;
    else if(value!==undefined&&value!==null)node.setAttribute(key,value);
  }
  for(const child of children.flat(Infinity))if(child!==null&&child!==undefined)node.append(child instanceof Node?child:document.createTextNode(String(child)));
  return node;
}
const panel=o=>el("section",{},el("h2",{},o.title),o.identity||null,o.body);
window.LexeditorUI={el,clone:structuredClone,columnPreferences:()=>({}),recordId:id=>String(id),infoHelp:t=>t,
  detailPanel:panel,detailSection:panel,detailField:o=>el("label",{},o.label,o.control),
  provenanceControl:o=>el("span",{},o.control,el("button",{type:"button",class:"test-restore",onclick:()=>o.apply(o.vanilla)},"Restore vanilla")),
  columnList:o=>el("div",{},...o.rows.map(row=>el("button",{type:"button","data-row":row.id,onclick:()=>o.select(row.id)},row.name))),
  pagedListDetail:o=>{
    const selected=o.rows.find(row=>row.id===o.selected)||o.rows[0];
    return el("div",{},el("input",{"aria-label":o.search.label,value:o.search.value,oninput:e=>o.search.change(e.target.value)}),
      o.master({rows:o.rows.slice(0,o.pageSize||16),selected:selected?.id,select:id=>o.change({page:0,pageSize:16,selected:id})}),selected?o.detail(selected):null);
  },
  platformConfigView:o=>{
    if(!o.config?.available)return el("div",{},o.config?.message,o.config?.path);
    const controls=(o.config.sections||[]).flatMap(s=>s.fields).map(field=>{
      let input;
      if(field.kind==="boolean")input=el("input",{type:"checkbox",checked:field.value,onchange:e=>o.change(field.id,e.target.checked)});
      else input=el("input",{type:["integer","number"].includes(field.kind)?"number":"text",value:typeof field.value==="object"?JSON.stringify(field.value):field.value,oninput:e=>o.change(field.id,["integer","number","enum"].includes(field.kind)?Number(e.target.value):e.target.value)});
      input.disabled=o.disabled;input.setAttribute("aria-label",field.id);
      return el("label",{},field.label,input);
    });
    return el("div",{},...controls);
  },
  dataMap:o=>({page:0,controls:[],content:el("div",{},...o.rows.map(row=>el("p",{},row.controls," ",row.status," ",row.notes)))}),
  sharedSettings:()=>({developerMode:false}),configureThemeSounds:()=>{},finishPluginLoading:()=>{window.testLoaded=true},
  EditHistory:class{constructor(o){this.options=o}observe(){}clear(){}},
  mountShell:o=>{
    window.testShell=o;
    const error=el("div",{id:"test-error"});
    const action=fn=>async()=>{error.textContent="";try{await fn()}catch(e){error.textContent=e.message}};
    document.querySelector(o.host).append(
      ...o.tabs.map(tab=>el("button",{type:"button",onclick:()=>o.navigate(tab.id)},tab.label)),
      el("button",{type:"button",onclick:o.help},"Data Map"),el("button",{type:"button",onclick:o.info},"Info"),
      el("button",{type:"button",id:"test-save",onclick:action(o.save)},"Save"),
      el("button",{type:"button",id:"test-discard",onclick:action(o.discard)},"Discard"),error);
    return {refresh:()=>{window.testDirty=o.dirtyCount()}};
  }
};
})();
'''


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()

    @classmethod
    def tearDownClass(cls):
        cls.playwright.stop()

    def setUp(self):
        self.browser = self.playwright.chromium.launch(headless=True,
            executable_path=os.environ.get("CHROMIUM") or shutil.which("chromium") or None)
        self.addCleanup(self.browser.close)
        self.backend = HttpTests("test_missing_kernel_still_exposes_dashboard_map_and_tweaks")
        self.backend.setUp()
        self.addCleanup(self.backend.doCleanups)
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page.set_default_timeout(5000)
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.failures = {}
        self.page.expose_function("testRequest", self.bridge_request)

    def bridge_request(self, path, options):
        if path in self.failures:
            return {"status": 400, "body": json.dumps({"error": self.failures[path]})}
        payload = json.loads(options["body"]) if options.get("body") else None
        status, body = self.backend.request(path, payload)
        return {"status": status, "body": json.dumps(body, ensure_ascii=False)}

    def open(self):
        # Offline page harness: no browser network access or policy changes.
        self.page.goto("about:blank")
        html = (server.PLUGIN_ROOT / "editor.html").read_text()
        bridge = "window.fetch=async(path,options={})=>{const r=await window.testRequest(path,options);return new Response(r.body,{status:r.status})};"
        identity = {"id": server.PLUGIN_ID, "name": server.PLUGIN_NAME, "edition": server.PLUGIN_EDITION}
        html = html.replace('<script src="/shared/framework.js"></script>', '<script>' + FRAMEWORK + bridge + 'window.__lexeditorPlugin=' + json.dumps(identity) + ';</script>')
        html = html.replace('<link rel="stylesheet" href="/shared/framework.css">', '')
        self.page.set_content(html)
        self.page.wait_for_function("window.testLoaded === true")

    def click(self, label):
        self.page.locator("header").get_by_role("button", name=label, exact=True).click()

    def test_kernel_api_failure_keeps_auxiliary_tabs_and_runtime_detection(self):
        self.failures["/api/data"] = "Broken test kernel"
        self.open()
        self.assertIn("Broken test kernel", self.page.locator("main").inner_text())
        self.click("Data Map")
        self.assertIn("Characters", self.page.locator("main").inner_text())
        self.click("Info")
        self.assertIn("Game root", self.page.locator("main").inner_text())
        self.click("Tweaks")
        self.assertIn("FFNx.toml", self.page.locator("main").inner_text())
        (self.backend.game / "FFNx.toml").write_bytes(CONFIG)
        self.page.get_by_label("windowed", exact=True).wait_for(timeout=8000)
        self.assertEqual(self.page.get_by_label("ff8_option", exact=True).count(), 0)
        self.assertEqual(self.page.evaluate("state.dataMap.rows.find(row=>row.category==='tweaks').status"), "integrated")
        self.page.get_by_label("windowed", exact=True).uncheck()
        self.page.evaluate("window.dispatchEvent(new Event('focus'))")
        self.assertFalse(self.page.get_by_label("windowed", exact=True).is_checked())
        external = CONFIG.replace(b"volume = 60", b"volume = 70")
        (self.backend.game / "FFNx.toml").write_bytes(external)
        self.click("Save")
        self.page.wait_for_function("document.querySelector('#test-error').textContent.includes('changed outside')")
        self.assertEqual((self.backend.game / "FFNx.toml").read_bytes(), external)
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.get_by_role("button", name="Reload settings", exact=True).click()
        self.page.wait_for_function("!state.platformLoading")
        self.assertTrue(self.page.get_by_label("windowed", exact=True).is_checked())
        self.assertEqual(self.page.get_by_label("volume", exact=True).input_value(), "70")
        self.assertEqual(self.errors, [])

    def test_character_save_invalid_input_and_vanilla_for_both_editions(self):
        for index, relative in enumerate(PATHS):
            with self.subTest(edition=relative):
                (self.backend.game / PATHS[1-index]).unlink(missing_ok=True)
                write_kernel(self.backend.game / relative)
                with patch.object(server, "PLUGIN_ID", "ff7-2013" if index == 0 else "ff7"):
                    self.open()
                self.click("Tweaks")
                tab = self.page.get_by_role("tab", name="FFNx", exact=True)
                self.assertTrue(tab.is_visible())
                self.assertEqual(tab.get_attribute("aria-selected"), "true")
                self.assertTrue(self.page.get_by_role("tabpanel", name="FFNx", exact=True).is_visible())
                self.click("Characters")
                self.assertEqual(self.page.locator("main button[data-row]").count(), 9)
                strength = self.page.get_by_label("Strength for Slot0", exact=True)
                strength.fill("33")
                self.click("Save")
                self.page.wait_for_function("!state.saving && window.testDirty === 0")
                target = self.backend.project / relative
                self.assertEqual(Kernel(target).records("characters")[0]["values"]["strength"], 33)
                self.assertEqual(Kernel(self.backend.game / relative).records("characters")[0]["values"]["strength"], 2)
                self.page.locator('main button[data-row="8"]').click()
                self.page.get_by_label("Kills to learn level 2 for Slot8", exact=True).fill("500")
                self.click("Save")
                self.page.wait_for_function("!state.saving && window.testDirty === 0")
                self.assertEqual(Kernel(target).records("characters")[8]["values"]["killsForLimit2"], 500)
                self.page.get_by_label("Strength for Slot8", exact=True).fill("")
                self.click("Save")
                self.assertIn("Correct the empty", self.page.locator("#test-error").inner_text())
                self.click("Discard")
                self.page.evaluate("testShell.selectProjectSource('vanilla')")
                self.assertTrue(self.page.get_by_label("Strength for Slot8", exact=True).is_disabled())
                before = self.page.evaluate("JSON.stringify(state.records)")
                self.page.locator(".test-restore").first.evaluate("node=>node.click()")
                self.assertEqual(self.page.evaluate("JSON.stringify(state.records)"), before)
        self.assertEqual(self.errors, [])

    def test_platform_api_failure_does_not_hide_characters(self):
        write_kernel(self.backend.game / PATHS[0])
        self.failures["/api/platform-config"] = "Bad test configuration"
        self.open()
        self.click("Characters")
        self.assertEqual(self.page.locator("main button[data-row]").count(), 9)
        self.click("Tweaks")
        self.assertIn("Bad test configuration", self.page.locator("main").inner_text())
        self.assertEqual(self.errors, [])

    def test_inflight_config_refresh_cannot_discard_new_edit(self):
        self.backend.config()
        self.open()
        self.click("Tweaks")
        self.page.wait_for_function("!state.platformLoading")
        self.page.evaluate("""() => {
            const original = window.fetch;
            window.fetch = (path,options) => path === '/api/platform-config'
                ? new Promise(resolve => {window.resolveRefresh = () => original(path,options).then(resolve)})
                : original(path,options);
        }""")
        self.page.evaluate("void refreshPlatformConfig()")
        self.page.wait_for_function("typeof window.resolveRefresh === 'function'")
        self.page.get_by_label("windowed", exact=True).uncheck()
        self.page.evaluate("void window.resolveRefresh()")
        self.page.wait_for_function("!state.platformLoading")
        self.assertFalse(self.page.get_by_label("windowed", exact=True).is_checked())
        self.assertEqual(self.page.evaluate("platformChanges().windowed"), False)
        self.assertEqual(self.errors, [])

    def install_extra(self, family):
        from verify_ff7_extended import scene_fixture, text_fixture, exe_fixture
        from games.ff7 import extended as ex
        import hashlib
        paths = {"scene":"data/battle/scene.bin", "text":"data/lang-en/kernel/kernel2.bin", "shop":"ff7_en.exe"}
        value = {"scene":scene_fixture,"text":text_fixture,"shop":exe_fixture}[family]()
        path = self.backend.game / paths[family]
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        if family == "shop":
            patched=patch.dict(ex.EXE_PROFILES,{hashlib.sha1(value).hexdigest().upper():0x400})
            patched.start();self.addCleanup(patched.stop)
        return path

    def save_wait(self):
        self.click("Save")
        self.page.wait_for_function("!state.saving")
        self.assertEqual(self.page.locator("#test-error").inner_text(),"")

    def test_scene_fields_save_without_kernel_and_keep_ai(self):
        from games.ff7.battle import SceneArchive
        source=self.install_extra("scene");before=source.read_bytes()
        self.open();self.click("Enemies")
        self.page.get_by_label("HP for Enemy0",exact=True).fill("12345")
        self.save_wait()
        self.assertEqual(SceneArchive((self.backend.project/"data/battle/scene.bin").read_bytes()).records("enemies")[0]["values"]["hp"],12345)
        self.click("Encounters")
        self.page.get_by_label("X for Battle 0",exact=True).first.fill("-123")
        self.save_wait()
        self.open();self.click("Enemies")
        self.assertEqual(self.page.get_by_label("HP for Enemy0",exact=True).input_value(),"12345")
        self.assertEqual(source.read_bytes(),before);self.assertEqual(self.errors,[])

    def test_text_and_shop_ui_persistence(self):
        from games.ff7 import extended as ex
        text=self.install_extra("text");shop=self.install_extra("shop")
        text_before,shop_before=text.read_bytes(),shop.read_bytes()
        self.open();self.click("Text")
        self.page.get_by_label("Text for Command help 0",exact=True).fill("Edited help")
        self.save_wait()
        self.click("Shops")
        self.page.get_by_label("Item ID for Shop 0",exact=True).first.fill("17")
        self.save_wait()
        self.click("Prices")
        self.page.get_by_label("Purchase price (gil) for Items 0",exact=True).fill("777")
        self.save_wait()
        self.open();self.click("Text")
        self.assertEqual(self.page.get_by_label("Text for Command help 0",exact=True).input_value(),"Edited help")
        self.assertEqual(ex.ShopExecutable((self.backend.project/"ff7_en.exe").read_bytes(),shop_before).records('shops')[0]['values']['item0'],17)
        self.assertEqual(text.read_bytes(),text_before);self.assertEqual(shop.read_bytes(),shop_before)
        self.assertEqual(self.errors,[])

    def test_partial_save_keeps_only_failed_family_dirty(self):
        write_kernel(self.backend.game/PATHS[0]);self.install_extra("text")
        self.open();self.click("Characters")
        self.page.get_by_label("Strength for Slot0",exact=True).fill("88")
        self.click("Text");self.page.get_by_label("Text for Command help 0",exact=True).fill("Pending")
        self.failures["/api/extended/save"]="Injected text write failure"
        self.click("Save");self.page.wait_for_function("!state.saving")
        self.assertIn("Injected",self.page.locator("#test-error").inner_text())
        self.assertEqual(self.page.evaluate("state.saved.characters[0].values.strength"),88)
        self.assertNotEqual(self.page.evaluate("state.saved.texts[0].values.text"),"Pending")
        self.assertGreater(self.page.evaluate("dirtyCount()"),0)
        del self.failures["/api/extended/save"]
        self.save_wait();self.assertEqual(self.page.evaluate("dirtyCount()"),0)



if __name__ == "__main__":
    unittest.main(verbosity=2, defaultTest="PageTests")
