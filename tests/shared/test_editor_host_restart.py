"""After a mod is created or renamed, the editor's new page finishes loading.

Creating, renaming, choosing or copying a mod restarts the plugin on a new
port, and the editor frame navigates there. The menu only answered the
frame's original origin (it moved only after restart_plugin), so the new
page's editor_ready was dropped and Lexer sat on "Loading editor..." forever.
"""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

MENU = """<!doctype html><div id="chooser-surface">menu</div><script>
window.__lexChooser = {load: async () => {}};
window.pywebview = {api: {
  set_dirty_count: async () => true,
  create_mod_project: async () => ({url: 'http://second.test/', identity: 'session-2'}),
  open_plugin_repository: async () => ({url: 'https://github.com/Lexer-Lux/Lexeditor'}),
}};
</script>"""

# The editor page: says it is ready, and on the first one asks to create a
# mod, then follows the result the way the framework does.
EDITOR = """<!doctype html><title>waiting</title><script>
let next = 1;
const call = (method, args = []) => new Promise(resolve => {
  const id = next++;
  addEventListener('message', function answer(event) {
    if (event.data?.type !== 'lexeditor-host-result' || event.data.id !== id) return;
    removeEventListener('message', answer);
    resolve(event.data);
  });
  parent.postMessage({type: 'lexeditor-host-call', id, method, args}, '*');
});
(async () => {
  const ready = await call('editor_ready');
  document.title = 'ready:' + location.host;
  if (location.host === 'first.test') {
    // A plain link result must not move the origin.
    await call('open_plugin_repository');
    const created = await call('create_mod_project', ['ds1', 'New mod']);
    location.href = created.result.url;
  }
})();
</script>"""


@pytest.fixture()
def page():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            yield browser.new_page()
        finally:
            browser.close()


def test_the_page_a_restart_opens_is_answered(page):
    page.route("http://menu.test/**", lambda route: route.fulfill(body=MENU, content_type="text/html"))
    for host in ("first.test", "second.test"):
        page.route(f"http://{host}/**", lambda route: route.fulfill(body=EDITOR, content_type="text/html"))
    page.goto("http://menu.test/")
    page.add_script_tag(path=str(ROOT / "ui" / "editor-host.js"))
    page.evaluate("LexeditorHost.open('http://first.test/')")
    second = None
    for _ in range(100):
        second = next((frame for frame in page.frames if frame.url.startswith("http://second.test")), None)
        if second:
            break
        page.wait_for_timeout(100)
    assert second, [frame.url for frame in page.frames]
    second.wait_for_function("document.title === 'ready:second.test'", timeout=5000)
