"""The Field page keeps its picture while the reader works, and edits like the
rest of the editor.

Lexer's Field complaints, checked on the real page from the installed game:

- "every time i try to use the slider on [the tile] it flickers out the entire
  panel and i can only change it by 1 increment at a time", and clicking a
  walkmesh triangle "makes the entire BG briefly flicker out of existence": the
  picture must be the same image element before and after, and the tile
  slider must be the same input after every step.
- the three panels are columns by default; a Deling-style setting stacks the
  picture over the tabs.
- tiles have their own tab, where clicking the picture selects a tile; the
  walkmesh tab does the same for triangles, with a hover mark as well.
- Camera values are ordinary properties, with the type rail.
- Background layers are one checkbox each.
- the picture has its help in its corner and no walkmesh-overlay switch.
- Doors, Exits and Triggers are tables that fit their column.
- a dialogue line's box has no "metric fuckton of empty space on the left".
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from plugins.ff8.plugin import FF8Session  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from tests.shared.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot, wait_eval,
)

MAP = "bghall_1"


def settle(cdp, seconds: float = 0.4) -> None:
    time.sleep(seconds)


def open_tab(cdp, tab: str) -> None:
    cdp.eval(f"state.fieldDetailTab={tab!r};rerenderFields();1")
    settle(cdp)


def click(cdp, x: float, y: float) -> None:
    for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
        cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left",
                                              "buttons": 1 if kind == "mousePressed" else 0,
                                              "clickCount": 1})


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-field-page-",
                                          ignore_cleanup_errors=True)
    settings = os.path.join(project.name, "ff8-editor.json")
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name,
                         "LEXEDITOR_FF8_EDITOR_SETTINGS": settings}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval(f"""(()=>{{const row=state.data.fields.rows.find(r=>r.name==={MAP!r});
              state.selected.fields=row.id;state.filters.fields={MAP!r};state.fieldDetailTab='tile';
              navigate('fields');return 1}})()""")
            wait_eval(cdp, "document.querySelector('.field-preview-stack')?.style.visibility===''"
                           "&&document.querySelector('.field-background-image')?.naturalWidth>0", 120)
            wait_eval(cdp, "!!document.querySelector('.field-background-image')?.lexGeometry", 30)

            layout = cdp.eval("""(()=>{const L=document.querySelector('.field-map-detail').closest('.lex-panel-layout');
              return {vertical:L.classList.contains('lex-panel-layout-vertical'),
                tabs:[...document.querySelectorAll('.lex-tabbed-panel [role=tab]')].map(t=>t.textContent.trim().replace(/\\?$/,'')),
                help:!!document.querySelector('.field-map-detail > .lex-media-help .lex-info-help, .field-map-detail > .lex-media-help button, .field-map-detail > .lex-media-help [aria-label]'),
                overlaySwitch:document.body.textContent.includes('Walkmesh overlay')}})()""")
            assert layout["vertical"] is False, layout
            assert "Tile" in layout["tabs"], layout
            assert layout["help"], layout
            assert layout["overlaySwitch"] is False, layout

            # The tile slider: one input and one picture across every step.
            steps = cdp.eval("""(async()=>{const image=document.querySelector('.field-background-image');
              const input=document.querySelector('input[aria-label$="selected background tile"]');const seen=[];
              for(let value=1;value<=6;value++){input.value=String(value);input.dispatchEvent(new Event('input',{bubbles:true}));
                await new Promise(r=>setTimeout(r,50));
                seen.push({sameInput:document.querySelector('input[aria-label$="selected background tile"]')===input,
                  sameImage:document.querySelector('.field-background-image')===image,
                  shown:document.querySelector('.field-preview-stack').style.visibility===''})}
              return seen})()""", await_promise=True)
            assert all(step["sameInput"] and step["sameImage"] and step["shown"] for step in steps), steps

            # Clicking the picture on the Tile tab selects the tile under the pointer.
            tile_point = cdp.eval("""(()=>{const row=state.data.fields.rows.find(r=>r._loaded&&r.background);
              const image=document.querySelector('.field-background-image'),g=image.lexGeometry,box=image.getBoundingClientRect();
              const tile=row.background.tiles.find(t=>t.id>20&&fieldTileAt(row,g,g.left+t.x+8,g.top+t.y+8)===t.id);
              return {id:tile.id,x:box.left+(g.left+tile.x+8)*box.width/g.width,y:box.top+(g.top+tile.y+8)*box.height/g.height}})()""")
            image_before = cdp.eval("window.__image=document.querySelector('.field-background-image');1")
            click(cdp, tile_point["x"], tile_point["y"])
            settle(cdp)
            picked = cdp.eval(f"""({{tile:state.fieldBackgroundSelection[{('bg/' + MAP)!r}],
              sameImage:document.querySelector('.field-background-image')===window.__image}})""")
            assert picked == {"tile": tile_point["id"], "sameImage": True}, (picked, tile_point, image_before)

            # The walkmesh tab: hover marks a triangle, a click selects it, the picture stays.
            open_tab(cdp, "walkmesh")
            tri_point = cdp.eval("""(()=>{const row=state.data.fields.rows.find(r=>r._loaded&&r.walkmesh);
              const image=document.querySelector('.field-background-image'),g=image.lexGeometry,box=image.getBoundingClientRect();
              const camera=row.camera.cameras[fieldOverlayCameraId(row)];
              for(const tri of row.walkmesh.triangles){if(tri.id<5)continue;const p=tri.vertices.map(v=>fieldProject(camera,v));if(!p.every(Boolean))continue;
                const x=(p[0].x+p[1].x+p[2].x)/3+g.left,y=(p[0].y+p[1].y+p[2].y)/3+g.top;
                if(x<2||y<2||x>g.width-2||y>g.height-2)continue;const hit=fieldTriangleAt(row,g,x,y);if(hit<0)continue;
                return {id:hit,x:box.left+x*box.width/g.width,y:box.top+y*box.height/g.height}}return null})()""")
            assert tri_point, tri_point
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": tri_point["x"], "y": tri_point["y"],
                                                  "buttons": 0, "button": "none"})
            settle(cdp, 0.2)
            hover = cdp.eval("fieldHover.triangle")
            assert hover == tri_point["id"], (hover, tri_point)
            click(cdp, tri_point["x"], tri_point["y"])
            settle(cdp)
            chosen = cdp.eval(f"""({{triangle:state.fieldWalkmeshSelection[{('bg/' + MAP)!r}],
              sameImage:document.querySelector('.field-background-image')===window.__image,
              picker:document.querySelector('input[aria-label$="selected walkmesh triangle"]').value}})""")
            assert chosen == {"triangle": tri_point["id"], "sameImage": True,
                              "picker": str(tri_point["id"])}, (chosen, tri_point)

            # Camera numbers are ordinary properties with the type rail.
            open_tab(cdp, "camera")
            camera = cdp.eval("""(()=>{const inputs=[...document.querySelectorAll('.lex-tabbed-panel-content input:not([type=checkbox])')];
              return {count:inputs.length,railed:inputs.filter(i=>i.closest('.lex-detail-field')?.querySelector('.lex-field-type-rail')).length}})()""")
            assert camera["count"] >= 13 and camera["railed"] == camera["count"], camera

            # Background layers and states are one checkbox each.
            open_tab(cdp, "background")
            layers = cdp.eval("""(()=>{const boxes=[...document.querySelectorAll('.lex-tabbed-panel input[type=checkbox]')];
              return {count:boxes.length,bool:boxes.filter(b=>b.closest('.lex-detail-field')?.dataset.lexType==='BOOL').length}})()""")
            assert layers["count"] >= 2 and layers["bool"] == layers["count"], layers

            # A dialogue line is the Text page's box: no label column beside it.
            open_tab(cdp, "dialogue")
            dialogue = cdp.eval("""(()=>{const box=document.querySelectorAll('.lex-tabbed-panel-content textarea')[1],
              pane=box.closest('.lex-tabbed-panel-content').getBoundingClientRect(),own=box.getBoundingClientRect();
              return {left:Math.round(own.left-pane.left),share:own.width/pane.width}})()""")
            # The panel keeps a scrollbar-wide gutter on both sides (about 13px).
            assert dialogue["left"] <= 24 and dialogue["share"] > .9, dialogue

            # Exits, doors and triggers are tables that fit their column.
            tables = {}
            for tab, selector, source in (("exits", ".field-gateway-table", "gateways"),
                                          ("doors", ".field-door-table", "triggers"),
                                          ("triggers", ".field-trigger-table", "triggers")):
                open_tab(cdp, tab)
                tables[tab] = cdp.eval(f"""(()=>{{const table=document.querySelector({selector!r});
                  const row=state.data.fields.rows.find(r=>r._loaded&&r.entrances);
                  return {{rows:table?.querySelectorAll('.lex-list-row.lex-column-list-row').length,
                    records:row.entrances.{source}.length,sw:table.scrollWidth,cw:table.clientWidth,pane:Math.round(table.closest(".lex-panel-layout-pane")?.getBoundingClientRect().width||0),fits:table.scrollWidth<=table.clientWidth+1}}}})()""")
                assert tables[tab]["rows"] == tables[tab]["records"] and tables[tab]["fits"], (tab, tables[tab])
            open_tab(cdp, "exits")
            image = screenshot(cdp, "ff8-field-page.png")

            # The Deling-style setting stacks the picture over the tabs.
            cdp.eval("""(async()=>{state.editorSettings=await api('/api/editor-settings/save',post({delingFieldLayout:true}));rerenderFields();return 1})()""",
                     await_promise=True)
            settle(cdp)
            deling = cdp.eval("document.querySelector('.field-map-detail').closest('.lex-panel-layout').classList.contains('lex-panel-layout-vertical')")
            assert deling is True, deling
            stacked = screenshot(cdp, "ff8-field-page-deling.png")
            print(json.dumps({"tabs": layout["tabs"], "tileSteps": len(steps), "tile": picked,
                              "triangle": chosen, "camera": camera, "layers": layers, "tables": tables,
                              "screenshots": [str(image), str(stacked)]}))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
