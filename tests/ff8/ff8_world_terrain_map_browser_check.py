"""World > Map swaps the game's brown minimap for the terrain drawn from above.

Lexer asked for a button to swap "that brown map" for the detailed map Deling
draws. The mesh and texture atlas endpoints existed with nothing drawing them;
the Terrain button renders them once in WebGL2 and uses the picture as the map.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time

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
                page.evaluate("()=>{state.worldTab='map';navigate('world')}")
                toggle = page.locator(".ff8-world-map-panel .world-terrain-toggle")
                toggle.wait_for(timeout=60000)
                brown = page.locator(".ff8-world-map-panel .lex-image-map-stage > img").get_attribute("src")
                assert "/assets/world-map.png" in brown, brown
                started = time.time()
                toggle.click()
                page.wait_for_function(
                    "()=>document.querySelector('.ff8-world-map-panel .lex-image-map-stage > img')?.src.startsWith('blob:')",
                    timeout=240000)
                seconds = round(time.time() - started, 1)
                assert page.locator(".ff8-world-map-panel .world-terrain-toggle").get_attribute("aria-pressed") == "true"
                # The picture is the terrain, not an empty canvas: land and sea
                # differ, so the image holds many distinct colours.
                colours = page.evaluate("""async()=>{const image=document.querySelector('.ff8-world-map-panel .lex-image-map-stage > img');
                  await image.decode();const canvas=document.createElement('canvas');canvas.width=256;canvas.height=192;
                  const context=canvas.getContext('2d');context.drawImage(image,0,0,256,192);
                  const data=context.getImageData(0,0,256,192).data,seen=new Set();
                  for(let i=0;i<data.length;i+=4)seen.add((data[i]>>3)<<10|(data[i+1]>>3)<<5|data[i+2]>>3);return seen.size}""")
                assert colours > 100, colours  # the brown minimap has a 16-colour palette
                # Off again gives the game's own minimap back.
                page.locator(".ff8-world-map-panel .world-terrain-toggle").click()
                page.wait_for_function(
                    "()=>document.querySelector('.ff8-world-map-panel .lex-image-map-stage > img')?.src.includes('/assets/world-map.png')",
                    timeout=20000)
                assert not errors, errors
                print(json.dumps({"renderSeconds": seconds, "colours": colours}))
                browser.close()
    finally:
        project.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
