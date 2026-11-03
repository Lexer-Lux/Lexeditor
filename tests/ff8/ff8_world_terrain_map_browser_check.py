"""Real terrain camera interaction, selection, cleanup and model compatibility."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
from tempfile import gettempdir

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8.plugin import FF8Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-terrain-ui-", ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True, args=["--mute-audio"])
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                original_files={path.relative_to(project.name):path.read_bytes() for path in Path(project.name).rglob('*') if path.is_file()}
                initial_dirty=page.evaluate('dirtyCount()')
                page.evaluate("()=>{state.worldTab='map';navigate('world')}")
                toggle = page.locator(".ff8-world-map-panel .world-terrain-toggle")
                toggle.wait_for(timeout=60000)
                brown = page.locator(".ff8-world-map-panel .lex-image-map-stage > img").get_attribute("src")
                assert "/assets/world-map.png" in brown, brown
                started = time.time()
                toggle.click()
                page.wait_for_function(
                    "()=>document.querySelector('.ff8-world-map-panel .lex-model-stage')?.dataset.texturesReady==='true'",
                    timeout=240000)
                seconds = round(time.time() - started, 1)
                assert page.locator(".ff8-world-map-panel .world-terrain-toggle").get_attribute("aria-pressed") == "true"
                canvas=page.locator('.ff8-world-map-panel .lex-model-stage canvas')
                colours = page.evaluate("""()=>{const image=document.querySelector('.ff8-world-map-panel .lex-model-stage canvas');
                  const canvas=document.createElement('canvas');canvas.width=256;canvas.height=192;
                  const context=canvas.getContext('2d');context.drawImage(image,0,0,256,192);
                  const data=context.getImageData(0,0,256,192).data,seen=new Set();
                  for(let i=0;i<data.length;i+=4)seen.add((data[i]>>3)<<10|(data[i+1]>>3)<<5|data[i+2]>>3);return seen.size}""")
                assert colours > 100, colours  # the brown minimap has a 16-colour palette
                view=page.locator('.ff8-world-map-panel .lex-model-stage')
                before=canvas.screenshot()
                initial=view.get_attribute('data-rotation')
                canvas.focus();canvas.press('ArrowRight')
                assert view.get_attribute('data-rotation')!=initial
                assert canvas.screenshot()!=before
                rotation=view.get_attribute('data-rotation')
                canvas.press('Shift+ArrowRight')
                assert view.get_attribute('data-pan')!='0,0'
                assert view.get_attribute('data-rotation')==rotation
                keyboard_pan=view.get_attribute('data-pan')
                box=canvas.bounding_box()
                page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
                page.mouse.down();page.mouse.move(box['x']+box['width']/2+40,box['y']+box['height']/2+20,steps=5);page.mouse.up()
                assert view.get_attribute('data-rotation')!=rotation
                assert view.get_attribute('data-pan')==keyboard_pan
                page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
                page.mouse.down(button='right');page.mouse.move(box['x']+box['width']/2+50,box['y']+box['height']/2+30,steps=5);page.mouse.up(button='right')
                assert view.get_attribute('data-pan')!=keyboard_pan
                zoom=float(view.get_attribute('data-zoom'))
                page.mouse.wheel(0,-500)
                page.wait_for_function('(z)=>+document.querySelector(".ff8-world-map-panel .lex-model-stage").dataset.zoom>z',arg=zoom)
                canvas.press('Home')
                assert view.get_attribute('data-rotation')=='0,1'
                assert view.get_attribute('data-pan')=='0,0'
                assert float(view.get_attribute('data-zoom'))==1.5
                output=Path(gettempdir())/'lexeditor-dev/rendered'
                output.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(output/'ff8-world-live-terrain.png'))
                for _ in range(12):canvas.press('+')
                for _ in range(3):canvas.press('ArrowDown')
                page.screenshot(path=str(output/'ff8-world-live-terrain-close.png'))
                canvas.press('Home');canvas.press('ArrowRight');canvas.press('Shift+ArrowRight')
                pose={key:view.get_attribute('data-'+key) for key in ['rotation','zoom','pan']}
                # Cell picking uses the same depth-tested terrain triangles.
                page.evaluate('window.__previousTerrain=document.querySelector(".ff8-world-map-panel .lex-model-stage")')
                selected=page.evaluate('state.selected.world')
                canvas.click(position={'x':box['width']*.55,'y':box['height']*.5})
                page.wait_for_function('(old)=>state.selected.world!==old',arg=selected)
                page.wait_for_function('()=>document.querySelector(".ff8-world-map-panel .lex-model-stage")?.dataset.texturesReady==="true"')
                assert page.evaluate('window.__previousTerrain.lexDispose instanceof Function')
                assert not page.evaluate('window.__previousTerrain.isConnected')
                page.wait_for_function('()=>window.__previousTerrain.querySelector("canvas").getContext("webgl").isContextLost()')
                assert {key:page.locator('.ff8-world-map-panel .lex-model-stage').get_attribute('data-'+key) for key in pose}==pose
                marker_label=page.evaluate('''()=>{
                  const markers=[...document.querySelectorAll('.ff8-world-map-panel .lex-image-map-point:not(.world-sky-point)')];
                  const marker=markers.find(node=>{const box=node.getBoundingClientRect();return !node.hidden&&document.elementFromPoint(box.left+box.width/2,box.top+box.height/2)===node});
                  return marker?.getAttribute('aria-label');
                }''')
                assert marker_label
                page.get_by_label(marker_label,exact=True).click()
                page.wait_for_function('()=>state.worldMapPoint!==null')
                assert page.evaluate('state.data.world.rows.find(row=>row.kind==="drawPoint"&&row.id===state.worldMapPoint).drawId')==int(marker_label.rsplit(' ',1)[1])
                assert page.evaluate('dirtyCount()')==initial_dirty
                # Off again gives the game's own minimap back.
                page.locator(".ff8-world-map-panel .world-terrain-toggle").click()
                page.wait_for_function(
                    "()=>document.querySelector('.ff8-world-map-panel .lex-image-map-stage > img')?.src.includes('/assets/world-map.png')",
                    timeout=20000)
                assert {path.relative_to(project.name):path.read_bytes() for path in Path(project.name).rglob('*') if path.is_file()}==original_files
                # The existing model-scene path still rotates and zooms.
                page.route('**/api/model-scene?*',lambda route:route.fulfill(json={
                    'positions':[[-1,-1,0],[1,-1,0],[0,1,0]],'textures':[],
                    'triangles':[{'texture':-1,'indices':[0,1,2],'uv':[[0,0],[1,0],[.5,1]]}]}))
                page.evaluate('()=>{document.querySelector("#main").replaceChildren(FF8ModelViewer({file:"probe.dat",dataset:"vanilla",label:"Model compatibility"}))}')
                page.wait_for_function('()=>document.querySelector(".lex-model-stage")?.dataset.texturesReady==="true"')
                model=page.locator('.lex-model-stage')
                model_canvas=model.locator('canvas');model_canvas.focus();model_canvas.press('ArrowRight');model_canvas.press('+')
                assert model.get_attribute('data-rotation')=='0.1,0'
                assert float(model.get_attribute('data-zoom'))>.9
                model_canvas.press('Home')
                assert model.get_attribute('data-rotation')=='0,0'
                assert float(model.get_attribute('data-zoom'))==.9
                assert not errors, errors
                print(json.dumps({"renderSeconds": seconds, "colours": colours}))
                browser.close()
    finally:
        project.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
