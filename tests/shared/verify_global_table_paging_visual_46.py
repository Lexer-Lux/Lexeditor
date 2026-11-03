"""Hidden non-FF8 acceptance for the shared paged Table panel."""

from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import base64
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.rdr import server as rdr_server  # noqa: E402
from tools.rdr_test_support import workspace  # noqa: E402
from plugins.warband.plugin import WarbandSession  # noqa: E402
from core.service_session import request_json  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


@contextmanager
def rdr_fixture():
    with tempfile.TemporaryDirectory(prefix="lexeditor-paging-rdr-") as name:
        with workspace(Path(name), count=65):
            originals = {path: path.read_bytes() for path in Path(name).rglob("*") if path.is_file()}
            service = rdr_server.create_server(0)
            worker = threading.Thread(target=service.serve_forever, daemon=True)
            worker.start()
            try:
                yield SimpleNamespace(url=f"http://127.0.0.1:{service.server_port}/")
            finally:
                service.shutdown()
                service.server_close()
                worker.join(timeout=5)
            for path, original in originals.items():
                assert path.read_bytes() == original, path


@contextmanager
def warband_fixture():
    with tempfile.TemporaryDirectory(prefix="lexeditor-paging-warband-") as name:
        project = Path(name)
        module = project / "ModuleSystem"
        module.mkdir()
        sources = {
            "module_items.py": "items = [\n" + ",\n".join(
                f'["fixture_{i:03}", "Fixture item {i:03}", '
                '[("fixture_mesh", 0)], itp_type_one_handed_wpn, itc_longsword, '
                '120, weight(1.5)|spd_rtng(97), imodbits_sword]'
                for i in range(65)) + "\n]\n",
            "module_troops.py": "troops = [\n" + ",\n".join(
                f'["troop_{i:03}", "Fixture troop {i:03}", "Fixture troops {i:03}", '
                'tf_hero, 0, 0, fac_commoners, [itm_fixture_000], '
                'str_4|agi_4|int_4|cha_4|level(10), wp(20), 0, 0]'
                for i in range(65)) + "\n]\n" + "\n".join(
                f'upgrade(troops, "troop_{i:03}", "troop_{i+1:03}")' for i in range(64)),
            "header_items.py": "itp_type_one_handed_wpn=2\nitc_longsword=1\nimodbits_sword=1\n",
            "header_troops.py": "tf_hero=16\nstr_4=4\nagi_4=1024\nint_4=262144\ncha_4=67108864\n",
        }
        for filename, source in sources.items():
            (module / filename).write_text(source, encoding="utf-8")
        (project / "settings.ini").write_text("[Test]\nenabled=1\n")
        game = project / "game"
        (game / "Modules").mkdir(parents=True)
        with WarbandSession({"LEXEDITOR_MOD_PROJECT": str(project),
                             "LEXEDITOR_WARBAND_ROOT": str(game)}) as session:
            items = request_json(session.url + "api/items")["rows"]
            assert len(items) == 65
            assert items[0]["value"] == "120" and items[0]["weight"] == "1.5"
            assert items[0]["inventoryMesh"] == "fixture_mesh"
            assert len(request_json(session.url + "api/troops")["rows"]) == 65
            assert len(request_json(session.url + "api/upgrades")["rows"]) == 64
            yield session
        for filename, source in sources.items():
            assert (module / filename).read_text(encoding="utf-8") == source


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = DEV_CACHE / "rendered" / "github-46-rdr-global-table.png"
    warband_output = DEV_CACHE / "rendered" / "github-46-warband-global-table.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-table-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with rdr_fixture() as session:
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", session.url,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1400, "height": 820, "deviceScaleFactor": 1, "mobile": False,
            })
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&!!document.querySelector('.lex-paged-list-detail')", 90)
            wait_eval(cdp, "document.fonts.status==='loaded'&&!!document.querySelector('.lex-barrel-grid>.lex-list')", 15)
            time.sleep(.5)
            initial_fit = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),master=root?.querySelector('.lex-barrelled-master'),list=root?.querySelector('.lex-barrel-grid>.lex-list'),header=list?.querySelector('.lex-column-list-header'),row=list?.querySelector('.lex-list-row');return{root:root?.getBoundingClientRect().height,master:master?.getBoundingClientRect().height,list:list?.getBoundingClientRect().height,scroll:list?.scrollHeight,client:list?.clientHeight,header:header?.getBoundingClientRect().height,row:row?.getBoundingClientRect().height,pageSize:state.itemPageSize,pager:root?.querySelector('.lex-pager')?.getBoundingClientRect().height};})()""")
            print({"plugin": "rdr", "initialFit": initial_fit})
            assert initial_fit["scroll"] <= initial_fit["client"] + 1, initial_fit
            before = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),list=root.querySelector('.lex-barrel-grid>.lex-list'),rows=[...list.querySelectorAll('.lex-list-row')],last=rows.at(-1)?.getBoundingClientRect(),box=list.getBoundingClientRect(),doc=document.documentElement;return{page:state.itemPage,pageSize:state.itemPageSize,pager:!!root.querySelector('.lex-pager'),overflow:getComputedStyle(list).overflowY,scroll:list.scrollHeight,client:list.clientHeight,lastBottom:last?.bottom,listBottom:box.bottom,documentScroll:doc.scrollHeight,documentClient:doc.clientHeight};})()""")
            assert before["pager"] and before["overflow"] == "hidden", before
            assert before["scroll"] <= before["client"] + 1, before
            assert before["lastBottom"] <= before["listBottom"] + 1, before
            assert before["documentScroll"] <= before["documentClient"] + 1, before
            old_keys = cdp.eval("[...document.querySelectorAll('.lex-barrel-grid .lex-list-row[data-key]')].map(row=>row.dataset.key)")
            cdp.eval("document.querySelector('.lex-barrelled-master').dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true,cancelable:true}))")
            wait_eval(cdp, f"state.itemPage==={before['page'] + 1}", 10)
            new_keys = cdp.eval("[...document.querySelectorAll('.lex-barrel-grid .lex-list-row[data-key]')].map(row=>row.dataset.key)")
            assert old_keys and new_keys and not set(old_keys).intersection(new_keys)
            rdr_samples = []
            for _ in range(30):
                rdr_samples.append(cdp.eval("""(()=>({page:state.itemPage,pageSize:state.itemPageSize,total:document.querySelector('.lex-pager-right')?.textContent.trim(),detailScroll:document.querySelector('.lex-detail')?.scrollHeight,detailClient:document.querySelector('.lex-detail')?.clientHeight}))()"""))
                time.sleep(.04)
            assert len({(row["page"], row["pageSize"], row["total"], row["detailScroll"], row["detailClient"]) for row in rdr_samples}) == 1, rdr_samples
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            print({"plugin": "rdr", "before": before, "afterPage": before["page"] + 1, "screenshot": str(output)})
        with warband_fixture() as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&state.tab==='items'&&!!document.querySelector('.warband-items')", 90)
            wait_eval(cdp, "document.fonts.status==='loaded'&&!!document.querySelector('.lex-barrel-grid>.lex-list')", 15)
            time.sleep(.5)
            before = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),list=root.querySelector('.lex-barrel-grid>.lex-list'),rows=[...list.querySelectorAll('.lex-list-row')],last=rows.at(-1)?.getBoundingClientRect(),box=list.getBoundingClientRect(),doc=document.documentElement;return{page:state.pages.items,pageSize:state.pageSizes.items,pager:!!root.querySelector('.lex-pager'),overflow:getComputedStyle(list).overflowY,scroll:list.scrollHeight,client:list.clientHeight,lastBottom:last?.bottom,listBottom:box.bottom,documentScroll:doc.scrollHeight,documentClient:doc.clientHeight};})()""")
            assert before["pager"] and before["overflow"] == "hidden", before
            assert before["scroll"] <= before["client"] + 1, before
            assert before["lastBottom"] <= before["listBottom"] + 1, before
            assert before["documentScroll"] <= before["documentClient"] + 1, before
            old_keys = cdp.eval("[...document.querySelectorAll('.lex-barrel-grid .lex-list-row[data-key]')].map(row=>row.dataset.key)")
            cdp.eval("document.querySelector('.lex-barrelled-master').dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true,cancelable:true}))")
            wait_eval(cdp, f"state.pages.items==={before['page'] + 1}", 10)
            new_keys = cdp.eval("[...document.querySelectorAll('.lex-barrel-grid .lex-list-row[data-key]')].map(row=>row.dataset.key)")
            assert old_keys and new_keys and not set(old_keys).intersection(new_keys)
            warband_samples = []
            for _ in range(30):
                warband_samples.append(cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),master=root?.querySelector('.lex-barrelled-master'),list=root?.querySelector('.lex-barrel-grid>.lex-list'),header=list?.querySelector('.lex-column-list-header'),row=list?.querySelector('.lex-list-row');return{page:state.pages.items,pageSize:state.pageSizes.items,total:document.querySelector('.lex-page-total')?.textContent.trim(),right:document.querySelector('.lex-pager-right')?.textContent.trim(),root:root?.clientHeight,master:master?.clientHeight,list:list?.clientHeight,scroll:list?.scrollHeight,header:header?.getBoundingClientRect().height,row:row?.getBoundingClientRect().height,fit:list?.dataset.lexFittedPageSize,font:document.fonts.status};})()"""))
                time.sleep(.04)
            assert len({(row["page"], row["pageSize"], row["total"], row["right"]) for row in warband_samples}) == 1, warband_samples
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            warband_output.write_bytes(base64.b64decode(shot["data"]))
            print({"plugin": "warband", "before": before, "afterPage": before["page"] + 1,
                   "screenshot": str(warband_output)})
            for view in ("troops",):
                cdp.eval(f"navigate('{view}')")
                wait_eval(cdp, f"state.tab==='{view}'&&!!document.querySelector('.warband-paged-table')", 30)
                wait_eval(cdp, "(()=>{const list=document.querySelector('.lex-barrel-grid>.lex-list');return list&&list.scrollHeight<=list.clientHeight+1})()", 15)
                table = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),list=root.querySelector('.lex-barrel-grid>.lex-list'),doc=document.documentElement;return{page:Number(root.dataset.lexPage),pager:!!root.querySelector('.lex-pager'),overflow:getComputedStyle(list).overflowY,scroll:list.scrollHeight,client:list.clientHeight,documentScroll:doc.scrollHeight,documentClient:doc.clientHeight};})()""")
                assert table["overflow"] == "hidden" and table["scroll"] <= table["client"] + 1, table
                assert table["documentScroll"] <= table["documentClient"] + 1, table
                if table["pager"]:
                    cdp.eval("document.querySelector('.lex-barrelled-master').dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true,cancelable:true}))")
                    wait_eval(cdp, f"state.pages.{view}==={table['page'] + 1}", 10)
                print({"plugin": "warband", "view": view, **table})
            # Troop Trees now uses the shared scrollable graph, not a paged
            # upgrade table. Keep that caller covered using its actual view.
            cdp.eval("navigate('upgrades')")
            wait_eval(cdp, "state.tab==='upgrades'&&!!document.querySelector('.warband-trees .lex-tree-graph[aria-label=\"Bottom-up troop upgrade tree\"]')", 30)
            wait_eval(cdp, "document.querySelector('.lex-tree-graph').scrollTop>0", 15)
            tree = cdp.eval("""(()=>{const graph=document.querySelector('.lex-tree-graph'),r=graph.getBoundingClientRect(),doc=document.documentElement;return{nodes:graph.querySelectorAll('[data-node]').length,edges:graph.querySelectorAll('svg path').length,left:r.left,right:r.right,top:r.top,bottom:r.bottom,x:r.left+r.width/2,y:r.top+r.height/2,scrollTop:graph.scrollTop,scrollHeight:graph.scrollHeight,clientHeight:graph.clientHeight,documentWidth:doc.scrollWidth,documentHeight:doc.scrollHeight,paged:!!document.querySelector('.warband-paged-table')};})()""")
            assert tree["nodes"] == 65 and tree["edges"] == 64, tree
            assert not tree["paged"], tree
            assert 0 <= tree["left"] < tree["right"] <= 1402, tree
            assert 0 <= tree["top"] < tree["bottom"] <= 822, tree
            assert tree["documentWidth"] <= 1402 and tree["documentHeight"] <= 822, tree
            assert tree["scrollHeight"] > tree["clientHeight"], tree
            cdp.call("Input.dispatchMouseEvent", {"type":"mouseWheel", "x":tree["x"], "y":tree["y"], "deltaX":0, "deltaY":-120})
            wait_eval(cdp, f"document.querySelector('.lex-tree-graph').scrollTop<{tree['scrollTop']}", 10)
            assert cdp.eval("state.pages.upgrades") == 0
            tree_output = output.with_name("github-46-warband-troop-tree.png")
            shot = cdp.call("Page.captureScreenshot", {"format":"png", "captureBeyondViewport":False, "fromSurface":True})
            tree_output.write_bytes(base64.b64decode(shot["data"]))
            print({"plugin":"warband", "view":"upgrades", **tree, "screenshot":str(tree_output)})
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
