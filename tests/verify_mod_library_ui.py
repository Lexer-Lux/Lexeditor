"""Headless browser import through the real host upload and import methods."""
from pathlib import Path
import base64
import json
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.desktop_host import HostApi
from plugins.ff7r.mod_support import PakModAdapter
from plugins.ff7r.tooling import pack_directory, get_file
from core.mod_library import metadata
from core.settings_manager import SettingsStore
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-library-ui-") as temp:
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
        host._plugins = {"ff7r": SimpleNamespace(mod_adapter=PakModAdapter())}
        enabled = [True]
        update_status = {}
        host.mod_library_status = lambda plugin: {
            "root": str(library), "canManage": enabled[0], "authorTest": enabled[0],
            "message": "Mod management is not supported for this game yet."}
        def entries(plugin):
            rows = []
            for folder in (library / plugin).glob("*"):
                info = metadata(folder)
                rows.append({"path": str(folder), "name": info["name"], "version": info["version"]})
            return {**host.mod_library_status(plugin), "entries": rows, "managedUpdate": update_status}
        host.mod_library_entries = entries
        calls = []
        def bridge(_source, name, args):
            calls.append(name)
            return getattr(host, name)(*args)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.route("http://fixture.test/**", lambda route: route.fulfill(
                    body="<html><body></body></html>", content_type="text/html"))
                page.goto("http://fixture.test/")
                page.add_style_tag(path=str(ROOT / "ui/framework.css"))
                page.add_style_tag(path=str(ROOT / "plugins/ff7r/game-appearance.css"))
                page.expose_binding("hostCall", bridge)
                page.evaluate("""() => { window.pywebview = {api:new Proxy({}, {
                    get:(_,name)=>(...args)=>window.hostCall(name,args)})}; }""")
                source = (ROOT / "ui/framework.js").read_text(encoding="utf-8")
                page.add_script_tag(content=source.replace("window.LexeditorUI = {", "window.LexeditorUI = {openModLibrary,"))
                page.evaluate("LexeditorUI.openModLibrary('ff7r')")
                # A real File/FileReader travels through the folder-entry path
                # and host chunk writer. Native OS drag delivery is outside this fixture.
                page.evaluate("""payload => {
                    const file = new File([Uint8Array.from(atob(payload), x=>x.charCodeAt(0))], 'probe_P.pak');
                    const child = {isFile:true,file:resolve=>resolve(file)};
                    const folder = {isDirectory:true,name:'Wrapped',createReader:()=>{
                        let read=false; return {readEntries:resolve=>{resolve(read?[]:[child]);read=true;}};
                    }};
                    const event = new Event('drop', {bubbles:true,cancelable:true});
                    Object.defineProperty(event,'dataTransfer',{value:{items:[{webkitGetAsEntry:()=>folder}]}});
                    document.querySelector('[aria-label="Mod library"]').dispatchEvent(event);
                }""", base64.b64encode(pak.read_bytes()).decode())
                page.get_by_role("button", name="Import mod", exact=True).wait_for()
                page.get_by_label("Package data folder").select_option("Wrapped")
                page.get_by_label("Mod name", exact=True).fill("Imported test")
                page.get_by_role("button", name="Import mod", exact=True).click()
                page.get_by_text("Imported test", exact=True).wait_for()
                copied = library / "ff7r/Imported test/probe_P.pak"
                assert get_file(copied, "End/Content/Probe.txt") == b"import probe"
                assert "upload_mod_chunk" in calls and "import_mod_package" in calls
                page.get_by_role("dialog").get_by_role("button", name="Close", exact=True).click()
                assert not host._mod_uploads
                enabled[0] = False
                update_status.update(message="The managed mod update did not finish.",
                    error="No stable managed mod release is available from the configured repository yet.")
                page.evaluate("LexeditorUI.openModLibrary('ff7r')")
                page.get_by_text("No stable managed mod release", exact=False).wait_for()
                assert page.get_by_role("button", name="Import folder…").is_disabled()
                assert page.get_by_role("button", name="Apply enabled mods").is_disabled()
                assert page.get_by_role("button", name="Make editable copy…").is_disabled()
                page.get_by_role("dialog").get_by_role("button", name="Close", exact=True).click()
                enabled[0] = True
                selections = []
                host._projects = SimpleNamespace(select=lambda plugin,path: selections.append(path) or {"path":path})
                host._restart_for_project = lambda plugin,project: {"project":project}
                host.mod_library_location = lambda: {"root": str(library)}
                page.evaluate("LexeditorUI.openModLibrary('ff7r')")
                page.get_by_role("button", name="Make editable copy…").click()
                page.get_by_text("Managed mods update automatically.", exact=False).wait_for()
                page.get_by_role("button", name="Make a copy", exact=True).click()
                page.get_by_label("New mod name").fill("Independent copy")
                page.get_by_role("button", name="Create copy", exact=True).click()
                page.wait_for_function("() => !document.querySelector('[aria-label=\"New mod name\"]')")
                # Flush the pending bridge callback before inspecting output.
                page.wait_for_function("() => document.querySelector('[aria-label=\"Mod library\"] button:disabled') !== null")
                independent = library / "ff7r/Independent copy"
                assert (independent / "content/End/Content/Probe.txt").read_text() == "import probe"
                assert selections == [str(independent)]
                assert metadata(independent)["editableContent"] is True
                page.get_by_role("dialog").get_by_role("button", name="Close", exact=True).click()
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
                assert host._settings.snapshot()["modLibraryPath"] == str(destination)
                page.get_by_role("button", name="Remove recovery copy…").click()
                page.get_by_role("button", name="Remove recovery copy", exact=True).click()
                page.get_by_role("button", name="Remove recovery copy…").wait_for(state="hidden")
                assert moved.exists() and not library.exists()
                print("Browser folder import, editable copy, unsupported controls, library move and recovery cleanup passed")
            finally:
                browser.close()
                for token in list(host._mod_uploads):
                    host.end_mod_upload(token)


if __name__ == "__main__":
    main()
