"""Verify fixed wmset field-to-world coordinates and their rendered editor."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import world_data_merge, world_map  # noqa: E402
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


def main() -> int:
    raw = world_map.ensure_baseline().read_bytes()
    document = world_map.parse(raw)
    rows = document["fieldReturns"]
    assert len(rows) == 64
    assert world_map.apply_field_return_edits(raw, [rows[0]]) == raw
    row = rows[0]
    edit = {**row, "x": row["x"] + 1, "y": row["y"] + 1, "z": row["z"] + 1}
    changed_raw = bytes(world_map.apply_field_return_edits(raw, [edit]))
    start = world_map._pointers(raw)[world_map.FIELD_RETURN_SECTION]
    changed = [index for index, pair in enumerate(zip(raw, changed_raw))
               if pair[0] != pair[1]]
    assert changed == [start, start + 4, start + 8]
    assert changed_raw[start + 10:start + 12] == raw[start + 10:start + 12]
    assert changed_raw[:start] == raw[:start]
    assert changed_raw[start + world_map.FIELD_RETURN_RECORD_SIZE:] == raw[
        start + world_map.FIELD_RETURN_RECORD_SIZE:]
    reread = world_map.parse(changed_raw)["fieldReturns"][0]
    assert (reread["x"], reread["y"], reread["z"], reread["unknown"]) == (
        edit["x"], edit["y"], edit["z"], row["unknown"])
    for bad in ({**row, "x": 2 ** 31}, {**row, "y": 32768},
                {**row, "id": 64}, {**row, "z": None}):
        try:
            world_map.apply_field_return_edits(raw, [bad])
        except ValueError:
            pass
        else:
            raise AssertionError(f"Field-return writer accepted {bad}")
    try:
        world_map.apply_field_return_edits(raw, [row, row])
    except ValueError as error:
        assert "duplicate" in str(error).lower()
    else:
        raise AssertionError("Field-return writer accepted duplicate edits")

    # The semantic merger treats each coordinate as an independent record unit
    # and refuses changes to the unresolved trailing word.
    x_mod = bytearray(raw)
    x_mod[start] ^= 1
    y_mod = bytearray(raw)
    y_mod[start + 8] ^= 1
    merged, conflicts, reason = world_data_merge.merge(
        raw, [("x", bytes(x_mod)), ("y", bytes(y_mod))], "wmset",
        "direct/world/dat/wmsetus.obj")
    assert merged is not None and not conflicts and not reason
    assert merged[start] == x_mod[start] and merged[start + 8] == y_mod[start + 8]
    unresolved = bytearray(raw)
    unresolved[start + 10] ^= 1
    rejected, _, reason = world_data_merge.merge(
        raw, [("unknown", bytes(unresolved))], "wmset",
        "direct/world/dat/wmsetus.obj")
    assert rejected is None and "outside proved" in reason

    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-return-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/world-map?dataset=vanilla")
            assert len(payload["fieldReturns"]) == 64
            api_edit = {**payload["fieldReturns"][0],
                        "z": payload["fieldReturns"][0]["z"] + 1}
            saved = api(session.url, "/api/world-map/save", {"edits": [api_edit]})
            assert saved["saved"] == 1
            assert api(session.url, "/api/world-map?dataset=current")["fieldReturns"][0]["z"] == api_edit["z"]

            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("navigate('world');state.worldTab='fieldReturns';state.selected.world=0;renderWorldMap()")
            wait_eval(cdp, "document.querySelector('.world-map-detail.world-field-return')!==null", 30)
            rendered = cdp.eval("""(()=>{const root=document.querySelector('.world-map-view'),panel=document.querySelector('.world-field-return');return{
              tabs:[...document.querySelectorAll('.world-map-tabs [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              active:document.querySelector('.world-map-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              inputs:[...panel.querySelectorAll('input[aria-label]')].map(node=>node.getAttribute('aria-label')),
              locked:panel.textContent.includes('UNRESOLVED WORD'),
              help:panel.querySelector('.lex-info-help')?.getAttribute('aria-label')||'',
              overflow:root.scrollWidth>root.clientWidth+1,
            }})()""")
            assert rendered["active"] == "Field → World"
            assert rendered["inputs"] == ["Field return 0 X", "Field return 0 Y",
                                          "Field return 0 Z"]
            assert rendered["locked"] and "not a field ID" in rendered["help"]
            assert not rendered["overflow"]
            before_x = cdp.eval("worldRow(state.data,'fieldReturn',0).x")
            cdp.eval("""(()=>{const input=document.querySelector('input[aria-label="Field return 0 X"]');input.value=String(Number(input.value.replaceAll(',',''))+1);input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, f"worldRow(state.data,'fieldReturn',0).x==={before_x + 1}", 10)
            assert cdp.eval("dirtyCount()") > 0
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 30)
            current = api(session.url, "/api/world-map?dataset=current")["fieldReturns"][0]
            assert current["x"] == before_x + 1
            image = screenshot(cdp, "goal-ff8-world-field-returns.png")
            print(json.dumps({"records": 64, "changedOffsets": changed,
                              "unknownPreserved": True, "semanticMerge": True,
                              "apiSaved": saved["saved"], "rendered": rendered,
                              "screenshot": str(image)}, ensure_ascii=True))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
