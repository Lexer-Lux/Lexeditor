"""A read-only session refuses writes in every plugin service.

The shared UI locks Save and the editing controls when the host opened a game
without a mod, but a page can still reach its own service. The guard lives in
the shared request handler so every service gets it, and it must classify read
routes as reads: locking the editor must never stop the page from loading data.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds3"))

from core.plugin_http import READ_ONLY_MESSAGE, PluginRequestHandler  # noqa: E402

WRITES = ("/api/save", "/api/cards/save", "/api/assets/delete", "/api/assets/rename",
          "/api/deployment/export", "/api/settings/activate", "/api/build/start",
          "/api/catalog/create", "/api/deployment/revert", "/api/palschema/patch/save")
READS = ("/api/content/file", "/api/dashboard", "/api/build", "/api/settings",
         "/api/datamap", "/api/status", "/api/deployment", "/api/data", "/api/config")


class FakeService(PluginRequestHandler):
    def __init__(self):
        self.sent = []

    def send_json(self, payload, status=200):
        self.sent.append((payload, status))


@contextmanager
def read_only(value):
    with patch.dict(os.environ, {"LEXEDITOR_MOD_READ_ONLY": value}):
        yield


class GuardTests(unittest.TestCase):
    def test_writes_are_refused_in_a_read_only_session(self):
        for path in WRITES:
            service = FakeService()
            with read_only("1"):
                self.assertTrue(service.refuse_write_when_read_only(path), path)
            self.assertEqual(service.sent[0][1], 403, path)
            self.assertEqual(service.sent[0][0]["error"], READ_ONLY_MESSAGE, path)

    def test_reads_are_untouched_in_a_read_only_session(self):
        for path in READS:
            service = FakeService()
            with read_only("1"):
                self.assertFalse(service.refuse_write_when_read_only(path), path)
            self.assertEqual(service.sent, [], path)

    def test_an_editable_session_writes_normally(self):
        for value in ("0", ""):
            for path in WRITES:
                service = FakeService()
                with read_only(value):
                    self.assertFalse(service.refuse_write_when_read_only(path), path)
                self.assertEqual(service.sent, [], path)


class LiveServiceTests(unittest.TestCase):
    """The guard runs inside a real plugin service, not only in the handler."""

    def _post(self, url, payload):
        request = urllib.request.Request(
            url + "/api/save", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as reply:
                return reply.status, json.loads(reply.read() or b"{}")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_a_real_service_refuses_save_without_a_mod(self):
        from core.service_session import LocalPluginSession
        from plugins.ds3.formats import encrypt_regulation
        from test_ds3_plugin import _bnd4
        with tempfile.TemporaryDirectory(prefix="lexeditor-read-only-") as temp_name:
            temp = Path(temp_name)
            source = temp / "installed-Data0.bdt"
            source.write_bytes(encrypt_regulation(_bnd4(), iv=b"\x51" * 16))
            environment = {
                "LEXEDITOR_DS3_SOURCE": str(source),
                "LEXEDITOR_DS3_PROJECT": str(temp / "no-such-project"),
                "LEXEDITOR_DS3_ROOT": str(temp / "game"),
                "LEXEDITOR_MOD_READ_ONLY": "1",
            }
            session = LocalPluginSession(module="plugins.ds3.server", plugin_id="ds3",
                                         app_root=ROOT, check=lambda: [], extra_env=environment)
            session.start()
            try:
                status, payload = self._post(session.url, {"table": "EquipParamWeapon", "id": 1000,
                                                           "key": "weight", "edits": []})
                self.assertEqual(status, 403, payload)
                self.assertEqual(payload["error"], READ_ONLY_MESSAGE, payload)
                # Reading still works: the page and its data are not locked.
                with urllib.request.urlopen(session.url + "/api/info", timeout=20) as reply:
                    self.assertEqual(reply.status, 200)
            finally:
                session.stop()


class RenderedLockTests(unittest.TestCase):
    """A page the host marked as having no mod locks itself."""

    def _shell(self, query):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 800})
                page.route("http://fixture/**", lambda route: route.fulfill(
                    body='<div id="shell"></div><main id="main"></main>',
                    content_type="text/html"))
                page.goto(f"http://fixture/{query}")
                page.add_style_tag(path=str(ROOT / "ui/framework.css"))
                page.add_script_tag(path=str(ROOT / "ui/framework.js"))
                page.evaluate("""()=>{
                  window.saved=0;
                  LexeditorUI.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},
                    tabs:[],activeTab:()=>'',navigate(){},dirtyCount:()=>1,
                    save:async()=>{window.saved++}});
                  const input=document.createElement('input');
                  input.type='text'; input.value='Original'; input.setAttribute('aria-label','Field');
                  document.querySelector('main').append(input);
                }""")
                page.wait_for_timeout(300)
                result = page.evaluate("""()=>{
                  const save=document.querySelector('#global-save');
                  return {
                    readonly:document.documentElement.getAttribute('data-lex-project-readonly'),
                    saveDisabled:save?save.disabled:null,
                    badge:document.querySelector('.lex-shell-header .lex-badge')?.textContent||null,
                  };
                }""")
                page.locator("main input").click()
                page.keyboard.type("Edited")
                result["typed"] = page.locator("main input").input_value()
                result["saved"] = page.evaluate("window.saved")
                return result
            finally:
                browser.close()

    def test_no_mod_session_locks_editing_and_says_why(self):
        result = self._shell("?lexNoMod=1")
        self.assertEqual(result["readonly"], "true", result)
        self.assertTrue(result["saveDisabled"], result)
        self.assertEqual(result["badge"], "NO MOD", result)
        self.assertEqual(result["typed"], "Original", result)
        self.assertEqual(result["saved"], 0, result)

    def test_an_ordinary_session_still_edits(self):
        result = self._shell("")
        self.assertEqual(result["readonly"], "false", result)
        self.assertIsNone(result["badge"], result)
        self.assertIn("Edited", result["typed"], result)
        self.assertFalse(result["saveDisabled"], result)


if __name__ == "__main__":
    unittest.main()
