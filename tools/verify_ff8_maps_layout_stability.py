"""Rendered regression check for the combined FF8 Maps view."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def api(url: str, path: str) -> dict:
    with urlopen(url + path, timeout=30) as response:
        return json.load(response)


def main() -> int:
    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert "if(row._loaded||row._loading||row._error)return" in source
    assert 'renderWorldMapContent(false):buildFields()' in source

    project = tempfile.TemporaryDirectory(prefix="lexeditor-maps-layout-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            fields = api(session.url, "/api/fields?dataset=current")["rows"]
            target = next(row for row in fields if row["key"] == "bg/bghall_1")
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval(
                f"state.selected.fields={target['id']};state.mapsTab='field';navigate('maps')"
            )
            wait_eval(cdp, "document.querySelector('.field-card-table')!==null", 30)

            # An idle, fully loaded field view must not rebuild itself.
            cdp.eval("window.__mapsMutations=0;window.__mapsRoot=document.querySelector('.ff8-maps-view');window.__mapsObserver=new MutationObserver(r=>window.__mapsMutations+=r.length);window.__mapsObserver.observe(document.querySelector('#main'),{childList:true})")
            time.sleep(0.75)
            result = cdp.eval("""(()=>{
              window.__mapsObserver.disconnect();
              const main=document.querySelector('#main').getBoundingClientRect();
              const outer=document.querySelector('.ff8-maps-view').getBoundingClientRect();
              const content=document.querySelector('.ff8-maps-content').getBoundingClientRect();
              const split=document.querySelector('.ff8-maps-content>.lex-paged-list-detail').getBoundingClientRect();
              const detail=document.querySelector('.field-map-detail').getBoundingClientRect();
              return {
                mutations:window.__mapsMutations,
                sameRoot:window.__mapsRoot===document.querySelector('.ff8-maps-view'),
                roots:document.querySelectorAll('.ff8-maps-view').length,
                nested:document.querySelectorAll('.ff8-maps-content .ff8-maps-view').length,
                main:[main.width,main.height],outer:[outer.width,outer.height],
                content:[content.width,content.height],split:[split.width,split.height],
                detail:[detail.left,detail.right,detail.top,detail.bottom],
                overflow:split.scrollWidth>split.clientWidth+1
              };
            })()""")
            assert result["mutations"] == 0 and result["sameRoot"], result
            assert result["roots"] == 1 and result["nested"] == 0, result
            assert abs(result["content"][0] - result["outer"][0]) < 2, result
            assert abs(result["split"][0] - result["content"][0]) < 2, result
            assert result["detail"][1] > result["main"][0] * 0.9, result
            assert result["detail"][3] <= result["content"][1] + result["detail"][2] + 2, result
            assert not result["overflow"], result
            result["fieldScreenshot"] = str(screenshot(cdp, "goal-ff8-maps-field-stability.png"))

            cdp.eval("state.mapsTab='world';state.worldTab='map';renderMaps()")
            wait_eval(cdp, "document.querySelector('.world-visual-stage')!==null", 30)
            world = cdp.eval("""(()=>({
              roots:document.querySelectorAll('.ff8-maps-view').length,
              nested:document.querySelectorAll('.ff8-maps-content .ff8-maps-view').length,
              width:document.querySelector('.world-map-view').getBoundingClientRect().width,
              content:document.querySelector('.ff8-maps-content').getBoundingClientRect().width
            }))()""")
            assert world["roots"] == 1 and world["nested"] == 0, world
            assert abs(world["width"] - world["content"]) < 2, world
            result["world"] = world
            result["screenshot"] = str(screenshot(cdp, "goal-ff8-maps-layout-stability.png"))
            print(json.dumps(result))
            return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
