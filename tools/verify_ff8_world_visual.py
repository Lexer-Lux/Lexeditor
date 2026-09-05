"""Verify the installed FF8 world map visual, WMX parser, editor, and save path."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import world_data_merge, world_geometry  # noqa: E402
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
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def binary(url: str, path: str) -> bytes:
    with urlopen(url + path, timeout=90) as response:
        assert response.headers.get_content_type() == "image/png"
        return response.read()


def rejected(raw: bytes, edit: dict, expected: str) -> None:
    try:
        world_geometry.apply_edits(raw, [edit])
    except ValueError as error:
        assert expected.lower() in str(error).lower(), error
    else:
        raise AssertionError(f"WMX editor accepted invalid {expected}")


def main() -> int:
    raw = world_geometry.ensure_baseline().read_bytes()
    parsed = world_geometry.parse(raw)
    assert parsed["segmentCount"] == 835
    assert parsed["baseSegmentCount"] == 32 * 24
    assert sum(row["polygonCount"] for row in parsed["segments"]) == 517_639
    first = parsed["segments"][0]
    assert world_geometry.apply_edits(raw, [first]) == raw
    next_group = first["groupId"] ^ 1
    edited = bytes(world_geometry.apply_edits(
        raw, [{"id": 0, "groupId": next_group}]))
    changed = [index for index, values in enumerate(zip(raw, edited))
               if values[0] != values[1]]
    assert changed and all(index < 4 for index in changed)
    assert edited[4:] == raw[4:]
    reread = world_geometry.parse(edited)["segments"][0]
    assert reread["groupId"] == next_group
    rejected(raw, {"id": 835, "groupId": 0}, "0 to 834")
    rejected(raw, {"id": 0, "groupId": -1}, "0 to 4294967295")
    try:
        world_geometry.apply_edits(raw, [first, first])
    except ValueError as error:
        assert "duplicate" in str(error).lower()
    else:
        raise AssertionError("WMX editor accepted duplicate segment edits")

    second_offset = world_geometry.SEGMENT_SIZE
    first_mod = edited
    second_group = parsed["segments"][1]["groupId"] ^ 1
    second_mod = bytes(world_geometry.apply_edits(
        raw, [{"id": 1, "groupId": second_group}]))
    merged, conflicts, reason = world_data_merge.merge(
        raw, [("first", first_mod), ("second", second_mod)], "geometry",
        "direct/world/dat/wmx.obj")
    assert merged is not None and not conflicts and not reason
    assert int.from_bytes(merged[:4], "little") == next_group
    assert int.from_bytes(merged[second_offset:second_offset + 4], "little") == second_group
    opaque = bytearray(raw)
    first_block_padding = int.from_bytes(raw[4:8], "little") + 3
    opaque[first_block_padding] ^= 1
    unsupported, _, reason = world_data_merge.merge(
        raw, [("opaque", bytes(opaque))], "geometry", "direct/world/dat/wmx.obj")
    assert unsupported is None and "outside proved" in reason

    minimap = world_geometry.minimap_png("vanilla")
    image = Image.open(BytesIO(minimap)).convert("RGBA")
    assert image.size == (256, 192)
    colors = image.getcolors(maxcolors=image.width * image.height)
    assert colors is not None and len(colors) >= 12

    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-world-visual-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/world-map?dataset=vanilla")
            assert len(payload["segments"]) == 835
            assert payload["segments"][0]["polygonCount"] == first["polygonCount"]
            served = binary(session.url, "/assets/world-map.png?dataset=vanilla")
            assert served == minimap

            api_edit = {"kind": "worldSegment", "id": 0, "groupId": next_group}
            saved = api(session.url, "/api/world-map/save", {"edits": [api_edit]})
            assert saved["saved"] == 1 and saved["files"][0].endswith("wmx.obj")
            current = api(session.url, "/api/world-map?dataset=current")
            assert current["segments"][0]["groupId"] == next_group

            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 180)
            cdp.eval("navigate('maps');state.mapsTab='world';state.worldTab='map';state.selected.world=0;renderMaps()")
            wait_eval(cdp, "document.querySelector('.world-visual-image')?.complete&&document.querySelector('.world-visual-image')?.naturalWidth===256", 60)
            rendered = cdp.eval("""(()=>{const outer=document.querySelector('.ff8-maps-view'),root=document.querySelector('.world-map-view'),map=document.querySelector('.world-visual-stage'),image=document.querySelector('.world-visual-image'),panel=document.querySelector('.world-segment-detail');return{
              mainTabs:[...document.querySelectorAll('nav button[data-tab]')].map(node=>node.querySelector('.lex-tab-label-text')?.textContent.trim()||''),
              mapTabs:[...outer.querySelectorAll(':scope>.ff8-maps-tabs [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              mapTabActive:outer.querySelector(':scope>.ff8-maps-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              tabs:[...document.querySelectorAll('.world-map-tabs [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              active:document.querySelector('.world-map-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              map:{width:map.getBoundingClientRect().width,height:map.getBoundingClientRect().height,natural:[image.naturalWidth,image.naturalHeight]},
              cells:document.querySelectorAll('.world-segment-cell').length,
              markers:document.querySelectorAll('.world-map-marker').length,
              inputs:[...panel.querySelectorAll('input[aria-label]')].map(node=>node.getAttribute('aria-label')),
              blocks:panel.querySelectorAll('.world-segment-block').length,
              text:panel.textContent,
              overflow:root.scrollWidth>root.clientWidth+1,
            }})()""")
            assert rendered["tabs"] == ["Map", "Regions", "Encounter Rules",
                                         "Encounter Groups", "Field → World",
                                         "Draw Points", "Sky Colours", "Train Tracks",
                                         "World Textures"]
            assert "Maps" in rendered["mainTabs"]
            assert "Field" not in rendered["mainTabs"] and "World Map" not in rendered["mainTabs"]
            assert rendered["mapTabs"] == ["Field", "World"]
            assert rendered["mapTabActive"] == "World"
            assert rendered["active"] == "Map"
            assert rendered["map"]["natural"] == [256, 192]
            assert abs(rendered["map"]["width"] / rendered["map"]["height"] - 4 / 3) < .02
            assert rendered["cells"] == 768 and rendered["markers"] == 128
            assert rendered["blocks"] == 16 and "POLYGONS" in rendered["text"]
            assert rendered["inputs"] == ["World segment 0 region ID",
                                           "World segment 0 group ID"]
            assert not rendered["overflow"]

            cdp.eval("document.querySelectorAll('.world-segment-cell')[33].click()")
            wait_eval(cdp, "state.selected.world===33&&document.querySelector('.world-segment-detail')?.textContent.includes('WORLD SEGMENT 33')", 20)
            before = cdp.eval("worldRow(state.data,'worldSegment',33).groupId")
            cdp.eval("""(()=>{const input=document.querySelector('input[aria-label="World segment 33 group ID"]');const value=Number(input.value.replaceAll(',',''))+1;input.value=String(value);input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, f"worldRow(state.data,'worldSegment',33).groupId==={before + 1}", 10)
            assert cdp.eval("dirtyCount()") > 0
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 120)
            current = api(session.url, "/api/world-map?dataset=current")
            assert current["segments"][33]["groupId"] == before + 1
            shot = screenshot(cdp, "goal-ff8-world-map-visual.png")
            print(json.dumps({
                "segments": 835,
                "polygons": 517_639,
                "mapSize": image.size,
                "changedOffsets": changed,
                "unknownBytesPreserved": True,
                "semanticMerge": True,
                "apiSaved": saved["saved"],
                "rendered": rendered,
                "screenshot": str(shot),
            }, ensure_ascii=True))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
