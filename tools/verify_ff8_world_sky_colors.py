"""Verify wmset section-33 sky/ambient records and their rendered editor."""

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
    rows = world_map.parse(raw)["skyColors"]
    assert len(rows) == 8
    assert world_map.apply_sky_color_edits(raw, [rows[0]]) == raw
    row = rows[0]
    edit = {**row, "x": row["x"] + 1, "y": row["y"] + 1,
            "z": row["z"] + 1}
    for key, _offset in world_map.SKY_COLOR_FIELDS:
        edit[key] = [(row[key][0] + 1) % 256, *row[key][1:]]
    changed_raw = bytes(world_map.apply_sky_color_edits(raw, [edit]))
    start = (world_map._pointers(raw)[world_map.SKY_SECTION]
             + int(row["recordOffset"]))
    changed = [index for index, pair in enumerate(zip(raw, changed_raw))
               if pair[0] != pair[1]]
    expected = [start, start + 4, start + 8, start + 12, start + 16,
                start + 20, start + 24, start + 28]
    assert changed == expected, changed
    # The fourth byte after every RGB triple and the entire unresolved tail stay exact.
    for offset in (15, 19, 23, 27, 31):
        assert changed_raw[start + offset] == raw[start + offset]
    assert changed_raw[start + 32:start + world_map.SKY_RECORD_SIZE] == raw[
        start + 32:start + world_map.SKY_RECORD_SIZE]
    reread = world_map.parse(changed_raw)["skyColors"][0]
    for key in ("x", "y", "z", *(field for field, _ in world_map.SKY_COLOR_FIELDS)):
        assert reread[key] == edit[key]
    bad_edits = [
        {**row, "x": 2 ** 31},
        {**row, "id": 8},
        {**row, "skyTop": [0, 0, 256]},
        {**row, "skyCenter": [0, 0]},
    ]
    for bad in bad_edits:
        try:
            world_map.apply_sky_color_edits(raw, [bad])
        except ValueError:
            pass
        else:
            raise AssertionError(f"Sky-colour writer accepted {bad}")
    try:
        world_map.apply_sky_color_edits(raw, [row, row])
    except ValueError as error:
        assert "duplicate" in str(error).lower()
    else:
        raise AssertionError("Sky-colour writer accepted duplicate edits")
    malformed = bytearray(raw)
    section = world_map._pointers(raw)[world_map.SKY_SECTION]
    malformed[section + 4:section + 8] = malformed[section:section + 4]
    try:
        world_map.parse(bytes(malformed))
    except ValueError as error:
        assert "pointer table" in str(error)
    else:
        raise AssertionError("Sky parser accepted duplicate record pointers")

    # Coordinates and each whole RGB triple are independent semantic units.
    x_mod = bytearray(raw)
    x_mod[start] ^= 1
    top_mod = bytearray(raw)
    top_mod[start + 20] ^= 1
    merged, conflicts, reason = world_data_merge.merge(
        raw, [("position", bytes(x_mod)), ("sky", bytes(top_mod))], "wmset",
        "direct/world/dat/wmsetus.obj")
    assert merged is not None and not conflicts and not reason
    assert merged[start] == x_mod[start] and merged[start + 20] == top_mod[start + 20]
    unknown = bytearray(raw)
    unknown[start + 23] ^= 1
    rejected, _, reason = world_data_merge.merge(
        raw, [("unknown", bytes(unknown))], "wmset",
        "direct/world/dat/wmsetus.obj")
    assert rejected is None and "outside proved" in reason

    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-sky-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/world-map?dataset=vanilla")
            assert len(payload["skyColors"]) == 8
            api_edit = {**payload["skyColors"][0],
                        "vehicles": [*payload["skyColors"][0]["vehicles"]]}
            api_edit["vehicles"][0] = (api_edit["vehicles"][0] + 1) % 256
            saved = api(session.url, "/api/world-map/save", {"edits": [api_edit]})
            assert saved["saved"] == 1
            current = api(session.url, "/api/world-map?dataset=current")
            assert current["skyColors"][0]["vehicles"] == api_edit["vehicles"]

            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("navigate('world');state.worldTab='skyColors';state.selected.world=0;renderWorldMap()")
            wait_eval(cdp, "document.querySelector('.world-map-detail.world-sky-detail')!==null", 30)
            rendered = cdp.eval("""(()=>{const root=document.querySelector('.world-map-view'),panel=document.querySelector('.world-sky-detail');return{
              tabs:[...document.querySelectorAll('.world-map-tabs [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              active:document.querySelector('.world-map-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              numbers:[...panel.querySelectorAll('input[type=text][aria-label]')].map(node=>node.getAttribute('aria-label')),
              colours:[...panel.querySelectorAll('input[type=color][aria-label]')].map(node=>({label:node.getAttribute('aria-label'),value:node.value})),
              swatches:[...document.querySelectorAll('.world-sky-swatch')].map(node=>({width:node.getBoundingClientRect().width,height:node.getBoundingClientRect().height,background:getComputedStyle(node).backgroundImage})),
              references:panel.querySelectorAll('.lex-reference-value').length,
              help:[...panel.querySelectorAll('.lex-info-help')].map(node=>node.getAttribute('aria-label')),
              overflow:root.scrollWidth>root.clientWidth+1,
            }})()""")
            assert rendered["active"] == "Sky Colours"
            assert rendered["numbers"] == ["Sky record 0 X", "Sky record 0 Y",
                                             "Sky record 0 Z"]
            assert len(rendered["colours"]) == 5
            assert rendered["references"] >= 1
            assert len(rendered["swatches"]) == 8
            assert all(swatch["width"] >= 70 and swatch["height"] >= 27
                       and "linear-gradient" in swatch["background"]
                       for swatch in rendered["swatches"]), rendered["swatches"]
            assert any("preserves each unused fourth" in text for text in rendered["help"])
            assert not rendered["overflow"]
            before = current["skyColors"][0]["skyTop"]
            next_hex = "#%02x%02x%02x" % ((before[0] + 1) % 256, before[1], before[2])
            cdp.eval(f"""(()=>{{const input=document.querySelector('input[aria-label="Sky record 0 sky top colour"]');input.value='{next_hex}';input.dispatchEvent(new Event('change',{{bubbles:true}}))}})()""")
            wait_eval(cdp, f"worldRow(state.data,'skyColor',0).skyTop[0]==={(before[0] + 1) % 256}", 10)
            assert cdp.eval("dirtyCount()") > 0
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 30)
            saved_row = api(session.url, "/api/world-map?dataset=current")["skyColors"][0]
            assert saved_row["skyTop"][0] == (before[0] + 1) % 256
            image = screenshot(cdp, "goal-ff8-world-sky-colours.png")
            print(json.dumps({"records": 8, "changedOffsets": changed,
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
