"""Verify FF8 selected-field walkmesh API, UI, save, and runtime merge."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import field_data, field_walkmesh, runtime_layout  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def runtime_merge() -> dict:
    source = field_data._walkmesh_source_path("bg/bghall_1", "vanilla")
    assert source is not None
    vanilla = source.read_bytes()
    parsed = field_walkmesh.read(vanilla)
    vertex = parsed["triangles"][0]["vertices"][0]
    next_x = vertex["x"] + (1 if vertex["x"] < 32767 else -1)
    next_y = vertex["y"] + (1 if vertex["y"] < 32767 else -1)
    x_mod = field_walkmesh.apply_edits(vanilla, [{
        "triangle": 0, "vertex": 0, "x": next_x,
    }])[0]
    y_mod = field_walkmesh.apply_edits(vanilla, [{
        "triangle": 0, "vertex": 0, "y": next_y,
    }])[0]
    with tempfile.TemporaryDirectory(prefix="lexeditor-walkmesh-baseline-") as folder:
        baseline = Path(folder)
        relative = Path("field/mapdata/bg/bghall_1/bghall_1.id")
        destination = baseline / relative
        destination.parent.mkdir(parents=True)
        destination.write_bytes(vanilla)
        merged, mode, conflicts = runtime_layout._compose_logical_payload(
            "direct/field/mapdata/bg/bghall_1/bghall_1.id",
            [("x", x_mod), ("y", y_mod)], baseline, None, None)
    assert merged is not None and mode == "semantic merge" and not conflicts
    result = field_walkmesh.read(merged)["triangles"][0]["vertices"][0]
    assert result["x"] == next_x and result["y"] == next_y
    return {"mode": mode, "x": next_x, "y": next_y}


def api_and_render() -> dict:
    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-field-walkmesh-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            vanilla = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=vanilla")
            vertex = vanilla["walkmesh"]["triangles"][0]["vertices"][0]
            next_x = vertex["x"] + (1 if vertex["x"] < 32767 else -1)
            saved = api(session.url, "/api/field/save", {"edits": [{
                "type": "walkmesh", "map": "bg/bghall_1", "triangle": 0,
                "vertex": 0, "x": next_x,
            }]})
            assert saved == {"saved": 1, "maps": 1}
            current = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert current["walkmesh"]["triangles"][0]["vertices"][0]["x"] == next_x
            output = Path(current["walkmeshSource"])
            changed = [index for index, pair in enumerate(zip(
                Path(vanilla["walkmeshSource"]).read_bytes(), output.read_bytes()))
                if pair[0] != pair[1]]
            assert changed and all(index in (4, 5) for index in changed)

            profile, browser, cdp = browser_session()
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            target = next(row for row in api(session.url, "/api/fields")["rows"]
                          if row["key"] == "bg/bghall_1")
            cdp.eval(f"state.selected.fields={target['id']};navigate('fields')")
            wait_eval(cdp, "document.querySelector('.field-walkmesh-preview canvas')!==null", 45)
            cdp.eval("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))", True)
            rendered = cdp.eval("""(()=>{const canvas=document.querySelector('.field-walkmesh-preview canvas'),panel=document.querySelector('.field-map-detail'),picker=document.querySelector('.field-walkmesh-picker input'),x=document.querySelector('input[aria-label="bghall_1 triangle 0 vertex 0 x"]'),y=document.querySelector('input[aria-label="bghall_1 triangle 0 vertex 0 y"]'),adj=document.querySelector('input[aria-label="bghall_1 triangle 0 vertex 0 adjacent"]'),source=x.closest('.lex-source-control'),pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;let painted=0;for(let index=3;index<pixels.length;index+=4)if(pixels[index])painted++;return{triangles:Number(document.querySelector('.field-walkmesh-picker span').textContent.replace('/','').trim())+1,x:Number(x.value.replaceAll(',','')),y:Number(y.value.replaceAll(',','')),adjacentRange:adj.title,vanilla:source?.lexVanillaValue?.(),refs:source?.querySelectorAll('.lex-reference-value').length||0,pickerBackground:getComputedStyle(picker).backgroundColor,pickerColor:getComputedStyle(picker).color,canvasWidth:canvas.getBoundingClientRect().width,canvasHeight:canvas.getBoundingClientRect().height,painted,overflow:panel.scrollWidth>panel.clientWidth+1}})()""")
            assert rendered["triangles"] == 382 and rendered["x"] == next_x, rendered
            assert rendered["vanilla"] == vertex["x"] and rendered["refs"] >= 1, rendered
            assert rendered["painted"] > 100 and rendered["canvasWidth"] >= 280, rendered
            assert rendered["canvasHeight"] >= 230 and not rendered["overflow"], rendered
            assert rendered["pickerColor"] == "rgb(255, 255, 255)" and rendered["pickerBackground"] != "rgb(255, 255, 255)", rendered
            next_y = rendered["y"] + (1 if rendered["y"] < 32767 else -1)
            cdp.eval(f"""(()=>{{const input=document.querySelector('input[aria-label="bghall_1 triangle 0 vertex 0 y"]');input.value={next_y};input.dispatchEvent(new Event('input',{{bubbles:true}}))}})()""")
            assert cdp.eval("dirtyCount()") >= 1
            cdp.eval("saveAll()", True)
            persisted = api(session.url, "/api/field?map=bg%2Fbghall_1&dataset=current")
            assert persisted["walkmesh"]["triangles"][0]["vertices"][0]["y"] == next_y
            wait_eval(cdp, "document.querySelector('.field-walkmesh-preview canvas')!==null", 45)
            cdp.eval("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))", True)
            rendered["uiSavePersisted"] = True
            rendered["screenshot"] = str(screenshot(
                cdp, "goal-ff8-field-walkmesh.png"))
            return rendered
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert "fieldWalkmeshSection" in source and 'type:"walkmesh"' in source
    print({"runtime": runtime_merge(), "rendered": api_and_render()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
