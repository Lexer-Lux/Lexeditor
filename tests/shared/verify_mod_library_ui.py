"""Headless browser import through the Mods tab and the real host methods."""
from pathlib import Path
import base64
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.desktop_host import HostApi
from plugins.ff7r.mod_support import PakModAdapter
from plugins.ff7r.tooling import pack_directory, get_file
from core.mod_library import metadata
from core.settings_manager import SettingsStore
from playwright.sync_api import sync_playwright
from verify_mod_library import repak_fixture


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-library-ui-") as temp, repak_fixture(Path(temp)):
        root = Path(temp)
        content = root / "content/End/Content"
        content.mkdir(parents=True)
        (content / "Probe.txt").write_text("import probe")
        pak = root / "probe_P.pak"
        pack_directory(root / "content", pak, version="V4")
        library = root / "library"
        host = HostApi.__new__(HostApi)
        host._mod_library_lock = threading.RLock()
        host._mod_uploads = {}
        host._plugins = {"ff7r": SimpleNamespace(mod_adapter=PakModAdapter(), managed_mod=None, lexmod="")}
        host._installations = SimpleNamespace(snapshot=lambda _plugin: {"root": str(root / "game")})
        host._projects = SimpleNamespace(
            snapshot=lambda _plugin: {"current": "", "canCreate": True, "projects": []},
            _spec=lambda _plugin: (None, SimpleNamespace(required_paths=[], required_any=[])),
            _problems=lambda *args: [])
        host._github = SimpleNamespace(visible_repository=lambda _repo: False)
        host._managed_mod_results = {}
        enabled = [True]
        host.mod_library_status = lambda plugin: {
            "root": str(library), "canManage": enabled[0], "authorTest": enabled[0],
            "message": "Mod management is not supported for this game yet."}
        host.mod_library_location = lambda: {"root": str(library), "move": None}
        calls = []
        def bridge(_source, name, args):
            calls.append(name)
            return getattr(host, name)(*args)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.route("http://fixture.test/**", lambda route: route.fulfill(
                    body='<html><body><main id="main"></main></body></html>', content_type="text/html"))
                page.goto("http://fixture.test/")
                page.add_style_tag(path=str(ROOT / "ui/framework.css"))
                page.add_style_tag(path=str(ROOT / "plugins/ff7r/game-appearance.css"))
                page.expose_binding("hostCall", bridge)
                page.evaluate("""() => { window.pywebview = {api:new Proxy({}, {
                    get:(_,name)=>(...args)=>window.hostCall(name,args).then(result=>{
                        (window.__completedHostCalls ||= []).push(name);return result;
                    })})}; }""")
                source = (ROOT / "ui/framework.js").read_text(encoding="utf-8")
                page.add_script_tag(content=source)
                page.evaluate("""() => {
                    document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
                    LexeditorUI.mountShell({host: '#shell', plugin: {id: 'ff7r', name: 'FF7R'},
                        tabs: [], activeTab: () => '', navigate: () => {}});
                }""")
                page.locator('[data-tab="mods"]').click()
                page.get_by_text("This game has no mods yet.").wait_for()
                # A real File/FileReader travels through the folder-entry path
                # and host chunk writer. Native OS drag delivery is outside this fixture.
                page.evaluate("""payload => {
                    const file = new File([Uint8Array.from(atob(payload), x=>x.charCodeAt(0))], 'probe_P.pak');
                    const child = {isFile:true,file:resolve=>resolve(file)};
                    const folder = {isDirectory:true,name:'Wrapped',createReader:()=>{
                        let read=false; return {readEntries:resolve=>{resolve(read?[]:[child]);read=true;}};
                    }};
                    const event = new Event('drop', {bubbles:true,cancelable:true});
                    Object.defineProperty(event,'dataTransfer',{value:{types:['Files'],
                        items:[{webkitGetAsEntry:()=>folder}]}});
                    document.querySelector('#main').dispatchEvent(event);
                }""", base64.b64encode(pak.read_bytes()).decode())
                page.get_by_role("button", name="Import mod", exact=True).wait_for()
                page.get_by_label("Package data folder").select_option("Wrapped")
                page.get_by_label("Mod name", exact=True).fill("Imported test")
                page.get_by_role("button", name="Import mod", exact=True).click()
                page.get_by_text("Imported test", exact=True).wait_for()
                copied = library / "ff7r/Imported test/probe_P.pak"
                assert get_file(copied, "End/Content/Probe.txt") == b"import probe"
                assert "upload_mod_chunk" in calls and "import_mod_package" in calls
                assert not host._mod_uploads
                enabled[0] = False
                page.locator('[data-tab="mods"]').click()
                page.wait_for_timeout(250)
                page.get_by_role("button", name="Add a mod").click()
                assert page.get_by_role("button", name="Add a folder…").is_disabled()
                assert page.get_by_role("button", name="Add a ZIP…").is_disabled()
                page.get_by_role("button", name="Cancel", exact=True).click()
                enabled[0] = True
                selections = []
                host._projects = SimpleNamespace(select=lambda plugin,path: selections.append(path) or {"path":path})
                host._restart_for_project = lambda plugin,project: {"project":project}
                page.locator('[data-tab="mods"]').click()
                page.locator(".lex-mods-page .lex-column-list").get_by_text("Imported test").click()
                page.get_by_role("button", name="Make an editable copy of Imported test", exact=True).click()
                page.get_by_text("Managed mods update automatically.", exact=False).wait_for()
                page.get_by_role("button", name="Make a copy", exact=True).click()
                page.get_by_label("New mod name").fill("Independent copy")
                page.get_by_role("button", name="Create copy", exact=True).click()
                page.wait_for_function("() => !document.querySelector('[aria-label=\\\"New mod name\\\"]')")
                # The button disables before the host copies and selects the
                # project. Wait for that actual bridge response, not its start.
                page.wait_for_function("() => window.__completedHostCalls.includes('copy_library_mod')")
                independent = library / "ff7r/Independent copy"
                assert (independent / "content/End/Content/Probe.txt").read_text() == "import probe"
                assert [Path(value).resolve() for value in selections] == [independent.resolve()], selections
                assert metadata(independent)["editableContent"] is True
                del host.mod_library_location
                host._settings = SettingsStore(root / "settings.json")
                host._settings.set_mod_library_path(library)
                host.lexeditor_settings = host._settings.snapshot
                host._session = None
                host._session_project_path = None
                host._dirty_count = 0
                destination = root / "relocated"
                host.choose_mod_library_location = lambda: {"source": str(library), "destination": str(destination)}
                host._projects = SimpleNamespace(relocate_library=lambda old,new,save: save(new))
                page.evaluate("LexeditorUI.openSettings()")
                page.get_by_role("button", name="Move…", exact=True).click()
                page.get_by_role("button", name="Move", exact=True).click()
                page.get_by_role("button", name="Remove recovery copy…").wait_for(state="visible")
                moved = destination / "ff7r/Imported test/probe_P.pak"
                assert moved.read_bytes() == copied.read_bytes()
                assert Path(host._settings.snapshot()["modLibraryPath"]).resolve() == destination.resolve()
                page.get_by_role("button", name="Remove recovery copy…").click()
                page.get_by_role("button", name="Remove recovery copy", exact=True).click()
                page.get_by_role("button", name="Remove recovery copy…").wait_for(state="hidden")
                assert moved.exists() and not library.exists()
                print("Browser Mods drop import, editable copy, unsupported controls, library move and recovery cleanup passed")
            finally:
                browser.close()
                for token in list(host._mod_uploads):
                    host.end_mod_upload(token)


if __name__ == "__main__":
    main()
