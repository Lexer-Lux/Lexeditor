"""Verify FF8 wmset section-34 Draw Point positions and their rendered editor."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import paths, world_data_merge, world_map  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode()
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def rejected(raw: bytes, edit: dict, expected: str) -> None:
    try:
        world_map.apply_draw_point_edits(raw, [edit])
    except ValueError as error:
        assert expected.lower() in str(error).lower(), error
    else:
        raise AssertionError(f"Draw Point writer accepted invalid {expected}")


def main() -> int:
    raw = world_map.ensure_baseline().read_bytes()
    parsed = world_map.parse(raw)
    assert len(parsed["drawPoints"]) == world_map.DRAW_POINT_COUNT == 128
    assert [row["drawId"] for row in parsed["drawPoints"]] == list(range(129, 257))
    first = parsed["drawPoints"][0]
    assert world_map.apply_draw_point_edits(raw, [first]) == raw
    edit = {**first, "x": first["x"] + 1, "y": first["y"] + 1,
            "subId": first["subId"] + 1}
    edited = bytes(world_map.apply_draw_point_edits(raw, [edit]))
    start = (world_map._pointers(raw)[world_map.DRAW_SECTION]
             + world_map.DRAW_HEADER_SIZE)
    changed = [index for index, (before, after) in enumerate(zip(raw, edited))
               if before != after]
    assert changed == [start, start + 1, start + 2]
    assert edited[start + 3] == raw[start + 3] == first["padding"]
    assert edited[:start] == raw[:start] and edited[start + 4:] == raw[start + 4:]
    reread = world_map.parse(edited)["drawPoints"][0]
    assert (reread["x"], reread["y"], reread["subId"]) == (
        edit["x"], edit["y"], edit["subId"])
    rejected(raw, {**first, "x": 256}, "0 to 255")
    rejected(raw, {**first, "id": 128}, "0 to 127")
    rejected(raw, {**first, "subId": None}, "integer")
    try:
        world_map.apply_draw_point_edits(raw, [first, first])
    except ValueError as error:
        assert "duplicate" in str(error).lower()
    else:
        raise AssertionError("Draw Point writer accepted a duplicate record edit")

    # Different mods can own different proved record fields. Conflicting claims
    # use the normal low-to-high winner while preserving unrelated fields.
    x_mod = bytearray(raw)
    x_mod[start] ^= 1
    y_mod = bytearray(raw)
    y_mod[start + 1] ^= 1
    merged, conflicts, reason = world_data_merge.merge(
        raw, [("x", bytes(x_mod)), ("y", bytes(y_mod))], "wmset",
        "direct/world/dat/wmsetus.obj")
    assert merged is not None and not conflicts and not reason
    assert merged[start] == x_mod[start] and merged[start + 1] == y_mod[start + 1]
    x2_mod = bytearray(raw)
    x2_mod[start] = (x2_mod[start] + 2) % 256
    merged, conflicts, reason = world_data_merge.merge(
        raw, [("x", bytes(x_mod)), ("x2", bytes(x2_mod))], "wmset",
        "direct/world/dat/wmsetus.obj")
    assert merged is not None and not reason
    assert conflicts == [{
        "unit": "direct/world/dat/wmsetus.obj:drawPoint:0:x",
        "winner": "x2", "claimants": ["x", "x2"],
    }]

    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-draw-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/world-map?dataset=vanilla")
            assert len(payload["drawPoints"]) == 128
            api_edit = {**payload["drawPoints"][0],
                        "x": (payload["drawPoints"][0]["x"] + 1) % 256}
            saved = api(session.url, "/api/world-map/save", {"edits": [api_edit]})
            assert saved["saved"] == 1 and saved["files"][0].endswith("wmsetus.obj")
            assert api(session.url, "/api/world-map?dataset=current")["drawPoints"][0]["x"] == api_edit["x"]

            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("navigate('world');state.worldTab='drawPoints';state.selected.world=0;renderWorldMap()")
            wait_eval(cdp, "document.querySelector('.world-map-detail.world-draw-point')!==null", 30)
            rendered = cdp.eval("""(()=>{const root=document.querySelector('.world-map-view'),panel=document.querySelector('.world-map-detail.world-draw-point'),map=panel.querySelector('.world-draw-map'),marker=map.querySelector('.world-draw-marker');return{
              tabs:[...document.querySelectorAll('.world-map-tabs [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              active:document.querySelector('.world-map-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              rows:document.querySelectorAll('.lex-list-row,.lex-column-list-row').length,
              inputs:[...panel.querySelectorAll('input')].map(node=>node.getAttribute('aria-label')),
              map:{width:map.getBoundingClientRect().width,height:map.getBoundingClientRect().height,label:map.getAttribute('aria-label')},
              marker:{left:marker.style.left,top:marker.style.top},
              help:panel.querySelector('.lex-info-help')?.getAttribute('aria-label')||'',
              overflow:root.scrollWidth>root.clientWidth+1,
            }})()""")
            assert rendered["active"] == "Draw Points"
            assert rendered["tabs"] == ["Map", "Regions", "Encounter Rules", "Encounter Groups",
                                        "Field → World", "Draw Points", "Sky Colours", "Train Tracks",
                                        "World Textures"]
            assert rendered["inputs"] == ["Draw Point 129 X", "Draw Point 129 Y",
                                          "Draw Point 129 sub-ID"]
            assert abs(rendered["map"]["width"] - rendered["map"]["height"]) < 2
            assert rendered["map"]["width"] > 250 and "Set Draw Point 129" in rendered["map"]["label"]
            assert "magic, quantity, and refill" in rendered["help"]
            assert not rendered["overflow"]

            # The visual placement control and the exact inputs both change the
            # same record. Save uses the normal global save button.
            before_xy = cdp.eval("(()=>{const row=worldRow(state.data,'drawPoint',0);return{x:row.x,y:row.y}})()")
            cdp.eval("""(()=>{const map=document.querySelector('.world-draw-map'),box=map.getBoundingClientRect();map.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:box.left+box.width*.25,clientY:box.top+box.height*.75}))})()""")
            wait_eval(cdp, f"worldRow(state.data,'drawPoint',0).x!=={before_xy['x']}&&worldRow(state.data,'drawPoint',0).y!=={before_xy['y']}", 10)
            assert cdp.eval("dirtyCount()") > 0
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 30)
            current = api(session.url, "/api/world-map?dataset=current")["drawPoints"][0]
            assert (current["x"], current["y"]) != (before_xy["x"], before_xy["y"])
            image = screenshot(cdp, "goal-ff8-world-draw-points.png")
            print(json.dumps({"records": 128, "changedOffsets": changed,
                              "semanticMerge": True, "apiSaved": saved["saved"],
                              "rendered": rendered, "screenshot": str(image)},
                             ensure_ascii=True))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
